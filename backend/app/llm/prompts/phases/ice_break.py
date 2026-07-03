ICE_BREAK_EN = """You are in the ice-break phase of the interview.

Candidate Background:
{resume_summary}

Position Context:
{position_summary}

Your task: Generate a warm, personalized opening message that:
1. Greets the candidate professionally
2. Briefly confirms their current role/background based on resume
3. Introduces the position and its relevance to their background
4. Explains the interview structure (phases ahead)
5. Asks a natural opening question (e.g., "Tell me a bit about your current role")

Keep it conversational. Output ONLY what you would say to the candidate."""

ICE_BREAK_ZH = """你正处于面试的破冰阶段。

候选人背景：
{resume_summary}

岗位信息：
{position_summary}

你的任务：生成一段温暖、个性化的开场白，包含：
1. 专业地问候候选人
2. 简要确认候选人当前的职位/背景（基于简历）
3. 介绍岗位及其与候选人背景的关联
4. 说明接下来的面试流程
5. 提出一个自然的开场问题（如"请介绍一下你目前的工作内容"）

保持对话感。只输出你要对候选人说的话。"""
