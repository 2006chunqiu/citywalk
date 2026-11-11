"""配置读取。所有密钥从环境变量来，代码里不写死。"""
from __future__ import annotations

import os
from pathlib import Path

# 允许从仓库根目录的 .env 读配置（没有这个包也不影响运行）
try:
    from dotenv import load_dotenv

    _root_env = Path(__file__).resolve().parents[2] / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
except Exception:  # noqa: BLE001 - 缺少 dotenv 时静默跳过
    pass


def _split(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


class Settings:
    # 高德 Web 服务 Key，支持多个，逗号分隔
    amap_web_keys: list[str] = _split(os.getenv("AMAP_WEB_KEYS"))
    # 模型服务（留空则文案自动降级为模板）
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    # 允许的前端来源
    cors_origins: list[str] = _split(os.getenv("CORS_ORIGINS")) or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # 单次生成的外部调用预算（PRD 5.4）
    api_call_budget: int = 45


settings = Settings()
