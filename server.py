"""
MODULE: server
WHAT: FastAPI web server replacing Streamlit. Serves the single-page frontend,
runs the pipeline via SSE streaming, manages API keys, and stores campaign history.
DECISION: FastAPI + uvicorn starts in <1 second with no network calls on boot.
SSE is streamed via fetch()+ReadableStream (not EventSource -- POST body required).
Pipeline runs in a background thread; asyncio.Queue bridges thread -> async SSE.
PRODUCTION ALTERNATIVE: Async task queue (Celery/Redis) with WebSocket for
bidirectional communication, multi-user session isolation, and job cancellation.
"""

import asyncio
import io
import json
import os
import threading
import zipfile
from pathlib import Path

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from config import BASE_DIR
import db
from pipeline import run_pipeline

load_dotenv()

app = FastAPI(title="CREATIVEpipeline", docs_url=None, redoc_url=None)

STATIC_DIR = BASE_DIR / "static"
OUTPUTS_DIR = BASE_DIR / "outputs"
ENV_PATH = BASE_DIR / ".env"

db.init_db()


# ---------------------------------------------------------------------------
# Static / file routes
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/outputs/{product}/{file}")
async def serve_output(product: str, file: str):
    path = OUTPUTS_DIR / product / file
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="image/png")


@app.post("/api/download-zip")
async def download_zip(request: Request):
    body = await request.json()
    # paths are relative: "{product}/{file}.png"
    rel_paths = body.get("paths", [])
    campaign_id = body.get("campaign_id", "campaign")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in rel_paths:
            full = OUTPUTS_DIR / rel
            if full.exists():
                zf.write(full, arcname=full.name)
    buf.seek(0)
    filename = "{}.zip".format(campaign_id)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename={}".format(filename)},
    )


@app.get("/report")
async def serve_report():
    report = OUTPUTS_DIR / "report.html"
    if not report.exists():
        return JSONResponse({"error": "No report yet"}, status_code=404)
    return FileResponse(report, media_type="text/html")


# ---------------------------------------------------------------------------
# API: campaigns
# ---------------------------------------------------------------------------

@app.get("/api/campaigns")
async def list_campaigns():
    rows = db.list_campaigns(limit=25)
    for r in rows:
        if isinstance(r.get("summary_json"), str):
            r["summary_json"] = json.loads(r["summary_json"] or "{}")
    return rows


@app.get("/api/campaigns/{row_id}")
async def get_campaign(row_id: int):
    row = db.get_campaign(row_id)
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)
    row["brief_json"] = json.loads(row["brief_json"])
    row["summary_json"] = json.loads(row["summary_json"])
    row["output_paths_json"] = json.loads(row.get("output_paths_json") or "{}")
    return row


# ---------------------------------------------------------------------------
# API: brief
# ---------------------------------------------------------------------------

@app.post("/api/brief/parse")
async def parse_brief(request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    from brief_parser_nl import parse_natural_language_brief
    try:
        brief = parse_natural_language_brief(text)
        return brief
    except EnvironmentError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/brief/example")
async def get_example_brief():
    example = BASE_DIR / "campaign_brief.json"
    if not example.exists():
        return JSONResponse({"error": "no example brief"}, status_code=404)
    with open(example) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# API: API key management
# ---------------------------------------------------------------------------

@app.post("/api/keys")
async def save_keys(request: Request):
    body = await request.json()
    bfl = (body.get("bfl_api_key") or "").strip()
    openai = (body.get("openai_api_key") or "").strip()
    if bfl:
        os.environ["BFL_API_KEY"] = bfl
        set_key(str(ENV_PATH), "BFL_API_KEY", bfl)
    if openai:
        os.environ["OPENAI_API_KEY"] = openai
        set_key(str(ENV_PATH), "OPENAI_API_KEY", openai)
    return {"saved": True}


@app.get("/api/keys/status")
async def keys_status():
    return {
        "bfl": bool(os.getenv("BFL_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
    }


# ---------------------------------------------------------------------------
# API: pipeline run (SSE)
# ---------------------------------------------------------------------------

@app.post("/api/run")
async def run_pipeline_sse(request: Request):
    body = await request.json()
    brief = body.get("brief")
    provider = body.get("provider", "flux")
    nl_parse_used = body.get("nl_parse_used", False)

    if not brief:
        return JSONResponse({"error": "brief required"}, status_code=400)

    os.environ["IMAGE_PROVIDER"] = provider
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # Track per-run state shared between callback and generator
    run_state = {"current_product": None}

    def callback(stage, message):
        event = json.dumps({"type": "progress", "stage": stage, "message": message})
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    def run_thread():
        try:
            result = run_pipeline(
                brief,
                progress_callback=callback,
                nl_parse_used=nl_parse_used,
            )
            # Normalize Path objects before JSON serialization
            outputs = {
                k: [str(p) for p in v]
                for k, v in (result.get("outputs_by_product") or {}).items()
            }
            rp = result.get("report_path")
            result["outputs_by_product"] = outputs
            result["report_path"] = str(rp) if rp else None
            # Normalize compliance paths
            compliance = {}
            for pid, pc in (result.get("compliance_by_product") or {}).items():
                compliance[pid] = {str(k): v for k, v in pc.items()}
            result["compliance_by_product"] = compliance
            # Persist to SQLite (outputs_by_product as Path objects still in original result)
            try:
                from db import save_campaign as db_save
                original_outputs = result.get("outputs_by_product", {})
                db_save(brief, result.get("run_summary", {}), {
                    k: [Path(p) for p in v] for k, v in original_outputs.items()
                })
            except Exception:
                pass
            event = json.dumps({"type": "complete", "result": result})
        except Exception as exc:
            event = json.dumps({"type": "error", "message": str(exc)})
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    # Emit pipeline_plan as the very first SSE event
    product_ids = [p.get("id", "unknown") for p in (brief.get("products") or [])]
    plan_event = json.dumps({"type": "pipeline_plan", "products": product_ids})

    thread = threading.Thread(target=run_thread, daemon=True)
    thread.start()

    async def generate():
        yield "data: {}\n\n".format(plan_event)
        seen_images_ready = set()

        while True:
            event_str = await queue.get()
            if event_str is None:
                break

            parsed = json.loads(event_str)
            stage = parsed.get("stage", "")
            message = parsed.get("message", "")

            if parsed.get("type") == "progress":
                # Track current product for associating PROMPT events
                if stage == "PRODUCT":
                    run_state["current_product"] = message.replace("Processing: ", "").strip()

                # Convert PROMPT stage to a typed prompt event (don't yield as progress)
                elif stage == "PROMPT":
                    prompt_event = json.dumps({
                        "type": "prompt",
                        "product_id": run_state["current_product"],
                        "prompt": message,
                    })
                    yield "data: {}\n\n".format(prompt_event)
                    continue

                # First COMPLIANCE per product signals images are saved -> images_ready
                elif stage == "COMPLIANCE" and message.startswith("Checking brand compliance for "):
                    pid = message[len("Checking brand compliance for "):].strip()
                    yield "data: {}\n\n".format(event_str)
                    if pid not in seen_images_ready:
                        seen_images_ready.add(pid)
                        ready_event = json.dumps({"type": "images_ready", "product_id": pid})
                        yield "data: {}\n\n".format(ready_event)
                    continue

            yield "data: {}\n\n".format(event_str)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)
