# feat-616 实施准备与验证边界

> 本文保留 R6（2026-10-16）历史准备证据。当前统一 PA 与独立审查版及资源状态见 [design](../design.md) 和 [新版原型验证](prototype-goal-journey-validation.md)；旧逐动作授权及手工结果回流检查不作为当前验收。

记录时间：2026-10-16；基线 main 481467ac16f0eda4561fca5c8230050541600de9。

## 已完成的准备

- 核实 main/本地 origin/main/实时远端 main 同 SHA；原工作区只含本 unit 未跟踪设计研究。
- 用户由设计请求升级为完整实现，明确仅 dot 云电脑；后续授权自主 UI 选择，采用 A 固定自定义名主导航。
- spec 收口；正式 design、7 个 canonical delta、单 M1 骨架已形成。设计审查前仍需等待原型作者冻结其完整旅程。
- 独立 DSH 可行性调查核对 19 个锁定包的公开源码和 integrity，结论已纳入 design；不伪称 runtime 测试通过。
- 文档检查最初因 markdown-it-py、pytest 缺失失败；仅在 /tmp/nano-pa-docs-check 安装官方 Python 检查依赖后，`PYTHONPATH=/tmp/nano-pa-docs-check ./scripts/docs-check` 通过：239 maintained Markdown sources / 64 required routes。该检查按其维护源选择逻辑运行，不代表所有未跟踪设计文本已逐条审查，也不代表产品测试通过。

## Gate 2 的两类检查

设计本身需独立审核：身份和资产 ACL、三个执行域、配置 profile 键、隐式 root 指令/扩展、资料放行并发、owner task delegated mutation、所有 canonical 冲突、原型信息组织。独立报告才能判定，不以作者摘要自签。

纯环境/资源缺口：
1. 当前无获准且可达的真实浏览器路径完成现产品与 prototype 视觉/交互走查。历史受拒路线不重试、不绕过；静态检查不代替渲染。
2. DeepSeek 凭据尚未由用户通过安全途径配置至云端隔离环境；本机 LM Proxy 不能推断可达，不搬运密钥。模型真实请求/响应与产品送达必须最终验证。

## 流程允许继续做什么

change-workflow 明确 Full 通过 Gate 2 才实施，prototype-and-runbook 明确未落实必验资源阻塞 Gate 2。无“有条件 Approved 后写产品代码”的默认路径。允许继续设计取证、独立文档审查、原型设计、依赖准备、未修改产品的基线构建/契约检查和验收计划；不把新增产品测试或代码称作准备来绕过 Gate。

若用户明确同意将真实视觉/DeepSeek 验证后移到交付前，须在本 unit 原话与 design 记录具体调整，独立 reviewer 仍完整审查静态设计；交付不能跳过真实验证。未获此授权前不创建实施分支、不改产品文件、不 push。

## 预定最低层验证落点（尚未执行）

- IM tests：唯一 PA 创建与配置 operation 恢复；source ACL/contactability/private Work 全面隔离；任务 owner grant+revision 原子性与真实 actor；事件事务/游标/撤权并发。
- PA tests：可信路由、非 owner 控制无效、durable observation ingestion/ack/处理三游标、最新回复与任务关闭使候选失效、幂等投递与 gap恢复。
- DSH native fixture：实际 request/history/tool result 均无 owner canary；AGENTS/root extensions 不注入；profile refresh/HMR/restart 不串域；非空最小工具表仍禁 run_code/local tool bypass；broker 拒绝伪造身份与越界对象。无真实模型密钥也能跑 deterministic fixture，但不能代替 DeepSeek。
- Web Vitest：首次启用、改名、来源/草稿/任务确认、取消/返回、重复点击与更新冲突；保护可观察行为，不锁 DOM 内部结构。
- 真栈 E2E：owner/peer/agent/group 四关系，自动感知非手动转交、owner已回复不催、对外精确释放、task写回不claim、撤权重建、消息送达≠完成、离线恢复。
- 独立体验：1440/768/390px 的命名/固定入口、建议阅读与来源、编辑关闭/返回、观察状态/覆盖、外部受众和精确授权；截图只是证据之一，实际操作和体验判断分别成立。

