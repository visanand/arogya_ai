"""FastAPI route handlers for AarogyaAI."""

import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, status

from chat_engine import generate_response, PAYMENT_PLACEHOLDER
from db import (
    save_user,
    save_chat,
    save_summary,
    get_user_by_phone,
    record_payment,
    mark_payment_paid,
)
from schemas import (
    Consent,
    UserInfo,
    SymptomData,
    Summary,
    StartPayload,
    ConsultRequest,
    WebChatPayload,
)
from utils import timestamp, detect_language
from razorpay_utils import (
    create_payment_link,
    verify_signature,
    is_payment_complete,
)
from session_store import get_session, save_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start")
async def start_chat(payload: StartPayload):
    logger.info("Starting chat for %s", payload.user.phone or payload.user.name)
    if not payload.consent.accepted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consent required")
    user_dict = payload.user.dict()
    user_dict["consent_time"] = payload.consent.timestamp
    await save_user(user_dict)
    return {"message": f"Welcome {payload.user.name}! How can I help you today?"}


@router.post("/triage")
async def triage(symptom: SymptomData):
    logger.debug("Triage request: %s", symptom.description)
    messages = [{"role": "user", "content": symptom.description}]
    reply = await generate_response(messages)
    await save_chat({"input": symptom.description, "output": reply, "time": timestamp()})
    return {"reply": reply}


@router.post("/consult")
async def consult(payload: ConsultRequest, consult_type: str = "audio"):
    logger.info("Consult requested type=%s", consult_type)
    amount = 99 if consult_type == "audio" else 249
    link = await create_payment_link(amount, f"AarogyaAI {consult_type} consult", payload.user.phone)
    await save_chat({
        "user": payload.user.dict(),
        "symptoms": payload.symptoms.dict(),
        "consult_type": consult_type,
        "requested_at": timestamp(),
        "payment_link": link["url"],
    })
    await record_payment(
        payload.user.phone,
        {
            "amount": amount,
            "link": link["url"],
            "link_id": link["id"],
            "status": "pending",
            "time": timestamp(),
        },
    )
    return {"payment_link": link["url"]}


@router.post("/chat")
async def web_chat(payload: WebChatPayload):
    """Handle a single web chat message and return the assistant's reply."""
    session_id = payload.session_id
    message = payload.message
    phone = payload.phone

    language = detect_language(message)

    session = await get_session(session_id)

    # Inject returning user context if phone is known and session is fresh
    if not session and phone:
        user = await get_user_by_phone(phone)
        if user:
            meta = (
                f"Returning user details: name={user.get('name')}, "
                f"age={user.get('age')}, gender={user.get('gender')}, "
                f"pin={user.get('pin')}"
            )
            session.append({"role": "system", "content": meta})

    session.append({"role": "user", "content": message})

    try:
        reply = await asyncio.wait_for(generate_response(session, language), timeout=12)

        payment_url = None
        if PAYMENT_PLACEHOLDER in reply:
            contact = phone or "unknown"
            link = await create_payment_link(99, "AarogyaAI consult", contact)
            payment_url = link["url"]
            reply = reply.replace(PAYMENT_PLACEHOLDER, link["url"])
            if phone:
                await record_payment(
                    phone,
                    {
                        "amount": 99,
                        "link": link["url"],
                        "link_id": link["id"],
                        "status": "pending",
                        "time": timestamp(),
                    },
                )

    except asyncio.TimeoutError:
        reply = "Sorry, the system is currently slow. Please try again in a few minutes."
        payment_url = None
    except Exception as e:
        logger.exception("Error generating reply: %s", e)
        reply = "Sorry, something went wrong. Please try again."
        payment_url = None

    session.append({"role": "assistant", "content": reply})
    await save_session(session_id, session)
    await save_chat({"session_id": session_id, "input": message, "output": reply, "time": timestamp()})

    return {"reply": reply, "payment_url": payment_url}


@router.post("/summary")
async def store_summary(summary: Summary):
    logger.info("Storing summary for %s", summary.user_phone)
    await save_summary(summary.dict())
    return {"status": "saved"}


@router.post("/payment-webhook")
async def payment_webhook(request: Request):
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")

    body = await request.body()

    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")
    entity = payload.get("payload", {}).get("payment", {}).get("entity")

    if not event or not entity:
        raise HTTPException(status_code=400, detail="Invalid Razorpay payload")

    await save_chat({
        "event": event,
        "entity": entity,
        "raw_payload": payload,
        "time": timestamp(),
    })

    contact = entity.get("contact")
    if contact:
        await record_payment(
            contact,
            {
                "payment_id": entity.get("id"),
                "amount": entity.get("amount", 0) / 100,
                "status": entity.get("status"),
                "time": timestamp(),
            },
        )

    return {"status": "ok"}
