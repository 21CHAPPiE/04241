"""Compatibility wrapper for the FastMCP runtime entrypoint."""

from __future__ import annotations

from app.server import create_server, main, mcp

__all__ = ["create_server", "main", "mcp"]
