import logging

import uvicorn

from core.settings import load_settings
from api.app import create_app

settings = load_settings()
app = create_app(settings)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    main()
