# feat-654: 固定日常协作验收环境 — 技术方案

> 对齐：[spec.md](spec.md)

## Changelog

## 现状分析

### 涉及范围

- `scripts/e2e-up.sh` 已支持 `default`/`feishu` profile，复制 `config/e2e/gateway.yaml`，分配端口和唯一节点，初始化测试用户，起真实 IM + Node/DSH；只检查节点 online，未创建 PA 或日常群。
- `config/e2e/gateway.yaml` 预置两个 single-thread Agent 和一个 Global，现有 critical-path 与生命周期测试直接依赖它们的 ID。模型目录在这份文件维护。
- `.claude/skills/change-*` 和 `docs/development/worktree-runtime.md` 负责真实验收的环境准备/交接，目前没有固定日常角色基线。
- `apps/im-server/src/personal-agent.ts` 的公开 POST 创建真实 PA、主人绑定、私人空间及私聊；PA ID 由服务生成，不能当普通 config Agent 冒充。

### 既有约束

- Node/DSH 接入、PA 与 IM 权限逻辑保持；本次只改开发 fixture、工具和文档。
- 不读取生产凭据、聊天或 workspace 作为模板。用户选择每需求独立副本，不建立共享持久测试服务。
- Auto owner 根由 `NANO_OWNER_CONFIG_ROOT` 决定；只向临时 Gateway YAML 填 `auto_mode` 不足以保证生效，必须在隔离 owner 根维护实际读取的配置。
- 同目录重启现有脚本会重建 IM，但保留旧 workspace 证据；日常 profile 的工作区需要按本轮节点身份划分，避免旧 memory、任务产物污染基线。

### 可复用能力

| 能力 | 处理 |
|---|---|
| e2e-up/down 与默认模型目录 | 复用；增加 `daily` profile，不另造进程管理器 |
| 默认 e2e-global 的工具/Feature 基线 | 复用，再显式设置日常角色模型、职责和模式；Skills 继续正常发现 |
| 公开 PA / Agent config / conversations API | 复用真实创建和配置流程，不直写 IM 数据库 |
| 既有 default/feishu profile | 保持自动测试及外部渠道专项入口；正常产品验收显式采用 daily |
| 生产 P/E/Q TEAM/ROLE | 只借鉴分工，使用仓库自有的简短固定提示词，不复制生产目录、授权或 GitHub 推送能力 |

### 相关历史

- `refactor-381` 建立起停脚本；`feat-393` 强调重建 IM 避免旧身份污染。日常 profile 在既有隔离入口增加基线，不替代这些生命周期约束。
- 当前 PA 首次创建和权限契约以 `docs/specs/im/personal-agent.md` 为准；本次不修改产品契约。

## 架构总览

正常验收使用 `scripts/e2e-up.sh --profile daily --wt <runtime-root>`。脚本从默认无密钥模型目录构造临时配置，加载仓库日常模板，启动原有真实栈，随后调用公开接口建立 PA 和日常群。只有完整 seed 成功才报告 ready 并写出日常交接清单。

新增一个小型 Python helper `scripts/e2e_daily.py`，分别提供启动前的 `prepare` 与节点就绪后的 `seed`。模板位于 `config/e2e/daily/`，存放角色定义和示例项目资料；不引入通用 fixture 框架或独立服务。

## 关键决策

1. **固定 3 个 Global 团队 Agent 加 1 个真实 PA。** ID 为 `daily-product`、`daily-engineering`、`daily-quality`；显示名采用 P/E/Q 与 `PA · 个人助手`。PA ID 由产品生成并写入本轮清单。研发日常群为主人 + P/E/Q，PA 通过主人的来源权限观察。P 处理普通群交办，E/Q 采用 mention-only；所有角色避免无事附和，heartbeat 默认关闭，需要验证时在副本开启。
2. **主模型和审核明确对齐生产。** P/E/Q 使用 `codexOAuth:gpt-6.1-sol / high`，PA 使用 `codexOAuth:gpt-6-astra / medium`，四者显式 `approval_mode: codex`、无备用主模型。审核固定 `codexOAuth:gpt-6-luna`；`low` 是当前 Guardian/输入审核的优先选择，不新增无效的审核 effort 配置字段。隔离 owner 配置明确 Auto enabled、Codex、无权限跳过，保留原默认拒绝处理。开发侧 reviewer 的模型表保持原契约。
3. **daily 是开发流程的默认产品验收模板，低层回归入口保持。** 修改 orchestrator 两种入口、设计 runbook 指引和 reviewer 交接约定，要求常规产品验收使用 daily 并声明场景增量。`e2e-up.sh` 无参数仍保留 default，以免已有 automated test 的身份与工作模式变化。`--profile daily` 不与 `--main-config` 或 Feishu 合并；需要外部渠道时另起专用 profile 作为补充。
4. **每次启动都拥有新的工作区基线。** daily 在 `.gateway-workspace/<node_id>/` 下建立 P/E/Q workspace 与共享 `project/`；动态 PA 同样使用该 workspace_base。同目录 down/up 不复用此前 Agent 的记忆或修改；保留旧目录只用于排障。模型覆盖环境变量只改变本轮工作模型，审核模型保持 Luna，清单反映实际工作模型及其默认 effort；覆盖时不把 Sol high 等固定 effort 错带给不支持的模型。
5. **只种固定资料和关系，启动不派发工作。** 示例项目为虚构的“轻记待办”，有背景、用户反馈和检查清单；E 可在共享项目写一个明确交办的产物，Q 读取实际产物核实。初始群和 PA 私聊为空，没有自动发消息、任务或模拟历史；不把 seed 成功等同于真实模型已验收。

