# 里程碑归档

> 基于设计文档 `docs/2026-07-02-resume-driven-interview-design.md` 第 10 节的实施路线图。
> 状态更新时间：2026-07-03

---

## 总览

| 里程碑 | 版本 | 状态 | 开始 | 完成 | 说明 |
|---|---|---|---|---|---|
| Phase 0 | v2.0.0 | ✅ 已完成 | 2026-07-02 | 2026-07-03 | 岗位管理系统 + 会话绑定 |
| Phase 1 | v2.1.0 | ✅ 已完成 | 2026-07-03 | 2026-07-03 | 简历解析 + 差距分析 + 策略生成 |
| Phase 2 | v2.2.0 | ✅ 已完成 | 2026-07-03 | 2026-07-03 | 新 FSM + 阶段拆分 + 岗位感知 |
| Phase 3 | — | ⬜ 未开始 | — | — | 分级评分 + 岗位匹配度 |
| Phase 4 | — | ⬜ 未开始 | — | — | 行为面试 + 文化匹配 |
| Phase 5 | — | ⬜ 未开始 | — | — | 完善 + 测试 + 迁移 |

---

## Phase 0 — 岗位管理系统

**版本**：v2.0.0 &nbsp;｜ &nbsp;**状态**：✅ 已完成

### 完成清单

- [x] JobPosition 数据模型 + DB 建表
- [x] 岗位 CRUD REST API（`/api/positions`）
- [x] 岗位列表 + 编辑页面前端（`/dashboard/positions`）
- [x] 种子数据：6 个预置岗位（`job_positions.json`）
- [x] Session ↔ JobPosition 绑定（一对一，`position_id` FK）
- [x] SessionCreateDialog 岗位选择器
- [x] 岗位表单 required_skills / preferred_skills 编辑器（P0 补修）
- [x] 缺失 i18n 键修复（`dashboard.failLoad` / `failDelete`）

### 关联文件

```
后端：models/job_position.py, schemas/job_position.py, api/rest_positions.py, db/seed.py, data/job_positions.json
前端：app/dashboard/positions/page.tsx, types/index.ts, lib/api.ts, i18n/locales/{en,zh}.json
```

---

## Phase 1 — 简历解析 + 差距分析 + 策略生成

**版本**：v2.1.0 &nbsp;｜ &nbsp;**状态**：✅ 已完成

### 完成清单

- [x] InterviewSession 模型扩展（6 个新字段）
- [x] 新增 Pydantic schemas：ResumeProfile, GapAnalysis, InterviewStrategy 等
- [x] 简历上传 API：`POST /api/sessions/{id}/resume`
- [x] 简历查询 API：`GET /api/sessions/{id}/resume`
- [x] 简历解析服务（`resume_parser.py`）：LLM 提取结构化 ResumeProfile
- [x] 差距分析服务（`gap_analyzer.py`）：确定性与 LLM 两阶段分析
- [x] 策略生成服务（`strategy_generator.py`）：分级权重预设 + LLM 个性化
- [x] 前端 SessionCreateDialog 增加简历上传区域
- [x] 文件提取器：PDF（PyPDF2）+ DOCX（python-docx）+ TXT

### 关联文件

```
后端：models/session.py, schemas/session.py, api/rest_sessions.py,
     services/resume_parser.py, services/gap_analyzer.py, services/strategy_generator.py
前端：components/dashboard/SessionCreateDialog.tsx, app/dashboard/page.tsx, lib/api.ts
依赖：python-docx, PyPDF2, python-multipart
```

### 未完成项（留待 Phase 2+ 消费）

- [ ] 面试开始时自动触发 GapAnalysis + Strategy 生成（目前 API 已就绪，InterviewAgent 尚未调用）
- [ ] 前端面试页面的简历预览组件
- [ ] 前端 GapAnalysis 概览展示

---

## Phase 2 — 新 FSM + 阶段拆分 + 岗位感知

**版本**：v2.2.0 &nbsp;｜ &nbsp;**状态**：✅ 已完成

### 完成清单

