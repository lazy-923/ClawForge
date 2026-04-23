from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from backend.config import settings
from backend.retrieval.text_matcher import extract_terms


@dataclass(frozen=True)
class DraftCandidate:
    name: str
    description: str
    goal: str
    constraints: list[str]
    workflow: list[str]
    why_extracted: str
    confidence: float


@dataclass(frozen=True)
class IntentTemplate:
    name: str
    description: str
    goal: str
    constraints: list[str]
    workflow: list[str]
    keywords: tuple[str, ...]
    reusable_terms: tuple[str, ...]


INTENT_TEMPLATES: dict[str, IntentTemplate] = {
    "rewrite": IntentTemplate(
        name="professional_rewrite",
        description="Rewrite text in a more professional and concise style.",
        goal="Rewrite the user's source text into a clearer and more professional form.",
        constraints=[
            "Preserve the original meaning.",
            "Avoid exaggerated wording.",
            "Prefer concise and work-ready phrasing.",
        ],
        workflow=[
            "Identify the target audience and output style.",
            "Keep key facts and constraints unchanged.",
            "Improve clarity, tone, and structure.",
        ],
        keywords=("rewrite", "polish", "professional", "email", "tone"),
        reusable_terms=("professional", "concise", "clear", "tone", "style", "formal"),
    ),
    "summary": IntentTemplate(
        name="structured_summary",
        description="Summarize source material into a short structured brief.",
        goal="Turn source material into a concise structured summary.",
        constraints=[
            "Keep the main points and action items.",
            "Avoid unnecessary detail.",
            "Use a predictable structure when possible.",
        ],
        workflow=[
            "Read the source and identify the main topics.",
            "Extract key points, decisions, or risks.",
            "Format the output as a short structured brief.",
        ],
        keywords=("summary", "summarize", "brief", "bullet", "bullets"),
        reusable_terms=("short", "brief", "bullet", "structured", "concise", "key"),
    ),
    "translate": IntentTemplate(
        name="faithful_translation",
        description="Translate text while preserving meaning and tone.",
        goal="Translate the source text accurately and naturally.",
        constraints=[
            "Keep the original intent intact.",
            "Avoid adding new information.",
            "Preserve the requested tone when possible.",
        ],
        workflow=[
            "Identify source and target language requirements.",
            "Translate key content accurately.",
            "Polish readability without changing meaning.",
        ],
        keywords=("translate", "translation", "english", "chinese", "bilingual"),
        reusable_terms=("accurate", "natural", "tone", "faithful", "preserve"),
    ),
    "weather": IntentTemplate(
        name="weather_lookup_refinement",
        description="Fetch and present weather information in a short helpful format.",
        goal="Retrieve weather information and summarize it clearly for the user.",
        constraints=[
            "Keep the response short and practical.",
            "Include the requested city or location.",
            "Highlight the most useful weather signal first.",
        ],
        workflow=[
            "Resolve the requested city or location.",
            "Retrieve the latest weather data.",
            "Summarize the result in a short helpful format.",
        ],
        keywords=("weather", "forecast", "temperature", "rain", "city"),
        reusable_terms=("short", "brief", "city", "forecast", "clear"),
    ),
}


