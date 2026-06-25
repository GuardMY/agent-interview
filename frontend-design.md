# AI 面试官 — 前端设计文档

## 一、概述

为 AI Interview Agent 构建一个现代化 Web 前端，提供候选人与 AI 面试官之间的实时文本交互界面、会话管理以及面试报告查看功能。

### 设计原则
- **专注体验**：候选人只需关注对话，界面不喧宾夺主
- **实时响应**：WebSocket 驱动，打字机效果，无感知延迟
- **渐进呈现**：面试前 → 面试中 → 面试后，各阶段界面分离
- **半自动模式**：AI 全程主持，人类面试官通过报告面板审阅结果

---

## 二、技术选型

| 层 | 选择 | 理由 |
|----|------|------|
| **框架** | Next.js 14 (App Router) | SSR 可选、文件路由、React Server Components |
| **语言** | TypeScript strict | 类型安全，WebSocket 消息协议需要类型约束 |
| **样式** | Tailwind CSS | 快速迭代，暗色模式内置 |
| **状态管理** | Zustand | 轻量、无 boilerplate，适合 WebSocket 实时状态 |
| **HTTP 客户端** | fetch + SWR | 缓存策略内置，适合 REST 轮询 |
| **WebSocket** | 原生 WebSocket API | 轻量，消息协议简单无需 Socket.IO |
| **UI 组件** | shadcn/ui | 基于 Radix，可定制，无障碍 |
| **代码编辑器** | Monaco Editor (按需加载) | V1.5 编程考核阶段使用 |
| **图表** | Recharts | 报告页面的评分雷达图/柱状图 |
| **动画** | Framer Motion | 消息淡入、状态切换过渡 |

---

## 三、路由设计

```
/                              → 重定向到 /dashboard
/dashboard                     → 面试官面板（会话列表 + 报告入口）
/interview/[sessionId]         → 候选人面试房间（WebSocket 实时对话）
/interview/[sessionId]/waiting → 等待连接页面
/interview/[sessionId]/result  → 面试总结页（候选人视角）
/report/[sessionId]            → 详细评分报告（面试官视角）
```

| 路由 | 面向角色 | 说明 |
|------|----------|------|
| `/dashboard` | 面试官 | 管理面试会话：创建、查看、删除、查看报告 |
| `/interview/[id]` | 候选人 | 核心面试界面：聊天 + 状态指示 |
| `/interview/[id]/waiting` | 候选人 | 连接前等待/准备页面 |
| `/interview/[id]/result` | 候选人 | 面试结束后的简单摘要（不含评分） |
| `/report/[id]` | 面试官 | 详细评分报告：总分、各题详情、雷达图 |

---

## 四、组件架构

### 4.1 页面组件树

```
Layout
├── DashboardPage
│   ├── SessionList          ← 会话列表（搜索/筛选/状态标签）
│   ├── SessionCreateDialog  ← 新建面试弹窗表单
│   └── QuickStats           ← 今日面试统计卡片
│
├── InterviewPage
│   ├── InterviewHeader      ← 面试官名称、岗位、进度、计时器
│   ├── ChatPanel            ← 对话消息列表（核心）
│   │   ├── MessageBubble    ← 单条消息（AI/候选人 双端样式）
│   │   ├── QuestionCard     ← 题目卡片（题目编号、分类标签）
│   │   ├── TypingIndicator  ← AI 正在输入动画
│   │   └── EvaluationToast  ← 每题评分后的短暂反馈
│   ├── InputPanel           ← 输入区域
│   │   ├── MessageInput     ← 文本输入框 + 发送按钮
│   │   └── CommandButtons   ← [跳过] [重复] 快捷按钮
│   └── StatusBar            ← 底部状态栏（连接状态、当前阶段）
│
├── ReportPage
│   ├── ReportHeader         ← 候选人信息、总分、是否推荐
│   ├── ScoreRadarChart      ← 五维评分雷达图
│   ├── AnswerTimeline       ← 逐题详情时间线
│   │   └── AnswerCard       ← 单题：题目、回答、得分、评语
│   └── ExportButton         ← 导出 PDF / 打印
│
└── Shared
    ├── LoadingSpinner
    ├── ErrorBoundary
    ├── ConnectionBadge       ← WebSocket 连接状态指示灯
    └── CountdownTimer        ← 倒计时组件
```

