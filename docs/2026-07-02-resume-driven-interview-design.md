# 基于简历 + 岗位的自适应面试流程 — 设计方案

> 状态：规划阶段 | 日期：2026-07-02 | 更新：融入岗位体系

---

## 一、问题分析：当前系统的局限

当前系统采用**静态题库随机抽题**模式，存在以下核心问题：

| 局限 | 详情 |
|---|---|
| **无简历感知** | 面试官 Agent 对候选人背景一无所知，所有候选人面对同一套题 |
| **无岗位绑定** | 面试 Session 不绑定具体岗位，无法针对 JD 要求进行匹配度评估 |
| **无个性化追问** | 无法针对候选人简历中的项目经历进行深度挖掘 |
| **固定评分权重** | 初级/中级/高级使用相同的四维权重（30/20/15/35），不符合实际用人标准 |
| **缺少行为面试** | 没有工作态度、团队协作、职业规划等软技能评估 |
| **问题无上下文** | 题目与题目之间相互独立，无法形成「由浅入深、逐层递进」的追问链 |
| **开场生硬** | Intro 阶段只是简单问候，没有基于简历 + 岗位的破冰对话 |
| **缺岗位匹配评估** | 无法评估候选人与岗位的匹配程度（技能匹配度、经验匹配度、文化匹配度） |

---

## 二、新方案核心思路

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         面试全流程（新）                                   │
│                                                                          │
│  [简历上传] ──→ [简历解析] ──→ [面试策略生成] ──→ [结构化面试执行]          │
│       │              │                │                   │              │
│       ▼              ▼                ▼                   ▼              │
│   PDF/DOCX      LLM提取        简历 ⊗ 岗位 ⊗ 级别    多阶段自适应问答      │
│   文本解析      结构化信息      三者融合生成个性化题纲   + 实时评分反馈       │
│                                             │                            │
│  [岗位管理] ──→ [岗位选择] ─────────────────┘                            │
│       │              │                                                   │
│       ▼              ▼                                                   │
│   创建/维护      绑定1个岗位                                              │
│   岗位JD         到面试Session                                           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

核心转变：**从「题库抽题」变为「简历 ⊗ 岗位 ⊗ 级别 三维驱动的自适应对话」**。

### 三个核心输入源

```
                    ┌──────────────┐
                    │   面试策略    │
                    │  (融合生成)   │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │   简历画像    │ │   岗位要求    │ │   目标级别    │
   │              │ │              │ │              │
   │ • 技能栈     │ │ • 必备技能    │ │ • 初级 L1    │
   │ • 项目经历   │ │ • 加分技能    │ │ • 中级 L2    │
   │ • 工作年限   │ │ • 岗位职责    │ │ • 高级 L3    │
   │ • 学历背景   │ │ • 部门/业务   │ │              │
   │ • 疑点标记   │ │ • 团队协作要求 │ │              │
   └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 三、岗位管理系统

### 3.1 岗位数据模型

```python
class JobPosition(Base):
    """岗位定义 — 可复用的 JD 模板"""
    __tablename__ = "job_positions"

    id: str (UUID, PK)
    title: str(200)                    # 岗位名称，如「高级后端工程师」
    department: str(100)               # 部门，如「基础架构部」
    level: str(20)                     # 目标级别：junior / mid / senior
    status: str(20)                    # active / archived

    # 岗位描述
    description: text                  # 岗位概述
    responsibilities: JSON             # 岗位职责列表
    # ["设计和实现高可用微服务架构", "Code Review 团队成员代码", ...]

    # 技能要求（分类分级）
    required_skills: JSON              # 必备技能
    # [{"skill": "Python", "min_years": 3, "level": "proficient"},
    #  {"skill": "Kubernetes", "min_years": 1, "level": "familiar"}, ...]
    preferred_skills: JSON             # 加分技能
    # [{"skill": "Rust", "level": "familiar"},
    #  {"skill": "分布式系统设计", "level": "proficient"}, ...]

    # 软技能要求
    soft_skill_requirements: JSON
    # {"teamwork": "high", "communication": "high",
    #  "ownership": "high", "leadership": "medium"}

    # 业务/领域要求
    domain_knowledge: JSON | None
    # ["互联网金融", "高并发系统", "数据处理"]

    # 面试配置（岗位级别的默认值，可在 Session 创建时覆盖）
    default_total_questions: int = 8
    default_duration_minutes: int = 45
    interview_focus_areas: JSON         # 该岗位面试应重点考察的方向
    # ["系统设计", "代码质量", "问题排查", "团队协作"]

    created_at, updated_at: datetime
