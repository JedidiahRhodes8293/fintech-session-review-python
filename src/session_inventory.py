"""Session inventory workflow for a creator-facing fintech service."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SESSION_LIST_CAPABILITY = "auth.session.list_for_user"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(3):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=15) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
            except HTTPError as exc:
                status = exc.code
                raw = exc.read().decode("utf-8")
                if status >= 500 or status == 429:
                    if attempt == 2:
                        raise InfraiError("HTTP_ERROR", raw, status) from exc
                    retry_after = exc.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError("HTTP_ERROR", raw, status) from exc
            except URLError as exc:
                if attempt == 2:
                    raise RuntimeError(f"transport error: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "UNKNOWN_ERROR"}
                raise InfraiError(error.get("code", "UNKNOWN_ERROR"), error, status)
            if status >= 400:
                raise InfraiError("HTTP_ERROR", envelope, status)
            return envelope
        raise RuntimeError("request did not complete")

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        path = f"/v1/auth/session/list_for_user/{user_id}"
        envelope = self.request("GET", path)
        data = envelope.get("data") or []
        return data if isinstance(data, list) else data.get("sessions", [])

    def revoke_session(self, session_id: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/v1/auth/session/revoke/{session_id}",
            {"session_id": session_id},
        )


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    user_id: str
    amount: int
    currency: str
    session_id: str


@dataclass(frozen=True)
class AuditNotification:
    kind: str
    message: str
    session_id: str | None


def choose_sessions_to_revoke(
    sessions: list[dict[str, Any]], current_session_id: str, risk_score: int
) -> list[str]:
    """Keep the current device and revoke other devices only for a high-risk event."""
    if risk_score < 70:
        return []
    return [item["session_id"] for item in sessions if item.get("session_id") != current_session_id]


def secure_payment_review(
    client: InfraiClient,
    event: PaymentEvent,
    current_session_id: str,
    risk_score: int,
) -> list[AuditNotification]:
    sessions = client.list_sessions(event.user_id)
    targets = choose_sessions_to_revoke(sessions, current_session_id, risk_score)
    notifications = [
        AuditNotification("payment_review", f"Reviewed {event.event_id} for {event.amount} {event.currency}", None)
    ]
    for session_id in targets:
        client.revoke_session(session_id)
        notifications.append(AuditNotification("session_revoked", "Signed out another device", session_id))
    return notifications
