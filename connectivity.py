import socket
import subprocess
import time

_BANNER_PREFIXES = (
    "** ",
    "***",
    "Warning:",
    "Connection ID:",
    "SSHgate version:",
    "https://",
    "http://",
)


def _clean_output(raw: str) -> str:
    lines = [
        ln for ln in raw.splitlines()
        if ln.strip() and not any(ln.strip().startswith(p) for p in _BANNER_PREFIXES)
    ]
    return " ".join(lines).strip()


def check_local(dest: str, port) -> tuple[bool, str]:
    try:
        t0 = time.time()
        sock = socket.create_connection((dest, int(port)), timeout=5)
        sock.close()
        ms = int((time.time() - t0) * 1000)
        return True, f"Connected in {ms}ms"
    except Exception as e:
        return False, str(e)


def check_remote(source: str, dest: str, port) -> tuple[bool, str]:
    cmd = [
        "ssh",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        source,
        f"nc -vz {dest} {port}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        success = result.returncode == 0
        output = _clean_output(result.stdout + result.stderr)
        return success, output or ("Success" if success else "Failed")
    except subprocess.TimeoutExpired:
        return False, "Timed out"
    except Exception as e:
        return False, str(e)
