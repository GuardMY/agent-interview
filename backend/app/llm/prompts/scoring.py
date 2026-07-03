SCORING_PROMPT_EN = """You are evaluating a candidate's answer in a technical job interview. Evaluate strictly but fairly.

Context:
- Question: {question_text}
- Category: {category}
- Difficulty Level: {difficulty}
- Expected Keywords: {expected_keywords}

Candidate's Answer:
{candidate_answer}

Score each dimension independently (1-5 scale where 1=Poor, 5=Excellent):

- technical_accuracy: Is the technical content correct? Are concepts accurately applied?
- depth_of_knowledge: Does the answer show deep understanding beyond surface-level? Are trade-offs discussed?
- communication: Is the answer well-structured, clear, and concise?
- problem_solving: Does the candidate demonstrate a logical approach? Consider edge cases?

Overall scoring:
1 - Poor: Completely incorrect, refusal to answer, or entirely off-topic
2 - Below Average: Partially correct but missing major concepts, contains significant errors
3 - Average: Generally correct but lacks depth, detail, or real-world context
4 - Good: Thorough and well-structured answer covering most expected points
5 - Excellent: Comprehensive, insightful, exceeds expectations, shows deep understanding

Output ONLY a valid JSON object (no code fences, no additional text):
{{
  "score": <integer 1-5, weighted average of the four dimensions>,
  "dimensions": {{
    "technical_accuracy": <integer 1-5>,
    "depth_of_knowledge": <integer 1-5>,
    "communication": <integer 1-5>,
    "problem_solving": <integer 1-5>
  }},
  "comment": "<1-2 sentences summarizing the evaluation, in English>",
  "strengths": ["<specific strength>", ...],
  "weaknesses": ["<specific gap>", ...],
  "matched_keywords": ["<keyword from expected list that was covered>", ...],
  "missing_points": ["<important point that was not addressed>", ...]
}}"""

SCORING_PROMPT_ZH = """你正在评估一场技术面试中候选人的回答。请严格但公平地评分。

上下文：
- 问题：{question_text}
- 类别：{category}
- 难度：{difficulty}
- 期望关键词：{expected_keywords}

候选人回答：
{candidate_answer}

为每个维度独立评分（1-5分，1=差，5=优秀）：

- technical_accuracy（技术准确性）：技术内容是否正确？概念是否准确应用？
- depth_of_knowledge（知识深度）：回答是否展示表面之外的深度理解？是否讨论了权衡？
- communication（沟通表达）：回答是否结构清晰、简洁明了？
- problem_solving（问题解决）：候选人是否展示了逻辑方法？是否考虑了边界情况？

总体评分标准：
1 - 差：完全错误、拒绝回答或完全偏离主题
2 - 低于平均：部分正确但遗漏了重要概念，存在明显错误
3 - 平均：基本正确但缺乏深度、细节或实际场景
4 - 好：回答全面、结构清晰，涵盖了大部分期望要点
5 - 优秀：回答全面、有见地、超出预期，展现出深刻理解

只输出有效的 JSON 对象（不要用代码块，不要加额外文字）：
{{
  "score": <整数 1-5，四个维度的加权平均>,
  "dimensions": {{
    "technical_accuracy": <整数 1-5>,
    "depth_of_knowledge": <整数 1-5>,
    "communication": <整数 1-5>,
    "problem_solving": <整数 1-5>
  }},
  "comment": "<1-2句话总结评估，使用中文>",
  "strengths": ["<具体的优点>", ...],
  "weaknesses": ["<具体的不足>", ...],
  "matched_keywords": ["<命中的期望关键词>", ...],
  "missing_points": ["<遗漏的重要知识点>", ...]
}}"""


def get_scoring_prompt(language: str = "en") -> str:
    """Return the scoring prompt template for the given language."""
    return SCORING_PROMPT_ZH if language == "zh" else SCORING_PROMPT_EN


# ═══════════════════════════════════════════════════════════════
# P3: Phase-aware V2 scoring prompts with behavioral + position_match
# ═══════════════════════════════════════════════════════════════

