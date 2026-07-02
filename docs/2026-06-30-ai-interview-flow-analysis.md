# AI 面试官 — 流程分析与大模型决策增强方案

> 基于 V1.0 代码库深度分析，聚焦流程管理清晰化与 LLM 替代人工决策的可行路径。

---

## 一、当前流程全景图

### 1.1 顶层流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  创建会话  │───→│  WS连接   │───→│  开场破冰  │───→│  技术问答  │───→│  结束评分  │
│ (REST)    │    │ (WS)      │    │ (INTRO)   │    │ (QA_LOOP) │    │ (WRAPUP)  │
│ 人工填写   │    │ 令牌验证   │    │ LLM生成   │    │ 5题循环   │    │ LLM生成   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                    │
                                                                    ▼
                                                              ┌──────────┐
                                                              │  查看报告  │
                                                              │ (REST)    │
                                                              │ 人工判断   │
                                                              └──────────┘
```

### 1.2 状态机详情

当前 FSM 定义在 [fsm.py](backend/app/core/fsm.py)，5 个状态 9 个事件：

```
                    ┌─────────┐
          ┌─────────│  IDLE   │
          │         └────┬────┘
          │              │ START
          │         ┌────▼────┐
  CANDIDATE_        │  INTRO  │──────────────┐
  DISCONNECT        └────┬────┘              │
          │              │ INTRO_COMPLETE     │ TIME_UP
          │         ┌────▼────┐              │
          │  ┌──────│ QA_LOOP │◄──────┐      │
          │  │      └────┬────┘       │      │
          │  │           │ ANSWER_    │ SKIP_│
          │  │           │ EVALUATED  │ QUEST│
          │  │      ┌────▼────┐       │      │
          │  │      │QUESTION_│───────┘      │
          │  │      │EXHAUSTED│              │
          │  │      └────┬────┘              │
          │  │           │                   │
          │  │      ┌────▼────┐              │
          │  └─────►│ WRAPUP  │◄─────────────┘
          │         └────┬────┘
          │              │ WRAPUP_COMPLETE
          │         ┌────▼────┐
          └────────►│  DONE   │
                    └─────────┘
```

**核心特点**：线性、单向、不可逆。一旦进入下一阶段，无法回退。

---

## 二、流程管理问题诊断

### 2.1 状态粒度过粗

| 问题 | 现状 | 影响 |
|------|------|------|
| QA_LOOP 内无子状态 | 题目展示 → 等待回答 → 评分 → 下一题全揉在一个 handler 里 | 无法精确定位当前步骤，断线后无法从中间点恢复 |
| 无"等待候选人回答"状态 | `_handle_qa()` 同时处理 answer/skip/repeat/clarify | 意图检测与评估逻辑耦合，难以扩展新命令 |
| WRAPUP 立即结束 | `_start_wrapup()` 直接触发 `WRAPUP_COMPLETE`，不等候选人回复 | 候选人没有反问环节，体验不完整 |
| INTRO 过于简单 | 开场白发送后立即等回复，无候选人确认就绪的步骤 | 候选人可能未准备好就进入问答 |

**建议**：将 QA_LOOP 拆分为子状态：

```
QA_LOOP
├── WAITING_FOR_ANSWER    # 等待候选人回答
├── EVALUATING             # LLM 评分中
├── GIVING_FEEDBACK        # 发送反馈
└── TRANSITIONING          # 准备下一题
```

### 2.2 断线恢复缺失

当前 [ws_interview.py:88-103](backend/app/api/ws_interview.py) 中的主循环一旦 WebSocket 断开，直接调用 `on_disconnect()` → 标记 DONE → 结束。前端有自动重连（[use-websocket.ts](frontend/src/hooks/use-websocket.ts)），但后端完全不支持状态恢复。

**现状代码路径**：
```
WebSocket 断开 → agent.on_disconnect() → FSM → DONE → session.status = "done"
```

**建议方案**：
1. 在 Question/Answer 表中持久化当前步骤（不仅仅是 `current_question_index`）
2. 重连时 `agent.start()` 检测到 `status != idle`，调用 `_resume_from_state()` 从断点继续
3. 前端重连成功后发送 `command.resume`，后端从 DB 恢复上一状态并重发最后一条消息

### 2.3 超时机制未激活

[fsm.py:38-51](backend/app/core/fsm.py) 定义了 `TIME_UP` 事件和完整的转换规则，但 [agent.py](backend/app/core/agent.py) 中没有任何 `asyncio.wait_for` 或定时器触发它。

| 超时场景 | 当前行为 | 应有行为 |
|----------|----------|----------|
| 候选人 2 分钟不回答 | 无限等待 | 礼貌提示，再等 30 秒，超时跳过 |
| 总面试超 30 分钟 | 无限进行 | 加速收尾或强制结束 |
| LLM API 超时 | 3 次重试后 fallback | 已有重试，但无降级策略（如临时切换模型） |

**关键代码缺失**：`config.py` 已定义 `answer_timeout_seconds: int = 120`，但 agent 中从未引用。

### 2.4 流程不可观测

当前对面试官而言，面试过程是一个"黑盒"——只能等面试结束后看报告。没有实时进度推送、没有过程干预能力。

**缺失的能力**：
- 面试官无法实时观看面试（只能打开候选人页面查看）
- 面试官无法中途介入（如追加问题、调整难度、提前终止）
- 无结构化日志/审计追踪（只有控制台 log）

---

## 三、LLM 替代人工决策分析

### 3.1 当前人机决策分布

```
全流程决策点分析：

