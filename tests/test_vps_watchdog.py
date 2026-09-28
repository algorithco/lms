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

    def test_parse_chat_ids(self):
        self.assertEqual(wd.parse_chat_ids("7423424205"), ["7423424205"])
        self.assertEqual(
            wd.parse_chat_ids("7423424205,5636907095"),
            ["7423424205", "5636907095"],
        )
        self.assertEqual(
            wd.parse_chat_ids(" 7423424205 , 5636907095,7423424205 "),
            ["7423424205", "5636907095"],
        )
        self.assertEqual(wd.parse_chat_ids(""), [])


class RepeatTests(SimpleTestCase):
    def test_new_resend_resolved_cycle(self):
        now = 100000.0
        new, resend, resolved = wd.update_active({}, {"disk"}, now)
        self.assertEqual((new, resend, resolved), (["disk"], [], []))
        active = {"disk": {"first": now, "last": now, "count": 1}}
        # still active 20s later → silent (repeat is 50s)
        new, resend, resolved = wd.update_active(active, {"disk"}, now + 20)
        self.assertEqual((new, resend, resolved), ([], [], []))
        # still active 60s later → resend
        new, resend, resolved = wd.update_active(active, {"disk"}, now + 60)
        self.assertEqual((new, resend, resolved), ([], ["disk"], []))
        # condition gone → resolved
        new, resend, resolved = wd.update_active(active, set(), now + 70)
        self.assertEqual((new, resend, resolved), ([], [], ["disk"]))

    def test_format_status_contains_key_lines(self):
        m = base_metrics(
            load15=1.5, cpu_pct=12.0, mem_avail_mb=3000.0, disk_pct=33.0,
            conns_established=41, ssh_failed_10m=2, banned_now=7,
            delta_429=0, delta_5xx=1, unhealthy_containers=[],
            cert_days_left=500.0,
            healthz={"status": "ok", "db": True, "version": "0.60.0"},
            public_listeners=[22, 80, 443],
        )
        text = wd.format_status(m, base_thresholds())
        for needle in ("load15: 1.5", "cpu: 12%", "mem avail: 3000MB",
                       "disk: 33%", "bans: 7", "v0.60.0", "OK"):
            self.assertIn(needle, text)

    def test_cpu_percent(self):
        prev = [1000, 0, 2000, 5000, 500, 0, 0, 0, 0, 0]
        cur = [1100, 0, 2100, 5050, 500, 0, 0, 0, 0, 0]
        pct = wd.cpu_percent(prev, cur)
        self.assertIsNotNone(pct)
        self.assertAlmostEqual(pct, 80.0, places=0)

    def test_parse_running_for(self):
        self.assertEqual(wd.parse_running_for("25 minutes ago"), 1500)
        self.assertEqual(wd.parse_running_for("3 hours ago"), 10800)
        self.assertIsNone(wd.parse_running_for("Up 3 hours"))

    def test_parse_healthz(self):
        good = wd.parse_healthz('{"status": "ok", "db": true, "version": "1"}')
        self.assertEqual(good["status"], "ok")
        self.assertIsNone(wd.parse_healthz("not json"))
        self.assertIsNone(wd.parse_healthz('{"nope": 1}'))

    def test_count_established(self):
        ss = "tcp ESTAB 0 0 1.1.1.1:443 2.2.2.2:1\ntcp TIME-WAIT 0 0 1.1.1.1:80 3.3.3.3:2\n"
        self.assertEqual(wd.count_established(ss), 1)
