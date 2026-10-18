"""HTTP API for the Siteline frontend, plus Photon and Twilio webhooks."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from siteline import approvals, events, export, inbound_email, photon, precedent, priority, storage, store, voice
from siteline.config import is_fictional_phone, settings
from siteline.demo import DEMO_FILE_NAME, ensure_demo
from siteline.extraction import SEED_CACHE
from siteline.playbook import (SPONSOR, approvers, default_playbook, load_playbook, playbook_log, render, reset_playbook,
                               record_moved, save_playbook, strip_rendered, validate_playbook)
from siteline.pipeline import Job, TriageOptions, replay_playbook, reprioritize_all, triage
from siteline.rules import RULE_ALIASES, bands

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
        "claudeModel": settings.extraction_model,
        "daytona": settings.daytona_enabled,
        "photon": settings.photon_enabled,
        "voice": settings.voice_enabled,
        "imap": settings.imap_enabled,
        "precedentStore": "postgres" if settings.database_url else "json",
        "documentStore": "s3" if settings.s3_enabled else "local",
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


@app.get("/api/agreements/{agreement_id}/document")
async def get_document(agreement_id: str) -> dict:
    """The whole redline as parsed: every paragraph, changed or not, so a change is read in context."""
    _agreement_or_404(agreement_id)
    doc = store.get_document(agreement_id)
    if not doc:
        raise HTTPException(404, "No document stored for this agreement")
    return {"paragraphs": doc["paragraphs"]}


class OverrideBody(BaseModel):
    outcome: Literal["accept", "counter", "escalate", "human_review"]
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
    approvals.sync_timer(change_id)  # no call about a change that is no longer an escalation
    events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
    events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})
    return d


class ConfirmBody(BaseModel):
    by: str = Field(default="Reviewer", min_length=1, max_length=80)


def _confirmation(body: ConfirmBody | None) -> dict:
    return {"by": (body.by if body else "Reviewer").strip() or "Reviewer", "at": store.now_ms()}


@app.post("/api/decisions/{change_id}/confirm")
async def confirm_decision(change_id: str, body: ConfirmBody | None = None) -> dict:
    """A person signs off on Siteline's suggestion (and any precedent shown with it)."""
    hit = store.find_decision(change_id)
    if not hit:
        raise HTTPException(404, "No such change")
    agreement_id, d = hit
    if store.is_waiting(d):
        raise HTTPException(409, "This change needs an approver's reply or your decision first.")
    d = store.update_decision(change_id, confirmation=_confirmation(body))
    events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
    events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})
    return d


@app.delete("/api/decisions/{change_id}/confirm")
async def unconfirm_decision(change_id: str) -> dict:
    hit = store.find_decision(change_id)
    if not hit:
        raise HTTPException(404, "No such change")
    agreement_id, _ = hit
    d = store.update_decision(change_id, confirmation=None)
    events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
    events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})
    return d


@app.post("/api/agreements/{agreement_id}/confirm-all")
async def confirm_all(agreement_id: str, body: ConfirmBody | None = None) -> dict:
    """Confirm every ready suggestion. Escalations and reviews still need their answer, and a
    suggestion that rests on a precedent needs its own confirm so someone reads the precedent."""
    _agreement_or_404(agreement_id)
    who = _confirmation(body)
    done, own = 0, 0
    for d in store.get_decisions(agreement_id):
        if store.is_waiting(d) or store.is_confirmed(d):
            continue
        if d.get("precedent"):
            own += 1
            continue
        d = store.update_decision(d["id"], confirmation=who)
        events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
        done += 1
    summary = store.get_agreement(agreement_id)
    events.publish("agreement.updated", {"agreement": summary})
    return {"confirmed": done, "needOwnConfirm": own, "agreement": summary}


@app.get("/api/escalations")
async def escalations() -> list[dict]:
    """Unanswered escalations across agreements, highest money at risk first."""
    return store.escalation_queue()


