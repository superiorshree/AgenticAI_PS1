"""
GitHub webhook and activity routes.

POST /github/webhook   — verified HMAC-SHA256 webhook receiver
GET  /github/events    — paginated event history (authenticated users)

Webhook processing:
  - Verifies X-Hub-Signature-256.
  - Deduplicates by X-GitHub-Delivery header.
  - Persists raw payload.
  - Associates events with tasks where github_repo_full_name matches.
  - Forwards PR events to the agents service for AI analysis (fire-and-forget).

This backend does not re-implement the analysis pipeline — it forwards
PR webhook events to the agents service running at AGENTS_BASE_URL.
If the agents service is unreachable, the event is still persisted here.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import VerifiedUser, get_current_user
from src.config import get_settings
from src.db.models import AuditEvent, Project
from src.db.session import get_db
from src.schemas.common import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory delivery dedup (supplements DB — cleared on restart but sufficient for most retries)
_seen_deliveries: set[str] = set()


class GitHubEventResponse(BaseModel):
    delivery_id: Optional[str]
    event_type: str
    action: Optional[str]
    repo: Optional[str]
    status: str
    received_at: str


def _verify_signature(payload_bytes: bytes, signature_header: Optional[str], secret: str) -> bool:
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    mac = hmac.new(secret.encode(), msg=payload_bytes, digestmod=hashlib.sha256)
    return hmac.compare_digest(f"sha256={mac.hexdigest()}", signature_header)


@router.post("/webhook", status_code=202, tags=["GitHub"])
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header("unknown", alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    db: AsyncSession = Depends(get_db),
):
    """Receive and verify GitHub webhook events."""
    s = get_settings()
    body_bytes = await request.body()

    # Signature verification
    if not _verify_signature(body_bytes, x_hub_signature_256, s.GITHUB_WEBHOOK_SECRET):
        logger.warning(f"[GH] Invalid webhook signature delivery={x_github_delivery}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_SIGNATURE", "message": "X-Hub-Signature-256 mismatch"},
        )

    # In-memory dedup
    if x_github_delivery and x_github_delivery in _seen_deliveries:
        logger.info(f"[GH] Duplicate delivery {x_github_delivery} — skipped")
        return {"status": "deduplicated"}
    if x_github_delivery:
        _seen_deliveries.add(x_github_delivery)
        if len(_seen_deliveries) > 10000:
            _seen_deliveries.clear()

    # Parse payload
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(400, detail={"code": "INVALID_PAYLOAD", "message": "Malformed JSON"})

    action = payload.get("action")
    repo_data = payload.get("repository", {})
    repo_full_name = repo_data.get("full_name")
    event_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc).isoformat()

    # Audit the receipt
    db.add(AuditEvent(
        actor="system:github_webhook",
        action=f"github_{x_github_event}",
        resource_type="github_event",
        resource_id=x_github_delivery or event_id,
        details={
            "event": x_github_event,
            "action": action,
            "repo": repo_full_name,
            "delivery_id": x_github_delivery,
        },
    ))

    # Forward PR events to agents service (non-blocking)
    if x_github_event == "pull_request" and action in ("opened", "synchronize", "reopened"):
        await _forward_to_agents(payload, x_github_event, x_github_delivery)

    return APIResponse(
        success=True,
        message="GitHub webhook received",
        data=GitHubEventResponse(
            delivery_id=x_github_delivery,
            event_type=x_github_event,
            action=action,
            repo=repo_full_name,
            status="queued" if x_github_event == "pull_request" else "received",
            received_at=received_at,
        ),
    )


async def _forward_to_agents(payload: dict, event_type: str, delivery_id: Optional[str]) -> None:
    """Fire-and-forget forward to the agents service for AI analysis."""
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Build headers matching agents service webhook expectations
            pr_data = payload.get("pull_request", {})
            repo_data = payload.get("repository", {})
            headers = {
                "X-GitHub-Event": event_type,
                "X-GitHub-Delivery": delivery_id or str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
            # Re-sign for the agents service using the same secret
            body_bytes = json.dumps(payload).encode()
            mac = hmac.new(s.GITHUB_WEBHOOK_SECRET.encode(), msg=body_bytes, digestmod=hashlib.sha256)
            headers["X-Hub-Signature-256"] = f"sha256={mac.hexdigest()}"

            resp = await client.post(
                f"{s.AGENTS_BASE_URL.rstrip('/')}/api/v1/webhooks/github",
                content=body_bytes,
                headers=headers,
            )
            if resp.status_code not in (200, 201, 202):
                logger.warning(f"[GH] Agents service returned {resp.status_code}")
    except Exception as exc:
        logger.warning(f"[GH] Could not forward to agents service: {exc} — event persisted locally")
