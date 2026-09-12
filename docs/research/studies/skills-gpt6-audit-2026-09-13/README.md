---
status: research-snapshot
recorded-at: 2026-09-13
nano-baseline: eb4da28150001de6655a92774d9a86ea0fe897a8
source-baseline: local Skill sources; no external model benchmark
current-owner: .claude/skills and src/personal_assistant/builtin_skills
---

# Workspace Skills 精简审计 — 2026-09-13

用户明确要求跳过 Skill 工作流，在独立 worktree 直接修改并提 PR。本次只改 Skill 文档及审计索引，没有修改应用源码、Skill 脚本、AGENTS 或开发生命周期权威。本报告是历史审计记录，不是新的共享必读规则；当前流程以各 Skill 和 [change-workflow](../../../development/change-workflow.md) 为准。

## 范围

主 checkout 递归发现 54 个不同的 SKILL.md：17 个受版本控制的开发 Skill、29 个 PA 内置 Skill、1 个未入仓开发副本、6 个忽略的运行态 Skill、1 个归档样本。排除 Git/依赖目录和其他 worktree 的重复 checkout；.agents/skills 是 .claude/skills 的软链接，不重复计数。用户全局 Skills 不在本仓范围。

改写 46 个维护源入口；审计但不覆盖本地运行态、未入仓副本及冻结历史。开发侧支持材料做内容审查；内置包全部支持文件做清点、静态扫描和导航检查，重点改写通用编排、设计和确认规则，保留 API 知识主体。未逐项执行所有 helper 或真实飞书调用，静态检查不证明其运行效果。

原主仓 dirty/untracked 保持不动，改动位于 codex/skills-gpt6 worktree。唯一有意吸收的既有改动是生产 Skill 的“健康后清理无进程占用的干净旧 prod-main worktree”要求，保留到入口与 runbook。

## 逐项尺寸

46 个入口合计 **615,904 → 80,483 UTF-8 字节，减少 86.9%**。基线为 Git eb4da2815，包含 frontmatter/正文/空行；KiB = 1024 字节，行数按 splitlines() 计算。不是 token、成本、延迟或质量实测。入口缩减来自删除指令和按需迁移知识，不代表整次任务上下文同比减少。

### 开发 Skills

| Skill | KiB 前 → 后 | 行数前 → 后 |
|---|---:|---:|
| [change-code-review](../../../../.claude/skills/change-code-review/SKILL.md) | 6.88 → 1.71 | 121 → 22 |
| [change-design-author](../../../../.claude/skills/change-design-author/SKILL.md) | 43.80 → 2.65 | 653 → 29 |
| [change-design-reviewer](../../../../.claude/skills/change-design-reviewer/SKILL.md) | 20.50 → 1.79 | 244 → 25 |
| [change-fast-close](../../../../.claude/skills/change-fast-close/SKILL.md) | 5.85 → 1.82 | 118 → 21 |
| [change-impl-worker](../../../../.claude/skills/change-impl-worker/SKILL.md) | 2.91 → 2.92 | 37 → 37 |
| [change-orchestrator](../../../../.claude/skills/change-orchestrator/SKILL.md) | 19.43 → 3.13 | 340 → 37 |
| [change-orchestrator-simple](../../../../.claude/skills/change-orchestrator-simple/SKILL.md) | 10.68 → 2.68 | 165 → 29 |
| [change-retro](../../../../.claude/skills/change-retro/SKILL.md) | 12.79 → 1.71 | 167 → 22 |
| [change-reviewer](../../../../.claude/skills/change-reviewer/SKILL.md) | 30.17 → 2.27 | 463 → 24 |
| [change-spec-author](../../../../.claude/skills/change-spec-author/SKILL.md) | 21.96 → 2.24 | 330 → 26 |
| [change-spec-reviewer](../../../../.claude/skills/change-spec-reviewer/SKILL.md) | 11.46 → 1.49 | 150 → 22 |
| [change-verifier](../../../../.claude/skills/change-verifier/SKILL.md) | 17.69 → 2.03 | 311 → 27 |
| [codebase-design](../../../../.claude/skills/codebase-design/SKILL.md) | 6.71 → 1.67 | 114 → 19 |
| [improve-codebase-architecture](../../../../.claude/skills/improve-codebase-architecture/SKILL.md) | 6.91 → 1.77 | 85 → 19 |
| [prod-fleet-deploy](../../../../.claude/skills/prod-fleet-deploy/SKILL.md) | 18.65 → 1.82 | 273 → 19 |
| [reverse-engineer-claude-code](../../../../.claude/skills/reverse-engineer-claude-code/SKILL.md) | 9.50 → 2.04 | 155 → 23 |
| [systematic-debugging](../../../../.claude/skills/systematic-debugging/SKILL.md) | 7.42 → 1.67 | 152 → 20 |