@app.delete("/api/decisions/{change_id}/override")
async def clear_override(change_id: str) -> dict:
    hit = store.find_decision(change_id)
    if not hit:
        raise HTTPException(404, "No such change")
    agreement_id, _ = hit
    d = store.update_decision(change_id, override=None)
    approvals.sync_timer(change_id)
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
    if store.seen_webhook(headers["webhook-id"]):
        return Response(status_code=204)  # a redelivery: the first one was already applied
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
    if n := store.unconfirmed(agreement_id):
        raise HTTPException(409, f"{n} suggestion(s) not yet confirmed by a person. Confirm them before exporting.")
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{meta["fileName"]}"',
            "X-Siteline-Export": json.dumps({k: v for k, v in meta.items() if k != "fileName"}),
        },
    )


@app.post("/api/agreements/{agreement_id}/complete")
async def complete_agreement(agreement_id: str) -> dict:
    """Confirm the agreement: keep the final document, save its accepted terms as precedent
    (the one write to the precedent store) and mark it executed."""
    try:
        data, meta = export.build_export(agreement_id)
    except KeyError:
        raise HTTPException(404, "Triage this agreement before confirming it") from None
    if meta["pending"]:
        raise HTTPException(409, f"{meta['pending']} item(s) still pending. Resolve them before confirming.")
    if n := store.unconfirmed(agreement_id):
        raise HTTPException(409, f"{n} suggestion(s) not yet confirmed by a person. Confirm them before completing.")
    file_name = re.sub(r"[^\w.-]", "_", meta["fileName"].replace("_counter-proposal", "_final"))
    if (rnd := store.state()["agreements"][agreement_id].get("round", 1)) > 1:
        file_name = file_name.removesuffix(".docx") + f"_r{rnd}.docx"  # never overwrite an earlier round's document
    key = f"{agreement_id}/{file_name}"
    try:
        storage.put(key, data)  # first, so no precedent ever cites a missing document
    except storage.StorageError as e:
        log.warning("final document upload failed: %s", e)
        raise HTTPException(502, "Could not store the final document. Nothing was saved; try again.") from None
    records = precedent.completed_records(agreement_id, key)
    try:
        store.post_completed(records)
    except store.PrecedentStoreError:
        raise HTTPException(503, "Could not save this agreement's precedents, so it was not marked executed. Try again.") from None
    a = store.state()["agreements"][agreement_id]
    store.put_agreement({**a, "status": "executed", "finalDocumentKey": key, "completedAt": store.iso_now()})
    summary = store.get_agreement(agreement_id)
    events.publish("agreement.updated", {"agreement": summary})
    return {"agreement": summary, "finalDocumentKey": key, "precedentsSaved": len(records)}


@app.get("/api/sources")
async def source_document(key: str) -> Response:
    """The final agreed document a precedent cites (its sourceKey)."""
    if not storage.valid_key(key):
        raise HTTPException(400, "Not a source document key")
    try:
        data = storage.get(key)
    except storage.StorageError as e:
        log.warning("source download failed: %s", e)
        raise HTTPException(502, "Could not fetch the source document") from None
    if data is None:
        raise HTTPException(404, "No such source document")
    return Response(data, media_type=storage.DOCX, headers={"Content-Disposition": f'attachment; filename="{key.rsplit("/", 1)[1]}"'})


# ---- playbook ---------------------------------------------------------------------------


def _playbook_settings() -> dict:
    return {"playbook": render(load_playbook()), "log": playbook_log(), "aliases": RULE_ALIASES}


class PlaybookBody(BaseModel):
    playbook: dict = Field(default_factory=dict)
    by: str = Field(default="Reviewer", min_length=1, max_length=80)


class PlaybookPreviewBody(BaseModel):
    playbook: dict | None = None
    # Preview a reset to the default playbook instead
    reset: bool = False


def _checked(raw: dict) -> tuple[dict, list[str]]:
    """The templates of a submitted playbook (rendered *Text keys dropped) and what is wrong with it."""
    pb = strip_rendered(raw)
    return pb, validate_playbook(pb)


