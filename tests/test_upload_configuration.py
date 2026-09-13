"""Exercise actual app startup with environment settings, without allocating large files."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("configured,expected_mb", [(None, 50), (6144, 6144), (10240, 10240)])
def test_upload_limit_at_startup_and_health(configured, expected_mb, tmp_path):
    env = dict(os.environ, PROOFCHECK_REPORT_DIR=str(tmp_path / "reports"), PROOFCHECK_AUTH="off")
    env.pop("MAX_UPLOAD_MB", None)
    if configured is not None:
        env["MAX_UPLOAD_MB"] = str(configured)
    code = f"""
from fastapi.testclient import TestClient
from proofcheck.web.app import app, MAX_UPLOAD_BYTES
assert MAX_UPLOAD_BYTES == {expected_mb} * 1024 * 1024
client = TestClient(app)
assert client.get('/api/health').json()['max_upload_bytes'] == MAX_UPLOAD_BYTES
# Below the aggregate ceiling, admission lets an incomplete body reach validation.
assert client.post('/api/check', content=b'', headers={{'Content-Length': str(MAX_UPLOAD_BYTES)}}).status_code == 422
# Byte arithmetic must also work beyond 32-bit lengths without reading/allocating a file.
assert client.post('/api/check', content=b'', headers={{'Content-Length': str(2 * MAX_UPLOAD_BYTES + 1024 * 1024 + 1)}}).status_code == 413
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_above_ten_gib_ceiling_fails_with_updated_message(tmp_path):
    env = dict(os.environ, MAX_UPLOAD_MB="10241", PROOFCHECK_REPORT_DIR=str(tmp_path / "reports"))
    result = subprocess.run([sys.executable, "-c", "import proofcheck.web.app"], env=env,
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "MAX_UPLOAD_MB must be between 1 and 10240" in result.stderr
