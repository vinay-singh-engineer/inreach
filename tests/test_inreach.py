import os
import sys
import tempfile
import socket
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from inReach import _clean_output, parse_hosts_file, run_check, check_local, _VERSION


# ── _clean_output ────────────────────────────────────────────────────────────

class TestCleanOutput:
    def test_keeps_nc_success_line(self):
        raw = "Connection to google.com 443 port [tcp/https] succeeded!"
        assert raw in _clean_output(raw)

    def test_strips_double_star_warning(self):
        raw = "** WARNING: connection is not using a post-quantum key exchange algorithm."
        assert _clean_output(raw) == ""

    def test_strips_connection_id(self):
        raw = "Connection ID: 9ff889f4-477d-45f1-89bd-15ebe470d9c4"
        assert _clean_output(raw) == ""

    def test_strips_sshgate_version(self):
        raw = "SSHgate version: 7056"
        assert _clean_output(raw) == ""

    def test_strips_warning_prefix(self):
        raw = "Warning: Permanently added 'host.example.com' (ED25519) to the list of known hosts."
        assert _clean_output(raw) == ""

    def test_strips_https_url(self):
        raw = "https://openssh.com/pq.html"
        assert _clean_output(raw) == ""

    def test_mixed_banner_and_nc_output(self):
        raw = (
            "** WARNING: some warning\n"
            "Connection ID: abc-123\n"
            "Connection to google.com 443 port [tcp/https] succeeded!"
        )
        result = _clean_output(raw)
        assert "succeeded" in result
        assert "WARNING" not in result
        assert "Connection ID" not in result

    def test_empty_input(self):
        assert _clean_output("") == ""

    def test_blank_lines_ignored(self):
        raw = "\n\n   \nConnection to google.com 443 port [tcp/https] succeeded!\n\n"
        assert "succeeded" in _clean_output(raw)


# ── parse_hosts_file ─────────────────────────────────────────────────────────

class TestParseHostsFile:
    def _write(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_plain_host_list(self):
        path = self._write("host1.example.com\nhost2.example.com\nhost3.example.com\n")
        assert parse_hosts_file(path) == ["host1.example.com", "host2.example.com", "host3.example.com"]

    def test_skips_comments(self):
        path = self._write("# this is a comment\nhost1.example.com\n# another comment\nhost2.example.com\n")
        assert parse_hosts_file(path) == ["host1.example.com", "host2.example.com"]

    def test_skips_ansible_group_headers(self):
        path = self._write("[webservers]\nhost1.example.com\nhost2.example.com\n[db]\nhost3.example.com\n")
        assert parse_hosts_file(path) == ["host1.example.com", "host2.example.com", "host3.example.com"]

    def test_skips_ansible_vars(self):
        path = self._write("[all:vars]\nansible_user=ec2-user\nansible_port=22\n[hosts]\nhost1.example.com\n")
        assert parse_hosts_file(path) == ["host1.example.com"]

    def test_skips_empty_lines(self):
        path = self._write("\nhost1.example.com\n\nhost2.example.com\n\n")
        assert parse_hosts_file(path) == ["host1.example.com", "host2.example.com"]

    def test_empty_file_returns_empty_list(self):
        path = self._write("")
        assert parse_hosts_file(path) == []

    def test_missing_file_exits(self):
        with pytest.raises(SystemExit):
            parse_hosts_file("/nonexistent/path/hosts.txt")


# ── check_local ──────────────────────────────────────────────────────────────

class TestCheckLocal:
    def test_success(self):
        mock_sock = MagicMock()
        with patch("socket.create_connection", return_value=mock_sock):
            ok, msg = check_local("google.com", 443)
        assert ok is True
        assert "Connected in" in msg
        assert "ms" in msg

    def test_failure_connection_refused(self):
        with patch("socket.create_connection", side_effect=ConnectionRefusedError("Connection refused")):
            ok, msg = check_local("localhost", 19999)
        assert ok is False
        assert "Connection refused" in msg

    def test_failure_timeout(self):
        with patch("socket.create_connection", side_effect=TimeoutError("timed out")):
            ok, msg = check_local("10.0.0.1", 443)
        assert ok is False


# ── run_check dispatch ───────────────────────────────────────────────────────

class TestRunCheck:
    def test_localhost_calls_check_local(self):
        with patch("inReach.check_local", return_value=(True, "Connected in 5ms")) as mock:
            run_check("localhost", "google.com", 443)
            mock.assert_called_once_with("google.com", 443)

    def test_127_calls_check_local(self):
        with patch("inReach.check_local", return_value=(True, "Connected in 5ms")) as mock:
            run_check("127.0.0.1", "google.com", 443)
            mock.assert_called_once_with("google.com", 443)

    def test_remote_host_calls_check_remote(self):
        with patch("inReach.check_remote", return_value=(True, "succeeded")) as mock:
            run_check("host1.example.com", "google.com", 443)
            mock.assert_called_once_with("host1.example.com", "google.com", 443)


# ── VERSION ──────────────────────────────────────────────────────────────────

class TestVersion:
    def test_version_not_empty(self):
        assert _VERSION != ""

    def test_version_format(self):
        parts = _VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
