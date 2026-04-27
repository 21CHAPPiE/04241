from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .huadong_workflow import (
    DEFAULT_HUADONG_MCP_COMMAND,
    DEFAULT_WORKFLOW_OUTPUT_ROOT,
    HUADONG_SCENARIO_IDS,
    HuadongWorkflowRequest,
    create_huadong_workflow_runner,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic Agno workflows against the Huadong MCP server."
    )
    parser.add_argument(
        "--scenario-id",
        required=True,
        help=f"Scenario id such as 6.3.1, or 'all'. Supported: {', '.join(HUADONG_SCENARIO_IDS)}",
    )
    parser.add_argument("--output-root", default=DEFAULT_WORKFLOW_OUTPUT_ROOT)
    parser.add_argument("--start-time", default=None)
    parser.add_argument("--end-time", default=None)
    parser.add_argument("--initial-end-time", default=None)
    parser.add_argument("--updated-end-time", default=None)
    parser.add_argument("--basin-dataset-path", default="data/basin_001_hourly.csv")
    parser.add_argument("--multistation-dataset-path", default="data/rain_15stations_flow.csv")
    parser.add_argument(
        "--mcp-command",
        default=DEFAULT_HUADONG_MCP_COMMAND,
        help="Command used by Agno MCPTools to launch the local MCP server.",
    )
    return parser


async def _run_async(args: argparse.Namespace) -> int:
    runner = create_huadong_workflow_runner(mcp_command=args.mcp_command)
    if args.scenario_id == "all":
        payload = await runner.run_all(output_root=args.output_root)
    else:
        result = await runner.run(
            HuadongWorkflowRequest(
                scenario_id=args.scenario_id,
                output_root=args.output_root,
                start_time=args.start_time,
                end_time=args.end_time,
                initial_end_time=args.initial_end_time,
                updated_end_time=args.updated_end_time,
                basin_dataset_path=args.basin_dataset_path,
                multistation_dataset_path=args.multistation_dataset_path,
            )
        )
        payload = result.content if hasattr(result, "content") else result
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
