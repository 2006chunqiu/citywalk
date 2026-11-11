"""进程内存储。开发阶段先用字典，接入 PostgreSQL 后替换为 repository 层。"""
from __future__ import annotations

from typing import Any

SCHEMES: dict[str, dict[str, Any]] = {}
SHARES: dict[str, str] = {}  # token -> schemeId


def save_result(result: dict) -> None:
    for scheme in result.get("schemes", []):
        SCHEMES[scheme["schemeId"]] = scheme


def get_scheme(scheme_id: str) -> dict | None:
    return SCHEMES.get(scheme_id)


def create_share(token: str, scheme_id: str) -> None:
    SHARES[token] = scheme_id


def get_share(token: str) -> dict | None:
    scheme_id = SHARES.get(token)
    return SCHEMES.get(scheme_id) if scheme_id else None