现有 security/acceptance-scenarios.md 是攻击材料来源；最终回归按最低可观察 seam 合并，不能给每句研究机械新建一个测试。

## 基线与最终检查纪律

先跑最窄现有相关测试，再 typecheck/build；实现后按当前 CI 执行 backend pnpm build/typecheck/test、Python非E2E与ruff、docs-check、Web test/audit及适用 iOS gate。当前云端 Linux 无原生 iOS GUI/Xcode，不假称通过；本次不改 iOS源码仍须验证普通 API 兼容。每个真实结果保留 SHA/命令/退出码，主干变化后重新判 gate 有效性。


## 后续已实测准备

- `pnpm install --frozen-lockfile` 首次因默认 pnpm 数据根不可创建而退出 254；改用显式可写的 /tmp/nano-pa-xdg、/tmp/nano-pa-cache 和 /tmp/nano-pa-pnpm-store 后退出 0，863 packages 安装完成。安装器校验 1007 lock entries 供应链策略通过。使用已提供 pnpm 11.25.0（仓库 packageManager 标记 11.7.0）；未改 lockfile，版本差异在基线结果中保留。
- 17:16 UTC 再次 `git ls-remote --exit-code origin refs/heads/main` 返回同一 481467ac，无上游推进。
- 安装及下列基线测试只针对现有产品，未添加新产品测试、未更改产品代码、未创建实施分支或发布。

- 窄基线命令：`pnpm exec vitest run packages/personal-assistant/tests/inbox.test.ts packages/personal-assistant/tests/global-agent.test.ts apps/im-server/tests/onboarding.test.ts apps/im-server/tests/identity.test.ts apps/im-server/tests/task-collaboration.test.ts`。首次 4 suite 加载失败因为 @nano/product-contracts 未 build（identity 8 tests 已过）；执行 `pnpm --filter @nano/product-contracts build` 后原命令退出 0，5 files / 62 tests passed。没有为通过测试修改产品源码。

- 未修改产品的 `pnpm build && pnpm typecheck` 均退出 0；构建的安装候选只是云端本地产物，未发布/部署。
- 现有 native DSH `pnpm exec vitest run packages/dsh-integration/tests/capabilities.test.ts packages/dsh-integration/tests/approval-workspace.test.ts` 退出 0：2 files / 5 tests。使用其临时目录和合成 fixture；这证明基线真实 DSH 子进程在当前云端能运行，不证明未来 PA 隔离已实现，也不代表真实 DeepSeek 调用。
- Web `npm ci --cache /tmp/nano-pa-npm-cache --no-audit --no-fund` 退出 0，353 packages，未更改 package-lock；当前 Node 24.19.0，与前端 CI Node 20 的差异保留，最终需跑规定 CI。

- Web baseline：`npm test -- src/features/onboarding/onboarding-page.test.tsx src/features/settings/agents/agent-create.test.tsx src/app/router.test.tsx && npm run build` 退出 0：3 files / 24 tests，TypeScript + Vite 构建通过。仅有既有 auth-session 动静态混合 import 和大 chunk 警告；未改产品以消除这些范围外警告。dist 为忽略产物、不提交。至此所选基线共 91 tests 通过，并非全仓测试或新 PA 行为通过。
- 再跑 docs-check 仍通过；git status 仍仅 feat-616 unit 未跟踪。全部构建/测试均未访问生产数据、用户电脑或真实 DeepSeek。

- 依赖架构基线：`PYTHONPATH=/tmp/nano-pa-docs-check python -m pytest tests/contract/test_runtime_dependency_contract.py -q` 退出 0，13 passed。累积所选基线 104 tests 通过；不等同完整 CI 或未来 PA 功能测试。

- Web `npm audit --audit-level=critical --cache /tmp/nano-pa-npm-cache` 退出 0，found 0 vulnerabilities。

## 2026-10-16 18:11 UTC — design closure preparation

