from __future__ import annotations

import json

from anthropic import Anthropic


MODEL = "claude-haiku-4-5-20251001"
SYSTEM_PROMPT = """You are a job relevance scorer for an AI/ML engineer based in Munich, Germany.
Score each job from 1 to 10 based on how relevant it is for someone with expertise in
LLMs, RAG systems, and AI agents. Return ONLY a JSON object with two fields:
score (integer 1-10) and reason (one sentence explanation).
Do not include any other text or markdown."""


def score_job(
    title: str,
    company: str,
    location: str,
    description: str,
) -> tuple[int, str] | None:
    try:
        client = Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _format_job(title, company, location, description),
                }
            ],
        )
        content = response.content[0].text
        payload = json.loads(content)
        score = int(payload["score"])
        reason = str(payload["reason"]).strip()

        if not 1 <= score <= 10 or not reason:
            raise ValueError("Invalid score response")

        return score, reason
    except Exception:
        # Leave the job unscored so the next scoring run retries it.
        return None


def _format_job(
    title: str,
    company: str,
    location: str,
    description: str,
) -> str:
    return (
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {location}\n"
        f"Description:\n{description}"
    )
