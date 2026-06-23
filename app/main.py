from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .batch_crawl import get_batch_status
from .config import APP_TITLE, STATIC_DIR, TEMPLATES_DIR
from .db import init_db
from .repository import fetch_dashboard_data, search_game_by_name
from .scheduler import create_scheduler
from .services import CrawlService, find_strategy_videos


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title=APP_TITLE)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

crawl_service = CrawlService()
scheduler = create_scheduler(crawl_service)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    if not scheduler.running:
        scheduler.start()
    asyncio.create_task(asyncio.to_thread(crawl_service.refresh_all))


@app.on_event("shutdown")
def on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": APP_TITLE},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/api/dashboard")
def get_dashboard():
    return JSONResponse(fetch_dashboard_data())


@app.get("/api/batch-status")
def batch_status():
    return JSONResponse(get_batch_status())


@app.get("/api/search")
async def search_game(q: str):
    query = q.strip()
    if not query:
        return JSONResponse({"error": "请输入游戏名称"}, status_code=400)
    match = search_game_by_name(query)
    if not match:
        return JSONResponse({"error": "数据库里暂时没有匹配到这款游戏"}, status_code=404)
    videos = await asyncio.to_thread(find_strategy_videos, match["game"]["name"])
    return JSONResponse({**match, "videos": videos})


@app.get("/api/meta")
def get_meta():
    jobs = scheduler.get_jobs()
    return JSONResponse(
        {
            "scheduler_running": scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "next_run_time": _job_next_run_time(job),
                }
                for job in jobs
            ],
        }
    )


@app.post("/api/refresh")
async def refresh_now():
    result = await asyncio.to_thread(crawl_service.refresh_all)
    return JSONResponse(result)


def _job_next_run_time(job) -> str | None:
    next_run_time = getattr(job, "next_run_time", None)
    return next_run_time.isoformat() if next_run_time else None