┌──────────────────────┬──────────┬──────────────────────────────┐
│       决策点          │ 当前决策者 │          LLM 可行性           │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 设定面试参数           │ 人工     │ 🟢 高 — LLM 分析 JD 自动配置    │
│ (技能/难度/题目数)     │          │                              │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 选择下一道题           │ 规则     │ 🟢 高 — LLM 上下文感知选题      │
│                      │ (随机)    │                              │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 判断是否需要追问       │ ❌ 未实现  │ 🟢 高 — LLM 根据回答质量决定   │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 判断回答意图           │ 关键词    │ 🟡 中 — LLM 更准但增加延迟     │
│ (回答/跳过/澄清/闲聊)  │ 启发式    │                              │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 评分 (1-5)            │ LLM      │ ✅ 已实现                     │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 难度调整               │ 规则     │ 🟢 高 — LLM 综合判断更细腻     │
│                      │ (连续阈值) │                              │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 是否推荐录用           │ 人工     │ 🟢 高 — LLM 综合报告 + 建议     │
│                      │ (看均分)  │                              │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 报告撰写               │ 规则聚合  │ 🟢 高 — LLM 叙事性报告         │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 题库质量管理           │ ❌ 未实现  │ 🟢 高 — LLM 自动审查/优化题目  │
├──────────────────────┼──────────┼──────────────────────────────┤
│ 候选人状态感知         │ ❌ 未实现  │ 🟡 中 — LLM 情绪/状态分析      │
│ (紧张/疲劳/回避)       │          │                              │
└──────────────────────┴──────────┴──────────────────────────────┘
```

### 3.2 详细分析：5 个可被 LLM 替代的关键人工决策

#### 决策 1：面试参数配置

**现状**（[rest_sessions.py](backend/app/api/rest_sessions.py)）：
面试官手动填写 `candidate_name`、`job_title`、`experience_level`、`key_skills`、`interview_language`。

**LLM 替代方案**：
```
输入：职位 JD 文本 / 简历文本
LLM 分析 → {
  "job_title": "Senior Backend Engineer",
  "experience_level": "senior",
  "key_skills": ["Python", "System Design", "Database Optimization", "Distributed Systems"],
  "suggested_categories": ["backend", "general"],
  "suggested_total_questions": 7,
  "focus_areas": ["高并发场景设计", "数据一致性", "性能调优"],
  "custom_prompt_hints": "候选人来自金融背景，可侧重数据一致性相关题目"
}
```

**价值**：减少面试官手动配置工作，确保技能标签与题库分类对齐，提高题目匹配度。

#### 决策 2：上下文感知选题

**现状**（[question_bank.py:33-71](backend/app/services/question_bank.py)）：
`random.choice(pool)` — 纯随机从符合难度和类别的题目池中选取。

**LLM 替代方案**：
```
输入：当前对话历史 + 已问题目列表 + 已评估的表现
LLM 选题 → {
  "selected_question": {...},
  "rationale": "候选人前两题在数据库方面表现优秀，但系统设计偏弱，
                此题考察分布式缓存，可同时验证两个维度",
  "customized_wording": "基于你的背景，我们来讨论一个实际场景...",
}
```

**价值**：题目之间形成逻辑递进，而非随机跳跃；可根据候选人回答中的具体表述定制提问角度。

#### 决策 3：智能追问

**现状**：不存在追问机制。每题只问一次，无论回答质量如何都直接进入下一题。

**LLM 替代方案**：
```
评分时同时返回：
{
  "score": 3,
  "need_follow_up": true,
  "follow_up_questions": [
    "你能具体说说在那个场景下是如何处理数据一致性的吗？",
    "如果 QPS 提升 10 倍，你的方案需要做什么调整？"
  ],
  "follow_up_strategy": "回答触及了概念但缺乏实践经验，用场景追问挖掘真实深度"
}
```

**价值**：这是区分 AI 面试官和固定问卷的关键差异点。人类面试官的核心价值之一就是追问能力。

#### 决策 4：综合录用建议

**现状**（[report.py](backend/app/services/report.py)）：
`avg_score = total_score / scored_count` — 前端根据 `avg_score >= 3.5` 显示"推荐"标签。

**LLM 替代方案**：
```
输入：全部问答记录 + 评分详情 + 维度分析
LLM 综合报告 → {
  "overall_score": 3.8,
  "recommendation": "cautious_hire",  // strong_hire | hire | cautious_hire | no_hire
  "recommendation_reasoning": "候选人在后端基础方面扎实（DB/API 设计均 4+），
                               但系统设计能力偏弱（2.5），考虑到岗位为 Senior，
                               建议加面一轮系统设计",
  "key_strengths": [...],
  "key_risks": [...],
  "suggested_next_steps": "安排系统设计专项面试，或降级为 Mid-Level 考虑",
  "narrative_summary": "张三在本次面试中展现出了扎实的后端开发基础..."
}
```

**价值**：从单一均分升级为有推理过程的综合判断，让人类面试官能理解 AI 的判断逻辑，而非看到一个黑盒数字。

#### 决策 5：题目质量管理

**现状**：题库是静态 JSON 文件（[questions.json](backend/data/questions.json)），30 道题，无质量反馈机制。

**LLM 替代方案**：
```
每次面试结束后，LLM 对每道题进行分析：
{
  "question_id": "q_03",
  "quality_assessment": {
    "discrimination_power": "high",    // 区分度：高分/低分候选人回答差异
    "clarity_score": 4,                 // 题目表述清晰度
    "difficulty_accuracy": "too_easy",  // 标注难度 vs 实际难度
    "common_misunderstandings": [...],  // 候选人对题目的常见误解
    "suggested_improvements": "增加具体场景约束，避免答案过于宽泛"
  }
}
```

**价值**：题库自我进化，从面试数据中学习哪些题好、哪些题需要修改。

---

## 四、流程重构方案

### 4.1 目标流程架构

```
                         ┌─────────────────────────┐
                         │    面试官控制面板         │
                         │  (实时监控 + 干预能力)    │
                         └───────────┬─────────────┘
                                     │ WebSocket (观察者模式)
                                     ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 智能配置  │───→│ 开场破冰  │───→│ 技术问答  │───→│ 候选人反问 │───→│ 综合报告  │
