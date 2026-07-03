FOLLOW_UP_DECISION_EN = """You are deciding whether to ask a follow-up question.

Current question: {question}
Candidate's answer: {answer}
Current follow-up depth: {depth}/3
Position skills being assessed: {position_skills}
Phase: {phase}

Decide: should we follow up, advance, or skip?

Return ONLY a JSON object:
{{"decision": "follow_up"|"advance"|"skip", "reason": "brief reason", "topic": "what to probe if following up"}}

Rules:
- "follow_up": Answer is interesting but needs more depth; mentions position-relevant tech worth exploring; answer is vague/partial (depth < 3)
- "advance": Answer is complete and satisfactory; we've probed enough on this topic
- "skip": Answer is completely off-topic or candidate seems stuck"""

FOLLOW_UP_DECISION_ZH = """你正在决定是否要追问。

当前问题：{question}
候选人回答：{answer}
当前追问深度：{depth}/3
评估的岗位技能：{position_skills}
当前阶段：{phase}

决定：追问、推进还是跳过？

只返回一个 JSON 对象：
{{"decision": "follow_up"|"advance"|"skip", "reason": "简短原因", "topic": "如果追问，追问什么"}}

规则：
- "follow_up"：回答有深挖价值；提到了值得探究的岗位相关技术；回答模糊/不完整（depth < 3）
- "advance"：回答完整且令人满意；该话题已挖掘足够
- "skip"：回答完全跑题或候选人明显卡住"""

FOLLOW_UP_GENERATE_EN = """You are generating a follow-up question.

Original question: {question}
Candidate's answer: {answer}
Follow-up depth: {depth}/3
Topic to probe: {topic}
Position skills being assessed: {position_skills}

Generate a natural follow-up question that:
1. References something specific the candidate said
2. Probes deeper on {topic}
3. If relevant, connects to position requirements: {position_skills}
4. Is conversational, not interrogating

Output ONLY the follow-up question."""

FOLLOW_UP_GENERATE_ZH = """你正在生成一个追问。

原始问题：{question}
候选人回答：{answer}
追问深度：{depth}/3
要探究的话题：{topic}
评估的岗位技能：{position_skills}

生成一个自然的追问，要求：
1. 引用候选人说过的具体内容
2. 深入探究 {topic}
3. 如果相关，联系岗位要求：{position_skills}
4. 保持对话感，而非审问感

只输出追问问题。"""
