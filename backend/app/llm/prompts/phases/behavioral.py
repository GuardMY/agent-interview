BEHAVIORAL_EN = """You are in the behavioral interview phase.

Behavioral Theme: {theme} (priority: {priority}/5)
Source: {source} (level-based / position requirement / resume gap)
Position Context: {position_context}
Experience Level: {experience_level}
Soft Skill Requirements: {soft_skills}

Your task: Generate a behavioral interview question.

Level-appropriate guidance:
- Junior: Focus on learning ability, handling feedback, teamwork fundamentals
- Mid: Focus on cross-team collaboration, handling conflict, technical decision-making
- Senior: Focus on leadership, mentoring, technical vision, managing ambiguity

The question should ask for a SPECIFIC past situation, not a hypothetical.
"I am interested in learning about a real situation where you..."

Output ONLY the question. Keep it natural and open-ended."""

BEHAVIORAL_ZH = """你正处于面试的行为评估阶段。

行为主题：{theme}（优先级：{priority}/5）
来源：{source}（级别驱动 / 岗位要求 / 简历差距）
岗位背景：{position_context}
经验级别：{experience_level}
软技能要求：{soft_skills}

你的任务：生成一道行为面试题。

级别差异化指导：
- 初级：关注学习能力、接受反馈、团队合作基础
- 中级：关注跨团队协作、处理冲突、技术决策
- 高级：关注领导力、指导他人、技术愿景、处理模糊性

问题必须要求候选人描述一个具体的过去经历，而非假设性问题。
"我想了解一个你亲身经历的情况，其中你..."

只输出问题。保持自然和开放式。"""
