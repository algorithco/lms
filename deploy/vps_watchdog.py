#!/usr/bin/env python3
"""LMS Platform — VPS watchdog (host-side, stdlib only).

Watches for unusual activity on the production VPS and notifies the admins
via a dedicated Telegram bot. Runs as a systemd SERVICE on the HOST (not in
Docker — containers cannot see fail2ban, host listeners or host auth logs):

    deploy/vps-watchdog.service → /opt/lms/deploy/vps_watchdog.py --daemon

Installed/enabled by deploy/remote-deploy.sh on every deploy (files arrive
via the deploy pipeline, never by hand).

Two interactions:
  - Any admin sends /start → the bot replies with a full status snapshot.
  - While an incident is ACTIVE the bot repeats the alert every 50 seconds;
    when it clears, one "resolved" message is sent.

Secrets live in /opt/lms/deploy/secrets/watchdog.env (chmod 600, NEVER in
git — see deploy/secrets/watchdog.env.example):
    WATCHDOG_BOT_TOKEN=123456:AA...   # dedicated admin bot (@BotFather)
    WATCHDOG_CHAT_ID=111,222          # comma-separated admin chats (each admin
                                      # messages the bot once, then read the id
                                      # via curl .../bot<TOKEN>/getUpdates)

Without WATCHDOG_CHAT_ID the script prints setup instructions and exits 0.

Signals (thresholds overridable via WATCHDOG_* env):
  - SSH brute force: 'Failed password'/'Invalid user' in journal last 10 min
  - fail2ban bans currently active (context line, always included when >0)
  - authkeys tripwire: sha256 of root+deploy authorized_keys vs state
    (catches the ElPatrono1337-style backdoor key of Sep 2026)
  - unexpected public listeners (anything beyond 22/80/443 on 0.0.0.0/::)
  - nginx 429/5xx deltas between runs (DDoS / app-error spike)
  - load15 > 2xCPU, CPU% > 90, mem available < 400MB, disk > 85%
  - established-connection flood (>2000 half+full), container restarts,
    unhealthy containers, origin TLS expiring < 30d
  - app health: GET <SITE_URL>/healthz (status/db/version)
  - host reboot detection (boot_id change)
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
REPEAT_SEC = 50
CHECK_INTERVAL = 50

DEFAULTS = {
    "SSH_FAIL_10M": 50,
    "DISK_PCT": 85,
    "LOAD_MULT": 2.0,
    "CPU_PCT": 90,
    "CONNS_ESTAB": 2000,
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


def bot_api(token: str, method: str, params: dict | None = None,
            data: dict | None = None, timeout: int = 40):
    """Raw Bot API call. GET when data is None, POST otherwise."""
    base = f"https://api.telegram.org/bot{token}/{method}"
    try:
        ctx = ssl.create_default_context()
        if data is None:
            qs = urllib.parse.urlencode(params or {})
            req = urllib.request.Request(base + ("?" + qs if qs else ""))
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.load(resp)
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(base, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.load(resp)
    except Exception as exc:
        print(f"watchdog: bot api {method} failed: {exc}", file=sys.stderr)
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


def count_established(ss_out: str) -> int:
    """Established TCP connections (DDoS/connection-flood signal)."""
    return sum(1 for line in (ss_out or "").splitlines() if "ESTAB" in line)


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


def parse_cpu_line(line: str) -> list[int] | None:
    parts = (line or "").split()
    if len(parts) < 5 or parts[0] != "cpu":
        return None
    try:
        return [int(x) for x in parts[1:]]
    except ValueError:
        return None


def cpu_percent(prev: list[int], cur: list[int]) -> float | None:
    """Busy % between two /proc/stat 'cpu' snapshots."""
    try:
        prev_idle = prev[3] + prev[4]
        cur_idle = cur[3] + cur[4]
        prev_total = sum(prev)
        cur_total = sum(cur)
        total_d = cur_total - prev_total
        idle_d = cur_idle - prev_idle
        if total_d <= 0:
            return None
        return max(0.0, min(100.0, (total_d - idle_d) / total_d * 100))
    except (IndexError, TypeError):
        return None


def parse_running_for(text: str) -> float | None:
    """'3 hours ago' / '25 minutes ago' / '2 days ago' → seconds."""
    m = re.match(r"\s*(\d+)\s+(second|minute|hour|day)s?\s+ago\s*", text or "")
    if not m:
        return None
    mult = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[m.group(2)]
    return int(m.group(1)) * mult


def parse_healthz(payload: str) -> dict | None:
    try:
        data = json.loads(payload or "")
    except ValueError:
        return None
    if not isinstance(data, dict) or "status" not in data:
        return None
    return data


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


def evaluate(metrics: dict, thresholds: dict, state: dict, now: float,
             cooldown: float = COOLDOWN_SEC) -> list[tuple[str, str]]:
    """Pure decision function (unit-tested). Returns [(key, text)]."""
    alerts: list[tuple[str, str]] = []

    def cooled(key: str) -> bool:
        return (now - float(state.get("alert_at", {}).get(key, 0))) < cooldown

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
        alerts.append(("http_429", f"HTTP 429 spike: +{d429} since last check (possible DDoS)"))
    d5xx = metrics.get("delta_5xx", 0)
    if d5xx >= thresholds["DELTA_5XX"]:
        alerts.append(("http_5xx", f"HTTP 5xx spike: +{d5xx} since last check (app errors)"))

    load15 = metrics.get("load15")
    ncpu = metrics.get("ncpu") or 1
    if load15 is not None and load15 > thresholds["LOAD_MULT"] * ncpu:
        alerts.append(("load", f"load15 {load15:.1f} on {ncpu} CPUs"))

    cpu = metrics.get("cpu_pct")
    if cpu is not None and cpu >= thresholds["CPU_PCT"]:
        alerts.append(("cpu", f"CPU busy {cpu:.0f}%"))

    conns = metrics.get("conns_established")
    if conns is not None and conns >= thresholds["CONNS_ESTAB"]:
        alerts.append(("conns", f"{conns} established connections (possible flood)"))

    mem_mb = metrics.get("mem_avail_mb")
    if mem_mb is not None and mem_mb < thresholds["MEM_MIN_MB"]:
        alerts.append(("memory", f"memory available only {mem_mb:.0f}MB"))

    disk = metrics.get("disk_pct")
    if disk is not None and disk >= thresholds["DISK_PCT"]:
        alerts.append(("disk", f"disk usage {disk:.0f}%"))

    bad = metrics.get("unhealthy_containers", [])
    if bad:
        alerts.append(("containers", f"unhealthy containers: {', '.join(bad[:5])}"))

    restarted = metrics.get("restarted_containers", [])
    if restarted:
        alerts.append(("restarts", f"containers restarted: {', '.join(restarted[:5])}"))

    cert_days = metrics.get("cert_days_left")
    if cert_days is not None and cert_days < thresholds["CERT_DAYS"]:
        alerts.append(("cert", f"origin TLS expires in {cert_days:.0f} days"))

    health = metrics.get("healthz")
    if health is not None and (health.get("status") != "ok" or not health.get("db")):
        alerts.append(("healthz", f"app health BAD: {health}"))

    if metrics.get("rebooted"):
        alerts.append(("reboot", "VPS was rebooted"))

    return [(k, t) for k, t in alerts if not cooled(k)]


def update_active(active: dict, now_keys: set[str], now: float,
                  repeat_sec: float = REPEAT_SEC) -> tuple[list[str], list[str], list[str]]:
    """Repeat tracker (pure, unit-tested). Returns (new, resend, resolved).

    - new: just appeared → send immediately.
    - resend: still active and last sent >= repeat_sec ago → send again.
    - resolved: tracked but condition gone → send one 'resolved' note.
    """
    new, resend, resolved = [], [], []
    for key in now_keys:
        entry = active.get(key)
        if not entry:
            new.append(key)
        elif now - float(entry.get("last", 0)) >= repeat_sec:
            resend.append(key)
    for key in active:
        if key not in now_keys:
            resolved.append(key)
    return new, resend, resolved


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
    payload = bot_api(token, "sendMessage", data={
        "chat_id": chat_id, "text": text, "disable_web_page_preview": "true",
    }, timeout=timeout)
    return bool(payload and payload.get("ok"))


def format_status(metrics: dict, thresholds: dict) -> str:
    """Full status snapshot for /start replies (pure, unit-tested)."""
    lines = ["\U0001f6a8 LMS VPS status:"]
    lines.append(f"load15: {metrics.get('load15', '?')} (x{metrics.get('ncpu', '?')})")
    cpu = metrics.get("cpu_pct")
    lines.append(f"cpu: {cpu:.0f}%" if cpu is not None else "cpu: ?")
    mem = metrics.get("mem_avail_mb")
    lines.append(f"mem avail: {mem:.0f}MB" if mem is not None else "mem avail: ?")
    disk = metrics.get("disk_pct")
    lines.append(f"disk: {disk:.0f}%" if disk is not None else "disk: ?")
    lines.append(f"conns established: {metrics.get('conns_established', '?')}")
    lines.append(f"ssh fails/10m: {metrics.get('ssh_failed_10m', '?')}")
    lines.append(f"fail2ban bans: {metrics.get('banned_now', '?')}")
    lines.append(f"http 429/5xx (window): {metrics.get('delta_429', 0)}/{metrics.get('delta_5xx', 0)}")
    bad = metrics.get("unhealthy_containers", [])
    lines.append("containers: OK" if not bad else f"containers BAD: {', '.join(bad)}")
    cert = metrics.get("cert_days_left")
    lines.append(f"origin TLS: {cert:.0f}d left" if cert is not None else "origin TLS: ?")
    health = metrics.get("healthz")
    if isinstance(health, dict):
        lines.append(f"app: {health.get('status')} db={health.get('db')} v{health.get('version')}")
    else:
        lines.append("app: unreachable")
    lines.append(f"listeners: {metrics.get('public_listeners', '?')}")
    return "\n".join(lines)


def gather(sample_cpu: bool = True) -> dict:
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
    if sample_cpu:
        try:
            with open("/proc/stat") as fh:
                prev = parse_cpu_line(fh.readline())
            time.sleep(1)
            with open("/proc/stat") as fh:
                cur = parse_cpu_line(fh.readline())
            if prev and cur:
                pct = cpu_percent(prev, cur)
                if pct is not None:
                    m["cpu_pct"] = pct
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
    tcp = run(["ss", "-tnH"])
    if tcp is not None:
        m["conns_established"] = count_established(tcp)
    tail = run(["tail", "-n", "20000", ACCESS_LOG])
    if tail is not None:
        n429, n5xx = count_nginx_codes(tail)
        m["http_429_total"] = n429
        m["http_5xx_total"] = n5xx
    ss = run(["ss", "-tlnH"])
    if ss is not None:
        m["public_listeners"] = parse_public_listeners(ss)
    docker = run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.RunningFor}}"], timeout=60)
    if docker is None:
        m["unhealthy_containers"] = ["docker daemon unreachable"]
        m["container_ages"] = {}
    else:
        bad, ages = [], {}
        for ln in docker.splitlines():
            if not ln or "|" not in ln:
                continue
            name, status, running_for = (ln.split("|") + ["", ""])[:3]
            if not status.startswith("Up"):
                bad.append(name)
            secs = parse_running_for(running_for)
            if secs is not None:
                ages[name] = secs
        m["unhealthy_containers"] = bad
        m["container_ages"] = ages
    try:
        with open("/proc/sys/kernel/random/boot_id") as fh:
            m["boot_id"] = fh.read().strip()
    except OSError:
        pass
    enddate = run(["openssl", "x509", "-in", ORIGIN_PEM, "-noout", "-enddate"])
    if enddate is not None:
        ts = parse_cert_notafter(enddate)
        if ts is not None:
            m["cert_days_left"] = (ts - time.time()) / 86400
    site = os.environ.get("WATCHDOG_SITE_URL", "https://grandec.uz")
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(site.rstrip("/") + "/healthz")
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            m["healthz"] = parse_healthz(resp.read().decode(errors="replace"))
    except Exception:
        m["healthz"] = None
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


def check_cycle(token: str, chat_ids: list[str], thresholds: dict,
                state: dict, now: float) -> dict:
    """One 50s check: gather → deltas → alerts → repeat/resolved fan-out."""
    m = gather()
    prev429 = int(state.get("http_429_total", m.get("http_429_total", 0)))
    prev5xx = int(state.get("http_5xx_total", m.get("http_5xx_total", 0)))
    m["delta_429"] = max(0, int(m.get("http_429_total", 0)) - prev429)
    m["delta_5xx"] = max(0, int(m.get("http_5xx_total", 0)) - prev5xx)
    prev_boot = state.get("boot_id")
    if m.get("boot_id") and prev_boot and m["boot_id"] != prev_boot:
        m["rebooted"] = True
    prev_ages = state.get("container_ages", {})
    cur_ages = m.get("container_ages", {})
    m["restarted_containers"] = sorted(
        n for n, secs in cur_ages.items()
        if n in prev_ages and secs < prev_ages[n] - 60
    )
    alerts = dict(evaluate(m, thresholds, state, now, cooldown=0))
    active = state.setdefault("active", {})
    new, resend, resolved = update_active(active, set(alerts), now)
    hostname = (run(["hostname"]) or "vps").strip()
    stamp = time.strftime("%H:%M")
    for key in new:
        text = f"\U0001f6a8 LMS watchdog ({hostname} {stamp}):\n- {alerts[key]}"
        if all(send_telegram(token, cid, text) for cid in chat_ids):
            active[key] = {"first": now, "last": now, "count": 1}
    for key in resend:
        entry = active[key]
        entry["count"] += 1
        mins = int((now - entry["first"]) / 60)
        text = (f"\U0001f6a8 STILL ACTIVE #{entry['count']} ({mins}m): {alerts[key]}\n"
                f"({hostname} {stamp})")
        if all(send_telegram(token, cid, text) for cid in chat_ids):
            entry["last"] = now
    for key in resolved:
        text = f"✅ resolved: {key} ({hostname} {stamp})"
        for cid in chat_ids:
            send_telegram(token, cid, text)
        active.pop(key, None)
    state["http_429_total"] = m.get("http_429_total", prev429)
    state["http_5xx_total"] = m.get("http_5xx_total", prev5xx)
    if m.get("authkeys_fingerprint"):
        state["authkeys_fingerprint"] = m["authkeys_fingerprint"]
    if m.get("boot_id"):
        state["boot_id"] = m["boot_id"]
    if cur_ages:
        state["container_ages"] = cur_ages
    save_state(state)
    return m


def daemon(token: str, chat_ids: list[str], thresholds: dict) -> int:
    """Long-running guard: 30s update long-poll + checks every 50s."""
    print("watchdog: daemon started (checks every 50s, repeats while active)",
          flush=True)
    state = load_state()
    offset = int(state.get("tg_offset", 0))
    last_check = 0.0
    while True:
        updates = bot_api(token, "getUpdates",
                          {"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                          timeout=60) or {}
        for upd in updates.get("result", []):
            offset = max(offset, int(upd.get("update_id", 0)) + 1)
            msg = upd.get("message", {})
            text = (msg.get("text") or "").strip()
            chat = str(msg.get("chat", {}).get("id", ""))
            if text.startswith("/start"):
                if chat in chat_ids:
                    m = gather(sample_cpu=False)
                    send_telegram(token, chat, format_status(m, thresholds))
                else:
                    send_telegram(token, chat, "⛔ unauthorized")
        state["tg_offset"] = offset
        save_state(state)
        now = time.time()
        if now - last_check >= CHECK_INTERVAL:
            last_check = now
            try:
                check_cycle(token, chat_ids, thresholds, state, now)
            except Exception as exc:
                print(f"watchdog: check failed: {exc}", file=sys.stderr)


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
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        return daemon(token, chat_ids, thresholds)
    now = time.time()
    state = load_state()
    m = gather(sample_cpu=False)
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