```

### 3.2 Session 与岗位的绑定

```
┌─────────────────────────────────────────────────────────────────┐
│                    Session ↔ 岗位 绑定关系                       │
│                                                                 │
│   InterviewSession                                              │
│   ┌───────────────────────────────────────────┐                │
│   │ id, candidate_name, experience_level, ...  │                │
│   │ resume_text, resume_profile_json           │                │
│   │ position_id: "uuid-1"                ← 新增  │               │
│   └──────────────┬────────────────────────────┘                │
│                  │ 1:1 (一个 Session 绑定一个岗位)                │
│                  ▼                                              │
│   ┌──────────────────────────┐                                  │
│   │ JobPosition              │                                  │
│   │ title: "高级后端工程师"   │                                  │
│   │ level: "senior"          │                                  │
│   │ department: "基础架构部"  │                                  │
│   └──────────────────────────┘                                  │
│                                                                 │
│   场景示例：                                                      │
│   - 初级岗位面试：绑定目标岗位，聚焦基础能力验证                  │
│   - 高级/架构师面试：绑定目标岗位，考察多维度高阶能力               │
│   - 内部转岗面试：绑定目标部门岗位，重点评估匹配度                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 岗位的 REST API

```
POST   /api/positions              # 创建岗位
GET    /api/positions              # 岗位列表（分页、筛选、搜索）
GET    /api/positions/{id}         # 岗位详情
PUT    /api/positions/{id}         # 更新岗位
DELETE /api/positions/{id}         # 归档岗位（软删除）
POST   /api/positions/{id}/copy    # 复制岗位（快速创建变体）
```

---

## 四、面试阶段重新设计

### 4.1 新状态机

```
现有 FSM（简单线性）:
  IDLE → INTRO → QA_LOOP → WRAPUP → DONE

新 FSM（多阶段、有策略）:
  IDLE → STRATEGY_GEN → ICE_BREAK → PROJECT_DEEP_DIVE
      → TECHNICAL_ASSESSMENT → BEHAVIORAL → CANDIDATE_QA
      → WRAPUP → DONE
      (各阶段支持 PAUSED / 超时自动推进)

其中 STRATEGY_GEN 是面试官内部阶段（候选人不可见），负责：
  简历解析 + 岗位要求分析 + 级别确定 → 生成面试策略
```