SCORING_PROMPT_EN_V2 = """You are evaluating a candidate's answer in a technical job interview. Evaluate strictly but fairly.

Context:
- Question: {question_text}
- Category: {category}
- Difficulty Level: {difficulty}
- Interview Phase: {phase}
- Position Context: {position_context}
- Expected Keywords: {expected_keywords}

Candidate's Answer:
{candidate_answer}

Score each dimension independently (1-5 scale where 1=Poor, 5=Excellent):

CORE DIMENSIONS (always scored):
- technical_accuracy: Is the technical content correct? Are concepts accurately applied?
- depth_of_knowledge: Does the answer show deep understanding beyond surface-level? Are trade-offs discussed?
- communication: Is the answer well-structured, clear, and concise?
- problem_solving: Does the candidate demonstrate a logical approach? Consider edge cases?

{extra_dimensions}

Overall scoring:
1 - Poor: Completely incorrect, refusal to answer, or entirely off-topic
2 - Below Average: Partially correct but missing major concepts, contains significant errors
3 - Average: Generally correct but lacks depth, detail, or real-world context
4 - Good: Thorough and well-structured answer covering most expected points
5 - Excellent: Comprehensive, insightful, exceeds expectations, shows deep understanding

Output ONLY a valid JSON object (no code fences, no additional text):
{{
  "score": <integer 1-5>,
  "dimensions": {{
    "technical_accuracy": <integer 1-5>,
    "depth_of_knowledge": <integer 1-5>,
    "communication": <integer 1-5>,
    "problem_solving": <integer 1-5>
    {extra_dimensions_json}
  }},
  "comment": "<1-2 sentences summarizing the evaluation, in English>",
  "strengths": ["<specific strength>", ...],
  "weaknesses": ["<specific gap>", ...],
  "matched_keywords": ["<keyword from expected list that was covered>", ...],
  "missing_points": ["<important point that was not addressed>", ...]
}}"""

SCORING_PROMPT_ZH_V2 = """你正在评估一场技术面试中候选人的回答。请严格但公平地评分。

上下文：
- 问题：{question_text}
- 类别：{category}
- 难度：{difficulty}
- 面试阶段：{phase}
- 岗位背景：{position_context}
- 期望关键词：{expected_keywords}

候选人回答：
{candidate_answer}

为每个维度独立评分（1-5分，1=差，5=优秀）：

核心维度（始终评估）：
- technical_accuracy（技术准确性）：技术内容是否正确？概念是否准确应用？
- depth_of_knowledge（知识深度）：回答是否展示表面之外的深度理解？是否讨论了权衡？
- communication（沟通表达）：回答是否结构清晰、简洁明了？
- problem_solving（问题解决）：候选人是否展示了逻辑方法？是否考虑了边界情况？

{extra_dimensions}

总体评分标准：
1 - 差：完全错误、拒绝回答或完全偏离主题
2 - 低于平均：部分正确但遗漏了重要概念，存在明显错误
3 - 平均：基本正确但缺乏深度、细节或实际场景
4 - 好：回答全面、结构清晰，涵盖了大部分期望要点
5 - 优秀：回答全面、有见地、超出预期，展现出深刻理解

只输出有效的 JSON 对象（不要用代码块，不要加额外文字）：
{{
  "score": <整数 1-5>,
  "dimensions": {{
    "technical_accuracy": <整数 1-5>,
    "depth_of_knowledge": <整数 1-5>,
    "communication": <整数 1-5>,
    "problem_solving": <整数 1-5>
    {extra_dimensions_json}
  }},
  "comment": "<1-2句话总结评估，使用中文>",
  "strengths": ["<具体的优点>", ...],
  "weaknesses": ["<具体的不足>", ...],
  "matched_keywords": ["<命中的期望关键词>", ...],
  "missing_points": ["<遗漏的重要知识点>", ...]
}}"""

