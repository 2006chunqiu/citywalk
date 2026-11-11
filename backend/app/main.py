"""应用入口。

启动：
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .errors import ApiError
from .routers import geo, health, route, share, tips

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


app.include_router(tips.router)
app.include_router(geo.router)
app.include_router(route.router)
app.include_router(share.router)
app.include_router(health.router)


@app.get("/")
async def index():
    return {"service": "citywalk-api", "docs": "/docs", "health": "/api/health"}
