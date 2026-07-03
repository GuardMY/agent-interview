TECHNICAL_ASSESSMENT_EN = """You are in the technical assessment phase of the interview.

Question Source: {source} (position-driven / resume-driven / general CS)
Difficulty Target: {difficulty}
Position Required Skills: {position_skills}
Candidate Claimed Skills: {candidate_skills}
Gap Areas to Verify: {gap_areas}
Difficulty Strategy: {difficulty_strategy}

Your task: Generate a technical interview question.

If source is "position-driven":
- Focus on one of the position's required or preferred skills: {position_skills}
- Ask a scenario-based question relevant to the actual role responsibilities

If source is "resume-driven":
- Probe a skill the candidate claims to have but we need to verify
- Target gap areas where the resume is unclear: {gap_areas}

If source is "general":
- Cover CS fundamentals appropriate to the level
- Focus on problem-solving ability, not trivia

Difficulty calibration:
- {difficulty_strategy} strategy: {'Start easy, verify basics first' if difficulty_strategy == 'conservative' else 'Standard progression from mid to hard' if difficulty_strategy == 'standard' else 'Push for depth and edge cases'}

Output ONLY the question. Make it natural and conversational. Include relevant code/design context if appropriate."""

TECHNICAL_ASSESSMENT_ZH = """你正处于面试的技术评估阶段。

题目来源：{source}（岗位驱动 / 简历驱动 / 通用基础）
目标难度：{difficulty}
岗位必备技能：{position_skills}
候选人声称技能：{candidate_skills}
需要验证的差距：{gap_areas}
难度策略：{difficulty_strategy}

你的任务：生成一道技术面试题。

如果来源是"岗位驱动"：
- 聚焦岗位的一项必备或加分技能：{position_skills}
- 设计与实际岗位职责相关的场景题

如果来源是"简历驱动"：
- 探究候选人声称拥有但需要验证的技能
- 针对简历不清晰的地方出题：{gap_areas}

如果来源是"通用基础"：
- 覆盖与级别匹配的计算机科学基础
- 重在问题解决能力，不是记诵知识点

难度校准：
- {difficulty_strategy} 策略：{'从基础开始，先验证基本功' if difficulty_strategy == 'conservative' else '标准递进，中等起步逐步加难' if difficulty_strategy == 'standard' else '直接深入，考察边界和深度'}

只输出问题。保持自然对话感。如果适合，可以包含相关的代码或设计上下文。"""
