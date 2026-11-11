"""Command-line entry point for the PS-069 Scholarship Eligibility & Disbursement Engine."""

import argparse
from pathlib import Path

from engine.engine import ScholarshipEngine


def main() -> None:
    """Parse arguments, run the command file, and export output CSV reports."""
    project_root = Path(__file__).resolve().parent
    default_data_dir = project_root / "T043-PS-069-sample-data"
    default_output_dir = project_root / "output"

    parser = argparse.ArgumentParser(
        description="PS-069 Scholarship Eligibility and Disbursement Engine"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_dir,
        help="Path to folder containing schemes.csv, applications.csv, commands.txt, etc.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help="Path where output CSV files will be written.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console printout of PRINT_* commands.",
    )
    args = parser.parse_args()

    engine = ScholarshipEngine(data_dir=args.data_dir, quiet=args.quiet)
    engine.run_commands_file()
    engine.write_outputs(args.output_dir)
    if not args.quiet:
        print(f"\nAll output CSVs written to: {args.output_dir}")


if __name__ == "__main__":
    main()
