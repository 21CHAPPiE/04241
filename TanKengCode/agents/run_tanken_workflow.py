from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .tanken_workflow import (
    DEFAULT_TANKEN_CASE_IDS,
    DEFAULT_TANKEN_MCP_COMMAND,
    TankenWorkflowRequest,
    create_tanken_workflow_runner,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic Agno workflow against the local Tanken MCP server."
    )
    parser.add_argument(
        "--case-id",
        required=True,
        help=f"Tanken case id such as 6.4.1, or 'all'. Supported cases: {', '.join(DEFAULT_TANKEN_CASE_IDS)}",
    )
    parser.add_argument("--event-csv-path", default=None, help="Optional event CSV override")
    parser.add_argument("--reservoir-config-path", default=None, help="Optional reservoir config override")
    parser.add_argument(
        "--mcp-command",
        default=DEFAULT_TANKEN_MCP_COMMAND,
        help="Command used by Agno MCPTools to launch the local Tanken MCP server.",
    )
    parser.add_argument(
        "--persist-result",
        action="store_true",
        help="If set, the workflow will request report persistence through the MCP tool.",
    )
    parser.add_argument(
        "--skip-case-report",
        action="store_true",
        help="If set, skip the final run_tanken_case MCP step and only execute the fixed tool chain.",
    )
    return parser


async def _run_async(args: argparse.Namespace) -> int:
    runner = create_tanken_workflow_runner(mcp_command=args.mcp_command)
    if args.case_id == "all":
        payload = await runner.run_all_cases(
            persist_result=args.persist_result,
            include_case_report=not args.skip_case_report,
            reservoir_config_path=args.reservoir_config_path,
        )
    else:
        request = TankenWorkflowRequest(
            case_id=args.case_id,
            event_csv_path=args.event_csv_path,
            reservoir_config_path=args.reservoir_config_path,
            persist_result=args.persist_result,
            include_case_report=not args.skip_case_report,
        )
        result = await runner.run(request)
        payload = result.content if hasattr(result, "content") else result
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
