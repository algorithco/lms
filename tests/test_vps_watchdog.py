"""VPS watchdog unit tests — pure decision/parsing logic only.

The script itself (deploy/vps_watchdog.py) is stdlib-only so it runs on the
bare host; here we load it by path and exercise evaluate() + parsers with
fixtures. No network, no subprocess, no root required.
"""
import importlib.util
import os
import time

from django.test import SimpleTestCase

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "deploy", "vps_watchdog.py",
)


def load_watchdog():
    spec = importlib.util.spec_from_file_location("vps_watchdog", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wd = load_watchdog()


def base_metrics(**over):
    m = {
        "ssh_failed_10m": 3,
        "public_listeners": [22, 80, 443],
        "delta_429": 0,
        "delta_5xx": 0,
        "load15": 0.5,
        "ncpu": 2,
        "mem_avail_mb": 2000.0,
        "disk_pct": 20.0,
        "unhealthy_containers": [],
        "cert_days_left": 900.0,
    }
    m.update(over)
    return m


def base_thresholds():
    return dict(wd.DEFAULTS)


class EvaluateTests(SimpleTestCase):
    def test_clean_host_no_alerts(self):
        alerts = wd.evaluate(base_metrics(), base_thresholds(), {}, time.time())
        self.assertEqual(alerts, [])

    def test_ssh_bruteforce_alert(self):
        alerts = wd.evaluate(
            base_metrics(ssh_failed_10m=120), base_thresholds(), {}, time.time(),
        )
        keys = [k for k, _ in alerts]
        self.assertIn("ssh_bruteforce", keys)

    def test_authkeys_change_is_backdoor_tripwire(self):
        state = {"authkeys_fingerprint": "aaa+bbb"}
        m = base_metrics()
        m["authkeys_fingerprint"] = "ccc+ddd"
        alerts = wd.evaluate(m, base_thresholds(), state, time.time())
        keys = [k for k, _ in alerts]
        self.assertIn("authkeys_changed", keys)

    def test_first_run_records_fingerprint_without_alert(self):
        m = base_metrics()
        m["authkeys_fingerprint"] = "aaa+bbb"
        alerts = wd.evaluate(m, base_thresholds(), {}, time.time())
        self.assertNotIn("authkeys_changed", [k for k, _ in alerts])

    def test_odd_listener_alert(self):
        alerts = wd.evaluate(
            base_metrics(public_listeners=[22, 80, 443, 4444]),
            base_thresholds(), {}, time.time(),
        )
        keys = [k for k, _ in alerts]
        self.assertIn("odd_listeners", keys)

    def test_http_spikes_alert(self):
        alerts = wd.evaluate(
            base_metrics(delta_429=500, delta_5xx=80),
            base_thresholds(), {}, time.time(),
        )
        keys = [k for k, _ in alerts]
        self.assertIn("http_429", keys)
        self.assertIn("http_5xx", keys)

    def test_resource_alerts(self):
        alerts = wd.evaluate(
            base_metrics(load15=9.0, mem_avail_mb=100.0, disk_pct=95.0),
            base_thresholds(), {}, time.time(),
        )
        keys = [k for k, _ in alerts]
        self.assertIn("load", keys)
        self.assertIn("memory", keys)
        self.assertIn("disk", keys)

    def test_cooldown_suppresses_repeat(self):
        now = time.time()
        state = {"alert_at": {"disk": now - 60}}
        alerts = wd.evaluate(base_metrics(disk_pct=95.0), base_thresholds(), state, now)
        self.assertNotIn("disk", [k for k, _ in alerts])
        state2 = {"alert_at": {"disk": now - 4000}}
        alerts2 = wd.evaluate(base_metrics(disk_pct=95.0), base_thresholds(), state2, now)
        self.assertIn("disk", [k for k, _ in alerts2])

    def test_container_and_cert_alerts(self):
        alerts = wd.evaluate(
            base_metrics(unhealthy_containers=["web (unhealthy)"], cert_days_left=5.0),
            base_thresholds(), {}, time.time(),
        )
        keys = [k for k, _ in alerts]
        self.assertIn("containers", keys)
        self.assertIn("cert", keys)


class ParserTests(SimpleTestCase):
    def test_parse_fail2ban_banned(self):
        out = "Status for the jail: sshd\n|- Filter\n`- Actions\n   |- Currently banned:\t7\n"
        self.assertEqual(wd.parse_fail2ban_banned(out), 7)
        self.assertIsNone(wd.parse_fail2ban_banned("garbage"))

    def test_parse_public_listeners(self):
        ss = (
            "tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n"
            "tcp LISTEN 0 4096 0.0.0.0:80 0.0.0.0:*\n"
            "tcp LISTEN 0 128 127.0.0.1:5432 0.0.0.0:*\n"
            "tcp LISTEN 0 128 0.0.0.0:4444 0.0.0.0:*\n"
            "tcp LISTEN 0 128 [::]:443 [::]:*\n"
        )
        self.assertEqual(wd.parse_public_listeners(ss), [22, 80, 443, 4444])

    def test_count_nginx_codes(self):
        sample = (
            '1.2.3.4 - - [28/Sep/2026:14:00:01 +0500] "GET / HTTP/1.1" 200 123 "-" "-"\n'
            '1.2.3.4 - - [28/Sep/2026:14:00:02 +0500] "GET /api/x HTTP/1.1" 429 0 "-" "-"\n'
            '1.2.3.4 - - [28/Sep/2026:14:00:03 +0500] "GET /api/y HTTP/1.1" 502 0 "-" "-"\n'
        )
        self.assertEqual(wd.count_nginx_codes(sample), (1, 1))