def extract_draft_candidate(
    recent_messages: list[dict[str, object]],
    *,
    latest_user_message: str,
    latest_assistant_message: str,
    identity_context: dict[str, object] | None = None,
) -> DraftCandidate | None:
    recent_user_messages = [
        str(item.get("content", "")).strip()
        for item in recent_messages
        if str(item.get("role", "")) == "user" and str(item.get("content", "")).strip()
    ]
    if not recent_user_messages:
        return None

    intent_signals = _collect_intent_signals(recent_user_messages)
    latest_intents = intent_signals[-1] if intent_signals else set()
    if not latest_intents:
        if _has_explicit_skill_signal(recent_user_messages, identity_context):
            return _try_llm_draft_candidate(
                recent_messages=recent_messages,
                latest_user_message=latest_user_message,
                latest_assistant_message=latest_assistant_message,
                identity_context=identity_context,
                dominant_intent=None,
                reusable_terms=[],
                repeated_intent=False,
                has_identity_match=bool(identity_context),
            )
        return None

    intent_counts = Counter(intent for intents in intent_signals for intent in intents)
    latest_terms = set(extract_terms(latest_user_message))
    dominant_intent = _choose_dominant_intent(
        latest_intents=latest_intents,
        intent_counts=intent_counts,
        identity_context=identity_context,
    )
    if dominant_intent is None:
        return None

    template = INTENT_TEMPLATES[dominant_intent]
    reusable_terms = sorted(latest_terms & set(template.reusable_terms))
    repeated_intent = intent_counts[dominant_intent] >= 2
    has_identity_match = _identity_matches_template(identity_context, template)
    if not repeated_intent and not (has_identity_match and reusable_terms):
        return None

    llm_candidate = _try_llm_draft_candidate(
        recent_messages=recent_messages,
        latest_user_message=latest_user_message,
        latest_assistant_message=latest_assistant_message,
        identity_context=identity_context,
        dominant_intent=dominant_intent,
        reusable_terms=reusable_terms,
        repeated_intent=repeated_intent,
        has_identity_match=has_identity_match,
    )
    if llm_candidate is not None:
        return llm_candidate

    evidence_messages = _select_evidence_messages(recent_user_messages, dominant_intent)
    why_extracted = _build_why_extracted(
        dominant_intent=dominant_intent,
        evidence_messages=evidence_messages,
        reusable_terms=reusable_terms,
        has_identity_match=has_identity_match,
    )
    confidence = _estimate_confidence(
        repeated_intent=repeated_intent,
        reusable_terms=reusable_terms,
        evidence_count=len(evidence_messages),
        has_identity_match=has_identity_match,
    )

    constraints = list(template.constraints)
    workflow = list(template.workflow)
    if latest_assistant_message and "bullet" in latest_terms and dominant_intent == "summary":
        constraints.append("Prefer bullet points when the user asks for them repeatedly.")
    if has_identity_match:
        identity_name = str(identity_context.get("name", "")).strip()
        constraints.append(f"Stay aligned with the established skill identity `{identity_name}`.")

    return DraftCandidate(
        name=template.name,
        description=template.description,
        goal=template.goal,
        constraints=_dedupe_preserve_order(constraints),
        workflow=_dedupe_preserve_order(workflow),
        why_extracted=why_extracted,
        confidence=confidence,
    )