# Phase-specific extra dimension definitions
PHASE_DIMENSION_CONFIG: dict[str, dict] = {
    "ice_break": {
        "en": {
            "extra_dimensions": """POSITION MATCH DIMENSIONS (score if observable):
- culture_fit: Does the candidate's communication style and demeanor align with the team culture?""",
            "extra_dimensions_json": """,\n    "culture_fit": <integer 1-5>""",
        },
        "zh": {
            "extra_dimensions": """岗位匹配维度（如可观察则评分）：
- culture_fit（文化匹配）：候选人的沟通风格和气质是否与团队文化相符？""",
            "extra_dimensions_json": """,\n    "culture_fit": <整数 1-5>""",
        },
    },
    "project_deep_dive": {
        "en": {
            "extra_dimensions": """POSITION MATCH DIMENSIONS (score based on project relevance):
- experience_alignment: How well does the candidate's project experience align with this role's responsibilities?
- skill_coverage: How much of the position's required tech stack is demonstrated in their project work?""",
            "extra_dimensions_json": """,\n    "experience_alignment": <integer 1-5>,\n    "skill_coverage": <integer 1-5>""",
        },
        "zh": {
            "extra_dimensions": """岗位匹配维度（基于项目相关性评分）：
- experience_alignment（经验匹配）：候选人的项目经验与岗位职责的匹配程度？
- skill_coverage（技能覆盖）：候选人项目经历中展示了多少岗位要求的技术栈？""",
            "extra_dimensions_json": """,\n    "experience_alignment": <整数 1-5>,\n    "skill_coverage": <整数 1-5>""",
        },
    },
    "technical_assessment": {
        "en": {
            "extra_dimensions": """POSITION MATCH DIMENSIONS:
- skill_coverage: To what extent does the candidate demonstrate proficiency in the position's required skills?
- level_alignment: Is the candidate operating at the level expected for this role?
- domain_fit: Does the candidate show relevant domain/industry knowledge?""",
            "extra_dimensions_json": """,\n    "skill_coverage": <integer 1-5>,\n    "level_alignment": <integer 1-5>,\n    "domain_fit": <integer 1-5>""",
        },
        "zh": {
            "extra_dimensions": """岗位匹配维度：
- skill_coverage（技能覆盖）：候选人在多大程度上展示了岗位所需技能的熟练度？
- level_alignment（级别匹配）：候选人的表现是否达到该岗位的目标级别？
- domain_fit（领域匹配）：候选人是否展示了相关的行业/领域知识？""",
            "extra_dimensions_json": """,\n    "skill_coverage": <整数 1-5>,\n    "level_alignment": <整数 1-5>,\n    "domain_fit": <整数 1-5>""",
        },
    },
    "behavioral": {
        "en": {
            "extra_dimensions": """BEHAVIORAL DIMENSIONS:
- teamwork: Does the candidate demonstrate effective collaboration skills?
- leadership: Does the candidate show leadership or mentoring capability?
- ownership: Does the candidate take responsibility and show accountability?
- growth_mindset: Does the candidate demonstrate learning agility and growth orientation?
- culture_fit: Does the candidate's work style align with the team culture requirements?

POSITION MATCH DIMENSIONS:
- culture_fit: How well does the candidate's behavioral profile match the position's soft skill requirements?
- growth_potential: Does the candidate show potential to grow within this specific role?""",
            "extra_dimensions_json": """,\n    "teamwork": <integer 1-5>,\n    "leadership": <integer 1-5>,\n    "ownership": <integer 1-5>,\n    "growth_mindset": <integer 1-5>,\n    "culture_fit": <integer 1-5>,\n    "growth_potential": <integer 1-5>""",
        },
        "zh": {
            "extra_dimensions": """行为维度：
- teamwork（团队协作）：候选人是否展现了有效的协作能力？
- leadership（领导力）：候选人是否展现了领导或指导他人的能力？
- ownership（责任心）：候选人是否体现了担当和责任感？
- growth_mindset（成长心态）：候选人是否展现了学习敏捷性和成长导向？
- culture_fit（文化匹配）：候选人的工作风格是否符合团队文化要求？

岗位匹配维度：
- culture_fit（文化匹配）：候选人的行为特质与岗位软技能要求的匹配程度？
- growth_potential（成长潜力）：候选人在该岗位上展现出的成长空间？""",
            "extra_dimensions_json": """,\n    "teamwork": <整数 1-5>,\n    "leadership": <整数 1-5>,\n    "ownership": <整数 1-5>,\n    "growth_mindset": <整数 1-5>,\n    "culture_fit": <整数 1-5>,\n    "growth_potential": <整数 1-5>""",
        },
    },
    "candidate_qa": {
        "en": {
            "extra_dimensions": """No extra dimensions — this is the candidate's Q&A phase.""",
            "extra_dimensions_json": "",
        },
        "zh": {
            "extra_dimensions": """无额外维度——这是候选人反问阶段。""",
            "extra_dimensions_json": "",
        },
    },
    "wrapup": {
        "en": {
            "extra_dimensions": """No extra dimensions — this is the wrapup phase.""",
            "extra_dimensions_json": "",
        },
        "zh": {
            "extra_dimensions": """无额外维度——这是总结阶段。""",
            "extra_dimensions_json": "",
        },
    },
}


def get_scoring_prompt_v2(
    language: str = "en",
    phase: str = "technical_assessment",
    position_context: str = "",
) -> str:
    """Return a phase-aware scoring prompt with behavioral + position_match dimensions.

    Args:
        language: "en" or "zh"
        phase: Current interview phase (ice_break, project_deep_dive, etc.)
        position_context: Position summary for context injection

    Returns:
        Formatted prompt template (still needs .format() with question data)
    """
    template = SCORING_PROMPT_ZH_V2 if language == "zh" else SCORING_PROMPT_EN_V2

    config = PHASE_DIMENSION_CONFIG.get(phase, PHASE_DIMENSION_CONFIG.get("technical_assessment", {}))
    lang_config = config.get(language, config.get("en", {}))

    return template.format(
        phase=phase,
        position_context=position_context or "General technical role",
        extra_dimensions=lang_config.get("extra_dimensions", ""),
        extra_dimensions_json=lang_config.get("extra_dimensions_json", ""),
        # Placeholders for the second .format() call with question data
        question_text="{question_text}",
        category="{category}",
        difficulty="{difficulty}",
        expected_keywords="{expected_keywords}",
        candidate_answer="{candidate_answer}",
    )