async def _apply_playbook() -> list[dict]:
    """Re-decide open suggestions under the saved playbook, text the approver of each escalation this
    save created (and no other), and push the updates to the browser."""
    changes = replay_playbook(load_playbook())
    record_moved(len(changes))
    for c in changes:
        if c["to"]["outcome"] == "escalate" and c["from"]["outcome"] != "escalate":
            await approvals.send_text(c["changeId"])
    for agreement_id in {c["agreementId"] for c in changes}:
        events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})
    for c in changes:
        if hit := store.find_decision(c["changeId"]):
            events.publish("decision.updated", {"agreementId": hit[0], "decision": hit[1]})
    return changes


@app.get("/api/playbook")
async def get_playbook() -> dict:
    return _playbook_settings()


@app.post("/api/playbook/preview")
async def preview_playbook(body: PlaybookPreviewBody) -> dict:
    """What saving `playbook` (or resetting to the default) would change: open suggestions only, nothing is saved."""
    pb, errors = _checked(default_playbook() if body.reset else body.playbook or {})
    if errors:
        return JSONResponse({"errors": errors}, status_code=422)
    return {"changes": replay_playbook(pb, dry_run=True)}


@app.put("/api/playbook")
async def put_playbook(body: PlaybookBody) -> dict:
    pb, errors = _checked(body.playbook)
    if errors:
        return JSONResponse({"errors": errors}, status_code=422)
    save_playbook(pb, body.by.strip())
    return {**_playbook_settings(), "changes": await _apply_playbook()}


@app.delete("/api/playbook")
async def delete_playbook(by: str = "Reviewer") -> dict:
    """Back to the default playbook, re-deciding open suggestions under it."""
    reset_playbook(by.strip() or "Reviewer")
    return {**_playbook_settings(), "changes": await _apply_playbook()}


# ---- site priority ----------------------------------------------------------------------


def _priority_settings() -> dict:
    return {
        "config": priority.load_config(),
        "bands": [{"field": f, **b} for f, b in bands().items()],
        "maxShare": priority.MAX_SHARE,
        "weeksPerMonth": priority.WEEKS_PER_MONTH,
        "log": priority.config_log()[-20:][::-1],
    }


class PriorityConfigBody(BaseModel):
    config: dict
    by: str = Field(default="Reviewer", min_length=1, max_length=80)


@app.get("/api/priority-config")
async def get_priority_config() -> dict:
    return _priority_settings()


@app.post("/api/priority-config/preview")
async def preview_priority_config(body: PriorityConfigBody) -> dict:
    """What saving `config` would change: open suggestions only, nothing is saved."""
    errors = priority.validate_config(body.config)
    if errors:
        return JSONResponse({"errors": errors}, status_code=422)
    return {"changes": reprioritize_all(body.config, dry_run=True)}


@app.put("/api/priority-config")
async def put_priority_config(body: PriorityConfigBody) -> dict:
    errors = priority.validate_config(body.config)
    if errors:
        return JSONResponse({"errors": errors}, status_code=422)
    priority.save_config(body.config, body.by.strip())
    changes = reprioritize_all()
    for a in store.list_agreements():
        events.publish("agreement.updated", {"agreement": a})
    for c in changes:
        hit = store.find_decision(c["changeId"])
        if hit:
            events.publish("decision.updated", {"agreementId": hit[0], "decision": hit[1]})
    return {**_priority_settings(), "changes": changes}


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
    """Stand-in for a real mailbox: record an email with this attachment, untriaged, in the inbox."""
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
async def eval_run(limit: int = 0, sandboxes: int = 12, concurrency: int = 16) -> dict:
    from siteline.evals.harness import run_eval

    if _eval_state["running"]:
        raise HTTPException(409, "An eval is already running")
    if not settings.claude_enabled:
        raise HTTPException(400, "The eval needs a model. Set OPENAI_API_KEY in backend/.env.")
    _eval_state.update(running=True, error=None)

    async def go() -> None:
        try:
            result = await run_eval(limit=limit, sandboxes=sandboxes, concurrency=concurrency)
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