- Live origin/main rechecked at 17:59 UTC: 481467ac16f0eda4561fca5c8230050541600de9, matching local HEAD; no upstream drift.
- Historical design baseline: the uncommitted R6 worktree passed all 14 file checks at review time. The temporary manifest was removed after archiving; its historical contents remain in Git commit `1190bbbfc`. Current reviews use the candidate commit and diff.
- Spec/design + prototype + 10 canonical deltas, one M1 .gitkeep. No product edits, commits, branches, push, services or credentials configured.
- All 6 prototype-only state scripts run sequentially from repository root: 97 checks passed, exit 0. Durable scripts and log: research/prototype-state-checks/ (latest-run.txt). Synthetic jsdom state machines are not visual, accessibility, backend, security or provider evidence.
- Independent R1–R6 review history is preserved in design-review.md. Formal R6 completed at 18:12 UTC: Issues Found, 0 critical / 2 warning; all reported substantive design/interaction issues closed. Real visual and DeepSeek resource prerequisites remain blocking. Do not treat static closure as Gate 2 approval.
- Root is awaiting explicit user permission to move real visual/DeepSeek validation to delivery-before-finalization. No such permission received here. Product implementation stays paused until a valid Gate 2 or an explicit documented adjustment is reviewed.

## 2026-10-18 — 用户要求提交设计并转交本地开发

用户明确要求：“你先提交并push下？我在本地继续开发。”本次仅发布本 unit 的需求、设计、原型、delta-spec 与研究/审查证据，使用独立文档分支；不修改产品代码、不创建 PR、不合并、不部署。这项发布授权取代上文历史性的“尚无发布授权”状态，但不表示用户批准调整 Gate 2 顺序。

接续入口：先读 `spec.md`、`design.md` 与 `design-review.md` Round 6。R6 仍为 Issues Found（0 CRITICAL / 2 WARNING），真实浏览器体验和 DeepSeek 必验资源仍待落实；M1 仅有空骨架，不能把设计交接视为实现或验收完成。本地开发接续时，应先按当地可用浏览器/API 资源核实两项恢复条件，再按仓库 change-* 流程推进。历史测试与 97 项原型状态检查只证明其注明的范围。

提交前维护检查修正了 auth-tenancy delta 中指向现行 gateway-relay 契约的相对链接（原路径在 delta 目录中不存在）；仅链接修正，无契约语义变化。R6 manifest 保留历史原值，交接树与该历史快照的这项差异不代表重审或 Gate 2 通过。另清理研究文档末尾空行。

交接前在同一基线上重跑：六个 prototype-state-checks 脚本共 97 项通过；补齐仓外临时 Python 检查依赖后，`PYTHONPATH=/tmp/nano-pa-handoff-docs-check ./scripts/docs-check` 通过（272 maintained Markdown sources / 64 required routes）；`git diff --cached --check` 通过。仍未运行真实视觉或 DeepSeek 验证。仓库 CI 当前只在 main push 或 pull_request 触发，本次仅推设计分支且不创建 PR，不等同获得远端 CI 结果。


## 2026-10-19 — 统一 PA 与独立外发审查设计修订

用户已授权按统一 PA 方案改设计，本次仍仅设计交付。当前权威为 [design 第7节](../design.md#7-统一理解入口辨来源出口独立审查) 与 [安全场景](../security/acceptance-scenarios.md)；R6 受限 external/observation session、全外部模型请求无私人 canary 不再是当前架构要求。旧研究保留为能力取证和已放弃方案的历史，不能据其建议覆盖新设计。

当前必须验证：PA 可以使用目标必要的私密资料；实际接收方和共享存储不能收到越权内容。审核不替代身份/ACL，原工具 fast path 不替代披露审查；IM/Channels 自动投递、附件/共享结果、网络参数、子任务、记忆写入及热更新均纳入。不可受控的任意代码/插件不能自动进入 PA，正常搜索、整理/制作、内部成果回流、持续跟进必须同时可用。

R9/R10 已核现有 UI 与新增可疑告知，本次不改原型。DeepSeek 隔离验收资源仍未落实，公开 DSH exports 的静态取证不等于新关口运行或模型效果验证。独立审查记录继续追加 design-review.md；不因本次设计修订宣称 Gate 2 通过、产品实施或生产部署。