│ LLM分析JD │    │ (INTRO)   │    │ (QA_LOOP) │    │ (Q&A)     │    │ LLM叙事  │
│ 自动设定   │    │           │    │ + 智能追问 │    │           │    │ + 录用建议 │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                     │
                                     ├── 选题：LLM 上下文感知
                                     ├── 追问：LLM 动态生成
                                     ├── 评分：多维 LLM 评估
                                     └── 难度：LLM 综合判断
```

### 4.2 状态机升级

```
                    ┌─────────┐
          ┌─────────│  IDLE   │
          │         └────┬────┘
          │              │ START
          │         ┌────▼────┐
          │         │  INTRO  │
          │         └────┬────┘
          │              │ INTRO_COMPLETE
          │         ┌────▼────┐
          │         │ QA_LOOP │◄──────────────────────┐
          │         └────┬────┘                       │
          │              │                            │
          │    ┌─────────┼─────────┐                  │
          │    │         │         │                  │
          │    ▼         ▼         ▼                  │
          │ ┌──────┐ ┌──────┐ ┌──────┐               │
          │ │ASKING│ │WAIT_ │ │EVAL_ │               │
          │ │      │→│ANSWER│→│UATE  │               │
          │ └──────┘ └──┬───┘ └──┬───┘               │
          │         │   │        │                    │
          │         │   ▼        ├──(追问)──► ASKING  │
          │         │ CLARIFY    │                    │
          │         │            ├──(下一题)─► ASKING  │
          │         │            │                    │
          │         │            ▼                    │
          │         │       ┌──────────┐              │
          │         │       │QUESTION_ │              │
          │         │       │EXHAUSTED │──────────────┘
          │         │       └────┬─────┘
          │         │            │
          │         │       ┌────▼────┐
          │         │       │CANDIDATE│
          │         │       │  Q&A    │  ← 新增：候选人反问环节
          │         │       └────┬────┘
          │         │            │
          │         │       ┌────▼────┐
          │         │       │ WRAPUP  │
          │         │       └────┬────┘
          │         │            │ WRAPUP_COMPLETE
          │         │       ┌────▼────┐
          │         └───────│  DONE   │
          │                 └─────────┘