### 4.2 核心组件详情

#### ChatPanel — 对话面板

```
┌─────────────────────────────────────────┐
│  [12:03] AI Interviewer                 │
│  ┌─────────────────────────────────┐    │
│  │ Hi Alice! 我是今天的技术面试官。  │    │
│  │ 本次面试预计 30 分钟，共 5 道题。  │    │
│  │ 先请你简单介绍一下自己？          │    │
│  └─────────────────────────────────┘    │
│                                         │
│                           [12:04] You   │
│              ┌──────────────────────┐   │
│              │ 你好！我是 Alice，    │   │
│              │ 3年Python后端开发...  │   │
│              └──────────────────────┘   │
│                                         │
│  [12:05] AI Interviewer                 │
│  ┌─────────────────────────────────┐    │
│  │ 第 1/5 题 · Backend · 中级      │    │
│  │                                 │    │
│  │ 请解释一下微服务架构的优缺点？   │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ⬇ 自动滚动到最新                       │
└─────────────────────────────────────────┘
```

#### AnswerTimeline — 报告时间线

```
┌────────────────────────────────────────────────────┐
│  Q1 · Backend · Junior                 ⭐ 4/5      │
│  ┌────────────────────────────────────────────────┐│
│  │ Q: What is REST?                              ││
│  │ A: REST is an architectural style that uses   ││
│  │    HTTP methods for CRUD operations...        ││
│  │                                               ││
│  │ ✅ Strengths: clear HTTP explanation          ││
│  │ ⚠️ Weaknesses: didn't mention caching         ││
│  │ 📝 评语: 理解扎实,可以补充缓存策略的讨论      ││
│  └────────────────────────────────────────────────┘│
│                                                    │
│  Q2 · Backend · Mid                   ⭐ 3/5      │
│  ...                                               │
│                                                    │
│  ──────── 总分: 3.6/5 ────────                     │
└────────────────────────────────────────────────────┘
```

---

## 五、状态管理（Zustand）

### 5.1 Store 结构

```typescript
// stores/interview-store.ts
interface InterviewStore {
  // ── 会话 ──
  sessionId: string | null;
  sessionStatus: InterviewStatus; // 'idle' | 'intro' | 'qa_loop' | 'wrapup' | 'done'
  
  // ── WebSocket ──
  ws: WebSocket | null;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
  
  // ── 对话 ──
  messages: Message[];              // 完整消息列表
  currentQuestion: QuestionData | null;
  evaluationFeedback: string | null; // 最新评语
  
  // ── 进度 ──
  questionIndex: number;
  totalQuestions: number;
  elapsedSeconds: number;
  
  // ── 动作 ──
  connect: (sessionId: string) => void;
  disconnect: () => void;
  sendMessage: (content: string) => void;
  sendCommand: (command: 'skip' | 'repeat') => void;
  addMessage: (msg: Message) => void;
}
```

### 5.2 消息类型定义

```typescript
// types/messages.ts
type ServerMessageType = 
  | 'interview.start'
  | 'interview.chat' 
  | 'interview.question'
  | 'interview.evaluation'
  | 'interview.end'
  | 'error';

type ClientMessageType =
  | 'message.answer'
  | 'message.chat'
  | 'command.skip'
  | 'command.repeat';

interface WSEnvelope<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;
}

interface Message {
  id: string;
  role: 'interviewer' | 'candidate' | 'system';
  content: string;
  timestamp: string;
  meta?: {
    questionId?: string;
    category?: string;
    difficulty?: string;
    questionNumber?: number;
    totalQuestions?: number;
    feedback?: string;
  };
}
```

---

## 六、WebSocket 数据流

### 6.1 连接生命周期

