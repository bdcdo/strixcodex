"""Entry point: `python -m strixcodex` starts the proxy on 127.0.0.1:8787."""
from __future__ import annotations

import argparse
import logging
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="strixcodex")
    parser.add_argument("--host", default=os.environ.get("STRIXCODEX_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("STRIXCODEX_PORT", "8787"))
    )
    parser.add_argument("--log-level", default=os.environ.get("STRIXCODEX_LOG", "info"))
    parser.add_argument("--reload", action="store_true", help="auto-reload (dev only)")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    uvicorn.run(
        "strixcodex.server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
