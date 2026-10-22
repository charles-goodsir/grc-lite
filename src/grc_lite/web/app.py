"""The local server. It is meant for one person on one machine, so the defences are about
keeping other web pages and other paths out, not about multiple users."""

import secrets
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from grc_lite.coverage import coverage
from grc_lite.grading import TAGS
from grc_lite.importer import file_notes
from grc_lite.loader import AssessmentError, load
from grc_lite.report import build_report
from grc_lite.web import export, files, grades, progress, records, search

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


class ImportIn(BaseModel):
    text: str = Field(max_length=files.MAX_BYTES)
    name: str = Field(default="", max_length=200)


class GradingIn(BaseModel):
    text: str = Field(max_length=1_000_000)
    name: str = Field(default="", max_length=200)
    replace: bool = False


class TagIn(BaseModel):
    tag: str = Field(max_length=60)


class MetaIn(BaseModel):
    name: str = Field(max_length=200)
    scale: int
    slots: int


def create_app(
    level: Path, assessment: Path, token: str | None = None, levels: Path | None = None
) -> FastAPI:
    token = token or secrets.token_urlsafe(32)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            sent = request.headers.get("x-grc-token", "").encode()
            if not secrets.compare_digest(sent, token.encode()):
                return JSONResponse({"detail": "missing or wrong token"}, 401)
            writing = request.method not in ("GET", "HEAD")
            grading = request.url.path.startswith("/api/grading")  # arrives after the lock
            if writing and export.is_locked(assessment) and not grading:
                return JSONResponse({"detail": "This level is submitted and locked"}, 423)
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
        found = files.resolve_visible(level, path, grades.revealed(assessment))
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
        return {"files": files.list_files(level, grades.revealed(assessment))}

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
        return {"paths": [p for p in files.list_files(level, grades.revealed(assessment))
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
        except records.ConflictError as e:
            raise HTTPException(409, str(e)) from None
        except records.RecordError as e:
            raise HTTPException(422, str(e)) from None

    @app.get("/api/records")
    def all_records():
        data = guarded(lambda: records.snapshot(assessment))
        return {**data, "locked": export.is_locked(assessment)}

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

    @app.get("/api/search")
    def find(q: str):
        return guarded(lambda: search.search(level, assessment, q))

    @app.get("/api/coverage")
    def coverage_report():
        def run():
            data = {kind: records.read_records(assessment, kind) for kind in records.KINDS}
            return coverage(data, date.today())

        return guarded(run)

    @app.get("/api/grading")
    def get_grading():
        return {"graded": grades.has_grading(assessment), "grading": grades.read(assessment),
                "tags": TAGS, "revealed": grades.revealed(assessment)}  # fmt: skip

    @app.post("/api/grading")
    def import_grading(body: GradingIn):
        return guarded(
            lambda: grades.import_grading(assessment, body.text, body.name, body.replace)
        )

    @app.put("/api/grading/mistakes/{mistake_id}")
    def tag_mistake(mistake_id: str, body: TagIn):
        done = guarded(lambda: grades.set_tag(assessment, mistake_id, body.tag))
        if done is None:
            raise HTTPException(404, "no such mistake")
        return done

    @app.get("/api/progress")
    def progress_across_levels():
        root = levels if levels is not None else level.resolve().parent
        return progress.progress(root, level, assessment)

    @app.post("/api/submit")
    def submit():
        return guarded(lambda: export.submit(level, assessment))

    @app.get("/api/submission")
    def submission():
        return export.submission_status(level, assessment)

    @app.post("/api/import-notes")
    def import_notes(body: ImportIn):
        def run():
            done = records.import_notes(assessment, body.text, body.name)
            moved = 0
            for title, text in file_notes(body.text).items():
                rel = (
                    title.split("/", 1)[1] if "/" in title else title
                )  # drop the notes tool's folder name
                if (
                    files.resolve_visible(level, rel)
                    and not files.notes_path(assessment, rel).exists()
                ):
                    target = files.notes_path(assessment, rel)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text)
                    moved += 1
            return {**done, "notes_imported": moved}

        return guarded(run)

    EXPORTS = {
        "submission.md": ("text/markdown", lambda: export.submission_md(level, assessment).encode()),
        "report.md": ("text/markdown", lambda: _report_markdown().encode()),
        "report.html": ("text/html", lambda: export.report_html(
            records.read_meta(assessment).name, _report_markdown())),
        "records.zip": ("application/zip", lambda: export.zip_bytes(assessment)),
        "records.xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         lambda: export.xlsx_bytes(assessment)),
        **{f"{kind}.csv": ("text/csv", lambda kind=kind: export.csv_bytes(assessment, kind))
           for kind in records.KINDS},
    }  # fmt: skip

    def _report_markdown() -> str:
        if records.problems(assessment):
            raise records.RecordError("fix the problems before exporting the report")
        try:
            return build_report(load(assessment), date.today())
        except AssessmentError:
            raise records.RecordError("nothing to report yet") from None

    @app.get("/api/export/{name}")
    def export_file(name: str):
        if name not in EXPORTS:
            raise HTTPException(404, "no such export")
        media, build = EXPORTS[name]
        body = guarded(build)
        return Response(body, media_type=media,
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})  # fmt: skip

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