```
Candidate 打开 /interview/[sessionId]
  │
  ├─ 页面加载 → 显示 waiting 状态
  │
  ├─ useEffect → new WebSocket(`ws://host/ws/interview/${sessionId}`)
  │     │
  │     ├─ ws.onopen → 更新 connectionState='connected'
  │     │
  │     ├─ ws.onmessage → 解析 WSEnvelope → dispatch 到 store
  │     │     │
  │     │     ├─ interview.start → 设置进度信息, 显示开场
  │     │     ├─ interview.chat   → 添加 AI 消息气泡
  │     │     ├─ interview.question → 显示题目卡片 + 题目编号
  │     │     ├─ interview.evaluation → 显示短暂反馈 toast
  │     │     ├─ interview.end    → 跳转到 /interview/[id]/result
  │     │     └─ error            → 显示错误提示
  │     │
  │     ├─ ws.onclose → 更新 connectionState='disconnected'
  │     │     └─ 尝试重连（指数退避，最多 3 次）
  │     │
  │     └─ ws.onerror → 更新 connectionState='error'
  │
  └─ 组件卸载 → ws.close()
```

### 6.2 消息发送

```typescript
// hooks/use-websocket.ts
function useInterviewWebSocket(sessionId: string) {
  const store = useInterviewStore();
  
  useEffect(() => {
    const ws = new WebSocket(`ws://${host}/ws/interview/${sessionId}`);
    
    ws.onmessage = (event) => {
      const envelope = JSON.parse(event.data);
      handleServerMessage(envelope, store);
    };
    
    // Heartbeat: every 30s ping to keep alive
    const heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
    
    return () => {
      clearInterval(heartbeat);
      ws.close();
    };
  }, [sessionId]);
  
  return {
    sendAnswer: (content: string) => { /* send message.answer */ },
    sendSkip: () => { /* send command.skip */ },
    sendRepeat: () => { /* send command.repeat */ },
    sendChat: (content: string) => { /* send message.chat */ },
    connectionState: store.connectionState,
  };
}
```

---

## 七、UI 流程与状态转换

### 7.1 候选人面试全流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  进入面试  │ → │  等待连接  │ → │  开场破冰  │ → │  问答循环  │ → │  结束总结  │
│  页面     │    │  (waiting) │    │  (INTRO)  │    │ (QA_LOOP) │    │  (DONE)   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     │               │               │               │               │
  URL参数         WebSocket      收到start       收到question    收到end
  sessionId       连接中         第1条chat       逐题回答        跳转result
                  状态提示       开场语交互      跳过/重复       显示摘要
```

### 7.2 面试官 Dashboard 流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Dashboard │ → │ 创建会话   │ → │ 分享链接   │
│ 会话列表   │    │ (Dialog)  │    │ 给候选人   │
└──────────┘    └──────────┘    └──────────┘
     │
     ├─ 查看进行中的面试 → 实时旁观（V1.5）
     │
     └─ 点击已完成会话 → /report/[id]
          ├── 总分 + 是否推荐
          ├── 雷达图（五维评分）
          ├── 逐题详情
          └── 导出 PDF
```

---

## 八、面试官 Dashboard 设计

```
┌─────────────────────────────────────────────────────────┐
│  🤖 AI Interview Dashboard                              │
│                                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐ │
│  │ 今日面试 │ │ 进行中   │ │ 平均分   │ │ [+ 新建面试]  │ │
│  │   12    │ │   3     │ │  3.8    │ │               │ │
│  └─────────┘ └─────────┘ └─────────┘ └───────────────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 搜索/筛选: [________] 岗位: [▼] 状态: [▼] 日期: [] ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 候选人      岗位          状态      得分    时间     ││
│  ├─────────────────────────────────────────────────────┤│
│  │ Alice Wang  Backend Eng   ✅ Done   4.2   10:30   ││
│  │ Bob Li      Frontend Eng  🔵 Live   -     11:00   ││
│  │ Carol Chen  DevOps        ⏳ Wait   -     11:15   ││
│  │ ...                                                ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

## 九、响应式与主题

### 9.1 断点策略

| 断点 | 宽度 | 面试页布局 |
|------|------|-----------|
| Mobile | < 640px | 单栏，全屏对话，隐藏侧边信息 |
| Tablet | 640-1024px | 对话为主，顶部栏显示进度 |
| Desktop | > 1024px | 对话居中（max-w-3xl），右侧状态面板 |

### 9.2 暗色模式

