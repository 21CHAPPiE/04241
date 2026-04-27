"""HTTP entrypoint for the Tanken REST API."""

from __future__ import annotations

import os

from project.tanken_rest_api import create_app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("TANKEN_REST_HOST", "0.0.0.0")
    port = int(os.environ.get("TANKEN_REST_PORT", "8001"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
