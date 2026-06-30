import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaignflow", description="Marketing-campaign ELT pipeline.")
    sub = parser.add_subparsers(dest="command")
    run_p = sub.add_parser("run", help="Generate data and build the bronze/silver/gold warehouse.")
    run_p.add_argument("--db", default="campaignflow.duckdb", help="DuckDB file path.")
    run_p.add_argument("--rows", type=int, default=5000, help="Approx raw rows to generate.")
    run_p.add_argument("--seed", type=int, default=42, help="Deterministic seed.")
    run_p.add_argument(
        "--landing-zone",
        action="store_true",
        help="Land raw in the blob landing zone (Azurite/Azure) and read bronze from az://.",
    )
    report_p = sub.add_parser("report", help="Print example analytics from the gold marts.")
    report_p.add_argument("--db", default="campaignflow.duckdb")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "run":
        from campaignflow.pipeline import run

        run(db_path=args.db, rows=args.rows, seed=args.seed, use_landing_zone=args.landing_zone)
        return 0
    if args.command == "report":
        from campaignflow.report import print_report

        print_report(db_path=args.db)
        return 0
    parser.print_help()
    return 0
