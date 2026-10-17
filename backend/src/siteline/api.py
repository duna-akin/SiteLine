"""HTTP API for the Siteline frontend, plus Photon and Twilio webhooks."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from siteline import approvals, events, export, inbound_email, photon, store, voice
from siteline.config import is_fictional_phone, settings
from siteline.demo import DEMO_FILE_NAME, ensure_demo
from siteline.extraction import SEED_CACHE
from siteline.playbook import SPONSOR, approvers, load_playbook, save_playbook, validate_playbook
from siteline.pipeline import Job, TriageOptions, triage

log = logging.getLogger("siteline.api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

_tasks: set[asyncio.Task] = set()
_eval_state: dict = {"running": False, "runId": None, "error": None}


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    ensure_demo()
    if not SEED_CACHE.exists():
        from siteline.demo_cache import write_seed

        write_seed()
    inbound_email.ensure_seed_attachments()
    approvals.rearm_timers()
    if settings.imap_enabled:
        _spawn(inbound_email.poll_forever())
    log.info("integrations: %s", integrations())
    yield
    approvals.cancel_all()
    for t in list(_tasks):
        t.cancel()


app = FastAPI(title="Siteline API", lifespan=lifespan)


def integrations() -> dict:
    real_phones = {k: not is_fictional_phone(v) for k, v in settings.approver_phones.items()}
    return {
        "claude": settings.claude_enabled,
        "claudeModel": settings.claude_model,
        "daytona": settings.daytona_enabled,
        "photon": settings.photon_enabled,
        "voice": settings.voice_enabled,
        "imap": settings.imap_enabled,
        "publicUrl": bool(settings.public_base_url),
        "approverPhonesReal": real_phones,
        "noReplySeconds": settings.no_reply_seconds,
    }


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "integrations": integrations(), "sponsor": SPONSOR, "inboundAddress": settings.inbound_address}


@app.get("/api/events")
async def stream_events() -> StreamingResponse:
    return StreamingResponse(events.stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- upload and triage ---------------------------------------------------------------


@app.get("/api/demo-file")
async def demo_file() -> Response:
    return Response(
        ensure_demo(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{DEMO_FILE_NAME}"'},
    )


async def _run_triage(job: Job, data: bytes, name: str, options: TriageOptions, source: str) -> None:
    try:
        await triage(data, name, options, source=source, job=job)
    except Exception as e:  # report every failure to the waiting browser
        log.exception("triage failed")
        events.publish("triage.failed", {"jobId": job.id, "error": str(e)})


@app.post("/api/agreements/upload")
async def upload(
    file: UploadFile | None = File(None),
    localParser: bool = Form(False),
    useCache: bool = Form(True),
) -> dict:
    if file is not None and file.filename:
        if not file.filename.lower().endswith(".docx"):
            raise HTTPException(400, "Upload a Word .docx file with tracked changes.")
        data = await file.read()
        name = file.filename
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(413, "File is larger than 20 MB.")
    else:
        data, name = ensure_demo(), DEMO_FILE_NAME
    job = Job("pending", name)
    _spawn(_run_triage(job, data, name, TriageOptions(local_parser=localParser, use_cache=useCache), "upload"))
    return {"jobId": job.id, "fileName": name, "sizeKb": max(1, len(data) // 1024)}


# ---- agreements and decisions -----------------------------------------------------------


@app.get("/api/agreements")
async def list_agreements() -> list[dict]:
    return store.list_agreements()


@app.get("/api/portfolio")
async def portfolio() -> list[dict]:
    return [a for a in store.list_agreements() if a["status"] != "executed"]


def _agreement_or_404(agreement_id: str) -> dict:
    a = store.get_agreement(agreement_id)
    if not a:
        raise HTTPException(404, "No such agreement")
    return a


@app.get("/api/agreements/{agreement_id}")
async def get_agreement(agreement_id: str) -> dict:
    a = _agreement_or_404(agreement_id)
    a.pop("log", None)
    return {"agreement": a, "decisions": store.get_decisions(agreement_id)}


@app.get("/api/agreements/{agreement_id}/decisions")
async def get_decisions(agreement_id: str) -> list[dict]:
    _agreement_or_404(agreement_id)
    return store.get_decisions(agreement_id)


class OverrideBody(BaseModel):
    outcome: Literal["accept", "fallback", "escalate", "human_review", "novel"]
    reason: str = Field(min_length=8, max_length=1000)


@app.post("/api/decisions/{change_id}/override")
async def override(change_id: str, body: OverrideBody) -> dict:
    hit = store.find_decision(change_id)
    if not hit:
        raise HTTPException(404, "No such change")
    agreement_id, d = hit
    if body.outcome == d["outcome"]:
        raise HTTPException(400, "Pick an outcome different from Siteline's.")
    d = store.update_decision(change_id, override={"outcome": body.outcome, "reason": body.reason.strip(), "at": store.now_ms()})
    if body.outcome == "escalate" and d["approval"]["state"] == "none":
        d = await approvals.send_text(change_id)
    events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
    events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})
    return d


@app.delete("/api/decisions/{change_id}/override")
async def clear_override(change_id: str) -> dict:
    hit = store.find_decision(change_id)
    if not hit:
        raise HTTPException(404, "No such change")
    agreement_id, _ = hit
    d = store.update_decision(change_id, override=None)
    events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
    events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})
    return d


# ---- approvals ------------------------------------------------------------------------


@app.get("/api/approvers")
async def get_approvers() -> dict:
    return approvers()


@app.post("/api/approvals/{change_id}/text")
async def approval_text(change_id: str) -> dict:
    try:
        return await approvals.send_text(change_id)
    except KeyError:
        raise HTTPException(404, "No such change") from None


class ReplyBody(BaseModel):
    reply: Literal[1, 2, 3]
    channel: Literal["imessage", "voice"] = "imessage"


@app.post("/api/approvals/{change_id}/reply")
async def approval_reply(change_id: str, body: ReplyBody) -> dict:
    try:
        return await approvals.record_reply(change_id, body.reply, body.channel)
    except KeyError:
        raise HTTPException(404, "No such change") from None


@app.post("/api/approvals/{change_id}/call")
async def approval_call(change_id: str) -> dict:
    try:
        return await approvals.place_call(change_id)
    except KeyError:
        raise HTTPException(404, "No such change") from None


@app.post("/api/webhooks/photon")
async def photon_webhook(request: Request) -> Response:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not photon.verify_webhook(body, headers):
        raise HTTPException(401, "Bad signature")
    event = json.loads(body)
    inbound = photon.parse_inbound(event)
    if inbound:
        await approvals.handle_inbound_text(inbound["handle"], inbound["spaceId"], inbound["text"])
    return Response(status_code=204)


@app.post("/api/webhooks/twilio/gather")
async def twilio_gather(request: Request, changeId: str) -> Response:
    form = dict(await request.form())
    params = {k: str(v) for k, v in form.items()}
    url = voice.gather_url(changeId)
    if not voice.verify_twilio(url, params, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(401, "Bad signature")
    message = await approvals.handle_call_digit(changeId, params.get("Digits", ""))
    return Response(voice.reply_twiml(message), media_type="application/xml")


# ---- export -----------------------------------------------------------------------------


@app.get("/api/agreements/{agreement_id}/export.docx")
async def export_docx(agreement_id: str) -> Response:
    try:
        data, meta = export.build_export(agreement_id)
    except KeyError:
        raise HTTPException(404, "Triage this agreement before exporting it") from None
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{meta["fileName"]}"',
            "X-Siteline-Export": json.dumps({k: v for k, v in meta.items() if k != "fileName"}),
        },
    )


# ---- playbook ---------------------------------------------------------------------------


@app.get("/api/playbook")
async def get_playbook() -> list[dict]:
    return load_playbook()


@app.put("/api/playbook")
async def put_playbook(rules: list[dict]) -> dict:
    errors = validate_playbook(rules)
    if errors:
        return JSONResponse({"errors": errors}, status_code=422)
    save_playbook(rules)
    return {"saved": len(rules), "at": store.now_ms()}


# ---- inbound email ------------------------------------------------------------------------


@app.get("/api/inbound-emails")
async def inbound_emails() -> dict:
    return {"address": settings.inbound_address, "imap": settings.imap_enabled, "emails": store.list_emails()}


@app.post("/api/inbound-emails/{email_id}/triage")
async def triage_email(email_id: str) -> dict:
    job_done = _spawn(inbound_email.triage_email(email_id))
    try:
        agreement = await job_done
    except KeyError:
        raise HTTPException(404, "No such email") from None
    return {"agreement": agreement}


@app.post("/api/inbound-emails/simulate")
async def simulate_email(
    file: UploadFile = File(...),
    sender: str = Form("contracts@site.example"),
    siteName: str = Form("Unknown site"),
    subject: str = Form("Our redline"),
) -> dict:
    """Stand-in for a real mailbox: record an email with this attachment and triage it."""
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "Attach a .docx")
    data = await file.read()
    meta = {"from": sender, "siteName": siteName, "subject": subject, "attachment": file.filename, "receivedAt": store.iso_now()}
    return await inbound_email.receive(meta, data)


# ---- evals --------------------------------------------------------------------------------


@app.get("/api/evals/latest")
async def eval_latest() -> dict:
    from siteline.evals.dataset import load_dataset
    from siteline.evals.harness import LATEST

    status = {k: v for k, v in _eval_state.items()}
    if LATEST.exists():
        return {"available": True, "result": json.loads(LATEST.read_text()), "status": status}
    data = load_dataset()
    return {
        "available": False,
        "status": status,
        "dataset": {
            "name": "cta-redlines-labeled-v1",
            "labeledChanges": len(data),
            "shouldEscalate": sum(1 for x in data if x["gold"] == "escalate"),
        },
    }


@app.post("/api/evals/run")
async def eval_run(limit: int = 0, sandboxes: int = 12) -> dict:
    from siteline.evals.harness import run_eval

    if _eval_state["running"]:
        raise HTTPException(409, "An eval is already running")
    if not settings.claude_enabled:
        raise HTTPException(400, "The eval needs Claude. Set ANTHROPIC_API_KEY in backend/.env.")
    _eval_state.update(running=True, error=None)

    async def go() -> None:
        try:
            result = await run_eval(limit=limit, sandboxes=sandboxes)
            _eval_state["runId"] = result["runId"]
        except Exception as e:
            log.exception("eval failed")
            _eval_state["error"] = str(e)
            events.publish("eval.failed", {"error": str(e)})
        finally:
            _eval_state["running"] = False

    _spawn(go())
    return {"started": True}


# ---- demo controls -----------------------------------------------------------------------


@app.post("/api/demo/reset")
async def demo_reset() -> dict:
    approvals.cancel_all()
    store.reset()
    inbound_email.ensure_seed_attachments()
    events.publish("demo.reset", {})
    return {"ok": True}