### 4.2 各阶段详解

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 0: STRATEGY_GEN（策略生成，面试官内部阶段，候选人不可见）              │
├──────────────────────────────────────────────────────────────────────────┤
│ • 输入：                                                                 │
│   - 候选人简历文件（PDF/DOCX/TXT）或手动填写的 profile                     │
│   - 绑定的岗位（含完整 JD）                                               │
│   - 目标级别（junior / mid / senior）                                     │
│ • 处理流程：                                                              │
│   1. LLM 解析简历 → ResumeProfile（技能、项目、履历、疑点）               │
│   2. 将 ResumeProfile 与 岗位要求 做 diff 分析 → GapAnalysis             │
│   3. 根据 GapAnalysis + 级别 → 生成 InterviewStrategy                    │
│ • 产物：                                                                 │
│   - ResumeProfile JSON                                                   │
│   - GapAnalysis JSON（技能差距、经验差距、项目匹配度）                    │
│   - InterviewStrategy JSON（分阶段面试计划）                              │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 1: ICE_BREAK（破冰 + 简历确认 + 岗位介绍，3-5 分钟）                  │
├──────────────────────────────────────────────────────────────────────────┤
│ • 目标：建立信任、确认简历关键信息、介绍岗位背景、观察沟通风格              │
│ • Agent 行为：                                                           │
│   - 基于简历 + 岗位生成个性化开场白                                       │
│   - 简要介绍岗位背景（让候选人感知到面试是「双向选择」）                    │
│   - 确认当前职位/工作状态                                                 │
│   - 对简历与岗位的「交汇点」做轻松讨论                                    │
│     （例：「你在 XX 项目用的技术栈和我们岗位要求很匹配」）                 │
│   - 说明接下来的面试流程                                                  │
│ • 评分维度：communication（沟通表达）                                     │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 2: PROJECT_DEEP_DIVE（项目深挖，10-15 分钟）                          │
├──────────────────────────────────────────────────────────────────────────┤
│ • 目标：验证简历真实性、评估技术深度、判断项目经验与岗位的匹配度            │
│ • Agent 行为：                                                           │
│   - 从简历中优先挑选与**岗位技术栈最相关**的 1-2 个项目                     │
│   - 按 STAR 方法追问：背景 → 任务 → 行动 → 结果                           │
│   - 追问技术决策：「为什么选 X 而不是 Y？」（对照岗位技术栈）               │
│   - 追问难点：「遇到的最大挑战是什么？怎么解决的？」                        │
│   - 追问量化结果：「性能提升多少？用户量多少？」                            │
│   - **对照岗位职责** 追问：「你在项目中承担的角色，和我们岗位要求的 XX 类似」 │
│ • 评分维度：                                                             │
│   - technical_accuracy（所述技术细节是否合理）                             │
│   - depth_of_knowledge（对项目技术栈的理解深度）                           │
│   - problem_solving（面对挑战时的解决思路）                                │
│   - communication（能否清晰描述复杂项目）                                 │
│   - position_match（项目经验与岗位要求的匹配度）← 新增                     │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 3: TECHNICAL_ASSESSMENT（技术能力评估，15-20 分钟）                    │
├──────────────────────────────────────────────────────────────────────────┤
│ • 目标：系统评估技术能力，对标岗位技能要求                                  │
│ • Agent 行为：                                                           │
│   - LLM 动态生成技术问题，三个子阶段：                                     │
│     a) 基础验证——确认简历声称的技能是否真实（对照岗位必备技能）             │
│     b) 深度探索——逐步提高难度，探测能力上限（对照岗位加分技能）             │
│     c) 场景设计——给出与岗位职责相关的实际场景，考察综合运用能力             │
│   - 每道题都是前一道的延伸或深化                                          │
│   - 错误回答 → 降低难度或换方向                                           │
│   - 优秀回答 → 追问更深层次或相关领域                                      │
│ • 问题的生成策略（三级来源）：                                             │
│   ┌──────────────────────────────────────────────────────────────┐       │
│   │ 40% 岗位驱动 —— 围绕 JD 的必备技能 + 核心职责                  │       │
│   │    例：岗位要求「高并发系统设计」→ 出高并发场景设计题           │       │
│   │                                                              │       │
│   │ 35% 简历驱动 —— 围绕候选人声称的技术栈 + 简历疑点              │       │
│   │    例：简历声称「精通 K8s」→ 出 K8s 调度/网络/排障题          │       │
│   │                                                              │       │
│   │ 25% 通用基础 —— CS 基础、系统设计、代码质量等                  │       │
│   │    例：数据结构、网络协议、设计模式                            │       │
│   └──────────────────────────────────────────────────────────────┘       │
│ • 评分维度：全部四个维度 + position_match                                 │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 4: BEHAVIORAL（行为/态度评估，5-10 分钟）                              │
├──────────────────────────────────────────────────────────────────────────┤
│ • 目标：评估工作态度、团队协作、职业规划、与岗位文化要求的匹配度            │
│ • Agent 行为：                                                           │
│   - 结合**岗位的 soft_skill_requirements** 生成差异化行为问题：            │
│     • 初级 + 岗位注重「学习能力」→ 问学习新技术的方法、失败经历            │
│     • 中级 + 岗位注重「团队协作」→ 问跨团队合作场景、冲突处理              │
│     • 高级 + 岗位注重「领导力」→ 问技术规划、团队建设、决策冲突            │
│   - 结合项目深挖中发现的行为线索追问                                      │
│   - 评估候选人对岗位的**文化匹配度**                                      │
│ • 评分维度：                                                             │
│   - teamwork / leadership（团队协作/领导力）                              │
│   - ownership（责任心）                                                   │
│   - growth_mindset（成长心态）                                            │
│   - position_culture_fit（与岗位团队文化匹配度）← 新增                     │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 5: CANDIDATE_QA（候选人反问，3-5 分钟）                                │
├──────────────────────────────────────────────────────────────────────────┤
│ • 目标：回答候选人关于岗位/团队的疑问，观察其关注点                         │
│ • Agent 行为：                                                           │
│   - 开放式邀请候选人提问（尤其鼓励关于岗位职责、技术方向的问题）            │
│   - 基于岗位信息回答关于技术栈、团队结构、业务方向的问题                   │
│   - 从反问质量侧面评估候选人的关注层次（技术/业务/成长/薪资）               │
│ • 评分维度：轻量观察（不纳入正式评分，但记入面试记录）                      │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 6: WRAPUP（总结结束，2-3 分钟）                                        │
├──────────────────────────────────────────────────────────────────────────┤
│ • 目标：专业收尾，说明后续流程                                             │
│ • Agent 行为：                                                            │
│   - 感谢候选人时间                                                        │
│   - 简要概括面试覆盖的内容（提及岗位相关的重点考察方向）                    │
│   - 说明下一步（HR 联系 / 结果反馈时间）                                   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 五、分级评分权重体系

