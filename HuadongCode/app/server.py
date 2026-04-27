"""Standalone FastMCP server for huadong-runtime."""

from __future__ import annotations

from fastmcp import FastMCP

from app.tools import setup_all_tools


def create_server() -> FastMCP:
    mcp_server = FastMCP("huadong-runtime")
    setup_all_tools(mcp_server)
    return mcp_server


mcp = create_server()


def main() -> None:
    """Run FastMCP server with default transport."""
    mcp.run()


if __name__ == "__main__":
    main()
