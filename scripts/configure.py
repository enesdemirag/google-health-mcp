"""Create a private operator environment without printing credentials or overwriting existing files."""

import argparse
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def main():
    parser = argparse.ArgumentParser(description="Configure the operator-owned Google Health MCP service.")
    parser.add_argument(
        "--google-client-json",
        type=Path,
        help="Downloaded Google Web application OAuth client JSON; never required from end users.",
    )
    parser.add_argument("--public-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    credentials = {}
    if args.google_client_json:
        data = json.loads(args.google_client_json.read_text())
        credentials = data.get("web", {})
        if not credentials.get("client_id") or not credentials.get("client_secret"):
            parser.error(
                "Use a Google Web application OAuth client JSON, not a Desktop application's credentials."
            )
    values = {
        "GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_ID": credentials.get("client_id", ""),
        "GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_SECRET": credentials.get("client_secret", ""),
        "GOOGLE_HEALTH_MCP_STORAGE_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "GOOGLE_HEALTH_MCP_TOKEN_SIGNING_KEY": secrets.token_urlsafe(48),
        "GOOGLE_HEALTH_MCP_PUBLIC_BASE_URL": args.public_base_url.rstrip("/"),
        "GOOGLE_HEALTH_MCP_HOST": "127.0.0.1",
        "GOOGLE_HEALTH_MCP_PORT": "8001",
        "GOOGLE_HEALTH_MCP_DATA_DIR": ".local/oauth",
    }
    lines = ["# Private operator configuration. Never commit or share this file."]
    lines.extend(f"{key}={json.dumps(value)}" for key, value in values.items())
    try:
        descriptor = os.open(args.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error(
            "The environment file already exists. Edit it explicitly; existing keys will not be replaced."
        )
    with os.fdopen(descriptor, "w") as output:
        output.write("\n".join(lines) + "\n")
    print(f"Created private configuration at {args.env_file}.")
    if not credentials:
        print("Set the operator's Google Web OAuth client ID and secret in this file before starting.")
    print(f"Register this Google callback: {args.public_base_url.rstrip('/')}/auth/callback")
    print("Keep both generated keys and the OAuth data volume across restarts.")


if __name__ == "__main__":
    main()