### 5.1 维度权重矩阵

不同级别的候选人，评估的侧重点不同（结合岗位要求动态微调 ±5%）：

```
┌──────────────────────────────────────────────────────────────────────┐
│                       分级评分权重矩阵                                 │
├────────────────────┬──────────┬──────────┬──────────┬────────────────┤
│ 维度                │ 初级 (L1)│ 中级 (L2)│ 高级 (L3)│ 评估方式        │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ 技术准确性           │   20%   │   15%   │   10%   │ LLM 语义评判    │
│ (technical_accuracy)│          │          │          │                 │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ 知识深度/广度        │   10%   │   15%   │   20%   │ LLM + 追问链     │
│ (depth_of_knowledge)│          │          │          │                 │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ 问题解决能力         │   15%   │   20%   │   25%   │ 场景题 + 项目追问 │
│ (problem_solving)   │          │          │          │                 │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ 沟通表达             │   10%   │   10%   │    5%   │ 全流程观察       │
│ (communication)     │          │          │          │                 │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ 行为/态度            │   20%   │   20%   │   20%   │ 行为面试 + 项目  │
│ (behavioral)        │          │          │          │ 深挖中的行为线索 │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ 岗位匹配度           │   25%   │   20%   │   20%   │ 全流程对标岗位JD │
│ (position_match)    │          │          │          │                 │
├────────────────────┼──────────┼──────────┼──────────┼────────────────┤
│                     │  100%   │  100%   │  100%   │                 │
└────────────────────┴──────────┴──────────┴──────────┴────────────────┘
```

### 5.2 权重设计的逻辑

- **初级**：岗位匹配度权重最高（招初级最看重「能不能快速上手岗位工作」），行为/态度次之（考察成长潜力），技术准确回到基础验证
- **中级**：问题解决 + 行为/态度 + 岗位匹配三足鼎立（能独立承担岗位职责，融入团队）
- **高级**：问题解决权重最高（架构能力、复杂问题处理），知识深度次之，沟通和技术准确权重降低（因为默认高级候选人这些方面已经过关）

### 5.3 岗位匹配度维度详解

```
position_match（岗位匹配度）的评估子维度：

┌──────────────────────────────────────────────────────────────────┐
│ 子维度               │ 评估内容                                   │
├──────────────────────────────────────────────────────────────────┤
│ skill_coverage       │ 候选人的技能栈覆盖了多少岗位必备/加分技能    │
│ experience_alignment │ 候选人过往经验与岗位职责的匹配程度           │
│ level_alignment      │ 候选人的能力级别与岗位目标级别是否匹配       │
│ domain_fit           │ 候选人的行业/领域经验与岗位业务方向是否匹配  │
│ culture_fit          │ 候选人的工作风格与岗位团队文化是否匹配       │
│ growth_potential     │ 候选人在该岗位上的成长空间和潜力             │
└──────────────────────────────────────────────────────────────────┘

在面试的每个阶段评估不同的子维度：
  ICE_BREAK           → culture_fit (初步感知)
  PROJECT_DEEP_DIVE   → experience_alignment, skill_coverage
  TECHNICAL_ASSESSMENT → skill_coverage, level_alignment, domain_fit
  BEHAVIORAL          → culture_fit, growth_potential
```

---

## 六、新增数据模型

### 6.1 GapAnalysis（简历与岗位差距分析）

```python
class GapAnalysis(BaseModel):
    """简历画像与岗位要求的差距分析"""
    position_id: str
    position_title: str

    # 技能匹配
    skills_matched: list[SkillMatch]
    # {skill_name, required_level, candidate_level, is_gap}
    skills_missing: list[str]          # 岗位要求但候选人完全不具备的技能
    skills_exceeding: list[str]        # 候选人具备但岗位不需要的额外技能
    skill_coverage_pct: float          # 技能覆盖率 0-100%

    # 经验匹配
    experience_gap_summary: str        # 「候选人缺少 X 年 Y 领域经验」
    project_relevance_score: float     # 项目经验与岗位职责的相关性 1-5

    # 级别匹配
    candidate_inferred_level: str      # 从简历推断的级别
    position_target_level: str         # 岗位的目标级别
    level_delta: int                   # -1 (偏低), 0 (匹配), +1 (偏高)

    # 面试策略建议
    recommended_focus_areas: list[str] # 面试应该重点考察的方向
    risk_areas: list[str]              # 需要重点验证的疑点
```

### 6.2 ResumeProfile（简历画像）

