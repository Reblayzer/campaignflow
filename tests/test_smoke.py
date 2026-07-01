from campaignflow import __version__
from campaignflow.cli import build_parser, main


def test_version_is_set():
    assert isinstance(__version__, str) and __version__


def test_run_parser_exposes_landing_zone_flag():
    assert build_parser().parse_args(["run", "--landing-zone"]).landing_zone is True
    assert build_parser().parse_args(["run"]).landing_zone is False


def test_cli_no_args_prints_help_and_returns_zero(capsys):
    code = main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "campaignflow" in out.lower()


def test_export_parser_has_db_and_out_defaults():
    args = build_parser().parse_args(["export"])
    assert args.db == "campaignflow.duckdb"
    assert args.out == "dashboard/public/data/marts.json"