### PA 内置 Skills

| Skill | KiB 前 → 后 | 行数前 → 后 |
|---|---:|---:|
| [conversation-skill-distiller](../../../../src/personal_assistant/builtin_skills/conversation-skill-distiller/SKILL.md) | 2.85 → 1.47 | 52 → 20 |
| [lark-approval](../../../../src/personal_assistant/builtin_skills/lark-approval/SKILL.md) | 6.79 → 1.44 | 99 → 28 |
| [lark-apps](../../../../src/personal_assistant/builtin_skills/lark-apps/SKILL.md) | 18.43 → 1.97 | 122 → 33 |
| [lark-attendance](../../../../src/personal_assistant/builtin_skills/lark-attendance/SKILL.md) | 1.58 → 0.92 | 57 → 23 |
| [lark-base](../../../../src/personal_assistant/builtin_skills/lark-base/SKILL.md) | 23.50 → 1.90 | 171 → 32 |
| [lark-calendar](../../../../src/personal_assistant/builtin_skills/lark-calendar/SKILL.md) | 12.21 → 1.57 | 204 → 29 |
| [lark-contact](../../../../src/personal_assistant/builtin_skills/lark-contact/SKILL.md) | 3.67 → 1.20 | 71 → 27 |
| [lark-doc](../../../../src/personal_assistant/builtin_skills/lark-doc/SKILL.md) | 9.09 → 1.65 | 84 → 30 |
| [lark-drive](../../../../src/personal_assistant/builtin_skills/lark-drive/SKILL.md) | 23.73 → 1.81 | 212 → 31 |
| [lark-event](../../../../src/personal_assistant/builtin_skills/lark-event/SKILL.md) | 10.90 → 1.19 | 163 → 25 |
| [lark-im](../../../../src/personal_assistant/builtin_skills/lark-im/SKILL.md) | 21.47 → 1.64 | 257 → 30 |
| [lark-mail](../../../../src/personal_assistant/builtin_skills/lark-mail/SKILL.md) | 23.94 → 1.70 | 290 → 32 |
| [lark-markdown](../../../../src/personal_assistant/builtin_skills/lark-markdown/SKILL.md) | 4.80 → 1.35 | 70 → 29 |
| [lark-minutes](../../../../src/personal_assistant/builtin_skills/lark-minutes/SKILL.md) | 12.99 → 1.54 | 207 → 30 |
| [lark-note](../../../../src/personal_assistant/builtin_skills/lark-note/SKILL.md) | 5.48 → 1.06 | 94 → 26 |
| [lark-okr](../../../../src/personal_assistant/builtin_skills/lark-okr/SKILL.md) | 12.27 → 1.43 | 167 → 30 |
| [lark-openapi-explorer](../../../../src/personal_assistant/builtin_skills/lark-openapi-explorer/SKILL.md) | 4.81 → 0.91 | 153 → 22 |
| [lark-shared](../../../../src/personal_assistant/builtin_skills/lark-shared/SKILL.md) | 10.65 → 0.94 | 211 → 17 |
| [lark-sheets](../../../../src/personal_assistant/builtin_skills/lark-sheets/SKILL.md) | 36.30 → 1.86 | 234 → 32 |
| [lark-skill-maker](../../../../src/personal_assistant/builtin_skills/lark-skill-maker/SKILL.md) | 2.40 → 0.94 | 85 → 22 |
| [lark-slides](../../../../src/personal_assistant/builtin_skills/lark-slides/SKILL.md) | 25.68 → 1.83 | 312 → 32 |
| [lark-task](../../../../src/personal_assistant/builtin_skills/lark-task/SKILL.md) | 12.00 → 1.49 | 175 → 30 |
| [lark-vc](../../../../src/personal_assistant/builtin_skills/lark-vc/SKILL.md) | 14.99 → 1.33 | 205 → 28 |
| [lark-vc-agent](../../../../src/personal_assistant/builtin_skills/lark-vc-agent/SKILL.md) | 19.56 → 1.59 | 201 → 29 |
| [lark-whiteboard](../../../../src/personal_assistant/builtin_skills/lark-whiteboard/SKILL.md) | 3.21 → 1.41 | 48 → 29 |
| [lark-wiki](../../../../src/personal_assistant/builtin_skills/lark-wiki/SKILL.md) | 11.02 → 1.51 | 115 → 30 |
| [lark-workflow-meeting-summary](../../../../src/personal_assistant/builtin_skills/lark-workflow-meeting-summary/SKILL.md) | 5.76 → 1.12 | 122 → 24 |
| [lark-workflow-standup-report](../../../../src/personal_assistant/builtin_skills/lark-workflow-standup-report/SKILL.md) | 4.52 → 1.10 | 122 → 24 |
| [nanoassistant-docs](../../../../src/personal_assistant/builtin_skills/nanoassistant-docs/SKILL.md) | 3.56 → 3.31 | 39 → 39 |

