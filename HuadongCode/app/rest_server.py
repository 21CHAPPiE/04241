"""HTTP entrypoint for the Huadong REST API."""

from __future__ import annotations

from app.config.settings import settings
from app.rest_api import create_app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
