from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

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
