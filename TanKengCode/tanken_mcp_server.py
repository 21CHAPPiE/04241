"""Standalone Tanken-specific MCP server."""

from __future__ import annotations

from pyresops.server import create_server

from .tanken_common import DEFAULT_RESERVOIR_CONFIG
from .tanken_mcp_tools import setup_tanken_mcp_tools


def create_tanken_mcp_server():
    """Create the Tanken MCP server with both core and site-specific tools."""
    mcp_server = create_server(
        name="tanken-mcp",
        reservoir_config_path=str(DEFAULT_RESERVOIR_CONFIG.resolve()),
    )
    setup_tanken_mcp_tools(mcp_server)
    return mcp_server


mcp = create_tanken_mcp_server()


def main() -> int:
    """Run the Tanken MCP server."""
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
