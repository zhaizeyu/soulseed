"""Web API 入口：python -m src.web 或 uvicorn src.web.server:app"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*AiohttpClientSession.*")

import uvicorn
from src.core.config_loader import get_config

def main() -> None:
    cfg = get_config()
    host = str(cfg.get("web_host", "0.0.0.0"))
    port = int(cfg.get("web_port", "8765"))
    uvicorn.run(
        "src.web.server:app",
        host=host,
        port=port,
        reload=bool(cfg.get("web_reload", False)),
    )

if __name__ == "__main__":
    main()