```

### 4.3 核心代码改造点

#### A. `agent.py` — 增加子状态机

```python
class QASubState(str, Enum):
    ASKING = "asking"           # 已发题，等待回答
    WAITING_FOR_ANSWER = "waiting_for_answer"
    CLARIFYING = "clarifying"    # 候选人要求澄清
    EVALUATING = "evaluating"    # LLM 评分中
    FOLLOWING_UP = "following_up"  # 追问
    TRANSITIONING = "transitioning"

class InterviewAgent:
    def __init__(self, ...):
        ...
        self._qa_substate: QASubState | None = None
        self._follow_up_count: int = 0  # 当前题追问次数
        self._max_follow_ups: int = 2
```

#### B. `agent.py` — 追问流程

```python
async def _evaluate_and_continue(self, answer_text: str) -> None:
    evaluation = await self._evaluator.evaluate(...)
    await self._store_answer(evaluation)

    # LLM 判断是否需要追问
    if evaluation.need_follow_up and self._follow_up_count < self._max_follow_ups:
        self._follow_up_count += 1
        follow_up = await self._llm.generate(
            prompt=get_follow_up_prompt(evaluation, answer_text),
            ...
        )
        self._qa_substate = QASubState.FOLLOWING_UP
        await self._send_message("interview.question", {"content": follow_up})
        return

    self._follow_up_count = 0
    self._questions.update_difficulty_with_context(evaluation, self._conversation)
    await self._ask_next_question()
```

#### C. `question_bank.py` — LLM 感知选题

```python
async def select_question_with_context(
    self, llm, conversation_context: str, previous_scores: list[int]
) -> QuestionData | None:
    """Let LLM choose the most contextually appropriate next question."""
    # Fallback to rule-based if LLM unavailable
    pool = self._get_filtered_pool()
    if len(pool) <= 3:
        return self._random_select(pool)

    # LLM picks the best next question
    prompt = build_question_selection_prompt(
        pool=pool, context=conversation_context, scores=previous_scores
    )
    response = await llm.generate(prompt, temperature=0.3)
    selected_index = parse_selection(response)
    return pool[selected_index]
```

#### D. `evaluator.py` — 多维评分 + 追问决策

```python
# 扩展 EvaluationResult schema
class EvaluationResult(BaseModel):
    score: int  # 1-5
    dimensions: dict[str, int]  # {"technical_accuracy": 4, "depth": 3, ...}
    comment: str
    strengths: list[str]
    weaknesses: list[str]
    matched_keywords: list[str]
    missing_points: list[str]
    need_follow_up: bool = False
    follow_up_questions: list[str] = []
    follow_up_rationale: str = ""
    candidate_state: str = "normal"  # confident | struggling | nervous | evasive
