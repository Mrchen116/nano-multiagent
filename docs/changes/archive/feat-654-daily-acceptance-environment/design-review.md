# Design Review — feat-654

## Round 1

### Metadata

- reviewer_target: `/root/design_review_654`（独立设计 reviewer）
- review_mode: `full`
- mode_reason: 首次 Gate 2 审查，覆盖首文档、设计全部决定、实际组装入口与 M1 骨架。
- baseline: `main@c694cddac6c58c98f381ffe8efae966d06259ac9`；审查开始时工作区 clean。
- started_at: `2026-10-25T01:00:51+08:00`（首次显式记录时间；资料阅读此前已开始）
- completed_at: `2026-10-25T01:01:31+08:00`
- duration: 至少 40 秒；未记录的前置阅读耗时不作精确声明。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**

固定 P/E/Q + 真实 PA、公开 API seed、工作模型与审核模型分离、复用既有进程入口的主体方案可行。尚需明确同目录重启时 owner 级可写资产的隔离，才能兑现“每次新的基线”。

### Coverage 与证据

1. **用户范围与固定角色。** 已完整阅读 `spec.md` 与 `design.md`。阵容、职责、空白研发日常群、PA 主人私聊、显式主模型/effort/审核规则、单需求独立副本和场景增量均有对应决定。Q 是产品成员而非独立开发 reviewer，设计明确保留了二者职责。生产角色和模型是首文档提供的现场依据；本 reviewer 未访问或独立复核生产，不把该来源声明升级为新的生产验证证据。
2. **实际启动入口。** `scripts/e2e-up.sh` 当前从脚本目录定位 checkout、接受独立 `--wt`、分配 IM 端口、复制配置、初始化 nano、运行 Node bind/start 并核对节点 owner/online；当前确实没有 daily seed。`apps/node/src/main.ts:40` 按 node_id 隔离 DSH home 与后续 Node/Inbox 状态，`apps/node/src/configuration.ts:41` 的 `defaultWorkspace` 支持为动态 PA 继承本轮 workspace_base。按 node_id 更新 P/E/Q、PA 与共享 project 的设计正确，但 owner 根有下述遗漏。
3. **PA 与群 seed 闭合。** `apps/im-server/src/personal-agent.ts:337` 的 POST 接收 request_key、display_name、node_id，产生服务端 PA ID、绑定、Global Agent 与空白私聊；`:363` 使用默认 PA 指令与真实 personal binding。`apps/im-server/src/control.ts:889` 公开 config PATCH 校验 profile_version 并走 Node 配置操作，GET 后保留字段再 PATCH 可实现模型/effort、approval_mode 和 heartbeat Feature 修改。`apps/im-server/src/messaging.ts:233` / `:823` 的公开创建接口接受团队成员并自动加入主人；visibility 可设 private。`personal-agent.ts:45` 的 sourceAccess 与 `:57` 的 sourceConversations 使用主人真实参与记录及政策排除，支持 PA 不入群仍读该来源。seed 校验 active、成员和来源不需虚构消息或直写数据库。
4. **模型覆盖与审核。** `config/e2e/gateway.yaml` 注册 Sol、Astra、Luna，三者支持设计所需 effort。`scripts/e2e_catalog.py:17` 可校验并设置工作模型；它本身不清理旧 effort，但设计已明确覆盖时使用所选模型默认 effort，该责任应落实在 prepare/PA PATCH，未将现有 helper 误称为已完成此能力。`apps/node/src/configuration.ts:58-77` 分别解析工作模型、effort、Agent Codex override 和独立 tool_approval_model；`apps/node/src/approval.ts:7` 实际读取 owner/config.yaml 与 workspace/.nanoassistant/config.yaml。`packages/dsh-integration/src/policy/codex.ts:105`、`policy/classifier.ts:28`、`personal-security.ts:119` 均优先受支持的 low，设计不新增虚构审核 effort 字段是正确选择。保留默认 deny 与不跳过审核符合 `packages/product-contracts/src/approval.ts:19`。
5. **旧 profile 与失败语义。** daily 独立 opt-in，无参数保留 default，继续使用原 Agent ID 的低层测试无需迁移。daily 拒绝 main-config/Feishu 混合，Feishu 的专用凭据与 listener lock 可保持原链路。复用 readiness 登录可避免额外登录；seed 非零失败、不输出 ready、不沿用旧清单、由 caller down 清理，与现有进程管理边界相容。当前 down 保留配置/证据，进一步说明新的 daily 基线必须主动使用新根，不能依赖 down 清空资产。
6. **前端与验收前置。** 本次不修改前端产品代码或布局，无新 must-match 原型要求。`apps/im-server/src/server.ts:272` / `:286` 已有 IM_FRONTEND_DIST_DIR 与 IM_TRAJECTORY_DIST_DIR，显式指定 checkout 构建产物可支持独立 runtime 目录。runbook 要求真实 API 消息、实际 E 产物与 Q 核查、PA 来源回答及真实 Web 阵容/入口，覆盖首文档用户旅程。模型目录存在只能证明可配置；代理健康为作者现场记录，未在本轮重测，真实模型与 Web 体验留待实施后独立验收。
7. **delta 与 milestone。** 仅改 fixture、启动工具与开发流程，产品 API 和权限不变，`no spec delta` 合理；长期说明归并 worktree-runtime 并更新入口，避免复制产品契约。`M1-daily-template/.gitkeep` 骨架存在，单 M1 无并行写冲突，包含真实产品证据、失败路径、同根重启、旧 default lifecycle 与本地 CI 退出要求。隔离回归需补充下述 owner 资产场景。
8. **职责与复杂度。** shell 继续管理生命周期，Python helper 负责静态模板准备和公开 API seed，IM/Node 保留身份与配置权威；无需引入 fixture 框架、数据库旁路或额外服务。模板仅借鉴角色，不扩展运行时依赖或自建 Agent Loop。现有能力复用充分，未发现需要阻断的额外抽象。

