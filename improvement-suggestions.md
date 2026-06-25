# AI 面试官 — 改进建议（按优先级排序）

基于 V1.0 代码审查的全面分析。

---

## P0 — 致命/安全（需立即修复）

### 1. 缺少身份认证与权限控制

**现状**：所有 API 端点完全开放，任何人可以创建会话、查看任意报告、删除数据。

**风险**：
- 候选人 A 可以查看候选人 B 的评分报告
- 恶意删除所有会话数据
- 面试链接泄露后无法追溯

**建议**：
```python
# 最小方案：Session 创建时生成唯一的 access_token
session = InterviewSession(
    ...,
    admin_token=secrets.token_urlsafe(32),   # 面试官用
    candidate_token=secrets.token_urlsafe(32), # 候选人用
)
# 面试页用 candidate_token 校验，Dashboard 用 admin_token 校验
```

| 方案 | 工作量 | 适用阶段 |
|------|--------|----------|
| Session Token 模式 | 2h | MVP/内部用 |
| JWT + 用户系统 | 3d | 生产环境 |
| OAuth2 (Google/GitHub) | 1d | 对外服务 |

### 2. 敏感文件泄露

**现状**：`.claude/settings.local.json` 已被提交到仓库。

**修复**：
```gitignore
# 追加到 .gitignore
.claude/
```

### 3. `.env.example` 真实密钥泄露风险

**现状**：曾被推送含真实 DeepSeek API key 的版本。虽然已 amend 修复，但 GitHub 可能缓存了历史。

**修复**：
- 轮换泄露的 API key（在 DeepSeek 控制台重新生成）
- 添加 pre-commit hook 检测密钥：

```bash
# .git/hooks/pre-commit
git diff --cached | grep -E 'sk-[a-zA-Z0-9]{20,}' && echo "API key detected!" && exit 1
```

### 4. 输入校验不足

**现状**：候选人回答直接存储到数据库，无长度限制或 XSS 防护。

**修复**：
```python
# rest_sessions.py 和 ws_interview.py
from pydantic import Field
content: str = Field(..., min_length=1, max_length=5000)  # 限制单条消息长度
```

```typescript
// 前端渲染时转义 HTML
<p className="whitespace-pre-wrap">{escapeHtml(message.content)}</p>
```

---

## P1 — 高优先级（影响功能完整性）

### 5. 题库管理缺少 CRUD API

**现状**：题库是静态 `questions.json`，修改需要重启服务。

**建议**：
```
GET    /api/questions                      # 题目列表（分页+筛选）
POST   /api/questions                      # 新增题目
PUT    /api/questions/{id}                 # 编辑题目
DELETE /api/questions/{id}                 # 删除题目
GET    /api/questions/categories           # 类别列表
```

加上前端题库管理页面（`/dashboard/questions`）。

### 6. Dashboard 无会话列表 API

**现状**：前端用 `localStorage` 存储 session ID 列表来模拟"所有会话"。多设备/浏览器不同步，清除缓存后数据丢失。

**建议**：后端新增：
```
GET /api/sessions?page=1&size=20&status=done&sort=started_at
```
无需 localStorage 技巧。

### 7. 面试超时机制未实现

**现状**：`InterviewFSM` 有 `TIME_UP` 事件但从未触发。

**建议**：
```python
# agent.py 中添加后台定时器
import asyncio

async def _start_timeout_timer(self):
    await asyncio.sleep(self._session.total_questions * 180)  # 每题3分钟
    if self._fsm.is_active:
        self._fsm.transition(InterviewEvent.TIME_UP)
        await self._start_wrapup()
```

### 8. 评分维度单一

**现状**：只返回 1-5 分 + 评语。无法区分候选人各方面水平。

**建议**：扩展 `scoring.py` prompt 输出：
```json
{
  "overall_score": 4,
  "dimensions": {
    "technical_accuracy": 4,
    "depth_of_knowledge": 3,
    "communication": 5,
    "problem_solving": 4
  },
  "comment": "..."
}
```
前端报告页可以用雷达图展示多维评分。

### 9. 面试试题无随机化种子

**现状**：`random.choice()` 选题，无法复现候选人看到的题目序列。

**建议**：
```python
# 基于 session_id 生成固定随机种子
import hashlib
seed = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % (2**32)
rng = random.Random(seed)
question = rng.choice(pool)
```
保证同一 session 复查时可验证选题。

