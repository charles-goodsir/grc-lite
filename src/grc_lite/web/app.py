"""The local server. It is meant for one person on one machine, so the defences are about
keeping other web pages and other paths out, not about multiple users."""

import secrets
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from grc_lite.loader import AssessmentError, load
from grc_lite.report import build_report
from grc_lite.web import files, records

STATIC = Path(__file__).parent / "static"
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class NotesIn(BaseModel):
    path: str
    text: str = Field(max_length=200_000)


class RecordIn(BaseModel):
    fields: dict[str, Any] = {}


class MetaIn(BaseModel):
    name: str = Field(max_length=200)
    scale: int
    slots: int


def create_app(level: Path, assessment: Path, token: str | None = None) -> FastAPI:
    token = token or secrets.token_urlsafe(32)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            sent = request.headers.get("x-grc-token", "").encode()
            if not secrets.compare_digest(sent, token.encode()):
                return JSONResponse({"detail": "missing or wrong token"}, 401)
            if request.method not in ("GET", "HEAD") and not request.headers.get(
                "content-type", ""
            ).startswith("application/json"):
                return JSONResponse({"detail": "JSON only"}, 415)
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    # added last so it runs first: a request for any other Host (DNS rebinding) is refused
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    def visible(path: str) -> Path:
        found = files.resolve_visible(level, path)
        if found is None:
            raise HTTPException(404, "no such file")
        return found

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text().replace("__TOKEN__", token)

    @app.get("/api/info")
    def info():
        return {"level": level.resolve().name}

    @app.get("/api/files")
    def list_files():
        return {"files": files.list_files(level)}

    @app.get("/api/file")
    def read_file(path: str):
        found = visible(path)
        if found.stat().st_size > files.MAX_BYTES:
            raise HTTPException(413, "file too large to show")
        return {"path": path, "kind": found.suffix.lower()[1:],
                "text": found.read_text(errors="replace")}  # fmt: skip

    @app.get("/api/notes")
    def read_notes(path: str):
        visible(path)
        target = files.notes_path(assessment, path)
        return {"text": target.read_text() if target.exists() else ""}

    @app.get("/api/notes-index")
    def notes_index():
        return {"paths": [p for p in files.list_files(level)
                          if files.notes_path(assessment, p).exists()]}  # fmt: skip

    @app.put("/api/notes")
    def write_notes(body: NotesIn):
        visible(body.path)
        target = files.notes_path(assessment, body.path)
        if not body.text.strip():
            target.unlink(missing_ok=True)
            return {"ok": True}
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_text(body.text)
        temp.replace(target)  # no half-written notes if the process dies mid-save
        return {"ok": True}

    def checked(kind: str) -> str:
        if kind not in records.KINDS:
            raise HTTPException(404, "unknown record type")
        return kind

    def guarded(action):
        try:
            return action()
        except records.RecordError as e:
            raise HTTPException(422, str(e)) from None

    @app.get("/api/records")
    def all_records():
        return guarded(lambda: records.snapshot(assessment))

    @app.post("/api/records/{kind}")
    def create_record(kind: str, body: RecordIn):
        return guarded(lambda: records.create(assessment, checked(kind), body.fields))

    @app.put("/api/records/{kind}/{ident}")
    def update_record(kind: str, ident: str, body: RecordIn):
        done = guarded(lambda: records.update(assessment, checked(kind), ident, body.fields))
        if done is None:
            raise HTTPException(404, "no such record")
        return done

    @app.delete("/api/records/{kind}/{ident}")
    def delete_record(kind: str, ident: str):
        done = guarded(lambda: records.delete(assessment, checked(kind), ident))
        if done is None:
            raise HTTPException(404, "no such record")
        return done

    @app.put("/api/meta")
    def put_meta(body: MetaIn):
        return guarded(lambda: records.set_meta(assessment, body.name, body.scale, body.slots))

    @app.get("/api/report")
    def report():
        found = records.problems(assessment)
        if found:
            return {"markdown": None, "problems": found}
        try:
            return {"markdown": build_report(load(assessment), date.today()), "problems": []}
        except AssessmentError:
            return {"markdown": None, "problems": records.problems(assessment)}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