面试页支持暗色模式（默认跟随系统），适合长时间专注：
- 对话气泡对比度增强
- 代码块使用暗色主题（One Dark Pro）
- 评分卡片使用半透明玻璃态

### 9.3 无障碍

- 消息列表支持 `aria-live` 区域，屏幕阅读器自动朗读新消息
- 所有按钮有明确的 `aria-label`
- Tab 键导航顺序：输入框 → 发送 → 跳过 → 重复
- 颜色对比度通过 WCAG AA 标准

---

## 十、面试页面状态处理

| 状态 | UI 表现 | 用户可操作 |
|------|---------|-----------|
| **连接中** | 加载动画 + "正在连接面试官..." | 等待 |
| **连接成功** | 绿色指示灯 + 收到首条消息 | 输入文本 |
| **AI 输入中** | 跳动的 `...` 动画 | 等待（输入框禁用） |
| **等待回答** | 光标在输入框中闪烁 | 输入文本、跳过、重复 |
| **评分反馈** | 短暂 toast 弹出 + 自动消失 | 无（1.5秒后自动继续） |
| **面试结束** | 感谢语 + 3秒后跳转到结果页 | 查看总结 |
| **连接断开** | 红色提示条 + "正在重连(1/3)..." | 等待重连 |
| **重连失败** | "连接已丢失，请刷新页面重试" | 刷新按钮 |
| **网络超时** | 输入框超时提示 + 自动发送空回答 | 无 |

---

## 十一、报告页面设计

```
┌─────────────────────────────────────────────────────────┐
│  📊 Interview Report                                    │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Alice Wang  ·  Backend Engineer  ·  2026-06-25   │   │
│  │ Status: Completed  ·  Duration: 28 min            │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │              │  │              │  │              │  │
│  │   Total      │  │  Questions   │  │  Recommended │  │
│  │   Score      │  │  Answered    │  │              │  │
│  │   3.8/5      │  │    5/5       │  │   ✅ Yes     │  │
│  │              │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────────────┐ ┌──────────────────────────┐  │
│  │   评分雷达图           │ │   各题得分柱状图          │  │
│  │   (技术/思维/沟通/     │ │   Q1 ████████ 4         │  │
│  │    解题/行为)          │ │   Q2 ██████   3         │  │
│  │                       │ │   Q3 ██████████ 5       │  │
│  └──────────────────────┘ └──────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Answer Details                                  │   │
│  │                                                  │   │
│  │  Q1 · Backend · Junior · ⭐ 4/5                  │   │
│  │  ┌──────────────────────────────────────────┐    │   │
│  │  │ [问题 + 候选人回答 + 评语 + 关键词]        │    │   │
│  │  └──────────────────────────────────────────┘    │   │
│  │                                                  │   │
│  │  Q2 · Backend · Mid · ⭐ 3/5                     │   │
│  │  ...                                            │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  [🖨 Print Report]  [📥 Export PDF]  [🔗 Share Link]    │
└─────────────────────────────────────────────────────────┘
```

---

