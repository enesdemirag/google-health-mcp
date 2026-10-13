import json
import stat
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


def test_operator_setup_creates_private_keys_without_printing_or_replacing_them(tmp_path):
    project = Path(__file__).resolve().parents[1]
    credentials = tmp_path / "web-client.json"
    credentials.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "operator.apps.googleusercontent.com",
                    "client_secret": "operator-private-secret",
                }
            }
        )
    )
    env_file = tmp_path / "operator.env"
    command = [
        sys.executable,
        str(project / "scripts/configure.py"),
        "--google-client-json",
        str(credentials),
        "--env-file",
        str(env_file),
    ]
    created = subprocess.run(command, capture_output=True, text=True, check=True)
    assert "operator-private-secret" not in created.stdout + created.stderr
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    data = dotenv_values(env_file)
    assert data["GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_SECRET"] == "operator-private-secret"
    assert len(data["GOOGLE_HEALTH_MCP_TOKEN_SIGNING_KEY"]) >= 32
    original = env_file.read_bytes()
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert env_file.read_bytes() == original


def test_desktop_google_credentials_are_not_a_multi_user_server_client(tmp_path):
    project = Path(__file__).resolve().parents[1]
    credentials = tmp_path / "desktop-client.json"
    credentials.write_text(json.dumps({"installed": {"client_id": "desktop", "client_secret": "secret"}}))
    env_file = tmp_path / "operator.env"
    result = subprocess.run(
        [
            sys.executable,
            str(project / "scripts/configure.py"),
            "--google-client-json",
            str(credentials),
            "--env-file",
            str(env_file),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not env_file.exists()
