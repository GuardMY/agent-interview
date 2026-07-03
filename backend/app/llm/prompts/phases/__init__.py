"""Phase-specific interview prompt templates.

Usage:
    from app.llm.prompts.phases import get_phase_prompt
    prompt = get_phase_prompt("ice_break", "en", position_summary="...", ...)
"""

from .ice_break import ICE_BREAK_EN, ICE_BREAK_ZH
from .project_deep_dive import PROJECT_DEEP_DIVE_EN, PROJECT_DEEP_DIVE_ZH
from .technical_assessment import TECHNICAL_ASSESSMENT_EN, TECHNICAL_ASSESSMENT_ZH
from .behavioral import BEHAVIORAL_EN, BEHAVIORAL_ZH
from .candidate_qa import CANDIDATE_QA_EN, CANDIDATE_QA_ZH
from .wrapup import WRAPUP_EN, WRAPUP_ZH
from .follow_up import FOLLOW_UP_DECISION_EN, FOLLOW_UP_DECISION_ZH, FOLLOW_UP_GENERATE_EN, FOLLOW_UP_GENERATE_ZH

__all__ = [
    "get_phase_prompt",
    "get_follow_up_prompt",
]

_PROMPT_REGISTRY = {
    "ice_break": {"en": ICE_BREAK_EN, "zh": ICE_BREAK_ZH},
    "project_deep_dive": {"en": PROJECT_DEEP_DIVE_EN, "zh": PROJECT_DEEP_DIVE_ZH},
    "technical_assessment": {"en": TECHNICAL_ASSESSMENT_EN, "zh": TECHNICAL_ASSESSMENT_ZH},
    "behavioral": {"en": BEHAVIORAL_EN, "zh": BEHAVIORAL_ZH},
    "candidate_qa": {"en": CANDIDATE_QA_EN, "zh": CANDIDATE_QA_ZH},
    "wrapup": {"en": WRAPUP_EN, "zh": WRAPUP_ZH},
}


def get_phase_prompt(phase_name: str, lang: str, **kwargs: str) -> str:
    """Get a phase-specific question generation prompt.

    Args:
        phase_name: One of ice_break, project_deep_dive, technical_assessment,
                    behavioral, candidate_qa, wrapup
        lang: "en" or "zh"
        **kwargs: Template variables (varies by phase)

    Returns:
        Formatted prompt string
    """
    entry = _PROMPT_REGISTRY.get(phase_name, {})
    template = entry.get(lang, entry.get("en", ""))
    if kwargs:
        return template.format(**kwargs)
    return template


def get_follow_up_prompt(purpose: str, lang: str, **kwargs: str) -> str:
    """Get a follow-up decision or generation prompt.

    Args:
        purpose: "decision" or "generate"
        lang: "en" or "zh"
        **kwargs: Template variables

    Returns:
        Formatted prompt string
    """
    if purpose == "decision":
        template = FOLLOW_UP_DECISION_ZH if lang == "zh" else FOLLOW_UP_DECISION_EN
    else:
        template = FOLLOW_UP_GENERATE_ZH if lang == "zh" else FOLLOW_UP_GENERATE_EN
    if kwargs:
        return template.format(**kwargs)
    return template