```python
class ResumeProfile(BaseModel):
    """LLM 从简历中提取的结构化信息"""
    name: str
    years_of_experience: float
    education: list[EducationEntry]
    skills: list[SkillEntry]          # {name, level_inferred, years}
    projects: list[ProjectEntry]
    work_history: list[WorkEntry]
    inferred_level: str
    key_strengths: list[str]
    potential_risk_areas: list[str]   # 需要重点验证的技能/经历
```

### 6.3 InterviewStrategy（面试策略 — 融合简历 + 岗位）

```python
class InterviewStrategy(BaseModel):
    """基于简历画像 + 岗位要求 + 目标级别 生成的面试执行策略"""
    session_id: str

    # 输入摘要
    resume_summary: str               # 简历一句话摘要
    position_summary: str              # 岗位的一句话摘要
    gap_analysis: GapAnalysis | None   # 与绑定岗位的差距分析

    # 各阶段配置
    phases: list[PhaseConfig]
    # {phase_name, max_duration_minutes, min_questions, max_questions,
    #  focus_areas (该阶段重点考察的方向)}

    # 技术考察范围（简历 ∩ 岗位 的交集 + 岗位独特要求 + 简历疑点）
    tech_focus_areas: list[TechFocusArea]
    # {topic, source("resume"|"position"|"both"), priority(1-5),
    #  suggested_difficulty, candidate_claimed_level, position_required_level}

    # 项目深挖目标（优先选择与岗位技术栈匹配的项目）
    project_deep_dive_targets: list[ProjectDeepDiveTarget]
    # {project_id, project_name, relevance_to_position(1-5),
    #  suggested_angle, tech_stack_overlap_with_position}

    # 行为面试主题（结合岗位 soft_skill_requirements + 级别定制）
    behavioral_themes: list[BehavioralTheme]
    # {theme, priority, source("level"|"position"|"resume_gap"),
    #  position_context, suggested_questions}

    # 评分权重（根据级别 + 岗位要求动态确定）
    scoring_weights: ScoringWeights

    # 难度曲线策略
    difficulty_strategy: str  # "conservative" | "standard" | "aggressive"

    # 面试节奏建议
    suggested_question_distribution: dict[str, int]
    # {"project_deep_dive": 2, "technical_base": 2, "technical_deep": 2,
    #  "technical_scenario": 1, "behavioral": 2}
```

### 6.4 扩展 InterviewSession

```python
# 现有 InterviewSession 新增字段：
class InterviewSession(Base):
    # ... 现有字段 ...

    # 新增：岗位绑定
    position_id: str | None            # 绑定的岗位 ID

    # 新增：简历相关
    resume_text: str | None
    resume_profile_json: dict | None
    gap_analysis_json: dict | None     # 与绑定岗位的差距分析

    # 新增：面试策略
    interview_strategy_json: dict | None

    # 新增：分阶段追踪
    current_phase: str | None
    phase_question_counts: dict | None
```

### 6.5 新评分维度

```python
class BehavioralDimensions(BaseModel):
    """行为面试维度"""
    teamwork: int | None = Field(None, ge=1, le=5)
    leadership: int | None = Field(None, ge=1, le=5)
    ownership: int | None = Field(None, ge=1, le=5)
    growth_mindset: int | None = Field(None, ge=1, le=5)
    culture_fit: int | None = Field(None, ge=1, le=5)

class PositionMatchDimensions(BaseModel):
    """岗位匹配度维度（新增）"""
    skill_coverage: int = Field(..., ge=1, le=5)
    experience_alignment: int = Field(..., ge=1, le=5)
    level_alignment: int = Field(..., ge=1, le=5)
    domain_fit: int = Field(..., ge=1, le=5)
    growth_potential: int = Field(..., ge=1, le=5)

class ExtendedEvaluationResult(EvaluationResult):
    """扩展现有评估结果"""
    behavioral: BehavioralDimensions | None = None
    position_match: PositionMatchDimensions | None = None
    question_chain_depth: int = 0
    is_follow_up: bool = False
    relates_to_position_requirement: str | None = None  # 该题关联的岗位要求
```

---

## 七、面试报告增强

### 7.1 新增报告内容

