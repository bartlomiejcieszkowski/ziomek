"""Tests for the CLI dependency guards (MCP exits, STT warns and continues)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ziomek.cli import main, mcp_installed
from ziomek.stt import stt_installed


class TestMcpInstalled:
    """Tests for the optional 'mcp' package availability check."""

    def test_true_when_package_importable(self):
        with patch("ziomek.cli.find_spec", return_value=object()):
            assert mcp_installed() is True

    def test_false_when_package_missing(self):
        with patch("ziomek.cli.find_spec", return_value=None):
            assert mcp_installed() is False


class TestMcpFlagGuard:
    """Tests for exiting when MCP is requested but 'mcp' is not installed."""

    def test_exits_with_error_when_mcp_missing(self, capsys):
        with (
            patch("sys.argv", ["ziomek", "--mcp"]),
            patch("ziomek.cli.mcp_installed", return_value=False),
            patch("ziomek.cli.run_server") as run_server,
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "mcp" in err.lower()
        assert "install" in err.lower()
        run_server.assert_not_called()

    def test_exits_with_error_when_mcp_stdio_missing(self, capsys):
        with (
            patch("sys.argv", ["ziomek", "--mcp-stdio"]),
            patch("ziomek.cli.mcp_installed", return_value=False),
            patch("ziomek.cli.run_server") as run_server,
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        assert "mcp" in capsys.readouterr().err.lower()
        run_server.assert_not_called()

    def test_runs_server_when_mcp_available(self, capsys):
        with (
            patch("sys.argv", ["ziomek", "--mcp"]),
            patch("ziomek.cli.mcp_installed", return_value=True),
            patch("ziomek.cli.stt_installed", return_value=True),
            patch("ziomek.cli.run_server") as run_server,
        ):
            main()

        assert capsys.readouterr().err == ""
        run_server.assert_called_once()

    def test_no_check_when_mcp_not_requested(self, capsys):
        with (
            patch("sys.argv", ["ziomek"]),
            patch("ziomek.cli.mcp_installed", return_value=False),
            patch("ziomek.cli.stt_installed", return_value=True),
            patch("ziomek.cli.run_server") as run_server,
        ):
            main()

        assert capsys.readouterr().err == ""
        run_server.assert_called_once()


class TestSttInstalled:
    """Tests for the optional 'stt' extra availability check."""

    def test_true_when_package_importable(self):
        with patch("ziomek.stt.find_spec", return_value=object()):
            assert stt_installed() is True

    def test_false_when_package_missing(self):
        with patch("ziomek.stt.find_spec", return_value=None):
            assert stt_installed() is False


class TestSttMissingExtraWarning:
    """Option 3: warn and continue — the server still runs with STT disabled."""

    def test_warns_but_still_runs_server(self, capsys):
        with (
            patch("sys.argv", ["ziomek"]),
            patch("ziomek.cli.mcp_installed", return_value=True),
            patch("ziomek.cli.stt_installed", return_value=False),
            patch("ziomek.cli.run_server") as run_server,
        ):
            main()  # must not raise SystemExit

        err = capsys.readouterr().err
        assert "stt" in err.lower()
        assert "ziomek[stt]" in err
        assert "install" in err.lower()
        run_server.assert_called_once()

    def test_no_warning_when_stt_available(self, capsys):
        with (
            patch("sys.argv", ["ziomek"]),
            patch("ziomek.cli.mcp_installed", return_value=True),
            patch("ziomek.cli.stt_installed", return_value=True),
            patch("ziomek.cli.run_server") as run_server,
        ):
            main()

        assert capsys.readouterr().err == ""
        run_server.assert_called_once()

    def test_warns_even_with_no_vscode(self, capsys):
        """The engine is created in every mode, so a missing extra is always reported."""
        with (
            patch("sys.argv", ["ziomek", "--no-vscode"]),
            patch("ziomek.cli.mcp_installed", return_value=True),
            patch("ziomek.cli.stt_installed", return_value=False),
            patch("ziomek.cli.run_server") as run_server,
        ):
            main()

        err = capsys.readouterr().err
        assert "ziomek[stt]" in err
        run_server.assert_called_once()
