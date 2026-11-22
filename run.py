"""芯知 SemiKB 启动入口。

用法:
    python run.py
    python run.py --reload
    python run.py --port 8010
"""
import argparse

import uvicorn

from semikb.common.config import Config


def parse_args():
    parser = argparse.ArgumentParser(description="芯知 SemiKB 半导体文档知识库")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = Config.instance()
    host = args.host or str(config.get("server.host", "0.0.0.0"))
    port = args.port or int(config.get("server.port", 8010))
    reload_mode = args.reload or bool(config.get("server.reload", False))
    uvicorn.run("semikb.main:app", host=host, port=port, reload=reload_mode)


if __name__ == "__main__":
    main()