```
相比现有报告，新增：
┌──────────────────────────────────────────────────────────────────┐
│                    增强后的面试报告结构                            │
│                                                                  │
│  1. 基本信息                                                      │
│     - 候选人姓名、岗位、级别、面试时长                              │
│                                                                  │
│  2. 岗位匹配雷达图 ← 新增                                         │
│     - 技能覆盖度 / 经验匹配度 / 级别匹配度 / 领域匹配度 / 成长潜力  │
│                                                                  │
│  3. 分阶段得分明细 ← 新增                                         │
│     - 项目深挖 / 技术评估 / 行为面试 各阶段平均分                   │
│                                                                  │
│  4. 综合评分（分级权重加权）                                       │
│     - 各技术维度 + 行为维度 + 岗位匹配度                           │
│                                                                  │
│  5. 逐题详情                                                      │
│     - 问题 + 回答 + 评分 + 关联的岗位要求 ← 新增关联标记           │
│                                                                  │
│  6. 面试官建议 ← 增强                                             │
│     - 是否推荐进入下一轮                                           │
│     - 候选人的核心优势（对标岗位）                                  │
│     - 候选人的主要短板（对标岗位）                                  │
│     - 建议的入职后培养方向（如有）                                  │
│                                                                  │
│  7. GapAnalysis 总结 ← 新增                                       │
│     - 技能缺口清单                                                 │
│     - 面试中已验证 vs 未验证的技能                                  │
│     - 入职后需培训的方向                                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 八、LLM Prompt 体系重构

### 8.1 新 Prompt 架构

```
现有 Prompt（简单）:
  └── interviewer.py（固定模板 + 简单格式化）
  └── scoring.py（固定评分模板）

新 Prompt 架构（分层、可组合、岗位感知）:
  ├── system/
  │   ├── interviewer_persona.py      # 面试官人设（含岗位背景知识）
  │   └── phase_context.py            # 阶段上下文构建（含岗位上下文注入）
  ├── phases/
  │   ├── ice_break.py                # 破冰：简历亮点 + 岗位介绍
  │   ├── project_deep_dive.py        # 项目深挖：对标岗位技术栈
  │   ├── technical_assessment.py     # 技术评估：岗位技能要求驱动
  │   ├── behavioral.py               # 行为面试：岗位软技能要求驱动
  │   └── wrapup.py                   # 结束：岗位后续流程说明
  ├── strategy/
  │   ├── resume_parser.py            # 简历 LLM 解析
  │   ├── gap_analyzer.py             # 简历 vs 岗位差距分析
  │   ├── strategy_generator.py       # 综合策略生成
  │   ├── question_generator.py       # 动态问题生成（简历+岗位双重驱动）
  │   ├── follow_up.py                # 追问生成
  │   └── difficulty_controller.py    # 难度控制逻辑
  └── scoring/
      ├── technical_scoring.py        # 技术维度评分
      ├── behavioral_scoring.py       # 行为维度评分
      ├── position_match_scoring.py   # 岗位匹配度评分 ← 新增
      └── overall_scoring.py          # 综合评分 + 报告生成
```

### 8.2 关键 Prompt 设计原则

```
问题生成 Prompt 核心要素（六层注入）:
  1. 简历上下文：「候选人在简历中声称精通 {skill}，有 {years} 年经验」
  2. 岗位要求注入：「该岗位的核心要求是 {requirements}」
  3. 岗位职责注入：「该岗位的主要职责包括 {responsibilities}，请围绕这些职责出题」
  4. 差距分析注入：「简历与岗位的差距在于 {gaps}，请重点验证这些方面」
  5. 前序问答注入：「上一题候选人回答得分 {score}，提到了 {key_points}」
  6. 难度控制提示：「当前难度 {difficulty}，请生成一道难度适中的问题」

岗位感知追问策略:
  - 候选人回答出色 → 追问到岗位加分技能方向（探测上限）
  - 候选人回答一般 → 追问岗位必备技能的更基础层面（确认下限）
  - 候选人回答差 → 标记为岗位技能缺口（gap），降低难度或换方向
  - 候选人与岗位技能不匹配 → 探索其学习能力和转岗意愿
```

### 8.3 岗位感知的 System Prompt

```
面试官 System Prompt 新增岗位上下文段：

「你正在面试 {candidate_name}，目标岗位是 {position_title} ({department})。
 该岗位的核心职责：{responsibilities}
 必备技能：{required_skills}
 加分技能：{preferred_skills}
 软技能要求：{soft_skills}

 候选人的简历画像显示：
 - 技能覆盖率：{skill_coverage}%
 - 与岗位的差距：{gaps}
 - 需要重点验证的方向：{focus_areas}

 你的面试策略是：{strategy_summary}

 在面试过程中：
 1. 对岗位必备技能，验证候选人是否真的掌握（而非简历夸大）
 2. 对岗位加分技能，尝试探测候选人的上限
 3. 对简历与岗位的差距区域，评估候选人的学习能力和适应力
 4. 始终结合岗位实际场景出题，而非抽象理论」