```

#### E. `report.py` — LLM 叙事报告

```python
class ReportService:
    @staticmethod
    async def build_narrative_report(
        session_id: str, db: AsyncSession, llm: BaseLLMAdapter
    ) -> NarrativeReport:
        """Generate a comprehensive narrative report with LLM."""
        data = await ReportService._gather_raw_data(session_id, db)
        prompt = build_narrative_report_prompt(data)
        response = await llm.generate(prompt, temperature=0.5, max_tokens=2000)
        return parse_narrative_report(response)
```

---

## 五、LLM 能力利用评估

### 5.1 当前 LLM 调用效率

| 调用场景 | 温度 | Token 消耗 | 调用频率 | 可优化空间 |
|----------|------|-----------|----------|-----------|
| 开场白 | 0.8 | ~150 | 1/会话 | 低 — 可缓存模板 |
| 问题包装 | 0.8 | ~100 | 5/会话 | 中 — 中文面试可预翻译 |
| 评分 | 0.3 | ~300 | 5/会话 | 中 — 可批处理多题 |
| 澄清 | 0.8 | ~100 | 0-3/会话 | 低 |
| 重复 | 0.8 | ~100 | 0-3/会话 | 低 |
| 结束语 | 0.7 | ~150 | 1/会话 | 低 — 可缓存模板 |

**总计**：约 2,000-3,500 token/会话（不含 system prompt）

### 5.2 新增 LLM 调用成本估算

| 新增场景 | 温度 | Token 消耗 | 调用频率 | 年度增加* |
|----------|------|-----------|----------|----------|
| JD 分析 + 自动配置 | 0.3 | ~500 | 1/会话 | +25% |
| 上下文感知选题 | 0.3 | ~400 | 5/会话 | +100% |
| 追问决策 | 0.3 | ~200 | 0-5/会话 | +50% |
| 综合报告生成 | 0.5 | ~1,000 | 1/会话 | +50% |
| 候选人状态分析 | 0.3 | ~200 | 5/会话 | +50% |
| 题目质量分析 | 0.3 | ~300 | 1/会话 | +15% |

> *假设 100 场面试/年，DeepSeek 当前定价

### 5.3 成本优化策略

1. **分层模型策略**：
   - 评分/报告 → 强模型（Claude Opus / DeepSeek-V4）
   - 选题/追问 → 快模型（DeepSeek-V4-Flash / Claude Haiku）
   - 翻译/包装 → 缓存或本地小模型

2. **批量调用**：将多次评分合并为一次 LLM 调用

3. **缓存策略**：
   - 题目翻译预生成（已在 improvement-suggestions.md #15 提出）
   - 常见追问模板缓存
   - System prompt 预热

4. **自适应 LLM 使用**：根据面试重要性动态调整模型层级

---

## 六、分阶段实施路线图

### Phase 1：流程清晰化（1-2 周）

**目标**：让现有流程可观测、可恢复、可干预

| 任务 | 文件 | 工作量 |
|------|------|--------|
| QA_LOOP 子状态引入 | `agent.py`, `fsm.py` | 3h |
| 每题超时机制 | `agent.py` | 2h |
| 断线状态恢复 | `agent.py`, `ws_interview.py` | 4h |
| 面试官实时观察 WebSocket | `ws_interview.py` (新增 observer 角色) | 3h |
| 结构化日志/审计 | `agent.py` | 2h |

### Phase 2：LLM 接管核心决策（2-3 周）

**目标**：用 LLM 替代选题、追问、报告三个关键决策点

| 任务 | 文件 | 工作量 |
|------|------|--------|
| LLM 上下文感知选题 | `question_bank.py` (新增 `select_question_with_context`) | 4h |
| 智能追问引擎 | `agent.py` (新增 `_handle_follow_up`), `evaluator.py` | 6h |
| 多维评分升级 | `evaluator.py`, `scoring.py`, `schemas/evaluation.py` | 3h |
| LLM 叙事报告 | `report.py`, `schemas/evaluation.py` | 4h |
| 录用建议 + 推理 | `report.py` | 2h |

### Phase 3：全自动化增强（2-3 周）

**目标**：实现端到端的 AI 自主决策

| 任务 | 文件 | 工作量 |
|------|------|--------|
| JD/简历分析自动配置 | 新增 `services/jd_analyzer.py` | 4h |
| LLM 意图检测替代关键词 | `conversation.py` (启用 `intent.py`) | 3h |
| 候选人状态感知 | `evaluator.py`, `conversation.py` | 4h |
| 题目质量自动评估 | 新增 `services/question_reviewer.py` | 4h |
| 难度调整 LLM 化 | `question_bank.py` | 2h |

### Phase 4：生态完善（长期）

| 任务 | 说明 |
|------|------|
| 编程考核模块 | Monaco Editor + Docker 沙箱 |
| 语音交互 | Whisper ASR + TTS |
| 多面试官模式 | 多个 AI 角色（算法官 + 系统设计官 + 行为官）|
| 面试数据分析仪表盘 | 评分趋势、题目区分度、候选人画像 |
| 候选人申诉通道 | 评分争议 → 人工复核流程 |

---

## 七、风险与缓解

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| LLM 追问偏离主线 | 中 | 追问次数硬限制 + 追问方向与预设考点对齐检查 |
| 评分一致性下降 | 中 | 定期校准（用标准答案测试评分分布） |
| LLM 成本失控 | 中 | 分层模型 + 缓存 + 月度预算告警 |
| 候选人感知 AI 面试不适 | 低 | 透明告知 + 保留人类复核通道 |
| 过度依赖 LLM 决策 | 高 | 关键决策（录用建议）标注为"仅供参考"，保留人工终审权 |
| prompt 注入风险 | 中 | 候选人输入与 LLM prompt 之间加隔离层，限制候选人对 system prompt 的影响 |

---

## 八、关键指标

| 指标 | 当前值 | Phase 2 目标 |
|------|--------|-------------|
| 单场面试 LLM 调用次数 | ~8-12 次 | ~15-20 次 |
| 评分维度 | 1 维 (总分) | 4 维 (准确/深度/沟通/问题解决) |
| 追问率 | 0% | 30-50% (有追问的题目占比) |
| 报告生成方式 | 规则聚合 | LLM 叙事 |
| 人工决策点 | 4 个 | 1 个 (仅最终录用决策) |
| 断线恢复能力 | 无 | 支持从任意子状态恢复 |
| 面试官过程参与度 | 0 (纯黑盒) | 实时观察 |

---

## 九、总结

当前 V1.0 系统已经建立了 AI 面试的基本骨架：状态机驱动的流程、LLM 评分、WebSocket 实时通信、双语支持。但在两个核心方向上存在明显不足：

1. **流程管理**：状态粒度粗、断线不可恢复、超时未激活、面试官无法观测过程。建议引入子状态机 + 状态持久化 + Observer 模式解决。

2. **LLM 利用**：评分之外的所有决策（选题、追问、难度调整、报告）都依赖硬编码规则或人工干预。而 LLM 完全有能力承担选题策略、追问决策、综合评估、录用建议等高级认知任务。

**核心建议**：逐步将"规则驱动的面试框架"升级为"LLM 驱动的自适应面试引擎"，同时保留人类在关键录用决策上的最终审批权。这样既能充分利用大模型的理解和推理能力，又能避免完全"黑盒决策"带来的信任和合规风险。

---

> 📅 分析日期：2026-06-30
>
> 🔍 分析范围：`backend/app/core/*`, `backend/app/services/*`, `backend/app/llm/*`, `backend/app/api/*`, `frontend/src/*`
>
> 📎 相关文档：
> - [AI 面试官设计文档](agent-interview-design.md) — 原始设计理念
> - [完整流程文档](agent-interview-flow.md) — V1.0 流程详解
> - [改进建议](improvement-suggestions.md) — P0-P3 优先级改进清单
> - [P0 解决方案](p0-solutions.md) — 已修复的安全问题
