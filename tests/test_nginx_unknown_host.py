"""Nginx unknown-Host tests — parked domains must never be served our site.

Regression: skolis.cz (a foreign domain) pointed its A record at our VPS IP
and nginx served the GRANDEC SPA to it, because no default_server existed:
the first listen block silently became the default for every unknown
Host/SNI, and the open ACME webroot could even have completed an HTTP-01
challenge for the stranger's domain.

Covers deploy/nginx/nginx-ssl.conf — the template regenerated into the live
deploy/nginx/nginx.conf on every deploy (see deploy/remote-deploy.sh).
Pure text parsing: no nginx binary, no network, no root required.
"""

from __future__ import annotations

import os
import re

from django.test import SimpleTestCase

CONF = os.path.join(
    os.path.dirname(__file__),
    "..",
    "deploy",
    "nginx",
    "nginx-ssl.conf",
)


def read_conf() -> str:
    with open(CONF, encoding="utf-8") as f:
        return f.read()


def split_server_blocks(text: str) -> list[str]:
    """Split top-level `server { ... }` blocks via brace counting."""
    blocks: list[str] = []
    for m in re.finditer(r"(?:^|\n)[ \t]*server[ \t]*\{", text):
        start = text.index("{", m.start())
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[m.start() : i + 1])
                    break
    return blocks


def listen_lines(block: str) -> list[str]:
    return re.findall(r"listen\s+([^;]+);", block)


def server_name(block: str) -> str:
    m = re.search(r"server_name\s+([^;]+);", block)
    return m.group(1) if m else ""


def locations(block: str) -> list[tuple[str, str]]:
    """(header, body) for each location — bodies never nest here."""
    return re.findall(r"location\s+([^\{]+)\{([^\}]*)\}", block)


class Port80CatchAllTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text = read_conf()
        cls.blocks = split_server_blocks(cls.text)
        cls.port80 = [
            b
            for b in cls.blocks
            if any(re.match(r"80(\s|$)", ln) for ln in listen_lines(b))
        ]

    def test_has_server_blocks(self):
        self.assertGreaterEqual(
            len(self.blocks), 4
        )  # 80 catch-all, 443 catch-all, redirect, 2x app host

    def test_first_port80_block_is_default_catchall(self):
        self.assertTrue(self.port80, "no port-80 server block found")
        first = self.port80[0]
        self.assertIn("default_server", first)
        self.assertIn("return 444", first)

    def test_catchall_serves_no_acme_challenge(self):
        for block in self.port80:
            if "default_server" in block:
                self.assertNotIn("acme-challenge", block)

    def test_catchall_keeps_docker_healthcheck_green(self):
        # compose healthcheck: wget http://127.0.0.1/healthz/ (Host: 127.0.0.1
        # matches no real name, so the default block must proxy it to the app).
        defaults = [b for b in self.port80 if "default_server" in b]
        self.assertEqual(len(defaults), 1)
        locs = dict((h.strip(), body) for h, body in locations(defaults[0]))
        self.assertIn("= /healthz/", locs)
        self.assertIn("proxy_pass", locs["= /healthz/"])

    def test_grandec_redirect_block_intact(self):
        named = [b for b in self.port80 if "grandec.uz" in server_name(b)]
        self.assertTrue(named, "grandec port-80 block lost its server_name")
        block = named[0]
        self.assertIn("acme-challenge", block)
        self.assertIn("return 301 https://$host$request_uri;", block)


class Port443CatchAllTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blocks = split_server_blocks(read_conf())
        cls.port443 = [
            b for b in cls.blocks if any("443" in ln for ln in listen_lines(b))
        ]

    def test_unknown_sni_handshake_rejected(self):
        defaults = [b for b in self.port443 if "default_server" in b]
        self.assertEqual(len(defaults), 1, "want exactly one port-443 default_server")
        block = defaults[0]
        self.assertIn("ssl_reject_handshake on", block)
        # A rejecting block must present nothing: no cert, no content.
        self.assertNotIn("ssl_certificate", block)
        self.assertNotIn("proxy_pass", block)
        self.assertNotIn("root", block)

    def test_app_hosts_keep_explicit_names_and_origin_cert(self):
        named = [b for b in self.port443 if "default_server" not in b]
        names = " ".join(server_name(b) for b in named)
        self.assertIn("grandec.uz", names)
        self.assertIn("admin.grandec.uz", names)
        for block in named:
            self.assertIn("ssl_certificate", block)
            self.assertIn("origin.pem", block)


class NoProxyLeakTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blocks = split_server_blocks(read_conf())

    def test_every_app_proxy_sits_behind_grandec_name_or_healthz(self):
        offenders: list[str] = []
        for block in self.blocks:
            name = server_name(block)
            for header, body in locations(block):
                if "proxy_pass" not in body:
                    continue
                if "grandec.uz" in name:
                    continue
                if header.strip() == "= /healthz/":
                    continue
                offenders.append(f"server_name=[{name}] location [{header.strip()}]")
        self.assertEqual(offenders, [])

    def test_braces_balanced(self):
        text = read_conf()
        self.assertEqual(text.count("{"), text.count("}"))
