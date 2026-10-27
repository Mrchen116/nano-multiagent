# Design Review

## Round 1

### Metadata

- reviewer: 独立 reviewer `/root/design_review`，非设计作者。
- reviewer target: `refactor-668-deterministic-e2e` 的 `motivation.md`、`design.md`、M1-e2e；基线 `687c9c1218c09a3e4c37f0247fa4b07287b1431a`，开始取证时 main 工作区干净。
- review_mode: full。
- mode_reason: 首轮 Gate 2，完整核对目标、现状、方案边界、no spec delta 与 milestone。
- started_at: 2026-10-27T21:39:03+08:00。
- completed_at: 2026-10-27T21:39:36+08:00。
- duration: 33 秒（结论收口记录窗口；此前源码取证未单独计时）。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案允许确定性驱动真实产品链，并将删除旧覆盖的前提明确限定为同一失败原因已有通过验证的替代保护。没有发现会使实施实质走偏的未收口设计问题。此结论是设计可实施性判断，不代表替代测试已实现或已通过。

### Coverage 与证据

1. **需求与基线。** 独立执行 `.venv/bin/python -m pytest tests/e2e --collect-only -q`，实际收集 32 项，其中 critical_paths 27 项、目录外环境测试 5 项。结合 `critical_paths/conftest.py` 的 live fixture 及测试依赖核对 14 项 live 路径。`scripts/e2e-critical.sh` 当前确实主动开启 live 开关。设计将全部 32 项纳入逐项映射，而非只改标题提到的工具、fork 和 restart，符合原始诉求；coverage.md 是实施交付物，不将尚不存在的映射冒充已验证证据。

2. **产品组装与职责。** `scripts/e2e-up.sh:237-285` 启动仓库构建的 IM 与 Node CLI；`apps/node/src/main.ts:110-155` 通过 `RuntimeSupervisor` 初始化真实运行时、恢复 binding、安装消费者并配置 provider；`packages/dsh-integration/src/client.ts:41` 后的客户端经 stdio 管理子进程。`SPEC.md:40` 规定的运行时边界得到保留。HTTP recording 响应属于测试夹具职责，不要求产品新增测试开关、第二套循环或直接依赖 DSH 私有实现。

3. **复用与接口可行性。** `test_agent_config_context_continuity_critical_path.py:227-370` 已支持 script/env 参数、全部 provider URL 重写、真实栈启动、JSONL 请求记录和 finally 清理；`anthropic_sse_compaction_recording.py` 已有真实 SSE 工具调用响应和 tool-use/tool-result 配对观察能力。提取现有共享 helper、仅增加当前场景需要的响应，比引入通用场景 DSL 更符合维护边界。脚本必须根据实际请求与工具结果推进，且断言独立落在真实出站请求、工具副作用和公开结果；这一限制足以排除“fixture 直接宣布成功”的假绿设计。

4. **Context 与恢复。** 设计决策 3 明确普通重启、压缩重启、fork 截断和源/分支隔离各自的保护，检查 messages/system/tools 和工具配对而非回复复述。既有 recording fork 测试实际只验证历史配置与前缀存在，设计已要求补截断与独立性，未将旧测试误称为完整替代。`packages/dsh-integration/tests/history.test.ts` 保护原生 fork/compact/restart，不能单独证明 IM fork 接线；设计保留 IM recording 路径是合理取舍。本次不修改产品 Context 的来源、选择、交付或恢复逻辑，因此不触发完整 Agent Context 设计审查；已核对其验证观察点，不能用 stub 成功外推模型理解与自主规划能力。

5. **协议、工具与跨进程覆盖。** 原生 `communication-native.test.ts` 使用真实 RuntimeClient，但 `product.call` 是测试 handler；`workflow-lifecycle.test.ts` 经运行时进程保护任务/child 生命周期；`personal-assistant/tests/heartbeat.test.ts` 使用替身 RuntimePort。它们分别保护运行时或产品模块边界，不能自动替代 HTTP/WS、IM 配置传播、定时触发后真实交付、`/stop` 入口等全链路风险。设计决策 1、4、5 要求按实际失败原因判断并保留接线缺口的真栈覆盖，因此不存在按名称直接删除的授权。Global J2 去除订单计算与自主规划，保留 Inbox 正文实际消费、同一 child 跟进及真实 dispatch/持久事实，能在不依赖真实模型的前提下保护机制。

