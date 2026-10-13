"""Check tracked files for private artifacts and recognizable real credentials.

This is a publication guard, not a complete security audit. Use synthetic fixtures.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(rb"GOCSPX-[A-Za-z0-9_-]{15,}"),
    re.compile(rb"ya29\.[A-Za-z0-9_-]{20,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\b[0-9]{10,}-[a-z0-9]{15,}\.apps\.googleusercontent\.com\b"),
]


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    failures = []
    for name in filter(None, paths):
        path = Path(name)
        if path.name.startswith(".env") and path.name != ".env.example":
            failures.append(f"Private environment: {name}")
        if any(part in {".local", ".venv", "__pycache__", "oauth"} for part in path.parts):
            failures.append(f"Private/generated directory: {name}")
        if path.suffix in {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key"}:
            failures.append(f"Private artifact: {name}")
        data = (ROOT / path).read_bytes()
        if any(pattern.search(data) for pattern in PATTERNS):
            failures.append(f"Credential-like content: {name}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Publication guard passed for {len(list(filter(None, paths)))} tracked files.")


if __name__ == "__main__":
    main()