## 十二、项目结构

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx               # Root layout + Tailwind + Providers
│   │   ├── page.tsx                 # Redirect to /dashboard
│   │   ├── dashboard/
│   │   │   └── page.tsx             # 面试官 Dashboard
│   │   ├── interview/
│   │   │   └── [sessionId]/
│   │   │       ├── page.tsx         # 面试房间主页面
│   │   │       ├── waiting/
│   │   │       │   └── page.tsx     # 等待连接页
│   │   │       └── result/
│   │   │           └── page.tsx     # 候选人结果页
│   │   └── report/
│   │       └── [sessionId]/
│   │           └── page.tsx         # 面试官报告页
│   │
│   ├── components/
│   │   ├── interview/
│   │   │   ├── ChatPanel.tsx        # 对话面板
│   │   │   ├── MessageBubble.tsx    # 消息气泡
│   │   │   ├── QuestionCard.tsx     # 题目卡片
│   │   │   ├── InputPanel.tsx       # 输入区域
│   │   │   ├── InterviewHeader.tsx  # 顶部信息栏
│   │   │   ├── TypingIndicator.tsx  # 输入中动画
│   │   │   ├── EvaluationToast.tsx  # 评分 toast
│   │   │   └── StatusBar.tsx        # 连接状态栏
│   │   ├── dashboard/
│   │   │   ├── SessionList.tsx      # 会话列表
│   │   │   ├── SessionCreateDialog.tsx
│   │   │   └── QuickStats.tsx       # 统计卡片
│   │   ├── report/
│   │   │   ├── ReportHeader.tsx
│   │   │   ├── ScoreRadarChart.tsx  # 雷达图
│   │   │   ├── AnswerTimeline.tsx   # 答题时间线
│   │   │   └── AnswerCard.tsx       # 单题详情卡片
│   │   └── ui/                      # shadcn/ui 基础组件
│   │       ├── button.tsx
│   │       ├── dialog.tsx
│   │       ├── input.tsx
│   │       └── ...
│   │
│   ├── hooks/
│   │   ├── use-websocket.ts         # WebSocket 连接管理
│   │   └── use-interview-timer.ts   # 面试计时器
│   │
│   ├── stores/
│   │   └── interview-store.ts       # Zustand 状态管理
│   │
│   ├── types/
│   │   ├── messages.ts              # WebSocket 消息类型
│   │   └── session.ts               # 会话/报告类型
│   │
│   └── lib/
│       ├── api.ts                   # REST API 封装
│       └── utils.ts                 # 格式化/工具函数
│
├── public/
│   └── favicon.svg
│
├── tailwind.config.ts
├── tsconfig.json
├── next.config.js
└── package.json
```

---

## 十三、与后端 API 对接

### REST API

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function createSession(data: CreateSessionRequest): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

export async function getSessionReport(sessionId: string): Promise<SessionReport> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/report`);
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}

// ... etc
```

### WebSocket URL

```typescript
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
const wsUrl = `${WS_BASE}/ws/interview/${sessionId}`;
```

---

## 十四、分阶段实施

### V1.0（对应当前后端，2 周）

- [ ] Next.js 项目初始化 + Tailwind + shadcn/ui
- [ ] `/interview/[sessionId]` 面试房间核心页面
  - [ ] WebSocket 连接管理 hook
  - [ ] 对话面板（消息列表 + 消息气泡）
  - [ ] 输入面板（文本输入 + 发送 + 跳过 + 重复）
  - [ ] 面试 header（进度 + 计时器）
  - [ ] 连接状态指示器
- [ ] `/dashboard` 面试官面板
  - [ ] 会话列表
  - [ ] 创建会话弹窗
  - [ ] 链接复制分享
- [ ] `/report/[sessionId]` 报告页
  - [ ] 总分 + 状态卡片
  - [ ] 逐题答题详情
- [ ] Zustand store + 类型定义

### V1.5（编程考核 + 旁观）

- [ ] Monaco Editor 集成（代码考核页面）
- [ ] 面试官实时旁观模式（只读 WebSocket）
- [ ] 暗色模式切换

### V2.0（完整体验）

- [ ] 语音输入/输出（Web Speech API）
- [ ] 雷达图 + 图表（Recharts）
- [ ] PDF 报告导出
- [ ] 简历上传 + 解析预览
- [ ] PWA 支持（离线提示）
- [ ] 国际化 i18n（中/英）

---

## 十五、环境变量

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 十六、关键交互细节

### 16.1 打字机效果（AI 消息流式渲染）

```typescript
// 后端支持流式输出时，前端逐字渲染
// V1.0 先使用完整消息 + fade-in 动画过渡
<motion.div
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  <MessageBubble content={msg.content} />
</motion.div>
```

### 16.2 评分反馈动画

```
收到 evaluation → 屏幕中央弹出 toast：
  ┌──────────────────────┐
  │  ✅ 得分: 4/5         │
  │  回答清晰，理解到位    │
  └──────────────────────┘
  → 1.5秒后自动消失
  → 下一道题平滑滑入
```

### 16.3 跳过/重复交互

- 跳过按钮：点击 → 确认 → 灰色提示 "已跳过，进入下一题"
- 重复按钮：点击 → AI 重新措辞 → 新消息气泡

---

> **前端哲学**：面试本身就是高压场景，UI 要做到 "存在但不喧哗" —— 所有交互都服务于对话本身，让候选人忘了界面的存在，专注于回答问题。