6. **失败观察与隔离。** 已检查原 bash 超时、后台通知、stop、subagent failure 测试，它们多处只凭最终文本或完成事件推断工具/失败曾发生。设计要求工具真实执行及下一请求中的 tool_result，可以使替代证据更强；下游应以此要求核实真实失败或取消发生，不能把脚本返回普通文本算作失败分支验证。当前 heartbeat 测试设置 5 秒 cadence 且没有 case 级撤销，设计明确 finally 关闭/撤销。function 级 stub 栈已有 teardown 进程和端口检查，适合复用。无生产数据、模型账号、真实代理或部署动作。

7. **契约、文档与实施出口。** 仅修改测试、fixtures、入口及开发文档，无产品行为变化，no spec delta 与无部署迁移合理。`testing.md` 继续拥有测试策略，catalog 和 fixture README 更新其使用说明，避免形成第二份权威。单一 M1-e2e 范围无并行冲突；退出标准包含 32 项处置、无外部 provider、实际请求/工具结果证据、受影响低层与完整 E2E、本地 CI、独立 code review 和 verification，足以承接设计中的删除前保护要求。

### 历史问题闭环

无；本轮为 R1。

### Issues

无。

### Recommendations

- **R1-R1（可选措辞修正）**：`design.md:19` 的“TS 原生 profile 已覆盖 … heartbeat 和路由”建议改为“已有 TS 原生运行时及产品模块测试覆盖 …”。实际 heartbeat 文件使用替身 RuntimePort，communication 原生测试也 stub 了 product.call。正文已经要求同因证据和跨进程缺口保护，因此这处概括不阻断；实施 coverage.md 应精确写出各保留测试的 seam，避免后人把模块保护误读为 IM 真栈保护。

### 验证边界

本轮只做设计、源码和测试收集审查，没有运行真实 LLM、没有启动产品服务，也没有执行 TS 或真实进程 E2E。新 deterministic fixture 的稳定性、全部替代断言及回归通过状态，留给实施和既定验证门禁取证。本 reviewer 仅新增本报告。

### Author Resolutions

- R1-R1: accepted。按实际测试 seam 修正 design 的概括措辞；不改变架构、范围或退出标准，R1 retained。无未闭环实质问题。

## Round 2

### Metadata

- reviewer: 原独立 reviewer `/root/design_review`，非增量设计作者。
- reviewer target: `7566971e736f2f07cb18302f8690218a7b13f3f7` 上尚未提交的 `motivation.md` 尾部 10 行及 `design.md` 开头 17 行“PR 内追加”内容。checkout 为 `codex/refactor-668-deterministic-e2e`；取证开始时仅这两个受审文件有改动。
- review_mode: delta。
- mode_reason: 用户明确授权在同一 PR 处理已审计的 8 组测试价值问题；变化限定于测试、fixture 与归档辅助脚本，沿用 M1 和原验证角色，无产品接口、运行时或 Context 改动，未触及 R1 的 E2E 核心设计。
- started_at: 2026-10-28T00:30:39+08:00。
- completed_at: 2026-10-28T00:31:03+08:00。
- duration: 24 秒（本轮源码复核与结论收口计时；此前文档读取未单独计时）。
- retained_from: Round 1；保留原 E2E provider 边界、真实进程与恢复风险判断、隔离及无部署迁移约束。本轮不重新宣称原 E2E 实现已通过，也不重新执行其测试。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

新增设计覆盖已授权的全部 8 组问题，强化、保留和删除的边界与已确认失败原因一致。没有发现实质未收口决定；无需扩大到新的产品需求、全仓清理或 E2E CI 接入。

### Coverage 与证据

审计输入为本机 `test-value-audit-20261028/report.md` 及 `mutation-results.json`、`manifest-final-results.json`、`archive-branch-results.json`。这些记录显示旧测试对已注入错误仍通过，或归档脚本错误跳过；本 reviewer 已回到当前实际源码和测试核对机制，未将报告标题当作覆盖证据，也未把首次 manifest 副本构建失败当作有效 mutation 结果。

