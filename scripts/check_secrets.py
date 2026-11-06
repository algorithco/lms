#!/usr/bin/env python3
"""
Zero-Leak Token Security Scanner & Git Pre-Commit Secret Guard.
Scans modified and staged files for exposed API keys, Telegram bot tokens,
and private credentials.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Sensitive patterns
SECRET_PATTERNS = [
    ("OPENAI_DEEPSEEK_KEY", re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b")),
    ("TELEGRAM_BOT_TOKEN", re.compile(r"\b[0-9]{9,10}:[a-zA-Z0-9_-]{35}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
]

# Paths to ignore completely
IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    "staticfiles",
    "media",
    ".backups",
    "__pycache__",
    ".mypy_cache",
}

IGNORE_FILES = {
    ".env.example",
    ".env.prod.example",
    "package-lock.json",
    "check_secrets.py",
}

def get_files_to_check() -> list[Path]:
    """Get list of files to check: all files if --all, else staged or modified files."""
    if "--all" in sys.argv:
        root = Path(".")
        source_files = []
        for ext in ("*.py", "*.ts", "*.tsx", "*.js", "*.json", "*.html", "*.yaml", "*.yml"):
            for path in root.rglob(ext):
                parts = set(path.parts)
                if not parts.intersection(IGNORE_DIRS) and path.name not in IGNORE_FILES:
                    source_files.append(path)
        return source_files

    try:
        # Check staged files first
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        staged = [Path(line.strip()) for line in res.stdout.splitlines() if line.strip()]
        if staged:
            return [p for p in staged if p.exists() and p.is_file()]

        # If no staged files, check unstaged modified files
        res = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        modified = [Path(line.strip()) for line in res.stdout.splitlines() if line.strip()]
        if modified:
            return [p for p in modified if p.exists() and p.is_file()]
    except Exception:
        pass

    # Fallback to scanning repo source directories
    root = Path(".")
    source_files = []
    for ext in ("*.py", "*.ts", "*.tsx", "*.js", "*.json", "*.html", "*.yaml", "*.yml"):
        for path in root.rglob(ext):
            parts = set(path.parts)
            if not parts.intersection(IGNORE_DIRS) and path.name not in IGNORE_FILES:
                source_files.append(path)
    return source_files


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Scan a single file for sensitive secrets."""
    parts = set(path.parts)
    if parts.intersection(IGNORE_DIRS) or path.name in IGNORE_FILES:
        return []

    leaks = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                # Allow dummy test placeholders
                if "test-bot-token" in line or "dummy" in line or "example" in line:
                    continue
                for name, pattern in SECRET_PATTERNS:
                    matches = pattern.findall(line)
                    for match in matches:
                        redacted = match[:6] + "..." + match[-4:] if len(match) > 10 else "***"
                        leaks.append((name, line_no, redacted))
    except Exception:
        pass

    return leaks


def main() -> int:
    files = get_files_to_check()
    all_leaks = []

    for file_path in files:
        leaks = scan_file(file_path)
        for name, line_no, redacted in leaks:
            all_leaks.append((file_path, name, line_no, redacted))

    if all_leaks:
        print("\n" + "=" * 60)
        print("🚨 SECURITY ALERT: EXPOSED SECRETS DETECTED!")
        print("=" * 60)
        for file_path, name, line_no, redacted in all_leaks:
            print(f"❌ [{name}] at {file_path}:{line_no} -> {redacted}")
        print("\nPlease remove hardcoded secrets and use environment variables via os.getenv(...)")
        print("=" * 60 + "\n")
        return 1

    print(f"✅ Secret Guard passed: 0 leaks found across {len(files)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
