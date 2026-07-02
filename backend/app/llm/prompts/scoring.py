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
