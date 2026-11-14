"""应用入口。

启动：
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .errors import ApiError
from .routers import geo, health, intent, route, share, tips

app = FastAPI(title="漫步江城 API", version="0.1.0", description="武汉 City Walk 路线推荐")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """参数校验失败也走统一错误结构，避免前端拿到 FastAPI 默认的 detail 数组。"""
    first = (exc.errors() or [{}])[0]
    parts = [str(p) for p in (first.get("loc") or []) if p not in ("body", "query", "path")]
    field = ".".join(parts) or "请求参数"
    msg = first.get("msg") or "参数不合法"
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_REQUEST", "message": f"{field}：{msg}"}},
    )


app.include_router(tips.router)
app.include_router(geo.router)
app.include_router(route.router)
app.include_router(share.router)
app.include_router(health.router)
app.include_router(intent.router)


@app.get("/")
async def index():
    return {"service": "citywalk-api", "docs": "/docs", "demo": "/demo", "health": "/api/health"}


WEB_DIR = Path(__file__).resolve().parent / "web"


@app.get("/demo", include_in_schema=False)
async def demo_page():
    """保底演示页：单文件 HTML，同源调用本服务接口。"""
    return FileResponse(WEB_DIR / "citywalk-demo.html", media_type="text/html")