- [x] FSM 扩展：新增 STRATEGY_GEN, ICE_BREAK, PROJECT_DEEP_DIVE, TECHNICAL_ASSESSMENT, BEHAVIORAL, CANDIDATE_QA 状态
- [x] FSM 动态阶段排序：通过 `set_phase_order()` 注入阶段序列，`PHASE_COMPLETE` 事件动态路由
- [x] PhaseRouter：阶段序列管理 + 问题计数追踪（`phase_router.py`）
- [x] InterviewAgent 双模式重构：`simple` 模式保持完全向后兼容，`strategy` 模式支持多阶段路由
- [x] 策略自动生成：`_generate_strategy()` 在启动时自动调用 Phase 1 服务链
- [x] 岗位感知 System Prompt 注入：`build_for_phase()` 方法注入简历摘要、岗位要求、差距分析
- [x] 阶段 Prompt 模块（`prompts/phases/`）：ice_break / project_deep_dive / technical_assessment / behavioral / candidate_qa / wrapup / follow_up
- [x] 动态问题生成器（`question_generator.py`）：40% 岗位驱动 / 35% 简历驱动 / 25% 通用基础，LLM 优先 + 题库兜底
- [x] 追问链 + 岗位对照逻辑：`_decide_follow_up()` + `_ask_follow_up()`，最多 3 层追问
- [x] 前端多阶段进度条（`PhaseProgressBar.tsx`）：分段颜色显示 + 阶段名称 + 岗位上下文
- [x] WebSocket 消息类型扩展：`interview.phase_change` / `interview.follow_up` / `interview.position_context` / `interview.strategy_ready`
- [x] 前端类型 + Store + Hook 更新：支持所有新消息类型和阶段状态
- [x] i18n 翻译补全：6 个新阶段状态 + 阶段名称中英文
- [x] Question 模型新增 `phase` 字段
- [x] 断线重连支持策略模式恢复

### 关联文件

```
后端：core/fsm.py, core/phase_router.py (新), core/agent.py,
     services/question_generator.py (新),
     llm/prompts/system.py, llm/prompts/phases/*.py (新),
     models/question.py, api/ws_interview.py
前端：types/index.ts, stores/interview-store.ts, hooks/use-websocket.ts,
     components/interview/PhaseProgressBar.tsx (新),
     components/interview/InterviewHeader.tsx,
     i18n/locales/{en,zh}.json
```

### 向后兼容性

| 场景 | 行为 |
|---|---|
| 无简历 + 无岗位 | `simple` 模式，完整走现有 INTRO→QA_LOOP→WRAPUP 流程 |
| 有简历 + 无岗位 | 部分策略模式（简历驱动出题，无岗位对照） |
| 无简历 + 有岗位 | 部分策略模式（岗位驱动出题，无简历深挖） |
| 有简历 + 有岗位 | 完整策略模式（三维驱动，全功能激活） |

---

## Phase 3 — 分级评分 + 岗位匹配度

**版本**：— &nbsp;｜ &nbsp;**状态**：⬜ 未开始

### 计划任务

- [ ] 分级权重配置（L1/L2/L3，含 position_match 维度）
- [ ] BehavioralDimensions + PositionMatchDimensions schema
- [ ] EvaluationEngine 重构：支持分级权重 + 岗位匹配维度
- [ ] position_match_scoring Prompt（6 个子维度）
- [ ] 分阶段评分汇总
- [ ] 报告增强：岗位匹配雷达图数据 + 分阶段得分 + Gap 总结
- [ ] 前端报告页：雷达图组件 + 分阶段展示

### 依赖

- [ ] Phase 2（需要阶段结构来产生分阶段评分数据）

---

## Phase 4 — 行为面试 + 文化匹配

**版本**：— &nbsp;｜ &nbsp;**状态**：⬜ 未开始

### 计划任务

- [ ] 级别差异化的行为问题生成 Prompt（含岗位 soft_skill_requirements）
- [ ] 行为评估 Prompt
- [ ] 项目深挖中的行为线索自动提取
- [ ] culture_fit 评估（对照岗位团队文化要求）
- [ ] 前端行为面试阶段 UI + 岗位文化匹配展示

### 依赖

- [ ] Phase 2（需要 BEHAVIORAL 阶段）

---

## Phase 5 — 完善 + 测试 + 迁移

**版本**：— &nbsp;｜ &nbsp;**状态**：⬜ 未开始

### 计划任务

- [ ] 端到端集成测试（4 种配置组合）
- [ ] LLM 输出质量评估（A/B test）
- [ ] 异步任务优化（简历解析 + GapAnalysis 并行化）
- [ ] 异常处理 + 降级方案
- [ ] 前端体验优化 + 国际化补全
- [ ] `interview_templates.json` → JobPosition 迁移

### 依赖

- [ ] Phase 1-4 全部完成

---

## 变更日志索引

| 版本 | 日期 | 里程碑 | 变更摘要 |
|---|---|---|---|
| v2.1.0 | 2026-07-03 | Phase 1 | 简历上传 + 解析 + 差距分析 + 策略生成 |
| v2.0.0 | 2026-07-03 | Phase 0 | 岗位管理系统 + 双令牌认证 + 前端升级 |
| v1.0.1 | — | 初始 | 核心面试引擎 + 题库 + 报告 |

> 详细变更见 [`CHANGELOG.md`](CHANGELOG.md)