def _try_llm_draft_candidate(
    *,
    recent_messages: list[dict[str, object]],
    latest_user_message: str,
    latest_assistant_message: str,
    identity_context: dict[str, object] | None,
    dominant_intent: str | None,
    reusable_terms: list[str],
    repeated_intent: bool,
    has_identity_match: bool,
) -> DraftCandidate | None:
    if not settings.llm_is_configured:
        return None

    template = INTENT_TEMPLATES[dominant_intent] if dominant_intent else None
    payload = {
        "latest_user_message": latest_user_message,
        "latest_assistant_message": latest_assistant_message,
        "recent_messages": _serialize_messages(recent_messages[-8:]),
        "identity_context": identity_context,
        "durability_signals": {
            "dominant_intent": dominant_intent,
            "repeated_intent": repeated_intent,
            "has_identity_match": has_identity_match,
            "reusable_terms": reusable_terms,
        },
        "fallback_template": _template_payload(template),
    }
    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
            streaming=False,
        )
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You extract reusable long-lived agent skills from recent turns. "
                        "Be conservative: return should_create=false for one-off tasks, "
                        "temporary preferences, or facts better suited for memory. "
                        "Return JSON only with shape: "
                        "{\"should_create\":true,\"name\":\"...\",\"description\":\"...\","
                        "\"goal\":\"...\",\"constraints\":[\"...\"],\"workflow\":[\"...\"],"
                        "\"why_extracted\":\"...\",\"confidence\":0.0}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ]
        )
        data = _parse_json_response(getattr(response, "content", ""))
        return _normalize_llm_candidate(data)
    except (APIConnectionError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _normalize_llm_candidate(data: dict[str, Any]) -> DraftCandidate | None:
    if not bool(data.get("should_create", False)):
        return None
    name = _clean_skill_name(data.get("name", ""))
    description = _clean_text(data.get("description", ""), limit=240)
    goal = _clean_text(data.get("goal", ""), limit=500)
    constraints = _coerce_string_list(data.get("constraints"), limit=8, item_limit=220)
    workflow = _coerce_string_list(data.get("workflow"), limit=8, item_limit=220)
    why_extracted = _clean_text(data.get("why_extracted", ""), limit=500)
    confidence = _coerce_confidence(data.get("confidence"))

    if not name or not description or not goal or not workflow:
        return None
    if confidence < 0.58:
        return None

    return DraftCandidate(
        name=name,
        description=description,
        goal=goal,
        constraints=_dedupe_preserve_order(constraints),
        workflow=_dedupe_preserve_order(workflow),
        why_extracted=why_extracted or "LLM identified a durable reusable skill pattern.",
        confidence=confidence,
    )


def _template_payload(template: IntentTemplate | None) -> dict[str, object] | None:
    if template is None:
        return None
    return {
        "name": template.name,
        "description": template.description,
        "goal": template.goal,
        "constraints": template.constraints,
        "workflow": template.workflow,
    }


def _collect_intent_signals(user_messages: list[str]) -> list[set[str]]:
    signals: list[set[str]] = []
    for message in user_messages:
        terms = set(extract_terms(message))
        intents = {
            intent
            for intent, template in INTENT_TEMPLATES.items()
            if terms & set(template.keywords)
        }
        signals.append(intents)
    return signals


def _choose_dominant_intent(
    *,
    latest_intents: set[str],
    intent_counts: Counter[str],
    identity_context: dict[str, object] | None,
) -> str | None:
    identity_name = str((identity_context or {}).get("name", "")).strip().lower()
    for intent in latest_intents:
        template = INTENT_TEMPLATES[intent]
        if template.name.lower() == identity_name:
            return intent

    ranked = sorted(
        latest_intents,
        key=lambda intent: (intent_counts[intent], intent),
        reverse=True,
    )
    return ranked[0] if ranked else None


def _identity_matches_template(
    identity_context: dict[str, object] | None,
    template: IntentTemplate,
) -> bool:
    if not identity_context:
        return False
    return str(identity_context.get("name", "")).strip().lower() == template.name.lower()


def _has_explicit_skill_signal(
    user_messages: list[str],
    identity_context: dict[str, object] | None,
) -> bool:
    if identity_context:
        return True
    joined = "\n".join(user_messages[-3:]).casefold()
    durable_markers = (
        "always",
        "whenever",
        "for future",
        "from now on",
        "next time",
        "remember this workflow",
        "turn this into a skill",
        "create a skill",
        "reuse this workflow",
    )
    return any(marker in joined for marker in durable_markers)


def _select_evidence_messages(user_messages: list[str], dominant_intent: str) -> list[str]:
    template = INTENT_TEMPLATES[dominant_intent]
    keywords = set(template.keywords)
    evidence = [
        message
        for message in user_messages
        if set(extract_terms(message)) & keywords
    ]
    return evidence[-3:]


def _build_why_extracted(
    *,
    dominant_intent: str,
    evidence_messages: list[str],
    reusable_terms: list[str],
    has_identity_match: bool,
) -> str:
    template = INTENT_TEMPLATES[dominant_intent]
    evidence_count = len(evidence_messages)
    reasons = [f"Recent user turns repeatedly point to the reusable workflow `{template.name}`."]
    if evidence_count == 1:
        reasons = [f"The latest turn aligns with the reusable workflow `{template.name}`."]
    if reusable_terms:
        reasons.append(
            "Stable preference signals were detected: "
            + ", ".join(reusable_terms[:4])
            + "."
        )
    if has_identity_match:
        reasons.append("The latest gateway top-1 hit reinforces the same skill identity.")
    return " ".join(reasons)


def _estimate_confidence(
    *,
    repeated_intent: bool,
    reusable_terms: list[str],
    evidence_count: int,
    has_identity_match: bool,
) -> float:
    confidence = 0.48
    if repeated_intent:
        confidence += 0.18
    if evidence_count >= 2:
        confidence += 0.1
    confidence += min(0.12, len(reusable_terms) * 0.04)
    if has_identity_match:
        confidence += 0.08
    return round(min(confidence, 0.95), 2)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _serialize_messages(messages: list[dict[str, object]]) -> list[dict[str, str]]:
    serialized: list[dict[str, str]] = []
    for message in messages:
        content = _clean_text(message.get("content", ""), limit=600)
        if not content:
            continue
        serialized.append(
            {
                "role": _clean_text(message.get("role", "message"), limit=40) or "message",
                "content": content,
            }
        )
    return serialized


def _parse_json_response(raw_content: object) -> dict[str, Any]:
    text = str(raw_content or "").strip()
    if not text:
        raise ValueError("Empty LLM draft response")
    if text.startswith("{"):
        data = json.loads(text)
    else:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM draft response did not contain JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM draft response must be an object")
    return data


def _clean_text(value: object, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).strip()
    if limit is not None:
        return text[:limit]
    return text


def _clean_skill_name(value: object) -> str:
    raw = _clean_text(value, limit=80).lower()
    normalized = re.sub(r"[^a-z0-9_ -]", "", raw)
    normalized = re.sub(r"[\s-]+", "_", normalized).strip("_")
    return normalized[:64]


def _coerce_string_list(value: object, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        clean = _clean_text(item, limit=item_limit)
        if clean:
            items.append(clean)
        if len(items) >= limit:
            break
    return items


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return round(confidence, 2)
