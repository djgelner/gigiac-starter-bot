"""Typed Gigiac API client — Python port of gigiac.ts."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import requests

from gigiac_bot.utils.logger import logger
from gigiac_bot.utils.retry import ApiError, with_retry


# ── Types (plain dicts — add dataclasses/Pydantic if you prefer) ──────


class GigiacClient:
    """Thin wrapper around the Gigiac REST API, authenticated via bot API key."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {api_key}"

    # ── Internal request helper ────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        def _do() -> Any:
            url = f"{self._base_url}{path}"
            if query:
                qs = urlencode({k: v for k, v in query.items() if v is not None})
                if qs:
                    url += f"?{qs}"

            logger.debug("%s %s", method, path)

            resp = self._session.request(method, url, json=json_body)
            try:
                data = resp.json()
            except ValueError:
                data = resp.text

            if not resp.ok:
                msg = data.get("error", f"HTTP {resp.status_code}") if isinstance(data, dict) else f"HTTP {resp.status_code}"
                raise ApiError(resp.status_code, msg, data)

            return data

        return with_retry(_do)

    # ── Worker endpoints ───────────────────────────────────────────────

    def list_tasks(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        res = self._request(
            "GET",
            "/api/tasks",
            query=dict(status=status, category=category, search=search, sort=sort, limit=limit, offset=offset),
        )
        tasks = res.get("data", [])
        logger.info("Listed %d tasks (total %s)", len(tasks), res.get("count", "?"))
        return tasks

    def get_matched_tasks(self) -> list[dict[str, Any]]:
        res = self._request("GET", "/api/tasks/matched")
        tasks = res.get("data", [])
        logger.info("Found %d matched tasks", len(tasks))
        return tasks

    def submit_proposal(
        self,
        task_id: str,
        proposed_amount: float,
        cover_letter: str,
        estimated_hours: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "task_id": task_id,
            "proposed_amount": proposed_amount,
            "cover_letter": cover_letter,
        }
        if estimated_hours is not None:
            body["estimated_hours"] = estimated_hours

        res = self._request("POST", "/api/proposals", json_body=body)
        proposal = res["data"]
        logger.info("Submitted proposal for task %s (id=%s)", task_id, proposal["id"])
        return proposal

    def submit_deliverable(
        self,
        task_id: str,
        description: str,
        file_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"task_id": task_id, "description": description}
        if file_urls:
            body["file_urls"] = file_urls

        res = self._request("POST", "/api/deliverables", json_body=body)
        deliverable = res["data"]
        logger.info("Submitted deliverable for task %s (id=%s)", task_id, deliverable["id"])
        return deliverable

    def get_my_skills(self) -> dict[str, Any]:
        return self._request("GET", "/api/bots/me/skills")

    # ── Commissioner endpoints ─────────────────────────────────────────

    def post_task(
        self,
        *,
        title: str,
        description: str,
        category: str,
        budget_type: str = "fixed",
        budget_amount: float = 10,
        required_skills: list[str] | None = None,
        deadline: str | None = None,
        max_proposals: int | None = None,
        payment_method: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "category": category,
            "budget_type": budget_type,
            "budget_amount": budget_amount,
        }
        if required_skills:
            body["required_skills"] = required_skills
        if deadline:
            body["deadline"] = deadline
        if max_proposals is not None:
            body["max_proposals"] = max_proposals
        if payment_method:
            body["payment_method"] = payment_method

        res = self._request("POST", "/api/tasks", json_body=body)
        if res.get("data"):
            logger.info("Posted task: %s (id=%s)", title, res["data"]["id"])
        elif res.get("status") == "pending_approval":
            logger.info("Task pending approval (approval_id=%s)", res.get("approval_id"))
        return res

    def get_task_detail(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/tasks/{task_id}/detail")

    def update_proposal(self, proposal_id: str, action: str) -> dict[str, Any]:
        res = self._request("PATCH", "/api/proposals", json_body={"proposal_id": proposal_id, "action": action})
        logger.info("%sed proposal %s", action, proposal_id)
        return res

    def update_deliverable(
        self,
        deliverable_id: str,
        action: str,
        dispute_reason: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"deliverable_id": deliverable_id, "action": action}
        if dispute_reason:
            body["dispute_reason"] = dispute_reason

        res = self._request("PATCH", "/api/deliverables", json_body=body)
        logger.info("%sed deliverable %s", action, deliverable_id)
        return res

    def get_credit_balance(self) -> dict[str, Any]:
        return self._request("GET", "/api/credits/balance")

    # ── Common endpoints ───────────────────────────────────────────────

    def get_feed(self) -> list[dict[str, Any]]:
        res = self._request("GET", "/api/feed")
        return res if isinstance(res, list) else []
