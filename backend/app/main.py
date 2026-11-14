"""应用入口。

启动：
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .config import settings
from .errors import ApiError
from .routers import geo, health, intent, route, share, tips
from .services import store

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


SHARE_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%% · 漫步江城</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; padding: 28px 16px 40px;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    color: #17332e; background: radial-gradient(circle at 20% 0%, #1d5a50 0%, #0b2b26 46%, #071b18 100%); }
  .card { width: min(100%, 520px); margin: 0 auto; overflow: hidden; border-radius: 24px;
    background: #f6f1e5; box-shadow: 0 30px 70px -30px rgba(0,0,0,.65); }
  .hero { padding: 26px 24px 22px; color: #f7f1e2;
    background: linear-gradient(135deg, #1c5b50 0%, #0e3b34 60%, #0a2a25 100%); }
  .kicker { margin: 0 0 8px; font-size: 11px; letter-spacing: .28em; color: rgba(255,255,255,.5); }
  h1 { margin: 0; font-size: 27px; font-weight: 600; letter-spacing: .04em; }
  .stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  .stats span { padding: 5px 10px; border: 1px solid rgba(255,255,255,.22); border-radius: 999px;
    background: rgba(255,255,255,.08); font-size: 12px; }
  .body { padding: 22px 24px 26px; }
  .lead { margin: 0 0 18px; font-size: 14px; line-height: 1.9; color: #48625c; }
  .stops { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; }
  .stops li { display: flex; align-items: center; gap: 12px; padding: 12px 0;
    border-bottom: 1px dashed #d8d2c2; }
  .stops li:last-child { border-bottom: 0; }
  .n { display: grid; place-items: center; width: 26px; height: 26px; flex: 0 0 auto;
    border-radius: 999px; background: #e7ded0; color: #7a5b43; font-size: 12px; font-weight: 600; }
  .meta { min-width: 0; flex: 1; }
  .meta b { display: block; font-size: 14.5px; font-weight: 600; }
  .meta small { display: block; margin-top: 2px; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; font-size: 11px; color: #7f8e89; }
  .nav { flex: 0 0 auto; padding: 6px 10px; border-radius: 999px; border: 1px solid #b9cec6;
    color: #1c5b50; font-size: 11px; text-decoration: none; }
  footer { margin-top: 18px; padding-top: 14px; border-top: 1px solid #ded8c9;
    font-size: 11px; line-height: 1.8; color: #8b9894; }
  .empty { padding: 24px; text-align: center; color: #48625c; }
</style>
</head>
<body>
  <article class="card">
    <header class="hero">
      <p class="kicker">WUHAN · CITY WALK</p>
      <h1>%%TITLE%%</h1>
      <div class="stats"><span>%%KM%% km</span><span>约 %%MIN%% 分钟</span><span>%%COUNT%% 站</span></div>
    </header>
    <main class="body">
      <p class="lead">%%LEAD%%</p>
      <ul class="stops">%%STOPS%%</ul>
      <footer>由「漫步江城」生成 · 点位来自本地种子库，步行路径由高德地图逐段计算<br>出行前请核实场馆开放时间</footer>
    </main>
  </article>
</body>
</html>"""


def _share_page_html(scheme: dict) -> str:
    title = html.escape(str(scheme.get("title") or "武汉 City Walk"))
    km = round((scheme.get("distanceM") or 0) / 1000, 1)
    minutes = round((scheme.get("durationS") or 0) / 60)
    waypoints = scheme.get("waypoints") or []
    stops = []
    for i, w in enumerate(waypoints, start=1):
        name = html.escape(str(w.get("name") or "途经点"))
        desc = html.escape(str(w.get("address") or w.get("typeName") or "途经点"))
        lng, lat = w.get("lng"), w.get("lat")
        if lng is not None and lat is not None:
            link = (
                "https://uri.amap.com/marker?"
                f"position={lng},{lat}&name={quote(str(w.get('name') or ''))}"
                "&src=wuhan-citywalk&coordinate=gaode&callnative=0"
            )
            nav = f'<a class="nav" href="{html.escape(link)}" target="_blank" rel="noreferrer">导航</a>'
        else:
            nav = ""
        stops.append(
            f'<li><span class="n">{i}</span><div class="meta"><b>{name}</b>'
            f"<small>{desc}</small></div>{nav}</li>"
        )
    lead = f"从{html.escape(str(waypoints[0].get('name') if waypoints else '起点'))}出发，"
    lead += f"到{html.escape(str(waypoints[-1].get('name') if waypoints else '终点'))}，"
    lead += f"共 {len(waypoints)} 站。"
    return (
        SHARE_PAGE.replace("%%TITLE%%", title)
        .replace("%%KM%%", f"{km}")
        .replace("%%MIN%%", f"{minutes}")
        .replace("%%COUNT%%", f"{len(waypoints)}")
        .replace("%%LEAD%%", lead)
        .replace("%%STOPS%%", "".join(stops) or '<li class="empty">这条路线没有途经点</li>')
    )


@app.get("/s/{token}", include_in_schema=False)
async def share_page(token: str):
    """分享页：给微信/手机浏览器打开的可读版本。"""
    scheme = store.get_share(token)
    if scheme is None:
        return HTMLResponse(
            "<meta charset='utf-8'><h1>链接已失效</h1><p>请让分享者重新生成。</p>",
            status_code=404,
        )
    return HTMLResponse(_share_page_html(scheme))