生产 Skill 表格使用 Git 基线；原主仓未提交版本为 20,149 字节 / 287 行，其新增规则也已保留。change-impl-worker 与 nanoassistant-docs 已较薄，只修触发、表达或导航，没有为了缩短删除必要信息。

## 删除与简化

| 原要求 | 改写 |
|---|---|
| 固定七路 review、每条候选一个 agent、固定旧模型/effort | 保留独立发现与验证，按风险选择角度、批次与并行度，沿用当前模型配置 |
| 固定设计图数量、按 800 行/10 文件/4 小时拆 milestone | 按独立交付、写冲突和验证需要拆分；图解释实际复杂关系 |
| 必派 Explore agent、3+ 竞争方案、候选配额 | 自主选择有价值的探索方式和方案数量 |
| 每轮重启全部服务、重复全量核查 | 以版本和证据有效性决定是否重建及重验范围 |
| 固定调试四阶段、所有层加日志、三次失败即架构问题 | 使用可区分假设的证据，次数不代替因果判断 |
| 每次读全部规范/共享鉴权，压缩后读两遍 | 按操作、故障、媒介加载参考，复用有效上下文 |
| 强制 todo/计划、固定视觉变体/图数/字数配额 | 保留真实内容与版式目标，需要可恢复设计状态时才用计划 |
| 同一具体授权反复确认 | 对象、范围、参数未变时复用；危险操作仍需明确授权 |

## 按需材料落点

| Skill | 参考内容 |
|---|---|
| change-spec-author | references/authoring.md：首文档各节边界；模板按类型加载 |
| change-design-author | prototype-and-runbook.md、review-loop.md：原型、验收前置、Gate 2 派发与恢复 |
| design-reviewer / reviewer / verifier | 各自 references：报告、模式、字段、固定 SHA 与同步 |
| change-orchestrator | validation.md、recovery.md：门禁、证据有效性、复验与恢复；Codex notes 去掉旧型号配方 |
| change-retro / codebase-design | investigation.md、vocabulary.md：取证命令、术语、例子与图 |
| prod-fleet-deploy | runbook.md：原命令、拓扑、身份、密钥、迁移和恢复；根保留环境不变量 |
| 27 个 lark-* | references/commands.md：命令表、参数、示例；高频操作从根直接到专项参考 |
| lark-slides | syntax-notes.md / visual-style.md：XML 技术与可选样式分离，原 schema/chart/上传/lint 保留 |
| lark-apps/creative-design | rendering-and-publishing.md：固定依赖、Babel 作用域、宿主评论锚点、素材与发布 |

原有脚本与领域模板保留，没有为简单说明新增脚本。修复邮件、事件、妙记、创意设计的实际死链和拆分后的相对路径；模板生成时才存在的 prototype.html 是明确的文件链接检查例外。

## 触发复核

每个改写入口均重新阅读，核对 frontmatter、正常调用所需资源和关键约束。以下为人工语义检查，不是模型触发率测试：

| 容易重叠的意图 | 触发边界 |
|---|---|
| 小修 / 需求对齐 / 已准入实施 | unit 由仓库规则判定；spec-author 只管首文档；准入后交 orchestrator |
| 默认实施 / 点名 simple / 快速开发事后交付 | 保留三个明确入口，不抢路由 |
| 需求 / 方案 / diff / 产品旅程 / 契约一致性 | spec-reviewer、design-reviewer、code-review、reviewer、verifier 分对象 |
| 只读生产调查 / 明确部署重启 | debugging 与 prod-fleet-deploy 分开 |
| 常规代码 / 接口设计 / 架构扫描 | 仅后两者触发设计 Skills，架构扫描保持显式调用 |
| 普通网站/PPT / 妙搭应用 / 飞书 Slides | apps 需要 Miaoda 上下文；slides 限在线原生对象 |
| 审批待办 / Task / 妙记内待办 | approval / task / minutes |
| 日程 / 会后 / 会中 / 已知 note_id | calendar / vc / vc-agent / note，多场汇总才用 meeting-summary |
| 文件 / 正文 / 原生 .md / Wiki / Base / Sheets | 按对象与动作分域，跨域只转必要部分 |
| 日程+任务综合摘要 / 单项查询 | 仅综合摘要触发 standup-report |
| 当前 Gateway 会话 / 另项消息 / 独立订阅 | Gateway 保持原会话所有权，IM/event 不重复接管 |
| 已封装 CLI / 确认未覆盖 API / 封装 Skill | 业务 Skill / openapi-explorer / 显式 skill-maker |
| 安装版用法 / 开发 / 现场状态 | nanoassistant-docs 给版本手册，现场事实需真实查询 |

