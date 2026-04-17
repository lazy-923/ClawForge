from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DraftCandidate:
    name: str
    description: str
    goal: str
    constraints: list[str]
    workflow: list[str]
    why_extracted: str
    confidence: float


KEYWORD_DRAFTS = {
    "rewrite": DraftCandidate(
        name="professional_rewrite",
        description="Rewrite text in a more professional and concise style.",
        goal="Rewrite the user's source text into a clearer and more professional form.",
        constraints=["Preserve the original meaning.", "Avoid exaggerated wording."],
        workflow=["Identify the target audience.", "Keep key facts.", "Improve clarity and tone."],
        why_extracted="The interaction indicates a reusable rewriting preference.",
        confidence=0.79,
    ),
    "summary": DraftCandidate(
        name="structured_summary",
        description="Summarize source material into a short structured brief.",
        goal="Turn source material into a concise structured summary.",
        constraints=["Keep the main points.", "Avoid unnecessary detail."],
        workflow=["Read the source.", "Extract key points.", "Format the summary."],
        why_extracted="The interaction indicates a reusable summarization workflow.",
        confidence=0.75,
    ),
    "summarize": DraftCandidate(
        name="structured_summary",
        description="Summarize source material into a short structured brief.",
        goal="Turn source material into a concise structured summary.",
        constraints=["Keep the main points.", "Avoid unnecessary detail."],
        workflow=["Read the source.", "Extract key points.", "Format the summary."],
        why_extracted="The interaction indicates a reusable summarization workflow.",
        confidence=0.75,
    ),
    "translate": DraftCandidate(
        name="faithful_translation",
        description="Translate text while preserving meaning and tone.",
        goal="Translate the source text accurately and naturally.",
        constraints=["Keep the intent intact.", "Avoid adding new information."],
        workflow=["Identify source language.", "Translate key content.", "Polish readability."],
        why_extracted="The interaction indicates a reusable translation preference.",
        confidence=0.77,
    ),
    "weather": DraftCandidate(
        name="weather_lookup_refinement",
        description="Fetch and present weather information in a short helpful format.",
        goal="Retrieve weather information and summarize it clearly for the user.",
        constraints=["Keep the response short.", "Include the target city."],
        workflow=["Resolve city name.", "Fetch weather data.", "Summarize the result."],
        why_extracted="The interaction indicates a repeatable weather lookup workflow.",
        confidence=0.71,
    ),
}


def extract_draft_candidate(user_message: str) -> DraftCandidate | None:
    lowered = user_message.lower()
    for keyword, candidate in KEYWORD_DRAFTS.items():
        if keyword in lowered:
            return candidate
    return None

