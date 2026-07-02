# P0 致命问题 — 解决方案

---

## P0-1 缺少身份认证与权限控制

### 问题

所有 API 完全开放：
- 任何人拿到 session_id 可以看任意报告
- Dashboard 无任何访问限制
- Delete 端点可被恶意调用清空数据

### 方案：Session Token 双密钥模式

**原理**：创建 session 时生成两个随机 token——`admin_token` 和 `candidate_token`。API 调用必须携带正确的 token。

```
创建会话:
  POST /api/sessions
  → 返回 { session_id, admin_token, candidate_token }

面试官 Dashboard:
  Header: X-Admin-Token: <admin_token>
  → 可查看/删除自己创建的会话

候选人面试/报告:
  URL: /interview/{session_id}?token=<candidate_token>
  URL: /report/{session_id}?token=<candidate_token>
  → 只能访问这一个会话
```

### 实施步骤

**Step 1**：Model 加字段
```python
# models/session.py
admin_token: Mapped[str] = mapped_column(
    String(64), nullable=False, unique=True,
    default=lambda: secrets.token_urlsafe(32)
)
candidate_token: Mapped[str] = mapped_column(
    String(64), nullable=False, unique=True,
    default=lambda: secrets.token_urlsafe(32)
)
```

**Step 2**：Schema 返回 token（仅创建时）
```python
# schemas/session.py
class CreateSessionResponse(SessionResponse):
    admin_token: str
    candidate_token: str

class SessionResponse(BaseModel):
    # ... 现有字段
    # 不包含 token，防止泄露
```

**Step 3**：创建端点返回 token
```python
# rest_sessions.py
@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest, db: AsyncSession):
    session = InterviewSession(...)
    db.add(session)
    await db.commit()
    return session  # 只有这一次返回 token
```

**Step 4**：中间件校验 token
```python
# api/auth.py
from fastapi import Header, HTTPException

async def verify_admin_token(
    session_id: str,
    x_admin_token: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> InterviewSession:
    session = await db.get(InterviewSession, session_id)
    if not session or session.admin_token != x_admin_token:
        raise HTTPException(403, "Forbidden")
    return session

async def verify_candidate_token(
    session_id: str,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewSession:
    session = await db.get(InterviewSession, session_id)
    if not session or session.candidate_token != token:
        raise HTTPException(403, "Forbidden")
    return session
```

**Step 5**：受保护的端点
```python
# 面试官端
@router.get("/sessions/{session_id}/report")
async def get_report(session = Depends(verify_admin_token)):
    ...

@router.delete("/sessions/{session_id}")
async def delete_session(session = Depends(verify_admin_token)):
    ...

# 候选人端
@router.get("/sessions/{session_id}")
async def get_session(session = Depends(verify_candidate_token)):
    ...
```

**Step 6**：前端适配
```typescript
// Dashboard: 创建会话后保存 admin_token
const session = await createSession(data)
localStorage.setItem(`admin_${session.id}`, session.admin_token)

// 请求时带上
fetch(`/api/sessions/${id}/report`, {
    headers: { 'X-Admin-Token': localStorage.getItem(`admin_${id}`) }
})

// 面试页 URL 携带 token
window.open(`/interview/${session.id}?token=${session.candidate_token}`)
```

**工作量**：~2 小时

---

## P0-2 `.claude/` 目录被提交到仓库

### 问题

`.claude/settings.local.json` 已存在于 git 历史中，包含本地 IDE 配置。

### 方案

**Step 1**：追加 `.gitignore`
```
# Claude IDE
.claude/
```

**Step 2**：从 git 历史中移除
```bash
git rm --cached -r .claude/
git commit -m "Remove .claude/ from tracking"
```

**工作量**：5 分钟（`.claude/` 是本地工具目录，不影响项目运行）

---

## P0-3 API Key 泄露风险

### 问题

- `.env.example` 曾被推送含真实 `DEEPSEEK_API_KEY`，虽已 amend 但 git reflog 中仍可恢复
- `.env` 虽在 `.gitignore` 中，但模板文件 `.env.example` 容易误填真实值