## 接口与数据流

1. `prepare` 读取脚本已复制的 Gateway config，加载固定角色模板，继承默认 Global 的工具与 Feature 配置，设置显式模型/effort/approval_mode；写入隔离 owner 的 Auto 配置、按新 node_id 划分的 workspace 与共享项目；提示词只引用本轮共享目录。继续采用既有 `NANO_MULTIAGENT_E2E_MODEL` 注册模型校验。
2. IM 初始化与 Node 启动仍由 e2e-up 执行；daily 启动时显式使用该 checkout 的 frontend dist/trajectory dist，使 `--wt` 为独立 runtime 目录时也能访问真实客户端产物。
3. 在已有 readiness 的登录会话中调用 `seed`，避免紧接着第二次登录触发速率限制。等待 P/E/Q 注册，POST `/im/v1/personal-agent`（固定请求键、显示名、本轮 node_id），GET/PATCH PA config 设置模型/effort、Codex、heartbeat false。保留产品创建的默认 PA 指令与 `personal_agent` 绑定。
4. POST `/im/v1/conversations` 建立私密“研发日常”群，成员只包含测试主人与三位团队 Agent。核对 PA active、来源列表包含日常群且未排除、四个角色存在，再生成 `.e2e-daily.json`。
5. 清单包含模板版本、实际模型/effort、审核模型/规则及 effort 来源说明、Agent ID/显示名、群与 PA 私聊 ID/URL、共享项目目录；不写 token。输出清单路径与可访问入口，供 reviewer 与用户复查。
6. seed 的任何失败令启动命令非零退出，不输出 ready 或留下上轮成功清单；调用方继续遵循既有 down 契约清理已启动进程。流程不暗自降级到 default。

PA 的配置 PATCH 使用当前公开 config 与 `profile_version`，不从 Gateway 运行中回写配置文件；普通 Agent 配置在启动前生成。初始化无需 LLM 调用；真实回复在独立验收阶段执行。

## 契约层增量 (delta-spec)

- no spec delta：仅改变开发/测试环境与流程，产品 API、PA 权限、客户端行为不变。长期使用规则归并 `docs/development/worktree-runtime.md`，领域入口和 docs/README 同步链接。

## 风险与回退

- 角色模型必须在现有目录注册；模型故障照实报告，不换模型或关闭审核。远端模型 availability 由真实聊天验证。
- PA 创建增加启动步骤，使用已有 Node 控制 API 和有界 HTTP timeout。缺任一角色或 PA active 时 startup 失败；`e2e-down.sh` 清理本次进程。
- 恢复旧 default 只适用于专项回归，不能把它冒充 daily 验收通过。回退提交可移除 daily 入口，默认和 Feishu 的生命周期保持。
- 提示词分工不是 OS 沙箱；此模板仅在用户授权的隔离测试现场运行，审核规则与工具硬限制继续生效。不借此宣称额外的强隔离权限机制。

## 一次性部署迁移

无。生产配置不改。

## Runbook for Reviewer

本 unit 不改客户端代码或 UI 布局，不生成原型。验收者可通过客户端相同 HTTP API 驱动真栈，并在真实 Web 检查阵容和入口。服务由 caller 集中准备，交接精确 SHA、清单和凭据（固定隔离 `nano` / `nano1234`）。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 本轮 IM + Node/DSH | `<checkout>/scripts/e2e-down.sh --wt <runtime-root>` | `PATH=<main>/.venv/bin:$PATH <checkout>/scripts/e2e-up.sh --profile daily --wt <runtime-root>` | IM health、node online、`.e2e-daily.json` 与公开 Agent/PA/group 状态一致 |

**Review 驱动方式**：真 IM + Node/DSH + 真实模型。用 API 发给 P 整理预置反馈、E 写出一个小型交付文档、Q 读取产物并评价，PA 从主人私聊查询来源群工作；以真实消息与文件证明。浏览器展示真实 Agent 列表、日常群和 PA 私聊。确认新实例没有旧消息、任务或文件修改。

**验收前置**：沿用仓库 venv、Node/pnpm，完成 `pnpm install --frozen-lockfile && pnpm build` 和 Web build；本机 `127.0.0.1:4000` 的健康检查已在设计时得到 `ok: true`，模型目录包含 Sol、Astra、Luna。健康并非模型回复证明，验收仍需真实消息。无外部账号、Feishu、生产数据或实体设备需求。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-daily-template | 固定模板、初始化、流程与验证 | 无 | 单 M1 | `config/e2e/daily/`、`scripts/e2e_daily.py`、`scripts/e2e-up.sh`、针对性 Python/真实栈测试、开发说明与相关 change skills | [reviewer] 首文档全部 Scenario 有真实产品证据；[worker] prepare/seed 失败与同根重新启动基线隔离有验证，公开 API 核对真实 PA、群成员和模型/审核配置，旧 default lifecycle 回归通过，相关 lint/docs 和本地 CI 通过 |