## 保留的真实约束

- Full/lite 准入、Gate 2 同一独立 reviewer、冻结产物、零 CRITICAL/WARNING、selected gate 矩阵；spec review 仍可选。
- 主仓保护、worktree/runtime 隔离、worker 两份短记录与集成锁、创建者清理、事件驱动等待。
- 用户原话、未回答问题不写成需求、架构依赖、真实入口、版本证据、canonical 归并、完整归档与 CI。
- Mini 唯一 IM、双 Gateway、代理、signing key、stop-before-config、迁移备份、运行进程占用核对。
- 飞书身份/scope、真实 ID、分页、部分失败、局部更新、重复日程范围、邮件草稿/发送、入会与发送授权。
- XML/schema、原生 chart、公式验证、上传 token、样式继承与实际渲染；确定性工具保留。
- 蒸馏显式输入、全部 JSONL 源可读、稳定模式证据、私密内容保护与真实 skill_manage 结果。

## 审计但未改写

不将未入仓/运行态内容静默提升为打包源，也不覆盖冻结历史；以下尺寸前后不变。

| 文件 | 字节 / 行数 | 判断 |
|---|---:|---|
| .claude/skills/conversation-skill-distiller/SKILL.md | 2,899 / 52 | 未入仓副本；与已优化内置源重复，保留本地定制，后续明确单一来源 |
| docs/changes/archive/refactor-486-agent-native-repository-knowledge-system/research-writing-artifacts/skill/SKILL.md | 7,520 / 123 | refactor-486 冻结样本，不作为当前注册源更新 |
| .nanoassistant/skills/conversation-learning-review/SKILL.md | 3,232 / 55 | 运行态；自主维护触发偏宽，需明确用户发起与自主维护边界 |
| .nanoassistant/skills/change-unit-delivery/SKILL.md | 3,762 / 43 | 运行态；普通实施也触发 simple，与仓库显式点名要求重叠 |
| .nanoassistant/skills/concurrency-safe-delivery/SKILL.md | 4,217 / 64 | 运行态；reservation 和确定性测试有价值，限已确认的进程内去重问题 |
| .nanoassistant/skills/frontend-debugging/SKILL.md | 3,289 / 76 | 运行态；几乎总是抽公共函数属于过度归因，后续应收窄 |
| .nanoassistant/skills/runtime-incident-investigation/SKILL.md | 3,345 / 40 | 运行态；只读/因果边界有用，固定全链路输出可进一步精简 |
| .nanoassistant/skills/agent-permission-mechanism-research/SKILL.md | 4,090 / 59 | 运行态；证据分层有用，与逆向 Skill 重叠，需明确维护所有权 |

## 仍需产品或流程判断

独立 finder/verifier、Gate 2 与验收矩阵是用户已有要求；进一步减少角色需要明确验证独立性。卡片 P0–P7 的部分视觉数量阈值、Slides 原生图表/placeholder 策略、Drive 批量治理 artifact 状态机仍可能偏重，但与领域规范及不可逆操作协议交织，本次保留策略，去掉重复加载与固定叙述。XML、权限治理和卡片组件参考较长，后续按实际使用证据决定再切分，不按行数清空领域知识。

## 验证与证据限度

- 静态清点 562 个维护源及支持文件；Python AST 和 JSON 可解析；46 个入口 YAML 有效，name、version、metadata 等非 description 字段保持不变。
- CommonMark 解析 1,976 条本地文件/图片导航，目标存在；排除代码示例与生成模板链接。未声称验证远程 URL 或全部 Markdown 锚点。
- 现有测试 34 passed：change workflow documentation、change skill archive、capability payload、builtin skill bootstrap、product workspace layout。
- 首轮测试发现根入口缺固定 Gateway 标识，已恢复；YAML 检查发现 whiteboard 旧多行 description 残留，已清理复验。没有降低测试断言或修改应用源码。
- 文档完整性通过（232 个维护 Markdown、73 条必需路由），git diff --check 通过；远端 CI 以 PR 最新结果为准。
- 未做真实飞书写入、生产部署、GPT-6 对照或触发率 benchmark。确认的是结构、路由、约束保留和打包兼容性；执行效果需后续任务观察。