```

---

## 九、前端改造要点

### 9.1 新增页面/组件

```
新增:
  ├── 岗位管理页（/positions）
  │   ├── 岗位列表（搜索、筛选、状态管理）
  │   ├── 岗位创建/编辑表单（含技能要求编辑器）
  │   └── 岗位详情预览
  ├── 简历上传页（创建 Session 时上传简历文件）
  ├── 简历预览组件（面试官端查看解析结果 + GapAnalysis 展示）
  ├── 面试策略预览（展示各阶段计划、题目数、时间分配、与岗位的对照）
  ├── 多阶段进度条（替换当前简单的题目进度）
  └── 岗位匹配雷达图（报告页）

改造:
  ├── SessionCreateDialog → 增加：
  │   ├── 岗位选择器（搜索 + 单选，显示岗位关键信息）
  │   ├── 简历上传（拖拽 + 解析进度）
  │   ├── 级别选择（可从岗位默认级别自动填充）
  │   └── 策略预览（岗位匹配快照）
  ├── interview/[sessionId]/page.tsx → 显示：
  │   ├── 当前阶段名称 + 阶段进度
  │   └── 当前阶段与岗位要求的关联提示（面试官端可见）
  └── ReportHeader → 展示：
      ├── 分阶段得分
      ├── 岗位匹配度雷达图
      └── 完整多维评分
```

### 9.2 WebSocket 消息扩展

```
新增消息类型:
  ├── interview.phase_change      # 阶段切换通知（含下一阶段的岗位关联信息）
  ├── interview.follow_up         # 追问（区别于新问题，标记为岗位某要求的深入）
  ├── interview.position_context  # 岗位上下文提示（面试官端可见的岗位相关信息）
  └── interview.strategy_ready    # 面试策略 + GapAnalysis 生成完毕（面试官端）
```

---

## 十、实施路线图

### Phase 0: 岗位管理系统（新增基础）

```
任务:
  1. 创建 JobPosition 数据模型 + DB migration
  2. 实现岗位 CRUD REST API（/api/positions）
  3. 实现岗位列表 + 编辑页面前端
  4. 种子数据：从现有 interview_templates.json 迁移出初始岗位
  5. Session 与 JobPosition 绑定（一对一）
  6. SessionCreateDialog 增加岗位选择器（单选）

预计工时: 2-3 天
依赖: 无（独立模块）
```

### Phase 1: 简历解析 + 差距分析 + 策略生成

```
任务:
  1. 实现简历文件上传 API（POST /api/sessions/{id}/resume）
  2. 实现 ResumeProfile 数据模型 + DB migration
  3. 实现简历 LLM 解析模块（backend/app/services/resume_parser.py）
  4. 实现 GapAnalysis 模块（backend/app/services/gap_analyzer.py）
     - 简历技能 vs 岗位必备技能
     - 项目经验 vs 岗位职责
     - 级别匹配判断
  5. 实现 InterviewStrategy 生成模块（backend/app/services/strategy_generator.py）
     - 融合 简历 ⊗ 岗位 ⊗ 级别 三维信息
  6. 前端：SessionCreateDialog 增加简历上传
  7. 前端：面试官端简历预览 + GapAnalysis 展示

预计工时: 4-5 天
依赖: Phase 0（需要岗位数据做差距分析）
```

### Phase 2: 面试阶段拆分 + 新 FSM + 岗位感知

```
任务:
  1. 重构 FSM：新增 STRATEGY_GEN + 6 个阶段状态
  2. 重构 InterviewAgent：添加阶段路由和阶段切换逻辑
  3. 实现岗位感知的 System Prompt（注入岗位要求/职责/差距分析）
  4. 实现各阶段 Prompt 模块
  5. 实现动态问题生成（岗位驱动 40% / 简历驱动 35% / 通用 25%）
  6. 实现追问链 + 岗位对照逻辑
  7. 前端：多阶段进度条 + 岗位关联提示
  8. 前端：WebSocket 消息处理扩展

预计工时: 5-6 天
依赖: Phase 1
```

### Phase 3: 分级评分 + 岗位匹配度评分

```
任务:
  1. 实现分级权重配置（L1/L2/L3，含 position_match 维度）
  2. 新增 BehavioralDimensions + PositionMatchDimensions
  3. 重构 EvaluationEngine：支持分级权重 + 岗位匹配维度
  4. 实现 position_match_scoring Prompt（6 个子维度）
  5. 实现分阶段评分汇总
  6. 重构报告生成：
     - 岗位匹配雷达图数据
     - 分阶段得分明细
     - Gap 总结
  7. DB migration：评分相关字段扩展

