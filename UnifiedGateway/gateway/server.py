from __future__ import annotations

import os

from gateway.app import create_app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("UNIFIED_REST_HOST", "0.0.0.0")
    port = int(os.environ.get("UNIFIED_REST_PORT", "8010"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