### 方案

**Step 1**：立即轮换密钥（用户操作）
- 登录 DeepSeek 控制台 → API Keys → 删除旧 key → 创建新 key
- 更新本地 `.env` 中的 `DEEPSEEK_API_KEY`

**Step 2**：添加 pre-commit hook 防再次泄露

```bash
# .githooks/pre-commit
#!/bin/bash
# Prevent API keys from being committed

PATTERNS=(
    'sk-[a-zA-Z0-9]{20,}'            # DeepSeek / OpenAI key
    'sk-ant-[a-zA-Z0-9]{20,}'        # Anthropic key
)

for pattern in "${PATTERNS[@]}"; do
    matches=$(git diff --cached -G"$pattern" --name-only)
    if [ -n "$matches" ]; then
        echo "❌ API key detected in:"
        echo "$matches"
        echo "Add to .gitignore or use .env instead"
        exit 1
    fi
done
```

```bash
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

**Step 3**：清理 git 历史中的残留（可选，更彻底）

```bash
# 使用 git filter-branch 或 BFG Repo-Cleaner 清理历史
# 如果仓库刚创建且只有一次提交，直接重建：
git checkout --orphan temp_branch
git add -A
git commit -m "V1.0"
git branch -D master
git branch -m master
git push -f origin master
```

> **注意**：Step 3 只有在仓库无其他协作者时可用。当前仓库仅 1 次提交，可以安全执行。

**工作量**：15 分钟

---

## P0-4 输入校验不足（XSS 风险）

### 问题

- `candidate_name`、`job_title` 等字段无 HTML 标签过滤
- `answer.content` 直接存储到数据库
- 前端渲染 `message.content` 时虽然用了 `whitespace-pre-wrap`，但没有对 HTML 实体转义

### 方案

**后端：Pydantic validator 过滤**

```python
# schemas/session.py
from pydantic import field_validator
import re

class CreateSessionRequest(BaseModel):
    candidate_name: str = Field(..., min_length=1, max_length=100)
    job_title: str = Field(..., min_length=1, max_length=200)

    @field_validator("candidate_name", "job_title")
    @classmethod
    def strip_html(cls, v: str) -> str:
        return re.sub(r"<[^>]*>", "", v).strip()
```

```python
# 同样的校验用于 WebSocket 消息
class AnswerPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def strip_html(cls, v: str) -> str:
        return re.sub(r"<[^>]*>", "", v).strip()
```

**前端：React 默认安全（已有保护，只需确认）**

React 的 JSX 默认转义 `{message.content}`，无需额外处理。唯一需要确认的是没有使用 `dangerouslySetInnerHTML`：

```bash
grep -r "dangerouslySetInnerHTML" frontend/src/
# 应该为空
```

**前端补充：限制输入长度**

```tsx
// InputPanel.tsx
<Textarea
    maxLength={5000}
    ...
/>
```

**工作量**：15 分钟

---

## 实施顺序

| 序号 | 项目 | 时间 | 依赖 |
|------|------|------|------|
| 1 | P0-2 移除 `.claude/` | 5min | 无 |
| 2 | P0-3 轮换密钥 + hook | 15min | 无 |
| 3 | P0-4 输入校验 | 15min | 无 |
| 4 | P0-1 Token 认证 | 2h | 前 3 项完成后 |
| **总计** | | **~2.5h** | |

---

## 影响评估

| 项 | 前端改动 | 后端改动 | DB 变更 | 兼容性 |
|----|---------|---------|---------|--------|
| P0-1 Token 认证 | 3 文件（api.ts, dashboard, interview page） | 5 文件（auth.py + 端点） | 2 新列 | URL 参数变化 |
| P0-2 移除 .claude | 无 | 无 | 无 | 无影响 |
| P0-3 密钥防护 | 无 | 无 | 无 | 需轮换真实 key |
| P0-4 输入校验 | 1 文件 | 2 文件 | 无 | 无影响 |

需要我开始实施哪个？建议先做 P0-2 + P0-3 + P0-4（快速修复），再做 P0-1（核心改动）。
