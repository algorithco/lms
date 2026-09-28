#!/usr/bin/env python3
"""LMS Platform — VPS watchdog (host-side, stdlib only).

Watches for unusual activity on the production VPS and notifies the admin
via a dedicated Telegram bot. Runs from cron on the HOST (not in Docker —
containers cannot see fail2ban, host listeners or host auth logs):

    */5 * * * * /usr/bin/python3 /opt/lms/deploy/vps_watchdog.py >>/var/log/lms-watchdog.log 2>&1

Secrets live in /opt/lms/deploy/secrets/watchdog.env (chmod 600, NEVER in
git — see deploy/secrets/watchdog.env.example):
    WATCHDOG_BOT_TOKEN=123456:AA...   # dedicated admin bot (@BotFather)
    WATCHDOG_CHAT_ID=111,222          # comma-separated admin chats (each admin
                                      # messages the bot once, then read the id
                                      # via curl .../bot<TOKEN>/getUpdates)

Without WATCHDOG_CHAT_ID the script prints setup instructions and exits 0.
Every alert has a 60-minute cooldown (state in /var/tmp/vps_watchdog.state.json)
so a sustained attack sends one message, not 12/hour.

Signals (thresholds overridable via WATCHDOG_* env):
  - SSH brute force: 'Failed password'/'Invalid user' in journal last 10 min
  - fail2ban bans currently active (context line, always included when >0)
  - authkeys tripwire: sha256 of root+deploy authorized_keys vs state
    (catches the ElPatrono1337-style backdoor key of Sep 2026)
  - unexpected public listeners (anything beyond 22/80/443 on 0.0.0.0/::)
  - nginx 429/5xx deltas between runs (DDoS / app-error spike)
  - load15 > 2xCPU, mem available < 400MB, disk > 85%
  - unhealthy docker containers, origin TLS expiring < 30d
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

STATE_PATH = "/var/tmp/vps_watchdog.state.json"
ACCESS_LOG = "/opt/lms/deploy/logs/access.log"
ORIGIN_PEM = "/opt/lms/deploy/secrets/origin.pem"
AUTHKEYS_FILES = ("/root/.ssh/authorized_keys", "/home/deploy/.ssh/authorized_keys")
ALLOWED_PUBLIC_PORTS = frozenset({22, 80, 443})
COOLDOWN_SEC = 3600

DEFAULTS = {
    "SSH_FAIL_10M": 50,
    "DISK_PCT": 85,
    "LOAD_MULT": 2.0,
    "MEM_MIN_MB": 400,
    "DELTA_429": 200,
    "DELTA_5XX": 50,
    "CERT_DAYS": 30,
}


def threshold(name: str):
    raw = os.environ.get("WATCHDOG_" + name, "")
    if raw == "":
        return DEFAULTS[name]
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return DEFAULTS[name]


def run(cmd: list[str], timeout: int = 30) -> str | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return None
        return proc.stdout
    except Exception:
        return None


def parse_fail2ban_banned(status_out: str) -> int | None:
    m = re.search(r"Currently banned:\s*(\d+)", status_out or "")
    return int(m.group(1)) if m else None


def parse_cert_notafter(openssl_out: str) -> float | None:
    m = re.search(r"notAfter=(.*)", openssl_out or "")
    if not m:
        return None
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%b  %d %H:%M:%S %Y %Z"):
        try:
            return time.mktime(time.strptime(m.group(1).strip(), fmt))
        except ValueError:
            continue
    return None


def parse_public_listeners(ss_out: str) -> list[int]:
    """Ports bound on all interfaces (0.0.0.0 / :: / [::] / *) from `ss -tlnH`.

    The local address column shifts when extra columns (e.g. process info
    with -p) are present, so scan for the first address-like token instead
    of assuming a fixed index.
    """
    ports: set[int] = set()
    for line in (ss_out or "").splitlines():
        parts = line.split()
        for token in parts[2:]:
            host, _, port = token.rpartition(":")
            if not port.isdigit():
                continue
            if "." in host or "[" in host or host == "*":
                if host.strip("[]") in ("0.0.0.0", "::", "*"):
                    ports.add(int(port))
                break
    return sorted(ports)


def count_nginx_codes(sample: str) -> tuple[int, int]:
    """(count_429, count_5xx) in an nginx access-log sample."""
    n429 = n5xx = 0
    for line in sample.splitlines():
        m = re.search(r'"\s(\d{3})\s', line)
        if not m:
            continue
        code = int(m.group(1))
        if code == 429:
            n429 += 1
        elif 500 <= code <= 599:
            n5xx += 1
    return n429, n5xx


def sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return None


def load_state(path: str = STATE_PATH) -> dict:
    try:
        with open(path) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict, path: str = STATE_PATH) -> None:
    try:
        with open(path, "w") as fh:
            json.dump(state, fh)
        os.chmod(path, 0o600)
    except OSError:
        pass


def evaluate(metrics: dict, thresholds: dict, state: dict, now: float) -> list[tuple[str, str]]:
    """Pure decision function (unit-tested). Returns [(key, text)]."""
    alerts: list[tuple[str, str]] = []

    def cooled(key: str) -> bool:
        return (now - float(state.get("alert_at", {}).get(key, 0))) < COOLDOWN_SEC

    fails = metrics.get("ssh_failed_10m")
    if fails is not None and fails >= thresholds["SSH_FAIL_10M"]:
        alerts.append(("ssh_bruteforce", f"SSH brute force: {fails} failures/10min"))

    fp = metrics.get("authkeys_fingerprint")
    prev = state.get("authkeys_fingerprint")
    if fp and prev and fp != prev:
        alerts.append(("authkeys_changed", "authorized_keys CHANGED (possible backdoor key!)"))

    odd = [p for p in metrics.get("public_listeners", []) if p not in ALLOWED_PUBLIC_PORTS]
    if odd:
        alerts.append(("odd_listeners", f"unexpected public listeners: {odd}"))

    d429 = metrics.get("delta_429", 0)
    if d429 >= thresholds["DELTA_429"]:
        alerts.append(("http_429", f"HTTP 429 spike: +{d429} since last run (possible DDoS)"))
    d5xx = metrics.get("delta_5xx", 0)
    if d5xx >= thresholds["DELTA_5XX"]:
        alerts.append(("http_5xx", f"HTTP 5xx spike: +{d5xx} since last run (app errors)"))

    load15 = metrics.get("load15")
    ncpu = metrics.get("ncpu") or 1
    if load15 is not None and load15 > thresholds["LOAD_MULT"] * ncpu:
        alerts.append(("load", f"load15 {load15:.1f} on {ncpu} CPUs"))

    mem_mb = metrics.get("mem_avail_mb")
    if mem_mb is not None and mem_mb < thresholds["MEM_MIN_MB"]:
        alerts.append(("memory", f"memory available only {mem_mb:.0f}MB"))

    disk = metrics.get("disk_pct")
    if disk is not None and disk >= thresholds["DISK_PCT"]:
        alerts.append(("disk", f"disk usage {disk:.0f}%"))

    bad = metrics.get("unhealthy_containers", [])
    if bad:
        alerts.append(("containers", f"unhealthy containers: {', '.join(bad[:5])}"))

    cert_days = metrics.get("cert_days_left")
    if cert_days is not None and cert_days < thresholds["CERT_DAYS"]:
        alerts.append(("cert", f"origin TLS expires in {cert_days:.0f} days"))

    return [(k, t) for k, t in alerts if not cooled(k)]


def parse_chat_ids(raw: str) -> list[str]:
    """Comma-separated admin chat ids (whitespace tolerant, order kept)."""
    seen: set[str] = set()
    out: list[str] = []
    for part in (raw or "").split(","):
        chat = part.strip()
        if chat and chat not in seen:
            seen.add(chat)
            out.append(chat)
    return out


def send_telegram(token: str, chat_id: str, text: str, timeout: int = 20) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            payload = json.load(resp)
        return bool(payload.get("ok"))
    except Exception as exc:
        print(f"watchdog: telegram send failed: {exc}", file=sys.stderr)
        return False


def gather() -> dict:
    m: dict = {}
    journal = run(["journalctl", "-u", "ssh", "--since", "10 minutes ago", "--no-pager"])
    if journal is not None:
        m["ssh_failed_10m"] = len(re.findall(r"Failed password|Invalid user", journal))
    banned = run(["fail2ban-client", "status", "sshd"])
    if banned is not None:
        m["banned_now"] = parse_fail2ban_banned(banned)
    try:
        with open("/proc/loadavg") as fh:
            m["load15"] = float(fh.read().split()[2])
        m["ncpu"] = os.cpu_count() or 1
    except OSError:
        pass
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    m["mem_avail_mb"] = int(line.split()[1]) / 1024
                    break
    except OSError:
        pass
    try:
        total, used, _free = shutil.disk_usage("/")
        m["disk_pct"] = used / total * 100
    except OSError:
        pass
    tail = run(["tail", "-n", "20000", ACCESS_LOG])
    if tail is not None:
        n429, n5xx = count_nginx_codes(tail)
        m["http_429_total"] = n429
        m["http_5xx_total"] = n5xx
    ss = run(["ss", "-tlnH"])
    if ss is not None:
        m["public_listeners"] = parse_public_listeners(ss)
    docker = run(["docker", "ps", "--format", "{{.Names}} {{.Status}}"], timeout=60)
    if docker is None:
        m["unhealthy_containers"] = ["docker daemon unreachable"]
    else:
        bad = [ln.split()[0] for ln in docker.splitlines() if ln and not ln.split(" ", 1)[1].startswith("Up")]
        m["unhealthy_containers"] = bad
    enddate = run(["openssl", "x509", "-in", ORIGIN_PEM, "-noout", "-enddate"])
    if enddate is not None:
        ts = parse_cert_notafter(enddate)
        if ts is not None:
            m["cert_days_left"] = (ts - time.time()) / 86400
    fps = [sha256_file(p) for p in AUTHKEYS_FILES]
    if all(fps):
        m["authkeys_fingerprint"] = "+".join(fps)  # type: ignore[arg-type]
    return m


def load_secrets_env(path: str = "/opt/lms/deploy/secrets/watchdog.env") -> None:
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


def main() -> int:
    load_secrets_env()
    token = os.environ.get("WATCHDOG_BOT_TOKEN", "")
    chat_ids = parse_chat_ids(os.environ.get("WATCHDOG_CHAT_ID", ""))
    if not token or not chat_ids:
        print(
            "watchdog: WATCHDOG_BOT_TOKEN/WATCHDOG_CHAT_ID not set.\n"
            "  1. Each admin messages the admin bot once (/start).\n"
            "  2. curl https://api.telegram.org/bot<TOKEN>/getUpdates\n"
            "  3. Put token + comma-separated chat ids in "
            "/opt/lms/deploy/secrets/watchdog.env (600)."
        )
        return 0
    thresholds = {k: threshold(k) for k in DEFAULTS}
    now = time.time()
    state = load_state()
    m = gather()
    prev429 = int(state.get("http_429_total", m.get("http_429_total", 0)))
    prev5xx = int(state.get("http_5xx_total", m.get("http_5xx_total", 0)))
    m["delta_429"] = max(0, int(m.get("http_429_total", 0)) - prev429)
    m["delta_5xx"] = max(0, int(m.get("http_5xx_total", 0)) - prev5xx)
    alerts = evaluate(m, thresholds, state, now)
    context = []
    if m.get("banned_now"):
        context.append(f"bans active: {m['banned_now']}")
    if m.get("ssh_failed_10m") is not None:
        context.append(f"ssh fails/10m: {m['ssh_failed_10m']}")
    if alerts:
        hostname = run(["hostname"]) or "vps"
        lines = [f"\U0001f6a8 LMS watchdog ({hostname.strip()} {time.strftime('%H:%M')}):"]
        lines += [f"- {text}" for _, text in alerts]
        if context:
            lines.append("(" + ", ".join(context) + ")")
        ok = all(send_telegram(token, cid, "\n".join(lines)) for cid in chat_ids)
        if not ok:
            return 1
        state.setdefault("alert_at", {}).update({k: now for k, _ in alerts})
    state["http_429_total"] = m.get("http_429_total", prev429)
    state["http_5xx_total"] = m.get("http_5xx_total", prev5xx)
    if m.get("authkeys_fingerprint"):
        state["authkeys_fingerprint"] = m["authkeys_fingerprint"]
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
