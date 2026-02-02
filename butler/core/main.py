import logging

import uvicorn

from .config import load_config
from .service import ButlerService
from .web import create_app


def build_service() -> ButlerService:
    config = load_config()
    return ButlerService(config)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

service = build_service()
app = create_app(service)


if __name__ == "__main__":
    uvicorn.run("butler.core.main:app", host="0.0.0.0", port=8000, log_level="info")