### 历史问题闭环

首次审查，无历史问题或 Author Resolution。

### Issues

#### R1-W1 — 同根重启未隔离 owner 级 Skill 等可写资产

- **位置：** `design.md:49`、`:54`，以及 M1 同根重启基线隔离退出标准。
- **证据：** 设计明确按 node_id 新建 workspace，却只说“写入隔离 owner 的 Auto 配置”，未决定 owner 根是否随本轮身份更新。所复用入口 `scripts/e2e-up.sh:194` 将 `NANO_OWNER_CONFIG_ROOT` 固定为 `<WT_ROOT>/.gateway-owner`。`apps/node/src/configuration.ts:92-100` 把该根下的 skills 同时作为可写 globalSkillRoot 和下次启动的发现目录，并从同一根加载 plugins.json。`packages/dsh-integration/src/knowledge/files.ts:72-84` 的现有 skill_manage 支持向 global scope 写入；模板继承的 e2e-global 已启用 skill_creation 和 skill_manage。`scripts/e2e-down.sh` 保留运行资产，不清空这些内容。
- **实际后果：** 在第一轮通过正常产品能力创建一个 global Skill，再于同一个 runtime-root down/up，新的 workspace 和 IM 数据虽然为空，新 Agent 仍会发现上一轮的 Skill。这个可复现路径违反设计承诺的“同目录 down/up 不复用此前 Agent 的记忆或修改”及固定初始基线；仅在 workspace 写产物的重启测试会漏掉它。
- **需要的设计收口：** 明确 daily 的 owner 根也按本轮 node_id 分配（例如 `<WT_ROOT>/.gateway-owner/<node_id>`），并把 Auto 配置写入同一实际根；或提出同样能保留旧证据且不继承上轮可写 owner 资产的简单方案。M1 加入旧 owner/global Skill 不被新一轮发现的验证。无需改变产品 Skill 机制或增加通用清理框架。

### Recommendations

无额外建议。

### 审查边界

本轮只读核对文档与当前代码，未执行产品验收、未启动服务、未接触生产、未修改设计或实现、未提交。唯一写入为本报告。

### Author Resolutions

- R1-W1 — accepted。现有 Node 的全局 Skill 根来自 ownerRoot，单独隔离 workspace 确实不足。design 的既有约束、关键决策 4 和 M1 退出标准已修订：daily 的 `NANO_OWNER_CONFIG_ROOT` 指向 `.gateway-owner/<node_id>/`，同根重启同时隔离 workspace 与 owner 配置/全局 Skill。回归需向前轮 owner 写入可发现 Skill，并验证后轮不继承。无需修改产品的 Skill 发现机制。

## Round 2

### Metadata

- reviewer_target: `/root/design_review_654`（同一独立设计 reviewer）
- review_mode: `closure`
- mode_reason: 实际 diff 仅修订 R1-W1 对应的 owner 根、既有约束和隔离回归明细；M1 身份、职责、依赖、范围与交付要求不变，退出标准补充的是原隔离承诺的具体测试对象，不构成 milestone 重划。无需求、产品 API、角色模型或新机制变化。
- baseline: `main@c694cddac6c58c98f381ffe8efae966d06259ac9` 加本轮作者的 design 三处修订及 R1 Author Resolutions。
- started_at: `2026-10-25T01:03:20+08:00`
- completed_at: `2026-10-25T01:03:26+08:00`
- duration: 6 秒（记录的复核区间）

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- 已核对完整 design diff、R1 Author Resolutions 及受影响的 owner 配置解析/消费链。`design.md:21` 明确 owner 与 workspace 同时按本轮身份划分；`:49` 明确 `NANO_OWNER_CONFIG_ROOT` 指向 `.gateway-owner/<node_id>/`，并覆盖全局 Skill、插件和 Auto 配置；`:94` 将 owner 全局 Skill 纳入同根重新启动的隔离验证。接口与数据流中 prepare 写入“隔离 owner”的要求由新的明确根路径消歧，不存在另一份固定 owner 写入约定。
- 本轮重新核对 `apps/node/src/configuration.ts:32`，配置内 `NANO_OWNER_CONFIG_ROOT` 优先决定 ownerRoot；`:92-100` 的可写 globalSkillRoot、插件 manifest 和 Skill 发现均引用该根。`apps/node/src/approval.ts:7-13` 从同一实际根读取 Auto 配置。`apps/node/src/main.ts:43` 会向该根安装内置 Skills，换新 owner 不会要求复制上一轮的生成资产或修改产品发现机制。因此该局部设计变更能同时隔离旧资产并保持初始化、审核和 Skill 能力。
- `retained_from: Round 1`：角色/用户场景、PA 与群公开 API seed、模型覆盖和审核 effort、旧 profile、失败语义、客户端构建入口、no spec delta、职责边界与其余验收证据要求均未改变，沿用 R1 对应代码核对。此次不重新宣称执行产品验收或生产核实。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R1-W1 | accepted；owner 根随 node_id 隔离，增加前轮全局 Skill 不被后轮继承的回归 | design 三处修订与本轮重新核对的 ownerRoot → Skills / plugins / approval 消费链一致 | closed |

### Issues

无。

### Recommendations

无。

### 审查边界

本轮仅关闭设计缺口；实现与真实产品证据仍由 M1 及后续独立门禁提供。只追加本报告，保留作者已有修改；未启动服务、未提交。
