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

    # --- 融合召回（双线并行） ---
    # 种子库文件路径；留空则用 repo 里的 data/poi.csv
    poi_csv: str = os.getenv("POI_CSV", "")
    # 高德通道总开关。RECALL_AMAP=0 时退回纯种子库，用于对照与兜底
    recall_amap_enabled: bool = os.getenv("RECALL_AMAP", "1") != "0"
    # 走廊中心点个数 / 每点翻页数（3×2=6 次调用）
    recall_amap_parts: int = int(os.getenv("RECALL_AMAP_PARTS", "3"))
    recall_amap_max_pages: int = int(os.getenv("RECALL_AMAP_MAX_PAGES", "2"))
    # 每条方案里种子库点位的保底占比，防止小店被高评分大景点挤掉
    seed_min_ratio: float = float(os.getenv("SEED_MIN_RATIO", "0.4"))


settings = Settings()
