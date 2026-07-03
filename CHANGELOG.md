# Changelog

本项目的所有重要变更记录。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [2.3.0] - 2026-07-03

### Added
- BehavioralDimensions + PositionMatchDimensions schema（`evaluation.py`）：5 个行为子维度 + 5 个岗位匹配子维度
- Answer 模型扩展：10 个新维度列 + `question_chain_depth` / `is_follow_up` / `relates_to_position_requirement`
- 评分 Prompt V2：阶段感知的评分提示（按阶段注入不同评估维度）
- 动态评分权重：EvaluationEngine 从 InterviewStrategy.scoring_weights 读取 L1/L2/L3 分级权重
- SessionReport 扩展：`phase_scores`（分阶段得分）、`position_match_summary`（雷达图数据）、`gap_summary`（差距分析总结）
- ReportService 增强：分阶段得分聚合 + 岗位匹配 5 维雷达图数据 + Gap 技能验证追踪
- SVG 雷达图组件（`RadarChart.tsx`）：纯 SVG 实现，无第三方图表库依赖
- 前端报告页增强：岗位匹配雷达图 + 分阶段得分进度条 + Gap 分析总结
- AnswerCard 增强：行为维度展示 + 岗位匹配维度展示 + 岗位要求关联标记
- 候选人结果页增强：岗位匹配雷达图
- i18n：14 个维度名称 + 8 个报告增强文案（中英文）

### Changed
- EvaluationEngine.evaluate() 签名扩展：新增可选 `weights`, `phase`, `position_context` 参数
- `_compute_weighted_score()` 改为动态权重：从 ScoringWeights 读取权重，自动包含 behavioral + position_match 维度
- Agent._evaluate_and_continue() 传入策略上下文：weights + phase + position_context
- ReportService 维度聚合扩展到全部 14 个维度字段

### Fixed
- EvaluationEngine 不再忽略 StrategyGeneratorService 生成的 grading weights

---

## [2.2.0] - 2026-07-03

### Added
- 多阶段 FSM：新增 6 个面试阶段状态（ICE_BREAK, PROJECT_DEEP_DIVE, TECHNICAL_ASSESSMENT, BEHAVIORAL, CANDIDATE_QA, STRATEGY_GEN）
- FSM 动态阶段排序：通过 `set_phase_order()` 支持数据驱动的阶段路由
- PhaseRouter：阶段序列管理与问题计数追踪
- InterviewAgent 双模式架构：`simple` 保持完全向后兼容，`strategy` 支持多阶段自适应面试
- 岗位感知 System Prompt 注入：`build_for_phase()` 方法注入简历/岗位/差距分析上下文
- 阶段专用 Prompt 模块（`prompts/phases/`）：7 个阶段和追问 Prompt 模板（双语）
- 动态问题生成器（`question_generator.py`）：40% 岗位驱动 / 35% 简历驱动 / 25% 通用基础，LLM 优先 + 题库兜底
- 追问链逻辑：LLM 决策是否追问 + 自动生成追问（最多 3 层），含岗位对照
- 前端多阶段进度条（PhaseProgressBar）：分段彩色进度条 + 岗位上下文提示
- WebSocket 新消息类型：`interview.phase_change`, `interview.follow_up`, `interview.position_context`, `interview.strategy_ready`
- 策略自动生成：面试启动时自动调用 Phase 1 服务链（解析→差距分析→策略生成）
- Question 模型新增 `phase` 字段用于阶段追踪

### Changed
- InterviewAgent 重构：新增策略模式支持，`handle_message()` 改为双模式分发
- SystemPromptBuilder 增强：支持阶段感知和岗位感知的 Prompt 构建
- 前端 Store/Hook 扩展：支持阶段状态、追问追踪、新 WebSocket 消息
- InterviewHeader 条件渲染：策略模式下显示 PhaseProgressBar 替代简单进度条

### Fixed
- 断线重连：策略模式下正确恢复阶段状态和 PhaseRouter

---

## [2.1.0] - 2026-07-03

### Added

- 简历上传功能：SessionCreateDialog 支持上传 PDF/DOCX/TXT 简历文件
- `POST /api/sessions/{id}/resume`：简历上传与文本提取 API
- `GET /api/sessions/{id}/resume`：查询简历解析状态与结果
- 简历解析服务（`resume_parser.py`）：LLM 提取结构化 ResumeProfile
- 差距分析服务（`gap_analyzer.py`）：简历画像 vs 岗位要求对比分析
- 策略生成服务（`strategy_generator.py`）：三维驱动（简历 ⊗ 岗位 ⊗ 级别）面试策略
- InterviewSession 扩展字段：`resume_text`, `resume_profile_json`, `gap_analysis_json`, `interview_strategy_json`, `current_phase`, `phase_question_counts`
- 岗位表单增加 required_skills / preferred_skills 编辑器

### Fixed

- 补充缺失的 i18n 键：`dashboard.failLoad` 和 `dashboard.failDelete`

---

## [2.0.0] - 2026-07-03

### Added
- 岗位绑定功能：会话创建时可关联 JobPosition，面试聚焦岗位技能
- Session Token 双令牌认证（admin_token + candidate_token）
- 输入消毒：XSS 防护（HTML 标签剥离 + maxLength 校验）
- pre-commit hook：阻止 API key 被提交到仓库

### Changed
- 前端全面升级到 Next.js 16 + React 19 + Tailwind CSS v4
- UI 组件从 Radix 迁移到 Base UI 原语 + shadcn (base-nova)
- 状态管理引入 Zustand 替代原有方案

### Fixed
- 移除 `.claude/` 目录的版本跟踪，加入 `.gitignore`

---

## [1.0.1] - 初始版本

### Added
- FastAPI 后端：AI 面试官核心引擎（FSM 状态机 + LLM 对话 + 评分）
- REST API：会话 CRUD、问题库管理、报告生成
- WebSocket 实时面试通道
- 面试模板和问题银行 JSON 数据文件
- 自适应难度调节
- 会话断线恢复
- 前端仪表盘和面试聊天室