| 新增范围 | 独立核对与设计判断 |
|---|---|
| 旧 SHA manifest | `packages/product-contracts/tests/node-update.test.ts` 的可选链在 null 时确实也得到 undefined；对应 `src/node-update.ts` 的公开解析函数支持 SHA tag 和省略可选能力。要求完整有效结果及字段省略断言，能在原最低层堵住假阳性，无需增加 installer/E2E 重复。原非法输入保护保留。 |
| 两个真实路由 | `src/IM/frontend/src/app/router.tsx` 实际注册 AgentsListPage 与 nodeId 创建页；列表走 listPublicAgents，创建页从 useParams 取得 nodeId 并加载节点/create-state。当前测试只匹配侧栏文字或允许错误页。设计复用 appRoutes/renderRouter，以 HTTP fixture 驱动实际页面、检查列表/表单和节点参数，保护路由与页面接线，没有改成只测替身组件。 |
| i18n 冷初始化 | `i18n/index.ts` 在模块初始化时读 localStorage；当前 beforeEach 的 setter 覆盖了默认值观察。清模块后观察默认与恢复、独立保留 setter/持久化验证，恰好覆盖这两个生命周期入口，不需要浏览器 E2E。 |
| rail 数据来源 | AgentsRailDesktop 实际只查询 listPublicAgents 并向 AgentLifecycleRow 传递 PublicAgent 字段，nodes 固定为空；public-agents.ts 将联系人 node_name/status 映射到这些字段。移除未消费的 listNodes mock、验证设备字段和必要选择接线，与实际 owner 一致；不要求 rail 拦截其未使用的 nodes lookup mutation。 |
| emoji 重复 | tool-calls-panel.test.tsx 两个 bash 无 emoji 的输入、展开动作和断言相同，删除一个保留一个不会损失已确认分支。unknown 与显式 emoji 优先级在设计中明确保留。 |
| rail 颜色重复 | 上层 rail 与 agent-row.test.tsx 都检查同一名称/ID CSS 类，AgentRow 已覆盖 normal/active。删除仅增加 wrapper/fixture 成本的上层重复，同时保留 rail 的数据及选择接线，符合最低有效层。 |
| 两项整句政策断言 | 当前 workflow 的 simplified-flow case 及 archive contract 的 ready-PR case 确实只搜索自然语言片段。限定删除这两项，不删除 archive 黑盒、链接与门禁矩阵检查，不引入新的文本解析框架，范围准确。 |
| codex unit 归档与 CI wiring | checker 当前在非 unit/ 前缀直接返回 0；实际 `.github/workflows/ci.yml:116-120` 在 PR 事件将 github.head_ref 交给该脚本，故当前 codex 分支被漏检。扩展识别明确的 codex unit 命名、复用 unit ID/目录判断，保留普通 codex 分支跳过，并对两个前缀参数化 active/retired/missing/duplicate/archived，能覆盖已证实缺口。用实际 YAML step 的事件、命令和 env 关系验证接线，比全文件字符串存在更贴近失败原因；不需要改产品或新增 CI 工作流。 |

### 架构、验证与范围判断

- 测试的归属维持在现有 parser、路由、i18n、rail/row、tool panel 和 archive contract；辅助脚本承担分支解析，测试不另建一套归档实现。没有新增公共抽象、通用 mutation framework 或模拟产品执行循环。
- 独立临时副本重放已确认 mutation，要求正常实现绿、对应坏实现红，并留实际日志，足以检查本次强化的有效性。rail 的旧 lookup mutation 用于证明原声明走错路径，应由已有 AgentRow 回退保护承担；本轮不把它变成 rail 的新职责。
- 删除项均有同因保留保护，或明确属于不应由永久测试锁定的自然语言政策。方案没有依据相似名称、数量或文件长度扩大删除。
- M1 增量明确了窄验证、前端全量/Python 非 E2E/产品 contracts、coverage 更新、独立 code review + verifier 和当前 head CI；原 DSH/E2E 未改范围保留证据的边界清楚。没有以本次测试审计为由接入 E2E CI、部署或发包。
- 无 UI 行为、内容关系、产品 Context 或产品 spec 变化，不要求新原型、产品体验验收或完整 Agent Context 审查；no spec delta 与无迁移继续成立。

### 历史问题闭环

- **R1-R1 — closed。** Author Resolution 为 accepted；当前 design 的可复用能力已改成“TS 原生运行时及产品模块测试”，并明确“模块替身不证明 IM 接线”，与 R1 建议和取证一致。其余 R1 无存活问题。

### Issues

无。

### Recommendations

无新增建议；按已确认的 8 组边界实施即可。

### 验证边界

这是新增设计的 delta 审查。仅读取审计证据与当前设计/源码/测试/CI 配置；未执行 mutation、测试或真实 LLM，未修改受审设计或代码，未提交。强化测试最终能否拦住坏实现及整体回归结果，由本轮实施和既定验证门禁给出实际证据。

### R2 Author Resolution

接受 R2 的 APPROVED 结论与 8 组实施边界。无未决问题；按增量方案落实，并以隔离 mutation、相关回归和独立代码审查验证。
