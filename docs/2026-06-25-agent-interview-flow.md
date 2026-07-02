# AI 面试官 — 完整处理流程文档

> 基于 V1.0 代码实际分析，覆盖从前端 Dashboard 创建会话到报告生成的完整链路。

---

## 一、系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js 16)                       │
│  /dashboard  │  /interview/[id]  │  /report/[id]                │
│                          │                                       │
│              WebSocket ◄─┼── REST (fetch)                        │
│              ws://host   │  http://host:8000                     │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                   Backend (FastAPI)                              │
│                                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐               │
│  │ REST API  │  │  WS Handler  │  │  CORS       │               │
│  │ /api/*    │  │  /ws/*       │  │  Middleware  │               │
│  └────┬─────┘  └──────┬───────┘  └─────────────┘               │
│       │               │                                          │
│       │    ┌──────────▼──────────┐                               │
│       │    │   InterviewAgent    │  ← 核心编排器                  │
│       │    │   ┌──────────────┐  │                               │
│       │    │   │ InterviewFSM  │  │  ← 状态机                     │
│       │    │   │ (5 states)    │  │                               │
│       │    │   └──────────────┘  │                               │
│       │    │   ┌──────────────┐  │                               │
│       │    │   │ Conversation │  │  ← 滑动窗口 + 意图检测         │
│       │    │   │ Manager      │  │                               │
│       │    │   └──────────────┘  │                               │
│       │    │   ┌──────────────┐  │                               │
│       │    │   │ Evaluation   │  │  ← LLM 评分引擎                │
│       │    │   │ Engine       │  │                               │
│       │    │   └──────────────┘  │                               │
│       │    └─────────────────────┘                               │
│       │               │                                          │
│       │    ┌──────────▼──────────┐                               │
│       │    │   QuestionBank      │  ← 自适应难度题库              │
│       │    │   Service           │                               │
│       │    └─────────────────────┘                               │
│       │               │                                          │
│       │    ┌──────────▼──────────┐                               │
│       │    │   LLM Adapter       │  ← DeepSeek / Claude 可插拔    │
│       │    └─────────────────────┘                               │
│       │                                                          │
│       ▼                                                          │
│  ┌────────────┐   ┌──────────┐   ┌────────────┐                │
│  │ Report     │   │ Models   │   │ Schemas    │                │
│  │ Service    │   │ (ORM)    │   │ (Pydantic) │                │
│  └────────────┘   └──────────┘   └────────────┘                │
│                          │                                       │
│                   ┌──────▼──────┐                                │
│                   │  SQLite DB  │                                │
│                   └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、项目结构

```
agent-interview/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI 入口 + CORS
│   │   ├── config.py                    # 全局配置 (pydantic-settings)
│   │   ├── api/
│   │   │   ├── rest_sessions.py         # REST: CRUD 会话 + 报告
│   │   │   └── ws_interview.py          # WebSocket: 实时面试连接
│   │   ├── core/
│   │   │   ├── fsm.py                   # 状态机: 5 状态 × 9 事件
│   │   │   ├── conversation.py          # 对话管理: 滑动窗口 + 意图
│   │   │   ├── evaluator.py             # 评分引擎: LLM 输出 → 结构化
│   │   │   └── agent.py                 # 面试编排器（核心）
│   │   ├── models/
│   │   │   ├── session.py               # InterviewSession ORM
│   │   │   ├── question.py              # Question ORM
│   │   │   └── answer.py                # Answer ORM
│   │   ├── schemas/
│   │   │   ├── session.py               # CreateSessionRequest / Response
│   │   │   ├── question.py              # QuestionData
│   │   │   ├── message.py               # WSMessage 信封
│   │   │   └── evaluation.py            # EvaluationResult / SessionReport
│   │   ├── services/
│   │   │   ├── question_bank.py         # 题库: 选题 + 自适应难度
│   │   │   └── report.py               # 报告生成
│   │   ├── llm/
│   │   │   ├── base.py                  # BaseLLMAdapter (ABC)
│   │   │   ├── deepseek.py             # DeepSeek 适配器
│   │   │   ├── claude.py               # Claude 适配器
│   │   │   └── prompts/
│   │   │       ├── system.py            # System Prompt (中/英)
│   │   │       ├── scoring.py           # 评分 Prompt (中/英)
│   │   │       └── interviewer.py       # 面试官对话 Prompt (集中管理)
│   │   └── db/
│   │       └── database.py              # Async Engine + Session
│   ├── data/
│   │   └── questions.json              # 题库 (30 题)
│   └── tests/                          # 52 个测试
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/page.tsx       # 面试官面板
│   │   │   ├── interview/[id]/page.tsx  # 候选人面试房间
│   │   │   └── report/[id]/page.tsx     # 评分报告
│   │   ├── components/
│   │   │   ├── dashboard/               # SessionList, CreateDialog, StatsCards
│   │   │   ├── interview/               # ChatPanel, MessageBubble, InputPanel, ...
│   │   │   ├── report/                  # ReportHeader, AnswerCard
│   │   │   ├── shared/                  # LanguageSwitcher
│   │   │   └── ui/                      # shadcn/ui 基础组件
│   │   ├── hooks/use-websocket.ts       # WebSocket 连接 + 消息分发
│   │   ├── stores/interview-store.ts    # Zustand 全局状态
│   │   ├── lib/api.ts                   # REST API 封装
│   │   ├── i18n/                        # 中英文翻译系统
│   │   └── types/index.ts               # TypeScript 类型定义
│   └── ...
├── .env                                 # API Key + 配置
├── docker-compose.yml
├── agent-interview-design.md            # 设计文档
└── agent-interview-flow.md              # 本文档
```

---

## 三、数据模型

### 3.1 数据库表

```
┌──────────────────────────────────┐
│       interview_sessions         │
├──────────────────────────────────┤
│ id           VARCHAR(36) PK      │
│ candidate_name VARCHAR(100)      │
│ job_title     VARCHAR(200)       │
│ experience    VARCHAR(20)        │  junior | mid | senior
│ key_skills    JSON               │
│ language      VARCHAR(10)        │  en | zh
│ status        VARCHAR(20)        │  idle→intro→qa_loop→wrapup→done
│ question_idx  INTEGER            │  当前题号
│ total_q       INTEGER            │  总题数 (默认 5)
│ started_at    DATETIME           │
│ completed_at  DATETIME (nullable)│
│ metadata      JSON               │
└──────┬───────────────────────────┘
       │ 1:N (CASCADE)
       ▼
┌──────────────────────────────────┐
│           questions              │
├──────────────────────────────────┤
│ id           VARCHAR(36) PK      │
│ session_id   VARCHAR(36) FK      │
│ question_text TEXT               │
│ category     VARCHAR(50)         │  backend|frontend|general|devops|ai_ml
│ difficulty   VARCHAR(20)         │  junior|mid|senior
│ keywords     JSON                │
│ order_index  INTEGER             │
│ status       VARCHAR(20)         │  pending|asked|answered|skipped
│ asked_at     DATETIME            │
└──────┬───────────────────────────┘
       │ 1:1
       ▼
┌──────────────────────────────────┐
│            answers               │
├──────────────────────────────────┤
│ id           VARCHAR(36) PK      │
│ question_id  VARCHAR(36) FK UNIQ │
│ session_id   VARCHAR(36) FK      │
│ content      TEXT                │  候选人原话
│ score        INTEGER (1-5)       │  LLM 评分
│ comment      TEXT                │  评语
│ strengths    JSON                │  优点列表
│ weaknesses   JSON                │  不足列表
│ keywords     JSON                │  命中关键词
│ missing_pts  JSON                │  遗漏知识点
│ raw_eval     JSON                │  LLM 原始返回
│ created_at   DATETIME            │
└──────────────────────────────────┘
```

### 3.2 Pydantic Schema（API 契约）

```python
# 创建面试请求
CreateSessionRequest:
    candidate_name: str          # 1-100 字符
    job_title: str               # 1-200 字符
    experience_level: str        # "junior"|"mid"|"senior"，默认 "mid"
    key_skills: list[str]        # 默认 []
    interview_language: str      # "en"|"zh"，默认 "en"

# 面试响应
SessionResponse:
    id, candidate_name, job_title, experience_level,
    interview_language, status,
    current_question_index, total_questions,
    started_at, completed_at

# 评分结果
EvaluationResult:
    score: int (1-5)
    comment: str
    strengths, weaknesses, matched_keywords, missing_points: list[str]

# 会话报告
SessionReport:
    session_id, candidate_name, job_title, experience_level, status
    total_questions, answered_count, average_score
    answers: list[AnswerReport]
```

---

## 四、状态机

### 4.1 状态图

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

### 4.2 状态枚举值

| 状态 | 含义 | 持续时间 |
|------|------|----------|
| `idle` | 会话已创建，等待 WebSocket 连接 | 创建后 ~ 连接前 |
| `intro` | AI 自我介绍 + 候选人开场 | ~1 轮对话 |
| `qa_loop` | 技术问答循环 | 5 题 × 每题约 3-5 分钟 |
| `wrapup` | 结束语 | 立即结束（不等待回复） |
| `done` | 面试完成 | 永久 |

### 4.3 事件触发源

| 事件 | 触发 |
|------|------|
| `START` | `agent.start()` |
| `INTRO_COMPLETE` | 候选人回复开场问题后 |
| `ANSWER_EVALUATED` | 评分完成，进入下一题 |
| `QUESTION_EXHAUSTED` | 题目用尽 / 题号达到上限 |
| `SKIP_QUESTION` | 候选人跳过 / 命令跳过 |
| `TIME_UP` | 超时（当前未启用） |
| `WRAPUP_COMPLETE` | 结束语发送后 |
| `CANDIDATE_DISCONNECT` | WebSocket 断开 |

---

## 五、面试完整流程

### 5.1 创建会话 (REST)

```
1. 用户在 Dashboard 填写表单
   ├── candidate_name: "张三"
   ├── job_title: "后端开发"
   ├── experience_level: "mid"
   ├── key_skills: ["springboot", "mysql"]
   └── interview_language: "zh"

2. POST /api/sessions  →  201 Created
   └── INSERT INTO interview_sessions
       (id, candidate_name, ..., status="idle", current_question_index=0)

3. 前端 localStorage 记录 session_id
   新标签页打开 /interview/{session_id}
```

### 5.2 面试进行 (WebSocket)

```
阶段 1: 连接 & 开场 ————————————————————————————————

4. WebSocket 连接 ws://host/ws/interview/{session_id}

5. InterviewAgent.start()
   ├── 加载 InterviewSession
   ├── FSM: IDLE ──START──► INTRO
   ├── 设置初始难度 = candidate.experience_level
   ├── 发送 interview.start {
   │     session_id, job_title, total_questions, duration_minutes
   │   }
   └── LLM 生成开场白 → 发送 interview.chat {content}

阶段 2: 技术问答循环 ——————————————————————————————

6. 候选人回复开场问题
   → agent._handle_intro()
   ├── FSM: INTRO ──INTRO_COMPLETE──► QA_LOOP
   └── 发送过渡消息 → _ask_next_question()

7. _ask_next_question() — 循环 5 次:
   ┌─────────────────────────────────────────┐
   │ a. 检查 idx >= 5? → _start_wrapup()    │
   │ b. QuestionBankService.select_question()│
   │    ├── 按当前难度筛选                    │
   │    ├── 排除已用过的                      │
   │    └── 随机抽取一道                      │
   │ c. 创建 Question 行 (status="asked")    │
   │ d. LLM 包装问题为自然口语               │
   │    └── get_prompt("question_wrap", lang)│
   │ e. 发送 interview.question {            │
   │      question_id, content, category,     │
   │      difficulty, question_number,        │
   │      total_questions                     │
   │    }                                     │
   └─────────────────────────────────────────┘

8. 候选人回答 → _handle_qa():
   ├── ConversationManager.detect_intent()
   │   ├── skip 关键词 → _handle_skip()
   │   ├── "end the interview" → _end_interview_early()
   │   ├── "can you repeat" → LLM 澄清
   │   └── 默认 → ANSWER
   ├── _evaluate_and_continue(answer)
   └── 回到步骤 7

9. _evaluate_and_continue() 内部:
   ├── 加载 Question from DB
   ├── EvaluationEngine.evaluate(question, answer, language)
   │   ├── get_scoring_prompt(language) → 中/英评分 prompt
   │   ├── LLM.generate(temperature=0.3)
   │   └── 多层 JSON 解析 → EvaluationResult {score, comment, ...}
   ├── 创建 Answer 行
   ├── QuestionBankService.update_difficulty(score)
   │   ├── score >= 4 × 2次 → 升级难度
   │   └── score <= 2 × 2次 → 降级难度
   └── 发送 interview.evaluation {feedback}

阶段 3: 结束 ————————————————————————————————————

10. 第 5 题评分完成后:
    _ask_next_question() 检测 idx >= total_questions
    → _start_wrapup()
    ├── FSM: QA_LOOP ──QUESTION_EXHAUSTED──► WRAPUP
    ├── LLM 生成结束语
    ├── 发送 interview.chat {content}
    ├── FSM: WRAPUP ──WRAPUP_COMPLETE──► DONE
    └── _finalize_session()
        ├── session.status = "done"
        ├── session.completed_at = now()
        └── 发送 interview.end

阶段 4: 查看报告 ————————————————————————————————

11. 用户访问 /report/{session_id}
    GET /api/sessions/{id}/report
    └── ReportService.build_report()
        ├── 加载 Session + Questions + Answers
        ├── 计算 average_score
        └── 返回 SessionReport JSON
```

### 5.3 备选路径

| 场景 | 触发方式 | 处理 |
|------|---------|------|
| **跳过** | `command.skip` 或候选人说 "skip" | 标记为 skipped，skip_count++，达到 3 次进入 wrapup |
| **重复** | `command.repeat` | LLM 重新措辞当前题 |
| **澄清** | 候选人说 "can you repeat" | LLM 生成解释，不换题 |
| **提前结束** | 候选人说 "end the interview" | 直接进入 _finalize_session |
| **断线** | WebSocket 关闭 | 自动重连 3 次（done 状态除外），失败则结束 |
| **LLM 失败** | API 错误 / 超时 | 3 次重试 → 评分 fallback 为 3 分；问题包装 fallback 为原题文本 |

---

## 六、WebSocket 消息协议

### 6.1 信封格式

```json
{"type": "<message_type>", "payload": {...}, "timestamp": "ISO8601"}
```

### 6.2 Server → Client

| type | payload | 发送时机 |
|------|---------|---------|
| `interview.start` | `{session_id, job_title, total_questions, duration_minutes}` | 连接后立即 |
| `interview.chat` | `{content: str}` | 开场、过渡语、结束语 |
| `interview.question` | `{question_id, content, category, difficulty, question_number, total_questions}` | 每题开始时 |
| `interview.evaluation` | `{feedback: str}` | 每题评分后（简短反馈） |
| `interview.end` | `{session_id, message: str}` | 面试完成 |
| `error` | `{code: str, message: str}` | 异常时 |

### 6.3 Client → Server

| type | payload | 说明 |
|------|---------|------|
| `message.chat` | `{content: str}` | 非问答的通用消息 |
| `message.answer` | `{content: str}` | 技术问题回答 |
| `command.skip` | `{}` | 跳过当前题 |
| `command.repeat` | `{}` | 重复/重述当前题 |

---

## 七、LLM 调用汇总

| 场景 | Prompt Key | System Prompt | Temperature | Max Tokens |
|------|-----------|---------------|-------------|------------|
| 开场白 | `intro_en` | 面试官人设 | 0.8 | 300 |
| 问题包装 | `question_wrap` | 面试官人设 | 0.8 | 200 |
| 评分 | `scoring` (无 system) | — | 0.3 | 500 |
| 澄清/追问 | `clarify` | 面试官人设 | 0.8 | 200 |
| 重复题目 | `repeat` | 面试官人设 | 0.8 | 200 |
| 结束语 | `wrapup` | 面试官人设 | 0.7 | 300 |

**注意**：
- 评分使用低 temperature (0.3) 保证一致性
- 对话类使用高 temperature (0.7-0.8) 保证自然度
- 所有对话 prompt 统一在 `interviewer.py` 中按 key 管理，通过 `get_prompt(key, lang, **kwargs)` 获取

---

## 八、对话管理

### 8.1 滑动窗口

`ConversationManager` 维护最近 N 条消息（默认 `sliding_window_size=10`），超出部分被丢弃。LLM 的 system prompt 只包含窗口内的对话，防止 token 溢出。

### 8.2 意图检测

关键词启发式（不使用 LLM，保证低延迟）：

```
消息 → to_lowercase():
  ├── "end the interview" / "stop" → DISENGAGE
  ├── 消息 < 30 字符 && ("skip" / "next" / "pass") → SKIP
  ├── "can you repeat" / "clarify" / "what do you mean" → CLARIFY
  ├── 消息 < 20 字符 && ("thank you" / "hello") → CHAT
  └── 默认 → ANSWER
```

---

## 九、自适应难度

```
初始难度 = candidate.experience_level

每题评分后:
  score >= 4 → consecutive_good++
                连续 2 次 ⇒ 升级 (junior→mid→senior)
  score <= 2 → consecutive_poor++
                连续 2 次 ⇒ 降级 (senior→mid→junior)
  score == 3 → 重置计数器

选题时按当前难度筛选，同难度用尽后放宽到全部
```

---

## 十、评分引擎

### 10.1 评分流程

```
1. 根据 language 获取评分 prompt (中/英)
2. 填入 {question_text, category, difficulty, expected_keywords, candidate_answer}
3. LLM.generate(temperature=0.3)
4. 多层 JSON 解析:
   ├── 去代码块 ```json ```
   ├── json.loads()
   ├── 正则提取第一个 {...}
   ├── 修复尾逗号
   └── 正则兜底提取 score + comment
5. 构建 EvaluationResult (score 限制 1-5)
6. 失败 → fallback score=3, comment="无法自动评估，请人工审核。"
```

### 10.2 评分标准

| 分数 | 含义 | 判断依据 |
|------|------|---------|
| 1 | 差 | 完全错误 / 拒绝回答 / 完全偏题 |
| 2 | 低于平均 | 部分正确但遗漏重要概念 |
| 3 | 平均 | 基本正确但缺乏深度 |
| 4 | 好 | 全面、结构清晰 |
| 5 | 优秀 | 全面、有见地、超出预期 |

---

## 十一、报告服务

```
GET /api/sessions/{id}/report

ReportService.build_report(session_id, db):
  1. SELECT session WITH questions, answers (JOIN)
  2. 构建 answer_map: question_id → Answer
  3. 遍历每个 Question:
     └── 匹配 Answer → 提取 score, comment
        → AnswerReport {question_text, category, difficulty,
                        order_index, status, answer_content,
                        score, score_comment}
  4. 计算 average_score = sum(scores) / count(scored)
  5. 返回 SessionReport {
       session_id, candidate_name, job_title, experience_level,
       status, total_questions, answered_count,
       average_score, answers[], started_at, completed_at
     }
```

---

## 十二、前端状态管理

### 12.1 Zustand Store

```
useInterviewStore:
  State:
    sessionId, jobTitle, interviewStatus, connectionState,
    questionIndex, totalQuestions, durationMinutes,
    messages[], currentQuestionMeta, evaluationFeedback,
    isWaitingForResponse

  Actions:
    setSession()           → 初始化会话元数据
    setConnectionState()   → connecting|connected|disconnected|error
    setInterviewStatus()   → idle|intro|qa_loop|wrapup|done
    addMessage()           → 追加消息到列表
    setCurrentQuestion()   → 更新当前题元数据
    incrementQuestionIndex()
    reset()
```

### 12.2 WebSocket Hook

```
useWebSocket(sessionId):
  连接 → 消息分发 → 自动重连(≤3次) → 发送辅助

  dispatch(envelope):
    interview.start    → setSession + setConnectionState("connected")
    interview.chat     → addMessage(interviewer) + 清除等待
    interview.question → addMessage(interviewer, meta) + setCurrentQuestion
    interview.evaluation → setEvaluationFeedback + incrementQuestionIndex
    interview.end      → setInterviewStatus("done")
    error              → addMessage(system)

  sendAnswer(content)  → send("message.answer") + addMessage(candidate)
  sendChat(content)    → send("message.chat") + addMessage(candidate)
  sendSkip()           → send("command.skip")
  sendRepeat()         → send("command.repeat")

  重连守卫: interviewStatus === "done" 时不重连
```

---

## 十三、语言切换机制

```
创建会话时选择 en 或 zh
  │
  ├── System Prompt   → SYSTEM_PROMPT_EN / SYSTEM_PROMPT_ZH
  ├── 对话 Prompt     → get_prompt(key, lang) 从 interviewer.py 目录查找
  ├── 评分 Prompt     → get_scoring_prompt(lang) 从 scoring.py
  ├── 问题包装        → 中文模式要求 LLM 先翻译英文题目再提问
  └── 报告            → 评语自动跟随评分 prompt 语言

前端 UI 语言: 独立的 i18n 系统 (LanguageSwitcher)
  ├── I18nProvider + useI18n() hook
  ├── detectLocale: localStorage → navigator.language → 默认 zh
  └── 覆盖: Dashboard / 面试页 / 报告页 / 所有子组件
```

---

## 十四、关键配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `deepseek` | anthropic / deepseek / openai |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek 模型名 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API 地址 |
| `DEFAULT_TOTAL_QUESTIONS` | 5 | 每题面试题数 |
| `DEFAULT_TIME_LIMIT_MINUTES` | 30 | 面试时长上限 |
| `MAX_SKIP_COUNT` | 3 | 最大跳题次数 |
| `SLIDING_WINDOW_SIZE` | 10 | 对话窗口大小 |
| `SCORING_CONSECUTIVE_GOOD` | 2 | 难度升级阈值（连续 N 次 >= 4 分） |
| `SCORING_CONSECUTIVE_POOR` | 2 | 难度降级阈值（连续 N 次 <= 2 分） |
| `LLM_REQUEST_TIMEOUT` | 60 | API 超时（秒） |
