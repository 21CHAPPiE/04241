from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from project.tanken import (
    DEFAULT_RESERVOIR_CONFIG,
    TANKEN_CASES,
    run_all_tanken_cases,
    run_tanken_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the project-layer Tanken demo flow.")
    parser.add_argument(
        "case_id",
        nargs="?",
        default="all",
        help=f"Case id to run. Supported: {', '.join(sorted(TANKEN_CASES))}, or 'all'.",
    )
    parser.add_argument("--event", type=Path, default=None, help="Optional event CSV path override for a single case run.")
    parser.add_argument(
        "--reservoir-config",
        type=Path,
        default=DEFAULT_RESERVOIR_CONFIG,
        help="Reservoir config path recorded in the report context.",
    )
    parser.add_argument("--no-save", action="store_true", help="Do not write JSON result files under project/results.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    save_result = not args.no_save
    if args.case_id == "all":
        payload = run_all_tanken_cases(
            reservoir_config_path=args.reservoir_config,
            save_result=save_result,
        )
    else:
        payload = run_tanken_demo(
            case_id=args.case_id,
            event_csv_path=args.event,
            reservoir_config_path=args.reservoir_config,
            save_result=save_result,
        )
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(serialized.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
