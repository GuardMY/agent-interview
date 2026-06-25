"""
Centralized bilingual prompts for the interview agent.
Usage: get_prompt("key", lang) or get_prompt("key", lang, question="...")
"""

# ── All interview prompts keyed by purpose ───────────────────

PROMPTS: dict[str, dict[str, str]] = {
    # ── Intro phase ──────────────────────────────────────────
    "intro_en": {
        "en": (
            "Begin the interview now. Greet the candidate warmly, introduce yourself as the interviewer, "
            "briefly outline what the interview will cover, and ask an opening question. "
            "Output only what you would say to the candidate, no meta-commentary."
        ),
        "zh": (
            "现在开始面试。热情问候候选人，介绍自己是面试官，简要说明面试流程，然后直接提出开场问题。"
            "只输出你要对候选人说的话，不要加任何前缀说明。"
        ),
    },
    "intro_transition": {
        "en": "Thank you! Let's begin with the technical questions.",
        "zh": "好的，我们开始技术问答环节。",
    },

    # ── Q&A phase ────────────────────────────────────────────
    "question_wrap": {
        "en": (
            'Ask the following interview question naturally and directly. '
            'Output only what you would say to the candidate, no meta-commentary:\n'
            'Question: "{question}"\n'
            'Category: {category}, Difficulty: {difficulty}'
        ),
        "zh": (
            '请提出下面这道面试题（需要先将英文题目翻译为地道中文后再提问），'
            '直接输出你要说的话，不要加任何前缀或说明：\n'
            '题目："{question}"\n'
            '类别：{category}，难度：{difficulty}'
        ),
    },
    "clarify": {
        "en": (
            "The candidate asked for clarification on the last question. "
            "Directly rephrase or explain — output only your response, no meta-commentary."
        ),
        "zh": (
            "候选人要求澄清上一道题。直接重新解释或措辞——只输出你的回答，不要加任何前缀说明。"
        ),
    },
    "repeat": {
        "en": (
            'Rephrase the following interview question. '
            'Output only the rephrased question, nothing else:\n'
            '"{question}"'
        ),
        "zh": (
            '重新措辞以下面试题。只输出重新措辞后的问题，不要加任何额外内容：\n'
            '"{question}"'
        ),
    },
    "skip_ack": {
        "en": "No problem, let's move on to the next question.",
        "zh": "没问题，我们进入下一题。",
    },
    "skip_limit": {
        "en": "You've reached the maximum number of skips. Let's wrap up.",
        "zh": "已达到最大跳过次数，我们结束面试吧。",
    },

    # ── Wrapup phase ─────────────────────────────────────────
    "wrapup": {
        "en": (
            "The interview is now complete. Thank the candidate, briefly summarize the interview, "
            "and close the conversation professionally. Output only what you would say."
        ),
        "zh": (
            "面试到此结束。感谢候选人，简要总结面试过程，专业地结束对话。"
            "只输出你要说的话，不要加任何前缀说明。"
        ),
    },
    "wrapup_fallback": {
        "en": "Thank you for your time! The interview is now complete. We will review your responses and get back to you.",
        "zh": "感谢你的时间！面试到此结束，我们会评估你的表现并尽快与你联系。",
    },
    "end_message": {
        "en": "Interview complete. Thank you for participating.",
        "zh": "面试结束，感谢你的参与。",
    },

    # ── Disconnect / early end ──────────────────────────────
    "early_end": {
        "en": "I understand. Thank you for your time today. We'll end the interview here.",
        "zh": "好的，感谢你今天的时间，面试到此结束。",
    },
}


def get_prompt(key: str, lang: str, **kwargs: str) -> str:
    """Get a prompt by key and language, optionally formatted with kwargs."""
    entry = PROMPTS.get(key)
    if not entry:
        raise KeyError(f"Unknown prompt key: {key}")

    template = entry.get(lang, entry.get("en", ""))
    if kwargs:
        return template.format(**kwargs)
    return template
