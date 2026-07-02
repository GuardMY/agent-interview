# AI 面试官 — 改进措施（基于流程分析）

> 配套分析文档：[2026-06-30-ai-interview-flow-analysis.md](2026-06-30-ai-interview-flow-analysis.md)

---

## 目录

- [措施总览](#措施总览)
- [P1：流程管理修复](#p1流程管理修复)
  - [1.1 QA_LOOP 子状态机](#11-qa_loop-子状态机)
  - [1.2 断线恢复](#12-断线恢复)
  - [1.3 超时机制](#13-超时机制)
  - [1.4 面试官实时观察](#14-面试官实时观察)
- [P2：LLM 接管核心决策](#p2llm-接管核心决策)
  - [2.1 多维评分 + 追问决策](#21-多维评分--追问决策)
  - [2.2 上下文感知选题](#22-上下文感知选题)
  - [2.3 LLM 叙事报告 + 录用建议](#23-llm-叙事报告--录用建议)
  - [2.4 LLM 意图检测](#24-llm-意图检测)
- [P3：全自动化增强](#p3全自动化增强)
  - [3.1 JD 分析自动配置](#31-jd-分析自动配置)
  - [3.2 候选人状态感知](#32-候选人状态感知)
  - [3.3 题目质量自动评估](#33-题目质量自动评估)
- [P4：前端配套改造](#p4前端配套改造)
- [配置变更汇总](#配置变更汇总)
- [测试策略](#测试策略)

---

## 措施总览

```
┌─────────────────────────────────────────────────────────────┐
│  优先级    │ 范围        │ 措施数 │ 工时     │ 核心收益       │
├───────────┼────────────┼───────┼─────────┼───────────────┤
│ P1 流程   │ 后端核心     │ 4      │ 14h     │ 可恢复、可观测  │
│ P2 LLM决策 │ 后端核心     │ 4      │ 19h     │ 追问、选题、报告 │
│ P3 自动化  │ 后端+前端    │ 3      │ 17h     │ 端到端AI自主    │
│ P4 前端    │ 前端        │ 3      │ 10h     │ 面试官体验      │
│ 合计      │            │ 14     │ 60h     │ —              │
└───────────┴────────────┴───────┴─────────┴───────────────┘
```

---

## P1：流程管理修复

### 1.1 QA_LOOP 子状态机

**问题**：QA_LOOP 内所有逻辑（展示题目、等待回答、评分、过渡）糅合在 `_handle_qa()` 一个方法中，无法跟踪当前精确步骤。

**措施**：在 `fsm.py` 中新增 `QASubState` 枚举，并在 `agent.py` 中引入子状态追踪。

#### 1.1.1 修改 `backend/app/core/fsm.py` — 新增子状态枚举

在文件末尾追加：

```python
class QASubState(str, Enum):
    """Sub-states within the QA_LOOP phase for fine-grained tracking."""
    ASKING = "asking"                   # 已发题，等待回答
    CLARIFYING = "clarifying"           # 候选人要求澄清，重新解释中
    EVALUATING = "evaluating"           # LLM 评分进行中
    FOLLOWING_UP = "following_up"       # 追问中
    FEEDBACK_GIVEN = "feedback_given"   # 反馈已发送，准备过渡
    SKIPPING = "skipping"               # 跳过当前题
```

#### 1.1.2 修改 `backend/app/core/agent.py` — 引入子状态

**a) `__init__` 中增加字段：**

```python
# 在 __init__ 中添加（约第 47 行后）
self._qa_substate: QASubState | None = None
self._follow_up_count: int = 0
self._max_follow_ups: int = 2
self._answer_timeout_task: asyncio.Task | None = None
```

**b) `_ask_next_question()` 方法改造（约第 186 行）：**

将方法末尾的状态变更显式化：

```python
async def _ask_next_question(self) -> None:
    # ... 现有选题 + 发送逻辑保持不变 ...
    
    # 在发送 interview.question 后追加：
    self._qa_substate = QASubState.ASKING
    self._follow_up_count = 0
    # 启动每题超时计时器（见 1.3）
    self._start_answer_timeout()
```

**c) `_handle_qa()` 方法改造（约第 116 行）：**

在方法开头增加子状态路由：

```python
async def _handle_qa(self, raw: dict) -> None:
    msg_type = raw.get("type", "")

    # 命令类消息独立处理
    if msg_type == "command.skip":
        self._qa_substate = QASubState.SKIPPING
        await self._handle_skip()
        return

    if msg_type == "command.repeat":
        await self._handle_repeat()
        return

    # 内容类消息：取消超时计时器
    self._cancel_answer_timeout()

    content = raw.get("payload", {}).get("content", "")
    if not content:
        return

    self._conversation.add_message("candidate", content)

    # 根据当前子状态路由
    if self._qa_substate == QASubState.FOLLOWING_UP:
        # 这是对追问的回答，评估后决定是否继续追问
        await self._evaluate_and_continue(content)
        return

    # 默认流：意图检测 → 评估
    intent = self._conversation.detect_intent(content)
    # ... 其余意图处理逻辑保持不变 ...
```

**d) 在 `_finalize_session()` 中清理子状态：**

```python
async def _finalize_session(self) -> None:
    self._qa_substate = None
    self._cancel_answer_timeout()
    # ... 其余逻辑保持不变 ...
```

#### 1.1.3 修改 `backend/app/models/session.py` — 持久化子状态

在 `InterviewSession` 模型中增加字段：

```python
# 新增字段
qa_substate = Column(String(30), nullable=True)  # QASubState 值
follow_up_count = Column(Integer, default=0)
```

对应的数据库迁移（Alembic 或手动 SQL）：

```sql
ALTER TABLE interview_sessions ADD COLUMN qa_substate VARCHAR(30);
ALTER TABLE interview_sessions ADD COLUMN follow_up_count INTEGER DEFAULT 0;
```

#### 1.1.4 在状态变更时同步写 DB

在 `agent.py` 中所有修改 `self._qa_substate` 和 `self._session.status` 的地方，同步调用 `await self._db.commit()` 或使用一个统一的 `_persist_state()` 方法：

```python
async def _persist_state(self) -> None:
    """Sync in-memory agent state to database for resume capability."""
    if self._session:
        self._session.qa_substate = self._qa_substate.value if self._qa_substate else None
        self._session.follow_up_count = self._follow_up_count
        await self._db.commit()
```

---

### 1.2 断线恢复

**问题**：[ws_interview.py:88-103](backend/app/api/ws_interview.py) WebSocket 断开后直接 `on_disconnect()` → 标记 DONE，所有进度丢失。

**措施**：区分"候选人主动结束"与"网络意外断开"，后者保留状态等待重连。

#### 1.2.1 修改 `backend/app/core/agent.py` — 区分断开原因

```python
async def on_disconnect(self, intentional: bool = False) -> None:
    """Handle client disconnect.
    
    Args:
        intentional: True if candidate explicitly ended, False for network drop.
    """
    if intentional:
        # 候选人主动结束 → 正常收尾
        self._fsm.transition(InterviewEvent.CANDIDATE_DISCONNECT)
        await self._finalize_session()
    else:
        # 网络意外断开 → 保留状态，等待重连
        if self._session:
            self._session.status = self._fsm.state.value  # 保留当前阶段
            await self._persist_state()
        logger.info(f"Session {self.session_id} disconnected, state preserved for reconnect")

    @property
    def is_reconnectable(self) -> bool:
        """Whether this session can be resumed after a disconnect."""
        return (
            self._fsm.is_active 
            and self._session is not None 
            and self._session.status not in (InterviewState.DONE.value,)
        )
```

#### 1.2.2 修改 `backend/app/core/agent.py` — 新增恢复方法

```python
async def resume(self) -> None:
    """Resume an interrupted interview from persisted state."""
    self._session = await self._get_session()
    if self._session is None:
        await self._send_error("Session not found")
        return

    # 恢复 FSM 到持久化的状态
    current_state = InterviewState(self._session.status)
    self._fsm._state = current_state  # 直接设置（跳过 transition 校验，因为这是恢复）

    # 恢复子状态
    if self._session.qa_substate:
        self._qa_substate = QASubState(self._session.qa_substate)
    self._follow_up_count = self._session.follow_up_count or 0

    # 发送重连确认
    await self._send_message("interview.resume", {
        "session_id": self.session_id,
        "current_state": current_state.value,
        "qa_substate": self._qa_substate.value if self._qa_substate else None,
        "question_index": self._session.current_question_index,
        "total_questions": self._session.total_questions,
    })

    # 根据当前状态恢复
    if current_state == InterviewState.INTRO:
        # 重新发送开场白
        intro_text = self._conversation.last_message.content if self._conversation.last_message else None
        if intro_text:
            await self._send_message("interview.chat", {"content": intro_text})
    elif current_state == InterviewState.QA_LOOP:
        if self._qa_substate in (QASubState.ASKING, QASubState.FOLLOWING_UP):
            # 如果有当前题目，重新发送
            await self._resend_current_question()
```

#### 1.2.3 修改 `backend/app/api/ws_interview.py` — 支持重连

```python
@router.websocket("/ws/interview/{session_id}")
async def ws_interview(websocket: WebSocket, session_id: str) -> None:
    # ... 现有的 token 验证保持不变 ...

    await websocket.accept()
    
    # 检查是否为重连
    async with async_session_factory() as check_db:
        stmt = select(InterviewSession).where(InterviewSession.id == session_id)
        session = (await check_db.execute(stmt)).scalar_one_or_none()
        is_reconnect = session and session.status not in ("idle", "done")

    llm = _create_llm_adapter()
    question_bank = _get_question_bank()  # 注：重连时用新实例，状态从 DB 恢复

    async with async_session_factory() as db:
        agent = InterviewAgent(
            session_id=session_id, websocket=websocket,
            db=db, llm=llm, question_service=question_bank,
        )

        try:
            if is_reconnect:
                await agent.resume()  # 从断点恢复
            else:
                await agent.start()   # 正常启动

            # 主消息循环（与现有一致）
            while agent._fsm.is_active:
                try:
                    raw = await websocket.receive_text()
                    message = json.loads(raw)
                    await agent.handle_message(message)
                except WebSocketDisconnect:
                    # 网络断开 → 保留状态（非 intentional）
                    await agent.on_disconnect(intentional=False)
                    return
                # ... 其余异常处理 ...
        except WebSocketDisconnect:
            await agent.on_disconnect(intentional=False)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
```

#### 1.2.4 前端适配 — 修改 `frontend/src/hooks/use-websocket.ts`

在消息分派中增加 `interview.resume` 处理：

```typescript
// 在 dispatch 函数中增加：
case "interview.resume":
  store.setSession(payload.session_id, payload.total_questions);
  store.setConnectionState("connected");
  store.setInterviewStatus(payload.current_state);
  store.setQuestionIndex(payload.question_index);
  // 如果当前有题目，重新显示
  if (payload.last_question) {
    store.setCurrentQuestion(payload.last_question);
  }
  break;
```

并在重连逻辑中将 `command.resume` 替换为等待服务端主动推送状态：

```typescript
// 重连时不再发送额外命令，由后端 resume() 主动推送状态
const connect = useCallback(() => {
  // ... 现有连接逻辑 ...
  // 移除原有的 command.resume 发送逻辑
  // 后端会在 WebSocket 连接成功后自动调用 agent.resume()
}, [sessionId]);
```

---

### 1.3 超时机制

**问题**：`InterviewEvent.TIME_UP` 已定义但从未触发，`answer_timeout_seconds=120` 配置未使用。

**措施**：在 agent 中增加每题超时 + 总面试超时两个定时器。

#### 1.3.1 修改 `backend/app/core/agent.py` — 增加超时管理

```python
import asyncio

class InterviewAgent:
    # 在 __init__ 中增加字段（见 1.1.2a）
    
    def _start_answer_timeout(self) -> None:
        """Start per-question answer timeout timer."""
        self._cancel_answer_timeout()
        timeout_seconds = settings.answer_timeout_seconds  # 默认 120s
        
        async def _timeout():
            await asyncio.sleep(timeout_seconds)
            if self._qa_substate in (QASubState.ASKING, QASubState.FOLLOWING_UP):
                logger.warning(f"Answer timeout for session {self.session_id}")
                # 发送超时提示
                await self._send_message("interview.chat", {
                    "content": get_prompt("timeout_warning", self._lang)
                })
                # 再等 30 秒最后机会
                await asyncio.sleep(30)
                if self._qa_substate in (QASubState.ASKING, QASubState.FOLLOWING_UP):
                    # 强制跳过
                    await self._handle_skip()
        
        self._answer_timeout_task = asyncio.create_task(_timeout())
    
    def _cancel_answer_timeout(self) -> None:
        """Cancel the current answer timeout timer."""
        if self._answer_timeout_task and not self._answer_timeout_task.done():
            self._answer_timeout_task.cancel()
            self._answer_timeout_task = None
    
    def _start_total_timeout(self) -> None:
        """Start total interview duration timeout."""
        total_seconds = self._session.total_questions * 180  # 每题3分钟
        
        async def _total_timeout():
            await asyncio.sleep(total_seconds)
            if self._fsm.is_active:
                logger.warning(f"Total timeout for session {self.session_id}")
                self._fsm.transition(InterviewEvent.TIME_UP)
                await self._start_wrapup()
        
        self._total_timeout_task = asyncio.create_task(_total_timeout())
```

#### 1.3.2 修改 `backend/app/llm/prompts/interviewer.py` — 新增超时提示

在 `PROMPTS` 字典中增加：

```python
"timeout_warning": {
    "en": "I notice you might need more time. Please provide your answer or let me know if you'd like to skip this question.",
    "zh": "我注意到你可能需要更多时间。请提供你的回答，或者告诉我你想跳过这道题。",
},
```

#### 1.3.3 在 `start()` 中启动总超时

```python
async def start(self) -> None:
    # ... 现有逻辑 ...
    self._start_total_timeout()  # 新增
```

#### 1.3.4 在 `_finalize_session()` 中清理

```python
async def _finalize_session(self) -> None:
    self._cancel_answer_timeout()
    if hasattr(self, '_total_timeout_task') and self._total_timeout_task:
        self._total_timeout_task.cancel()
    # ... 其余逻辑 ...
```

---

### 1.4 面试官实时观察

**问题**：面试官无法实时观看面试过程，只能等结束后看报告。面试过程是"黑盒"。

**措施**：新增 Observer WebSocket 端点，面试官 Dashboard 连接后实时接收面试事件流。

#### 1.4.1 新增 `backend/app/api/ws_observer.py`

```python
"""WebSocket endpoint for interviewer real-time observation."""

import json
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.database import async_session_factory
from app.models.session import InterviewSession

logger = logging.getLogger(__name__)
router = APIRouter(tags=["observer"])

# In-memory registry: session_id -> set of observer WebSockets
_observers: dict[str, set[WebSocket]] = {}


def register_observer(session_id: str, ws: WebSocket) -> None:
    _observers.setdefault(session_id, set()).add(ws)


def unregister_observer(session_id: str, ws: WebSocket) -> None:
    if session_id in _observers:
        _observers[session_id].discard(ws)
        if not _observers[session_id]:
            del _observers[session_id]


async def broadcast_to_observers(session_id: str, message: dict) -> None:
    """Send a message to all observers of a session."""
    if session_id not in _observers:
        return
    dead: list[WebSocket] = []
    payload = json.dumps(message)
    for ws in _observers[session_id]:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _observers[session_id].discard(ws)


@router.websocket("/ws/observe/{session_id}")
async def ws_observe(websocket: WebSocket, session_id: str) -> None:
    """Observer endpoint — receives real-time interview events. Requires admin token."""
    qs = parse_qs(websocket.scope.get("query_string", b"").decode())
    token = qs.get("token", [None])[0]

    async with async_session_factory() as db:
        result = await db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session or token != session.admin_token:
            await websocket.close(code=4003, reason="Forbidden")
            return

    await websocket.accept()
    register_observer(session_id, websocket)
    logger.info(f"Observer connected for session {session_id}")

    try:
        # 发送当前快照
        if session:
            await websocket.send_text(json.dumps({
                "type": "observer.snapshot",
                "payload": {
                    "status": session.status,
                    "question_index": session.current_question_index,
                    "total_questions": session.total_questions,
                    "candidate_name": session.candidate_name,
                    "job_title": session.job_title,
                },
                "timestamp": "",
            }))

        # 保持连接，静默接收广播
        while True:
            # 只监听断开，不从客户端接收数据
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unregister_observer(session_id, websocket)
```

#### 1.4.2 修改 `backend/app/core/agent.py` — 在关键事件点广播

在 `_send_message()` 方法中增加 observer 广播：

```python
async def _send_message(self, msg_type: str, payload: dict) -> None:
    """Send a structured WebSocket message to the client AND observers."""
    try:
        msg = WSMessage(type=msg_type, payload=payload)
        raw = msg.model_dump_json()
        await self._ws.send_text(raw)

        # 广播给观察者（仅发送非敏感的面试事件）
        from app.api.ws_observer import broadcast_to_observers
        if msg_type in OBSERVER_EVENTS:
            await broadcast_to_observers(self.session_id, json.loads(raw))
    except Exception as e:
        logger.error(f"Failed to send WS message '{msg_type}': {e}")

# 模块级常量：哪些事件推送给观察者
OBSERVER_EVENTS = {
    "interview.start", "interview.chat", "interview.question",
    "interview.evaluation", "interview.end",
}
```

#### 1.4.3 注册路由 — 修改 `backend/app/api/__init__.py`

```python
from app.api.ws_observer import router as observer_router

# 在主应用中注册
app.include_router(observer_router)
```

#### 1.4.4 前端适配 — Dashboard 增加实时监控组件

在 `frontend/src/components/dashboard/` 下新增 `LiveObserver.tsx`：

```tsx
// 核心逻辑：
// 1. 对每个活跃会话建立 /ws/observe/{sessionId}?token=admin_token 连接
// 2. 收到 observer.snapshot 显示当前进度
// 3. 收到 interview.question / interview.evaluation 实时更新进度条
// 4. 收到 interview.end 标记该会话为"可查看报告"
```

---

## P2：LLM 接管核心决策

### 2.1 多维评分 + 追问决策

**问题**：评分仅返回 1-5 总分，无维度拆分；无追问机制，每题只问一次。

**措施**：扩展评分 prompt 输出多维评分 + 追问决策字段，在 agent 中实现追问循环。

#### 2.1.1 修改 `backend/app/schemas/evaluation.py` — 扩展 Schema

```python
from pydantic import BaseModel, Field

class EvaluationDimension(BaseModel):
    technical_accuracy: int = Field(ge=1, le=5, default=3)
    depth_of_knowledge: int = Field(ge=1, le=5, default=3)
    communication: int = Field(ge=1, le=5, default=3)
    problem_solving: int = Field(ge=1, le=5, default=3)


class EvaluationResult(BaseModel):
    # 现有字段
    score: int = Field(ge=1, le=5)
    comment: str = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    matched_keywords: list[str] = []
    missing_points: list[str] = []

    # 新增字段
    dimensions: EvaluationDimension | None = None
    need_follow_up: bool = False
    follow_up_questions: list[str] = []
    follow_up_rationale: str = ""
    candidate_confidence: str = "normal"  # confident | nervous | struggling | evasive


class AnswerReport(BaseModel):
    # 现有字段保持不变，新增：
    dimensions: EvaluationDimension | None = None
    had_follow_up: bool = False


class SessionReport(BaseModel):
    # 现有字段保持不变，新增：
    dimension_averages: EvaluationDimension | None = None
    recommendation: str | None = None  # strong_hire | hire | cautious_hire | no_hire
    recommendation_reasoning: str | None = None
    narrative_summary: str | None = None
```

#### 2.1.2 修改 `backend/app/llm/prompts/scoring.py` — 扩展评分 Prompt

完整替换 `SCORING_PROMPT_EN` 和 `SCORING_PROMPT_ZH`：

```python
SCORING_PROMPT_EN = """You are evaluating a candidate's answer in a technical job interview. Be strict but fair.

Context:
- Question: {question_text}
- Category: {category}
- Difficulty Level: {difficulty}
- Expected Keywords: {expected_keywords}

Candidate's Answer:
{candidate_answer}

Evaluation Rubric (1-5 scale per dimension):
1-Poor / 2-Below Average / 3-Average / 4-Good / 5-Excellent

Score each dimension independently:

**technical_accuracy** (1-5): Is the technical content correct? Are concepts accurately applied?
**depth_of_knowledge** (1-5): Does the answer show deep understanding beyond surface-level? Are trade-offs discussed?
**communication** (1-5): Is the answer well-structured, clear, and concise?
**problem_solving** (1-5): Does the candidate demonstrate a logical approach? Consider edge cases?

Answer quality assessment:
- If score >= 4 in all dimensions: no follow-up needed, move on
- If score is 2-3 with specific gaps: ask 1 targeted follow-up to probe deeper
- If score is 1: no follow-up (candidate clearly doesn't know), move on

Candidate's apparent state: "confident" | "nervous" | "struggling" | "evasive"
- "evasive": answer is vague, avoiding specifics
- "struggling": trying but getting concepts wrong
- "nervous": correct but hesitant

Output ONLY a valid JSON object (no code fences, no additional text):
{{
  "score": <integer 1-5, weighted average of dimensions>,
  "dimensions": {{
    "technical_accuracy": <1-5>,
    "depth_of_knowledge": <1-5>,
    "communication": <1-5>,
    "problem_solving": <1-5>
  }},
  "comment": "<1-2 sentences summarizing the evaluation>",
  "strengths": ["<specific strength>", ...],
  "weaknesses": ["<specific gap>", ...],
  "matched_keywords": ["<keyword covered>", ...],
  "missing_points": ["<important point not addressed>", ...],
  "need_follow_up": <true | false>,
  "follow_up_questions": ["<a specific follow-up question>", ...],
  "follow_up_rationale": "<why follow-up is needed, one sentence>",
  "candidate_confidence": "normal"
}}"""

SCORING_PROMPT_ZH = """你正在评估一场技术面试中候选人的回答。请严格但公平地评分。

上下文：
- 问题：{question_text}
- 类别：{category}
- 难度：{difficulty}
- 期望关键词：{expected_keywords}

候选人回答：
{candidate_answer}

评分标准（每个维度 1-5 分）：

**technical_accuracy（技术准确性）**：技术内容是否正确？概念是否准确应用？
**depth_of_knowledge（知识深度）**：回答是否展示表面之外的深度理解？是否讨论了权衡？
**communication（沟通表达）**：回答是否结构清晰、简洁明了？
**problem_solving（问题解决）**：候选人是否展示了逻辑方法？是否考虑了边界情况？

回答质量评估：
- 所有维度 >= 4 分：无需追问，进入下一题
- 得分 2-3 且有明确知识缺口：提出 1 个有针对性的追问
- 得分 1：无需追问（候选人显然不了解），直接进入下一题

候选人状态：confident（自信）| nervous（紧张）| struggling（困难）| evasive（回避）

只输出有效的 JSON 对象（不要用代码块，不要加额外文字）：
{{
  "score": <整数 1-5，各维度加权平均>,
  "dimensions": {{
    "technical_accuracy": <1-5>,
    "depth_of_knowledge": <1-5>,
    "communication": <1-5>,
    "problem_solving": <1-5>
  }},
  "comment": "<1-2句话总结评估，使用中文>",
  "strengths": ["<具体的优点>", ...],
  "weaknesses": ["<具体的不足>", ...],
  "matched_keywords": ["<命中的期望关键词>", ...],
  "missing_points": ["<遗漏的重要知识点>", ...],
  "need_follow_up": <true | false>,
  "follow_up_questions": ["<具体的追问问题>", ...],
  "follow_up_rationale": "<为什么需要追问，一句话>",
  "candidate_confidence": "normal"
}}"""
```

#### 2.1.3 修改 `backend/app/core/evaluator.py` — 解析新字段

在 `_build_result()` 方法中增加新字段解析：

```python
def _build_result(self, data: dict) -> EvaluationResult:
    score = data.get("score", 3)
    try:
        score = int(score)
        score = max(1, min(5, score))
    except (ValueError, TypeError):
        score = 3

    # 解析维度评分
    dimensions = None
    dims_raw = data.get("dimensions")
    if isinstance(dims_raw, dict):
        try:
            from app.schemas.evaluation import EvaluationDimension
            dimensions = EvaluationDimension(
                technical_accuracy=int(dims_raw.get("technical_accuracy", 3)),
                depth_of_knowledge=int(dims_raw.get("depth_of_knowledge", 3)),
                communication=int(dims_raw.get("communication", 3)),
                problem_solving=int(dims_raw.get("problem_solving", 3)),
            )
        except Exception:
            pass

    return EvaluationResult(
        score=score,
        comment=data.get("comment", "No evaluation available."),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        matched_keywords=data.get("matched_keywords", []),
        missing_points=data.get("missing_points", []),
        # 新增
        dimensions=dimensions,
        need_follow_up=bool(data.get("need_follow_up", False)),
        follow_up_questions=data.get("follow_up_questions", []),
        follow_up_rationale=data.get("follow_up_rationale", ""),
        candidate_confidence=data.get("candidate_confidence", "normal"),
    )
```

#### 2.1.4 修改 `backend/app/core/agent.py` — 实现追问循环

重写 `_evaluate_and_continue()` 方法：

```python
async def _evaluate_and_continue(self, answer_text: str) -> None:
    """Evaluate the answer. If follow-up needed, ask it; otherwise next question."""
    if not self._current_question_id or not self._session:
        return

    question = await self._get_current_question()
    if question is None:
        return

    # 评分
    self._qa_substate = QASubState.EVALUATING
    await self._persist_state()

    evaluation = await self._evaluator.evaluate(
        QuestionData(
            question_text=question.question_text,
            category=question.category,
            difficulty=question.difficulty,
            expected_keywords=question.expected_keywords or [],
        ),
        answer_text,
        language=self._lang,
    )

    # 存储回答（包含维度数据）
    answer = Answer(
        question_id=question.id,
        session_id=self.session_id,
        content=answer_text,
        score=evaluation.score,
        score_comment=evaluation.comment,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses,
        matched_keywords=evaluation.matched_keywords,
        missing_points=evaluation.missing_points,
        llm_evaluation_raw={
            "score": evaluation.score,
            "comment": evaluation.comment,
            "dimensions": evaluation.dimensions.model_dump() if evaluation.dimensions else None,
            "strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
            "matched_keywords": evaluation.matched_keywords,
            "missing_points": evaluation.missing_points,
            "need_follow_up": evaluation.need_follow_up,
            "candidate_confidence": evaluation.candidate_confidence,
        },
    )
    self._db.add(answer)
    question.status = "answered"
    await self._db.commit()

    # 难度调整（基于维度评分，比单分数更准确）
    self._questions.update_difficulty(evaluation.score)

    # ── 追问决策 ──
    if (
        evaluation.need_follow_up
        and evaluation.follow_up_questions
        and self._follow_up_count < self._max_follow_ups
    ):
        self._follow_up_count += 1
        follow_up_q = evaluation.follow_up_questions[0]

        self._qa_substate = QASubState.FOLLOWING_UP
        await self._persist_state()

        # 用 LLM 将追问包装为自然对话
        try:
            wrapped = await self._llm.generate(
                prompt=get_prompt("follow_up_wrap", self._lang,
                                  original_question=question.question_text,
                                  candidate_answer=answer_text[:500],
                                  follow_up_question=follow_up_q,
                                  follow_up_rationale=evaluation.follow_up_rationale),
                system_prompt=self._build_system_prompt(),
                max_tokens=200,
                temperature=0.7,
            )
        except Exception:
            wrapped = follow_up_q

        self._conversation.add_message("interviewer", wrapped)
        await self._send_message("interview.follow_up", {
            "question_id": self._current_question_id,
            "content": wrapped,
            "follow_up_number": self._follow_up_count,
        })
        self._start_answer_timeout()
        return

    # ── 无追问 → 下一题 ──
    # 发送简短反馈
    strength_str = "; ".join(evaluation.strengths[:2]) if evaluation.strengths else "Good effort."
    await self._send_message("interview.evaluation", {"feedback": strength_str})

    self._follow_up_count = 0
    self._qa_substate = QASubState.FEEDBACK_GIVEN
    await self._persist_state()

    await self._ask_next_question()
```

#### 2.1.5 修改 `backend/app/llm/prompts/interviewer.py` — 新增追问 Prompt

```python
"follow_up_wrap": {
    "en": (
        "You asked the candidate this question:\n"
        '"{original_question}"\n\n'
        "The candidate answered (summarized):\n"
        '"{candidate_answer}"\n\n'
        "You want to follow up with this question to probe deeper:\n"
        '"{follow_up_question}"\n\n'
        "Rationale: {follow_up_rationale}\n\n"
        "Naturally ask the follow-up question. Be encouraging but direct. "
        "Output only what you would say, no meta-commentary."
    ),
    "zh": (
        "你向候选人提了这个问题：\n"
        '"{original_question}"\n\n'
        "候选人回答（摘要）：\n"
        '"{candidate_answer}"\n\n'
        "你想追问以下问题以深入了解：\n"
        '"{follow_up_question}"\n\n'
        "追问理由：{follow_up_rationale}\n\n"
        "自然地提出追问。语气要鼓励但直接。只输出你要说的话。"
    ),
},
```

#### 2.1.6 新增 `backend/app/models/answer.py` 字段（如需持久化维度）

当前 `llm_evaluation_raw` 已是 JSON 列，维度数据会自动存储在其中。但如果需要结构化查询，可在 Answer 模型中增加：

```python
# 可选：增加结构化维度列
dimension_technical = Column(Integer, nullable=True)
dimension_depth = Column(Integer, nullable=True)
dimension_communication = Column(Integer, nullable=True)
dimension_problem_solving = Column(Integer, nullable=True)
had_follow_up = Column(Boolean, default=False)
```

---

### 2.2 上下文感知选题

**问题**：选题用 `random.choice()`，题目之间无逻辑关联，不考虑候选人已展现的强弱项。

**措施**：新增 LLM 选题方法，作为随机选题的升级替代；选题 prompt 传入对话历史和评分记录。

#### 2.2.1 修改 `backend/app/services/question_bank.py` — 新增 LLM 选题方法

```python
async def select_question_with_context(
    self,
    llm,  # BaseLLMAdapter
    conversation_context: str,
    previous_scores: list[dict],  # [{"question": "...", "score": 4, "category": "backend"}, ...]
    interviewer_lang: str = "en",
) -> QuestionData | None:
    """Let LLM choose the most contextually appropriate next question.
    
    Falls back to random selection if LLM is unavailable or pool is small.
    """
    pool = self._get_filtered_pool_with_indices()
    if len(pool) <= 2:
        # 池子太小，无需 LLM
        if pool:
            index, question = random.choice(pool)
            self._used_indices.add(index)
            return question
        return None

    # 构建选题 prompt
    questions_text = "\n".join(
        f"[{i}] [{q.difficulty}] [{q.category}] {q.question_text}"
        for i, (_, q) in enumerate(pool[:15])  # 最多给 15 道候选
    )

    scores_text = "\n".join(
        f"- Q: {s['question'][:80]}... → Score: {s['score']}/5 ({s['category']})"
        for s in previous_scores[-5:]  # 最近 5 题
    ) if previous_scores else "(first question)"

    prompt = (
        "You are selecting the next interview question. Choose the ONE question "
        "that best evaluates the candidate based on their performance so far.\n\n"
        f"Previous performance:\n{scores_text}\n\n"
        f"Recent conversation context:\n{conversation_context[:500]}\n\n"
        f"Available questions (choose by index):\n{questions_text}\n\n"
        "Selection principles:\n"
        "- If recent scores are high, increase difficulty slightly\n"
        "- If a category was answered weakly, probe a related topic\n"
        "- Avoid asking two very similar questions in a row\n"
        "- Prioritize uncovering unknown areas over confirming known strengths\n\n"
        "Respond ONLY with a JSON object:\n"
        '{"selected_index": <integer>, "rationale": "<one sentence>"}'
    )

    try:
        response = await llm.generate(
            prompt=prompt,
            system_prompt="You are an expert technical interviewer designing an adaptive interview sequence.",
            max_tokens=150,
            temperature=0.3,
        )
        parsed = self._parse_selection_json(response)
        if parsed and 0 <= parsed["selected_index"] < len(pool):
            index, question = pool[parsed["selected_index"]]
            self._used_indices.add(index)
            logger.info(f"LLM selected question index={index}, rationale: {parsed.get('rationale')}")
            return question
    except Exception as e:
        logger.warning(f"LLM question selection failed: {e}, falling back to random")

    # Fallback: random
    if pool:
        index, question = random.choice(pool)
        self._used_indices.add(index)
        return question
    return None


def _get_filtered_pool_with_indices(self) -> list[tuple[int, QuestionData]]:
    """Get filtered pool with original indices (same logic as select_question)."""
    target_difficulty = self._current_difficulty
    pool = [
        (i, q) for i, q in enumerate(self._questions)
        if i not in self._used_indices and q.difficulty == target_difficulty
    ]
    if not pool:
        pool = [
            (i, q) for i, q in enumerate(self._questions)
            if i not in self._used_indices
        ]
    return pool


@staticmethod
def _parse_selection_json(raw: str) -> dict | None:
    import re
    raw = raw.strip()
    # Remove code fences
    m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
    if m:
        raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None
```

#### 2.2.2 修改 `backend/app/core/agent.py` — `_ask_next_question()` 接入 LLM 选题

```python
async def _ask_next_question(self) -> None:
    if not self._session:
        return

    idx = self._session.current_question_index
    if idx >= self._session.total_questions:
        await self._start_wrapup()
        return

    # ── 上下文感知选题 ──
    # 收集已有评分记录
    previous_scores = await self._get_previous_scores()
    conversation_context = self._conversation.format_window_for_llm()

    q_data = await self._questions.select_question_with_context(
        llm=self._llm,
        conversation_context=conversation_context,
        previous_scores=previous_scores,
        interviewer_lang=self._lang,
    )
    if q_data is None:
        await self._start_wrapup()
        return

    # ... 后续创建 Question 记录、包装、发送逻辑保持不变 ...


async def _get_previous_scores(self) -> list[dict]:
    """Get previous question scores for context-aware selection."""
    if not self._session:
        return []
    stmt = (
        select(Question, Answer)
        .join(Answer, Question.id == Answer.question_id, isouter=True)
        .where(Question.session_id == self.session_id)
        .order_by(Question.order_index)
    )
    result = await self._db.execute(stmt)
    scores = []
    for q, a in result:
        scores.append({
            "question": q.question_text,
            "score": a.score if a else None,
            "category": q.category,
            "difficulty": q.difficulty,
        })
    return scores
```

---

### 2.3 LLM 叙事报告 + 录用建议

**问题**：报告只是简单聚合（均分 + 逐题展示），录用判断依赖前端 `avg >= 3.5` 的硬编码规则。

**措施**：新增 LLM 驱动的综合报告生成，输出叙事性总结、维度分析、录用建议及推理。

#### 2.3.1 新增 `backend/app/llm/prompts/report.py`

```python
REPORT_PROMPT_EN = """You are a senior technical hiring manager reviewing an interview. Write a comprehensive evaluation report.

Candidate: {candidate_name}
Position: {job_title} ({experience_level})
Interview Language: {language}
Questions Asked: {total_questions} | Answered: {answered_count}

Question-by-Question Summary:
{q_and_a_summary}

Overall Metrics:
- Average Score: {average_score}/5
- Dimension Averages: Technical Accuracy {dim_tech}/5, Depth {dim_depth}/5, Communication {dim_comm}/5, Problem Solving {dim_solve}/5

Write a structured report. Output ONLY a valid JSON object:
{{
  "narrative_summary": "<2-3 paragraph narrative evaluation of the candidate. Include: overall impression, standout moments, concerning patterns.>",
  "recommendation": "<strong_hire | hire | cautious_hire | no_hire>",
  "recommendation_reasoning": "<detailed reasoning for the recommendation, referencing specific answers and scores>",
  "key_strengths": ["<strength 1 with evidence>", ...],
  "key_risks": ["<risk 1 with evidence>", ...],
  "suggested_next_steps": "<what should happen next — another interview round? specific focus area? offer?>",
  "overall_band": "<junior | mid | senior> — what level does this candidate actually operate at, regardless of their claimed level?"
}}"""

REPORT_PROMPT_ZH = """你是一位资深技术招聘经理，正在审阅一场面试。请撰写一份全面的评估报告。

候选人：{candidate_name}
岗位：{job_title}（{experience_level}）
问题数：{total_questions} | 已答：{answered_count}

逐题摘要：
{q_and_a_summary}

总体指标：
- 平均分：{average_score}/5
- 维度均分：技术准确性 {dim_tech}/5，知识深度 {dim_depth}/5，沟通表达 {dim_comm}/5，问题解决 {dim_solve}/5

请撰写一份结构化报告。只输出有效的 JSON 对象（使用中文）：
{{
  "narrative_summary": "<2-3段叙事性评价。包含：整体印象、突出表现、值得关注的模式。使用中文>",
  "recommendation": "<strong_hire（强烈推荐）| hire（推荐）| cautious_hire（谨慎推荐）| no_hire（不推荐）>",
  "recommendation_reasoning": "<推荐理由的详细说明，引用具体的回答和分数>",
  "key_strengths": ["<优势1 + 具体例证>", ...],
  "key_risks": ["<风险1 + 具体例证>", ...],
  "suggested_next_steps": "<下一步建议：加面？特定领域考察？发offer？>",
  "overall_band": "<junior | mid | senior> — 无论候选人声称的级别如何，其实际水平属于哪个级别？"
}}"""


def get_report_prompt(language: str = "en") -> str:
    return REPORT_PROMPT_ZH if language == "zh" else REPORT_PROMPT_EN
```

#### 2.3.2 修改 `backend/app/services/report.py` — 新增 LLM 报告方法

```python
from app.llm.prompts.report import get_report_prompt


class ReportService:

    # 保留原有 build_report() 作为轻量版本

    @staticmethod
    async def build_narrative_report(
        session_id: str, db: AsyncSession, llm
    ) -> dict | None:
        """Generate a comprehensive LLM-powered narrative report."""
        # 1. 先用原有方法收集基础数据
        base_report = await ReportService.build_report(session_id, db)
        if base_report is None:
            return None

        # 2. 构建问答摘要
        qa_lines = []
        for i, ans in enumerate(base_report.answers):
            score_str = f"{ans.score}/5" if ans.score else "N/A"
            comment_str = ans.score_comment or "No comment"
            qa_lines.append(
                f"Q{i+1} [{ans.difficulty}][{ans.category}]: {ans.question_text[:150]}...\n"
                f"  Answer: {ans.answer_content[:200] if ans.answer_content else '(no answer)'}\n"
                f"  Score: {score_str} — {comment_str}"
            )
        qa_summary = "\n\n".join(qa_lines)

        # 3. 计算维度均分（如果有多维数据）
        dim_tech = dim_depth = dim_comm = dim_solve = base_report.average_score or 3

        # 4. 调用 LLM 生成叙事报告
        prompt = get_report_prompt(base_report.session_id and "en" or "en").format(
            candidate_name=base_report.candidate_name,
            job_title=base_report.job_title,
            experience_level=base_report.experience_level,
            language="en",
            total_questions=base_report.total_questions,
            answered_count=base_report.answered_count,
            q_and_a_summary=qa_summary,
            average_score=f"{base_report.average_score:.1f}" if base_report.average_score else "N/A",
            dim_tech=dim_tech,
            dim_depth=dim_depth,
            dim_comm=dim_comm,
            dim_solve=dim_solve,
        )

        try:
            response = await llm.generate(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.5,
            )
            narrative = ReportService._parse_narrative_json(response)
        except Exception:
            narrative = {
                "narrative_summary": "Report generation failed. Please review manually.",
                "recommendation": None,
                "recommendation_reasoning": "",
                "key_strengths": [],
                "key_risks": [],
                "suggested_next_steps": "",
                "overall_band": None,
            }

        # 5. 合并基础报告和叙事报告
        return {
            **base_report.model_dump(),
            **narrative,
        }

    @staticmethod
    def _parse_narrative_json(raw: str) -> dict:
        import re, json
        raw = raw.strip()
        m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
        if m:
            raw = m.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return {"narrative_summary": raw, "recommendation": None}
```

#### 2.3.3 修改 `backend/app/api/rest_sessions.py` — 新增叙事报告端点

```python
@router.get("/api/sessions/{session_id}/report/narrative")
async def get_narrative_report(
    session_id: str,
    token: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get an LLM-powered narrative interview report. Requires admin token."""
    # 验证 admin token
    verify_admin_token(session_id, token, db)  # 使用已有的认证逻辑

    llm = _create_llm_adapter()
    report = await ReportService.build_narrative_report(session_id, db, llm)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report
```

---

### 2.4 LLM 意图检测

**问题**：意图检测使用关键词启发式（[conversation.py:53-90](backend/app/core/conversation.py)），已有 LLM fallback 代码（[intent.py](backend/app/llm/prompts/intent.py)）但从未调用。

**措施**：在关键词检测不确定时启用 LLM 意图检测作为二级判断。

#### 2.4.1 修改 `backend/app/core/conversation.py` — 增加混合检测

```python
from app.llm.prompts.intent import detect_intent_fallback

class ConversationManager:
    def __init__(self, ..., llm=None):
        ...
        self._llm = llm  # 新增：可选 LLM 引用

    async def detect_intent_hybrid(self, message: str) -> IntentType:
        """
        Two-tier intent detection:
        1. Fast keyword heuristic (low latency)
        2. LLM fallback for ambiguous cases (high accuracy)
        """
        # Tier 1: keyword heuristic
        result = self.detect_intent(message)

        # If high-confidence keyword match, return immediately
        if result != IntentType.ANSWER:
            return result

        # Tier 2: for ANSWER result, verify with LLM if:
        # - Message is very short (could be a command)
        # - Message contains question marks (could be a clarification)
        # - LLM is available
        msg = message.strip()
        ambiguous = len(msg) < 20 or "?" in msg

        if ambiguous and self._llm:
            try:
                context = self.format_window_for_llm()
                llm_result = await detect_intent_fallback(
                    self._llm.generate, message, context
                )
                confidence = llm_result.get("confidence", 0.5)
                intent_str = llm_result.get("intent", "answer")

                if confidence > 0.7 and intent_str != "answer":
                    return IntentType(intent_str)
            except Exception:
                pass  # LLM fallback failed, stick with keyword result

        return result
```

#### 2.4.2 修改 `backend/app/core/agent.py` — `__init__` 中传入 LLM

```python
# 在 __init__ 中
self._conversation = ConversationManager(llm=llm)  # 传入 LLM 引用
```

#### 2.4.3 修改 `backend/app/core/agent.py` — 使用混合检测

```python
async def _handle_qa(self, raw: dict) -> None:
    # ... 现有逻辑 ...
    
    # 将 intent = self._conversation.detect_intent(content)
    # 替换为：
    intent = await self._conversation.detect_intent_hybrid(content)
```

---

## P3：全自动化增强

### 3.1 JD 分析自动配置

**问题**：创建面试时需手动填写所有参数（岗位、技能、经验级别），高度依赖面试官对岗位的理解。

**措施**：新增 JD 分析服务，面试官粘贴 JD 文本即可自动生成面试配置建议。

#### 3.1.1 新增 `backend/app/services/jd_analyzer.py`

```python
"""Job Description analysis service — extracts structured interview config from JD text."""

import json
import re
import logging

from app.llm.base import BaseLLMAdapter

logger = logging.getLogger(__name__)

JD_ANALYSIS_PROMPT = """Analyze the following job description and extract structured interview configuration.

Job Description:
{jd_text}

Extract and infer the following. Output ONLY a valid JSON object:
{{
  "job_title": "<standardized job title, e.g. 'Senior Backend Engineer'>",
  "experience_level": "<junior | mid | senior>",
  "key_skills": ["<skill1>", "<skill2>", ...],  // top 5-8 most important skills
  "suggested_categories": ["<category1>", ...],  // from: backend, frontend, general, devops, ai_ml
  "suggested_total_questions": <integer 3-10>,
  "focus_areas": ["<area1>", ...],  // specific topics to emphasize
  "interview_hints": "<1-2 sentences of guidance for the AI interviewer about what to focus on>"
}}

Rules:
- Infer experience_level from years required: 0-2→junior, 3-5→mid, 6+→senior
- key_skills should be specific technologies/concepts (e.g. "Python", "Distributed Systems", "Kubernetes")
- suggested_total_questions: 3-5 for junior, 5-7 for mid, 7-10 for senior
- suggested_categories should align with the role (backend role → primarily backend + general)
- interview_hints should guide the AI interviewer on what matters most for this role"""


class JDAnalyzer:
    """Analyzes job descriptions using LLM to auto-configure interviews."""

    def __init__(self, llm: BaseLLMAdapter):
        self._llm = llm

    async def analyze(self, jd_text: str) -> dict:
        """Analyze JD text and return structured interview config."""
        if not jd_text or len(jd_text.strip()) < 50:
            return self._fallback_result()

        prompt = JD_ANALYSIS_PROMPT.format(jd_text=jd_text[:3000])

        try:
            response = await self._llm.generate(
                prompt=prompt,
                max_tokens=600,
                temperature=0.3,
            )
            result = self._parse_response(response)
            if result:
                return result
        except Exception as e:
            logger.warning(f"JD analysis failed: {e}")

        return self._fallback_result()

    def _parse_response(self, raw: str) -> dict | None:
        raw = raw.strip()
        m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
        if m:
            raw = m.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    def _fallback_result(self) -> dict:
        return {
            "job_title": "Software Engineer",
            "experience_level": "mid",
            "key_skills": [],
            "suggested_categories": ["general"],
            "suggested_total_questions": 5,
            "focus_areas": [],
            "interview_hints": "",
        }
```

#### 3.1.2 新增 REST 端点 `POST /api/sessions/analyze-jd`

在 `backend/app/api/rest_sessions.py` 中增加：

```python
from pydantic import BaseModel, Field
from app.services.jd_analyzer import JDAnalyzer

class JDAnalyzeRequest(BaseModel):
    jd_text: str = Field(..., min_length=50, max_length=5000)

@router.post("/api/sessions/analyze-jd")
async def analyze_jd(request: JDAnalyzeRequest):
    """Analyze a job description and return suggested interview configuration."""
    llm = _create_llm_adapter()
    analyzer = JDAnalyzer(llm)
    result = await analyzer.analyze(request.jd_text)
    return result
```

#### 3.1.3 前端适配 — Dashboard 增加 JD 粘贴入口

在 `SessionCreateDialog.tsx` 中增加一个"粘贴 JD 自动填充"按钮，调用 `POST /api/sessions/analyze-jd`，将返回结果自动填入表单字段。

---

### 3.2 候选人状态感知

**问题**：评分 prompt 虽已返回 `candidate_confidence`（见 2.1 改造），但 agent 未根据此信息调整面试策略。

**措施**：在 agent 中根据候选人状态动态调整面试行为（语气、节奏、提示策略）。

#### 3.2.1 修改 `backend/app/core/agent.py` — 状态感知调度

在 `_evaluate_and_continue()` 评分后增加状态感知逻辑：

```python
# 在 _evaluate_and_continue() 方法内，评分完成后：

# 收集候选人状态（跨题目追踪）
self._candidate_state_history.append({
    "question_index": self._session.current_question_index - 1,
    "confidence": evaluation.candidate_confidence,
    "score": evaluation.score,
})

# 状态感知的行为调整
if evaluation.candidate_confidence == "struggling":
    # 连续两题 struggling → 降难度 + 更鼓励的语气
    recent = self._candidate_state_history[-3:]
    struggling_count = sum(1 for s in recent if s["confidence"] == "struggling")
    if struggling_count >= 2:
        self._questions.set_initial_difficulty(
            self._questions.DIFFICULTY_ORDER[
                max(0, self._questions.DIFFICULTY_ORDER.index(
                    self._questions.current_difficulty) - 1)
            ]
        )

elif evaluation.candidate_confidence == "nervous":
    # 在 system prompt 中增加安抚性引导
    self._interview_style_hint = "encouraging"  # 影响 system prompt 构建

elif evaluation.candidate_confidence == "evasive":
    # 标记，下一题加强追问
    self._interview_style_hint = "probing"

# 在 _build_system_prompt() 中使用 _interview_style_hint：
def _build_system_prompt(self) -> str:
    # ... 现有逻辑 ...
    style_hint = ""
    if self._interview_style_hint == "encouraging":
        style_hint = "\nNote: The candidate appears nervous. Be extra encouraging and patient."
    elif self._interview_style_hint == "probing":
        style_hint = "\nNote: The candidate may be avoiding specifics. Ask more pointed follow-ups."
    
    # 将 style_hint 追加到 prompt 末尾
    return base_prompt + style_hint
```

---

### 3.3 题目质量自动评估

**问题**：题库是静态 JSON，30 道题无质量反馈机制。不知道哪些题区分度好、哪些题难度标注不准确。

**措施**：每次面试结束后，LLM 分析答题数据，为每道题生成质量评估，累积后用于题库优化。

#### 3.3.1 新增 `backend/app/services/question_reviewer.py`

```python
"""Post-interview question quality review using LLM."""

import json
import re
import logging

from app.llm.base import BaseLLMAdapter

logger = logging.getLogger(__name__)

QUESTION_REVIEW_PROMPT = """Review the quality of this interview question based on how candidates answered it.

Question:
- Text: {question_text}
- Category: {category}
- Labeled Difficulty: {labeled_difficulty}

Candidate Answers Summary:
{answers_summary}

Evaluate:
1. Is the labeled difficulty accurate given how candidates performed?
2. Does this question effectively discriminate between strong and weak candidates?
3. Is the question wording clear, or did candidates frequently misunderstand it?
4. What improvements would you suggest?

Output ONLY a valid JSON object:
{{
  "difficulty_accuracy": "<accurate | too_easy | too_hard>",
  "discrimination_power": "<high | medium | low>",
  "clarity_score": <1-5>,
  "common_misunderstandings": ["<thing candidates frequently got wrong>", ...],
  "suggested_improvements": "<specific rewording or restructuring suggestion, or null if none>",
  "should_retire": <true | false>
}}"""


class QuestionReviewer:
    """Analyzes question quality based on interview results."""

    def __init__(self, llm: BaseLLMAdapter):
        self._llm = llm

    async def review_question(
        self,
        question_text: str,
        category: str,
        difficulty: str,
        answers: list[dict],  # [{"score": 3, "content": "..."}, ...]
    ) -> dict | None:
        """Review a single question based on answer data."""
        if not answers:
            return None

        answers_text = "\n".join(
            f"- Score: {a['score']}/5, Answer: {a['content'][:200]}..."
            for a in answers[-5:]  # 最近 5 次回答
        )

        prompt = QUESTION_REVIEW_PROMPT.format(
            question_text=question_text,
            category=category,
            labeled_difficulty=difficulty,
            answers_summary=answers_text,
        )

        try:
            response = await self._llm.generate(
                prompt=prompt,
                max_tokens=400,
                temperature=0.3,
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning(f"Question review failed: {e}")
            return None

    def _parse_response(self, raw: str) -> dict | None:
        raw = raw.strip()
        m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
        if m:
            raw = m.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return None
```

#### 3.3.2 修改 `backend/app/core/agent.py` — 面试结束后触发评估

在 `_finalize_session()` 末尾增加异步触发（不阻塞结束流程）：

```python
async def _finalize_session(self) -> None:
    # ... 现有逻辑保持不变 ...

    # 异步触发题目质量评估（fire-and-forget）
    asyncio.create_task(self._trigger_question_review())


async def _trigger_question_review(self) -> None:
    """Post-interview: review question quality (non-blocking)."""
    try:
        from app.services.question_reviewer import QuestionReviewer
        reviewer = QuestionReviewer(self._llm)

        # 加载本场所有问答
        stmt = (
            select(Question, Answer)
            .join(Answer, Question.id == Answer.question_id, isouter=True)
            .where(Question.session_id == self.session_id)
        )
        result = await self._db.execute(stmt)

        for q, a in result:
            if a:
                review = await reviewer.review_question(
                    question_text=q.question_text,
                    category=q.category,
                    difficulty=q.difficulty,
                    answers=[{"score": a.score, "content": a.content}],
                )
                if review:
                    # 存储评估结果（新增 QuestionReview 表或写入 question metadata）
                    logger.info(f"Question {q.id} review: {review}")
    except Exception as e:
        logger.warning(f"Question review trigger failed: {e}")
```

---

## P4：前端配套改造

### 4.1 WebSocket 消息协议扩展

在 `frontend/src/types/index.ts` 中增加新的消息类型：

```typescript
// 新增消息类型
type WSMessageType =
  | "interview.start"
  | "interview.chat"
  | "interview.question"
  | "interview.evaluation"
  | "interview.end"
  | "interview.resume"       // 新增：重连恢复
  | "interview.follow_up"    // 新增：追问
  | "error";
```

### 4.2 面试官实时 Dashboard

在 `frontend/src/components/dashboard/` 下新增/修改：

| 组件 | 功能 |
|------|------|
| `LiveSessionCard.tsx` | 对每个活跃会话，显示实时进度（当前题号/总题数、最近事件） |
| `InterviewProgressBar.tsx` | 可视化面试进度条 |
| `ObserverConnection.tsx` | 管理 `/ws/observe/{id}` 连接的生命周期 |

核心 Hook：

```typescript
// hooks/use-observer.ts
function useObserver(sessionId: string, adminToken: string) {
  // 连接 ws://host/ws/observe/{sessionId}?token=adminToken
  // 接收 observer.snapshot / interview.question / interview.evaluation / interview.end
  // 更新 Dashboard UI
}
```

### 4.3 JD 分析入口

在 `SessionCreateDialog.tsx` 中：

```tsx
// 新增 JD 粘贴区
<Textarea
  placeholder="粘贴 JD 文本，AI 将自动分析并填充面试配置..."
  value={jdText}
  onChange={handleJdChange}
/>
<Button onClick={handleAnalyzeJD} disabled={jdText.length < 50}>
  AI 分析 JD
</Button>

// handleAnalyzeJD:
// 1. POST /api/sessions/analyze-jd { jd_text }
// 2. 将返回的 job_title, experience_level, key_skills 等填入表单
```

---

## 配置变更汇总

修改 `backend/app/config.py`：

```python
class Settings(BaseSettings):
    # ... 现有配置 ...

    # 新增：追问题配置
    max_follow_ups_per_question: int = 2       # 每题最多追问次数
    follow_up_enabled: bool = True              # 是否启用追问

    # 新增：LLM 选题配置
    llm_question_selection: bool = True         # 是否用 LLM 选题（False 回退到随机）
    llm_question_selection_max_pool: int = 15   # 给 LLM 的最大候选题目数

    # 新增：报告配置
    narrative_report_enabled: bool = True       # 是否生成叙事报告

    # 新增：JD 分析
    jd_analysis_enabled: bool = True

    # 修改：确保原有配置被引用
    answer_timeout_seconds: int = 120           # 每题回答超时（已存在，确保 agent 引用）
    total_interview_timeout_multiplier: int = 3  # 总超时 = total_questions × this × 60s
```

---

## 测试策略

### 单元测试

| 模块 | 测试内容 | 关键断言 |
|------|---------|---------|
| `test_fsm.py` | 子状态枚举值、转换规则 | QASubState 值不重复 |
| `test_evaluator.py` | 多维评分 JSON 解析、追问字段解析 | `need_follow_up` 正确解析 |
| `test_question_bank.py` | LLM 选题 fallback、选题 JSON 解析 | LLM 失败时正确回退到随机 |
| `test_report.py` | 叙事报告 JSON 解析、字段合并 | narrative_summary 非空 |
| `test_jd_analyzer.py` | JD 分析 JSON 解析、fallback | 短文本触发 fallback |
| `test_agent.py` | 子状态流转、追问计数、超时取消 | 追问次数不超过 max |

### 集成测试

| 场景 | 验证点 |
|------|--------|
| 完整面试 → 追问触发 | 回答质量 2-3 分时 `need_follow_up=true`，agent 发送 `interview.follow_up` |
| 断线 → 重连恢复 | 断开时状态持久化，重连后 `interview.resume` 发送，继续面试 |
| 每题超时 | 120s 无回答 → 提示 → 30s 后强制跳过 |
| JD 分析 → 自动配置 | 粘贴 JD → 返回结构化的配置建议 |
| LLM 选题 vs 随机选题 | LLM 选题的题目序列有逻辑递进 |
| 叙事报告生成 | 报告包含 narrative_summary + recommendation + reasoning |

### 回归测试

- 确保现有 52 个测试用例全部通过
- 确保 `llm_question_selection=False` 时行为与 V1.0 完全一致（向后兼容）
- 确保 `follow_up_enabled=False` 时每题只问一次（原有行为）

---

> 📅 编写日期：2026-06-30
>
> 📎 基于分析：[2026-06-30-ai-interview-flow-analysis.md](2026-06-30-ai-interview-flow-analysis.md)
>
> 📐 设计原则：
> - **渐进增强**：所有 LLM 决策点均有规则 fallback，不引入新的单点故障
> - **向后兼容**：新增字段均有默认值，原有 API 行为不改变
> - **可观测**：每个改造点都增加了日志和状态持久化
> - **人工终审**：LLM 的录用建议标注为"仅供参考"，保留人类决策权