---

## P2 — 中优先级（改善用户体验）

### 10. 面试断线无法恢复

**现状**：WebSocket 断线后 3 次重连失败即结束。候选人丢失所有进度。

**建议**：
```python
# 重连时从 DB 恢复面试状态
async def start(self):
    if self._session.current_question_index > 0:
        # 从已答的最后一题继续
        await self._resume_from(self._session.current_question_index)
```

### 11. 候选人无法查看自己的报告

**现状**：报告页面 (`/report/[id]`) 无权限控制，但也没有候选人入口。

**建议**：面试结束页添加"查看你的面试报告"按钮，通过 `candidate_token` 访问。

### 12. Dashboard 统计卡片数据不完整

**现状**：StatsCards 中 `avgScore` 固定 `null`，"今日面试"统计实际显示的是全部。

**建议**：
- 后端 `GET /api/sessions` 返回列表时附赠聚合统计
- 增加日期筛选参数 `?date_from=2026-06-25`

### 13. 面试结束无通知

**现状**：面试官需要手动刷新 Dashboard 才知道面试完成。

**建议**：
- 后端 `interview.end` 时写一条通知记录
- Dashboard 定时轮询 `GET /api/notifications?unread=true`
- 或通过 WebSocket 推送到 Dashboard 页

### 14. 对话历史不能导出

**现状**：报告只有评分，没有完整对话记录。

**建议**：
```python
# report.py 中增加对话文本
class SessionReport:
    transcript: list[Message]  # 完整问答对话
```
并可导出为 TXT / PDF。

### 15. 题目翻译未缓存

**现状**：每题都调用 LLM 翻译英文题目为中文，浪费 tokens 和延迟。

**建议**：预生成中文版题库 `questions_zh.json`，中文面试直接使用中文题面。

### 16. 未配置日志文件持久化

**现状**：日志只输出到控制台（stdout），服务重启后丢失。

**建议**：
```python
# main.py
import logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/interview.log", encoding="utf-8"),
    ],
)
```

---

## P3 — 低优先级（锦上添花）

### 17. 编程考核模块

见 `frontend-design.md` 中的 V1.5 规划 —— Monaco Editor + Docker 沙箱。

### 18. 语音交互

Web Speech API 实现语音输入/输出，降低文字输入门槛。

### 19. 暗色模式

前端 Tailwind 配置 `darkMode: "class"`，增加主题切换。

### 20. 多语言扩展

当前 `interviewer.py` 的 `PROMPTS` 字典已支持中英双语，扩展新语言只需在每个 key 下加一列：

```python
"question_wrap": {
    "en": "...",
    "zh": "...",
    "ja": "...",  # 日文
    "ko": "...",  # 韩文
}
```

### 21. 面试模版

预设不同岗位的面试配置：
```json
{
  "backend_engineer": {
    "total_questions": 5,
    "categories": ["backend", "general"],
    "difficulty_start": "mid"
  },
  "frontend_engineer": { ... },
  "data_analyst": { ... }
}
```

### 22. PDF 报告导出

使用 `reportlab`（后端）或 `html2pdf`（前端）生成正式 PDF 面试报告。

### 23. PWA 支持

添加 `manifest.json` + Service Worker，候选人可以离线查看面试记录。

### 24. CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
- name: Backend Tests
  run: cd backend && pip install -r requirements.txt && pytest
- name: Frontend Build
  run: cd frontend && npm ci && npm run build
```

### 25. 编译题库为 Python 模块

当前 `questions.json` 每次启动时 IO 读取，可以改用 Python 字典常量，减少文件依赖。

---

## 优先级汇总

| 优先级 | 数量 | 关键项 |
|--------|------|--------|
| P0 致命/安全 | 4 | 认证、密钥泄露、XSS |
| P1 功能缺失 | 5 | 题库 CRUD、会话列表 API、超时 |
| P2 体验改善 | 7 | 断线恢复、通知、统计、导出 |
| P3 长期规划 | 9 | 编程考核、语音、PDF、CI/CD |

**建议执行顺序**：先修 P0（安全基线）→ 补 P1 中 `GET /api/sessions` 和题库 CRUD（解除 localStorage 依赖）→ P2 中选 1-2 个高价值项 → 其余按需迭代。