预计工时: 3-4 天
依赖: Phase 2
```

### Phase 4: 行为面试 + 岗位文化匹配

```
任务:
  1. 实现级别差异化的行为问题生成 Prompt（含岗位 soft_skill_requirements）
  2. 实现行为评估 Prompt
  3. 项目深挖中的行为线索提取
  4. culture_fit 评估（对照岗位团队文化要求）
  5. 前端：行为面试阶段 UI + 岗位文化匹配展示

预计工时: 2-3 天
依赖: Phase 2
```

### Phase 5: 完善 + 测试 + 迁移

```
任务:
  1. 端到端集成测试（覆盖：有简历+有岗位 / 有简历+无岗位 / 无简历+有岗位）
  2. LLM 输出质量评估（A/B test 新旧方案）
  3. 性能优化（简历解析 + GapAnalysis + 策略生成 并发化）
  4. 异常处理 + 降级方案
  5. 前端体验优化 + 国际化文案
  6. 从 interview_templates.json 迁移到 JobPosition 模型

预计工时: 2-3 天
```

---

## 十一、风险与回退方案

| 风险 | 缓解措施 | 回退方案 |
|---|---|---|
| LLM 生成的面试问题质量不稳定 | 保留题库作为 seed，LLM 基于种子题改写而非完全凭空生成 | 降级为岗位题库模式（静态题 + 岗位标签） |
| 简历解析准确度不足 | 面试官可手动修正 ResumeProfile | 允许跳过简历解析，手动输入关键信息 |
| GapAnalysis 误判 | 面试官可调整差距分析的权重参数 | 降级为无 GapAnalysis 模式 |
| 策略生成延迟过长 | 异步生成 + 缓存 + 提前生成（创建 Session 后立即后台生成） | 使用默认策略模板快速启动 |
| 岗位数据不完善 | 提供岗位模板 + 快速复制功能 | 允许 Session 不绑定岗位（回退到纯简历驱动） |
| LLM 追问跑偏 | 设置追问深度上限（max 3 层）+ 岗位主题约束 | 跳过追问，回到主问题流 |
| 新阶段状态机复杂度增加 | 充分单元测试 + 状态回滚能力 | 保留旧 FSM 作为 simplified 模式 |

---

## 十二、与现有系统的兼容

新方案设计为**增量演进**而非推倒重来：

1. **数据库**：新增字段而非修改现有字段，旧数据通过默认值兼容。JobPosition 是全新表
2. **FSM**：保留现有状态枚举，新增状态值，旧状态机逻辑作为 `simple_mode` 保留
3. **API**：新增端点，现有端点保持不变，Session 创建 API 的 position_id 为可选参数
4. **前端**：通过 feature flag 控制新旧模式切换
5. **问答流程**：新方案在 `resume_driven_mode=True` 时激活，否则回退到现有题库模式
6. **评分**：保留现有四维评分，新增行为维度和岗位匹配维度作为可选扩展
7. **现有模板**：`interview_templates.json` 可逐步迁移为 JobPosition 数据
8. **无岗位模式**：Session 不绑定岗位时，回退到纯简历驱动的面试（position_match 维度不计入评分）

### 兼容性矩阵

```
┌─────────────────────────────────────────────────────────────────┐
│ 配置组合                    │ 行为                               │
├─────────────────────────────────────────────────────────────────┤
│ 无简历 + 无岗位              │ 现有题库模式（完全向后兼容）         │
│ 有简历 + 无岗位              │ 简历驱动面试（position_match 不计入）│
│ 无简历 + 有岗位              │ 岗位驱动面试（对照 JD 出题）        │
│ 有简历 + 有岗位              │ 完整新模式（三维驱动）              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 十三、成功指标

- **岗位匹配度评估准确度**：GapAnalysis 的技能覆盖率与实际面试验证结果一致性 > 85%
- 面试官反馈：问题的**个性化程度**和**岗位针对性**明显提升
- 候选人体验：面试对话更自然，感觉「被了解」而非「被考试」，对岗位有清晰的认知
- 评估准确度：分阶段评分 + 分级权重的综合评分与人工面试评分一致性 > 80%
- 简历解析准确率：关键字段（技能、项目、年限）提取准确率 > 90%
- 岗位匹配雷达图：面试官对报告实用性满意度 > 85%
- 系统可用性：LLM 生成延迟 < 3 秒（P95），策略生成 + GapAnalysis < 15 秒
