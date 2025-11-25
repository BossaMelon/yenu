from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from yenu.settings import UPLOADS_DIR
from yenu.routers.api import router as api_router
from yenu.routers.pages import router as pages_router


app = FastAPI(title="Yenu: Local Recipe Manager")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(pages_router)

# Static & uploads
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
# Serve uploads at both /uploads and /assets/uploads to match stored paths
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/assets/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="assets_uploads")


# Error handling: return JSON for API routes, template for pages.
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith("/api")


def _friendly_from_details(details: list[dict]) -> list[str]:
    msgs: list[str] = []
    for e in details:
        loc = [str(x) for x in e.get("loc", [])]
        field_path = ".".join(loc)
        msg = str(e.get("msg", ""))
        text = ""
        path_str = ",".join(loc)
        # Map common fields to user-friendly Chinese messages
        if any(x == "title" for x in loc):
            text = "标题不能为空"
        elif any(x == "ingredients" for x in loc) and ("at least" in msg or "too short" in msg or "ensure" in msg):
            text = "至少需要一个配料"
        elif any(x == "steps" for x in loc) and ("at least" in msg or "too short" in msg or "ensure" in msg):
            text = "至少需要一个步骤"
        elif any(x == "name" for x in loc):
            text = "配料名称不能为空"
        elif any(x == "unit" for x in loc):
            text = "单位不能为空"
        else:
            text = msg or field_path
        if text:
            msgs.append(text)
    # De-duplicate while preserving order
    seen = set()
    unique: list[str] = []
    for m in msgs:
        if m not in seen:
            unique.append(m)
            seen.add(m)
    return unique or ["输入有误，请检查后重试"]


def _friendly_from_value_error(exc: Exception) -> str:
    text = str(exc)
    if "Unsupported image type" in text:
        return "不支持的图片格式（仅支持 JPEG/PNG）"
    if "Image too large" in text:
        return "图片过大，请压缩后再上传"
    return text or "输入有误，请检查后重试"


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if _is_api_request(request):
        return JSONResponse(status_code=exc.status_code, content={"error": "http_error", "friendly": [str(exc.detail)]})
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "friendly": [str(exc.detail)]},
        status_code=exc.status_code,
    )


try:
    # Pydantic v1 path
    from pydantic.error_wrappers import ValidationError as PydValidationError
except Exception:  # pragma: no cover
    try:  # Pydantic v2 path
        from pydantic import ValidationError as PydValidationError  # type: ignore
    except Exception:  # pragma: no cover
        PydValidationError = Exception  # type: ignore


@app.exception_handler(PydValidationError)
async def validation_exception_handler(request: Request, exc: PydValidationError):
    details = getattr(exc, "errors", lambda: [])()
    friendly = _friendly_from_details(details if isinstance(details, list) else [])
    if _is_api_request(request):
        return JSONResponse(status_code=400, content={"error": "validation_error", "friendly": friendly})
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 400, "friendly": friendly},
        status_code=400,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    friendly = _friendly_from_value_error(exc)
    if _is_api_request(request):
        return JSONResponse(status_code=400, content={"error": "invalid_input", "friendly": [friendly]})
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 400, "friendly": [friendly]},
        status_code=400,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if _is_api_request(request):
        return JSONResponse(status_code=500, content={"error": "internal_error", "friendly": ["系统内部错误，请稍后再试"]})
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 500, "friendly": ["系统内部错误，请稍后再试"]},
        status_code=500,
    )
