from campaignflow import __version__
from campaignflow.cli import main


def test_version_is_set():
    assert isinstance(__version__, str) and __version__


def test_cli_no_args_prints_help_and_returns_zero(capsys):
    code = main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "campaignflow" in out.lower()
