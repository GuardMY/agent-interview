SCORING_PROMPT_EN = """You are evaluating a candidate's answer in a technical job interview. Evaluate strictly but fairly.

Context:
- Question: {question_text}
- Category: {category}
- Difficulty Level: {difficulty}
- Expected Keywords: {expected_keywords}

Candidate's Answer:
{candidate_answer}

Evaluation Rubric (1-5 scale):
1 - Poor: Completely incorrect, refusal to answer, or entirely off-topic
2 - Below Average: Partially correct but missing major concepts, contains significant errors
3 - Average: Generally correct but lacks depth, detail, or real-world context
4 - Good: Thorough and well-structured answer covering most expected points
5 - Excellent: Comprehensive, insightful, exceeds expectations, shows deep understanding

Output ONLY a valid JSON object (no code fences, no additional text):
{{
  "score": <integer 1-5>,
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

评分标准（1-5分）：
1 - 差：完全错误、拒绝回答或完全偏离主题
2 - 低于平均：部分正确但遗漏了重要概念，存在明显错误
3 - 平均：基本正确但缺乏深度、细节或实际场景
4 - 好：回答全面、结构清晰，涵盖了大部分期望要点
5 - 优秀：回答全面、有见地、超出预期，展现出深刻理解

只输出有效的 JSON 对象（不要用代码块，不要加额外文字）：
{{
  "score": <整数 1-5>,
  "comment": "<1-2句话总结评估，使用中文>",
  "strengths": ["<具体的优点>", ...],
  "weaknesses": ["<具体的不足>", ...],
  "matched_keywords": ["<命中的期望关键词>", ...],
  "missing_points": ["<遗漏的重要知识点>", ...]
}}"""


def get_scoring_prompt(language: str = "en") -> str:
    """Return the scoring prompt template for the given language."""
    return SCORING_PROMPT_ZH if language == "zh" else SCORING_PROMPT_EN
