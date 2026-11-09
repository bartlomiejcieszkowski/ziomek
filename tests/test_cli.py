"""Tests for the command: what a run is told about its parts."""

from unittest.mock import patch

from ziomek.cli import main
from ziomek.stt import stt_installed


def run_with(argv, stt_available=True):
    """Run the command with a stand-in for the run, so what it was told can be read back."""
    with (
        patch("sys.argv", ["ziomek"] + argv),
        patch("ziomek.cli.stt_installed", return_value=stt_available),
        patch("ziomek.cli.run_server") as called,
    ):
        main()
    return called


class TestMcpFlagPlumbing:
    """The flags for the tools decide what the run is told about them."""

    def test_the_run_is_told_to_turn_the_tools_off_when_the_flag_is_given(self):
        called = run_with(["--no-mcp"])
        assert called.call_args.kwargs["no_mcp"] is True

    def test_the_run_is_told_to_use_stdio_when_stdio_is_stated(self):
        called = run_with(["--mcp-stdio"])
        assert called.call_args.kwargs["mcp_transport"] == "stdio"

    def test_the_run_is_not_told_to_turn_the_tools_off_when_nothing_is_stated(self):
        """Nothing stated on the command line leaves the decision to the config file."""
        called = run_with([])
        assert called.call_args.kwargs["no_mcp"] is None


class TestSttInstalled:
    """Tests for the optional 'stt' extra availability check."""

    def test_the_command_says_the_speech_package_is_there_when_it_can_be_found(self):
        with patch("ziomek.stt.find_spec", return_value=object()):
            assert stt_installed() is True

    def test_false_when_package_missing(self):
        with patch("ziomek.stt.find_spec", return_value=None):
            assert stt_installed() is False


class TestSttMissingExtraWarning:
    """Option 3: warn and continue — the server still runs with STT disabled."""

    def test_warns_but_still_runs_server(self, capsys):
        called = run_with([], stt_available=False)  # must not raise SystemExit

        err = capsys.readouterr().err
        assert "stt" in err.lower()
        assert "ziomek[stt]" in err
        assert called.call_count == 1

    def test_no_warning_when_stt_available(self, capsys):
        called = run_with([])

        assert capsys.readouterr().err == ""
        assert called.call_count == 1

    def test_warns_even_with_no_gamepad(self, capsys):
        """Gamepad gating does not gate STT, so a missing extra is still reported."""
        called = run_with(["--no-gamepad"], stt_available=False)

        assert "ziomek[stt]" in capsys.readouterr().err
        assert called.call_count == 1

    def test_does_not_warn_when_stt_is_disabled(self, capsys):
        """With --no-stt we never use STT, so a missing extra is not worth reporting."""
        called = run_with(["--no-stt"], stt_available=False)

        assert capsys.readouterr().err == ""
        assert called.call_count == 1


class TestSttFlagPlumbing:
    """--no-stt reaches run_server as no_stt."""

    def test_no_stt_passed_to_run_server(self):
        called = run_with(["--no-stt"])
        assert called.call_args.kwargs["no_stt"] is True


class TestGamepadFlagPlumbing:
    """--no-gamepad reaches run_server as no_gamepad."""

    def test_no_gamepad_passed_to_run_server(self):
        called = run_with(["--no-gamepad"])
        assert called.call_args.kwargs["no_gamepad"] is True
