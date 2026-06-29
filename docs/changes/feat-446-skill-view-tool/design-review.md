# Design 评审: feat-446-skill-view-tool

**结论**: Issues Found

## 核实台账（逐条核过的承重原子；结论附证据）

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `skill_manage` 是当前 skill 读写混合工具，action 含 `view` | 从注册入口追到工具实现 | ✓ 生产经 `build_kernel()` 调 `_register_self_evolution_builtins()` 注册 `SkillManageTool`（`src/agent/sdk/kernel.py:492`, `src/agent/sdk/kernel.py:590`）；工具 action enum 含 `view`（`src/agent/platform/tools/builtins/skill_manage.py:27`, `src/agent/platform/tools/builtins/skill_manage.py:171`） |
| 现状: `skill_manage(action=view)` 返回 SKILL.md 内容 | 读工具分发与 view handler | ✓ `_dispatch()` 将 `view` 路由到 `_view()`（`src/agent/platform/tools/builtins/skill_manage.py:339`），读取 `skill.location.read_text()` 后返回 `success/name/content/location`（`src/agent/platform/tools/builtins/skill_manage.py:425`） |
| 现状: prompt 仍引导模型用 `read` 加载 skill | 读 formatter | ✓ `SKILLS_GUIDANCE` 写明 "Use the read tool to load a skill's file"（`src/agent/core/skills/formatter.py:8`） |
| 现状: `/skill:<name>` 目前只重写为自然语言，不保证走专用工具 | 读 slash rewrite | ✓ `rewrite_skill_command()` 输出 `Use the "<name>" skill for this request.`（`src/agent/core/agent/skill_commands.py:39`），未指定 `skill_view` |
| 现状: feature gate 只能表达单工具依赖 | 读 feature registry | ✓ `FeatureEntry.requires_tool: str | None`（`src/agent/core/agent/prompt_sections/feature_registry.py:26`），`skill_creation` 当前只依赖 `skill_manage`（`src/agent/core/agent/prompt_sections/feature_registry.py:63`） |
| 现状: compaction 当前只写 compact_boundary + summary turn | 读 runtime compaction | ✓ `_compact_session()` 写 `compact_boundary` 后写 summary turn（`src/agent/core/agent/runtime.py:2099`, `src/agent/core/agent/runtime.py:2124`），当前没有 invoked skill 注入步骤 |
| 现状: JSONL resume 只恢复白名单 metadata | 读 JSONL load helper | ✓ `_extract_message_metadata()` 只保留 `is_meta/is_compact_summary/is_provider_error/entrypoint` 与 tool_calls（`src/agent/core/session/jsonl_store.py:811`），新增 `is_skill_reinjection` 必须显式加 |
| 现状: `.usage.json` 会在 agent workspace/gateway 侧，而不是 IM DB | 追 skill root 与 IM 架构 | ✓ skill root 由 session metadata 的 `workspace_root + workspace_config_dirname` 推导（`src/agent/platform/tools/builtins/skill_manage.py:283`, `src/agent/platform/tools/builtins/skill_manage.py:296`）；IM 契约禁止直接调 agent/读 gateway workspace，runtime 能力经 gateway WS 解析（`docs/specs/im/spec.md:22`, `docs/specs/im/spec.md:125`, `docs/specs/im/spec.md:256`） |
| 现状: IM 前端数据来自 `/im/v1/*` API | 读前端 API 与路由 | ✓ agent 能力页通过 `authFetch` 调 IM API（`src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts:1`）；现有路由没有 skill dashboard 入口（`src/IM/frontend/src/app/router.tsx:35`） |

### 决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 决策 1: 独立 `skill_view`，`skill_manage` 只留写侧 | 四问 | ✓ 拍死且由 spec Q1 驱动（`docs/changes/feat-446-skill-view-tool/spec.md:37`）；落在当前 built-in 注册路径内（`src/agent/sdk/kernel.py:564`） |
| 决策 2: `.usage.json` per-workspace 统计模型 | 四问 | ✗ 数据模型不完整：dashboard 要显示来源 F1/F2/F3/F4（`spec.md:253`），但 design 只存 `created_by: "auto"` 这类粗粒度字段（`design.md:135`），无法区分 F1 vs F2、F3 vs F4；同时没有说明 `skill_manage(create/patch)` 如何写入 provenance |
| 决策 3: invoked skill compaction 存活 | 四问 | ✓ 方向成立，且 design 已点名需要加 `is_skill_reinjection` 白名单（`design.md:152`, `design.md:158`）；实现时需对齐 JSONL metadata 白名单（`src/agent/core/session/jsonl_store.py:811`） |
| 决策 4: Curator 三态 + per-workspace | 四问 | ✓ 状态机、阈值、管辖范围拍死（`design.md:160`, `design.md:179`），符合 spec 的 30/90/7 天与 per-workspace 要求（`spec.md:187`, `spec.md:125`） |
| 决策 5: `.curator_state.json` 独立存储 | 四问 | ✓ 拍死且有损坏回退（`design.md:183`, `design.md:196`） |
| 决策 6: `requires_any_tool` feature gate | 四问 | ✓ 拍死了 OR 依赖模型，并覆盖仅有 skill_view 时的文案条件化（`design.md:200`, `design.md:204`） |
| 决策 7: F4 由 Curator 扫描触发 | 四问 | ✗ 分层数据流不闭合：design 把 `maybe_run_curator()` 定位为 `core/skills/curator.py`（`design.md:277`），又在该流程里 `Thread(target=f4_runner.run)` 调 platform runner（`design.md:298`, `design.md:304`）。按字面实现会让 core 依赖 platform，撞 `core` 不依赖 `platform` 的硬规则（`SPEC.md:145`） |
| 决策 8: `skill_view` 工具接口 | 四问 | ✗ 并发语义自相矛盾：接口示例写 `is_concurrency_safe = False` 且注明会写 `.usage.json`（`design.md:234`），理由段又说 `is_concurrency_safe = True` 因为只读（`design.md:246`）。worker 会被迫猜 |

### spec 约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Req: `skill_view` 独立只读工具可用 | 覆盖检查 | ✓ 决策 1 + 决策 8 覆盖（`design.md:113`, `design.md:219`） |
| Req: `skill_manage` 不再包含 view action | 覆盖检查 | ✓ 决策 1 和 M1 覆盖（`design.md:115`, `design.md:384`） |
| Req: 使用统计追踪 use_count / last_used_at / session refs | 覆盖检查 | ✓ 决策 2 覆盖（`design.md:121`） |
| Req: `/skill:<name>` 也记录统计 | 覆盖检查 | ✓ After 图和 formatter/slash 迁移覆盖（`design.md:88`, `design.md:384`） |
| Req: compaction survival | 覆盖检查 | ✓ 决策 3 覆盖（`design.md:150`） |
| Req: Curator 自动生命周期 | 覆盖检查 | ✓ 决策 4 + M2 覆盖（`design.md:160`, `design.md:385`） |
| Req: F4 Per-skill Batch | 覆盖检查 | △ 有决策和 M2 覆盖（`design.md:208`, `design.md:385`），但触发/执行跨 core-platform 的接口未闭合 |
| Req: F2 从历史 session 蒸馏 skill | 覆盖检查 | ✗ spec 场景包含“用户在 IM 左边栏选择若干已结束 session，跳转到新对话并写意图”（`spec.md:217`），design 的 M3 只交付一个 SKILL.md（`design.md:386`），没有 IM 会话选择/跳转入口、数据传递方式或退出标准 |
| Req: 使用统计面板（IM 前端） | 覆盖检查 | ✗ spec 要真实 Skill 列表、Agent 维度、健康度三视图（`spec.md:251`），design 只有 prototype 链接（`design.md:337`）和 `IM/frontend/src/` 组件范围（`design.md:387`），没有数据 API / WS RPC / gateway provider |
| Req: 所有引用点迁移 | 覆盖检查 | ✓ 现状表列出了 product/kernel/self_improvement/formatter/capability projection（`design.md:17`） |
| 非目标: 不加 file_path 参数 | 越界检查 | ✓ 决策 8 明确不带 `file_path`（`design.md:246`） |

### delta-spec 条目

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| kernel ADDED: `skill_view` 工具可用 | 用法/THEN 检查 | ✓ 工具返回和统计/compaction 场景覆盖（`docs/changes/feat-446-skill-view-tool/specs/kernel/spec.md:5`） |
| kernel MODIFIED: `skill_manage` action 枚举 | 锚 canonical 检查 | ✓ 是对既有内置工具行为的修改，用 MODIFIED 合理（`docs/changes/feat-446-skill-view-tool/specs/kernel/spec.md:25`） |
| kernel MODIFIED: 内置工具注册列表 | THEN 可观察检查 | ✗ Scenario 直接要求查看内部 `_register_self_evolution_builtins`（`specs/kernel/spec.md:35`），违反 delta-spec “THEN 只能写消费者可观察结果”的红线；应改为 `Kernel.list_tools` / 会话 enabled_tools 可见 |
| im: no spec delta | 覆盖检查 | ✗ 不成立。IM 契约把浏览器前端和终端用户列为消费者（`docs/specs/im/spec.md:5`），且 runtime/workspace 数据必须经 gateway WS RPC 代理（`docs/specs/im/spec.md:125`）。本 unit 新增 dashboard 和 F2 IM 选择交互，缺 IM delta 会让收尾归并无锚 |
| gateway: no spec delta | 覆盖检查 | ✗ 若 dashboard/F2 需要读取 `.usage.json` 或 session transcript 路径，gateway 需要新增 WS RPC/provider；design 未说明 no-delta 的依据 |
| cli: no spec delta | 覆盖检查 | ✓ CLI 只是默认工具列表增加 `skill_view`，对 CLI 外部命令面无新增契约（`design.md:348`） |

### milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| M1 `skill-view-core` | 垂直性/退出标准 | ✓ 可独立验收：工具可用、移除 view、usage、compaction、引用迁移均在一条内核路径上（`design.md:384`） |
| M2 `curator-f4` | 垂直性/范围 | ✗ F4 runner 与 core curator 的分层接口未定义，M2 范围同时写 `core/skills/curator.py` 与 `platform/tools/builtins/f4_runner.py`（`design.md:385`），worker 会猜 core 如何合法触发 platform job |
| M3 `f2-distill` | spec 覆盖 | ✗ 只交付蒸馏 SKILL.md（`design.md:386`），漏掉 spec 的 IM 会话选择 + 跳转新对话场景（`spec.md:217`） |
| M4 `dashboard` | 垂直性/数据流 | ✗ 横切成纯前端组件（`design.md:387`），但真实数据在 gateway/workspace 侧（`skill_manage.py:283`），没有 API/provider 的 milestone 范围 |
| 并行组 | 范围交集 | ✓ 当前表未声明同组并行互撞；M2/M4 均依赖 M1（`design.md:389`） |

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | Dashboard 数据通道 | ✗ `.usage.json` 属 gateway/agent workspace，IM 前端不能直接读；自然归属应是 IM HTTP route -> gateway WS RPC -> gateway provider 读 workspace sidecar。design 放成纯 `IM/frontend/src/` 会迫使前端 mock、复用错误 API，或把 IM 变成跨机直读 workspace，长期破坏 IM/gateway 边界 |
| 归属 | Core Curator 触发 platform F4 runner | ✗ core curator 直接启动 platform runner 会形成 core -> platform 反向依赖。长期代价是 `tests/contract/test_core_no_platform_imports.py` 失效或被绕过；应改成 core 只产出 `F4Trigger`，由 sdk/platform/gateway 调度层消费 |
| 归属 | F2 会话选择入口 | ✗ 用户场景天然属于 IM 前端/IM HTTP 会话域，蒸馏 SKILL.md 属 agent skill 域。design 只写 skill 文件，把交互入口留空，长期会出现“skill 存在但用户无从把 session IDs 传进去”的半成品 |
| 该不该存在 | `.usage.json` 中 `created_by` | ✗ 字段存在但粒度不足。删除测试后会发现 dashboard 的 F1/F2/F3/F4 来源列、Curator 的 auto/manual 边界都依赖它；应提升为 `source: F1|F2|F3|F4` 或等价枚举，并规定写入点。否则后续只能靠目录名/调用者猜测来源 |
| 深还是浅 | 前端 prototype | ✗ prototype 只展示静态 UI，没有把“数据从哪来、loading/offline/error 怎么显示、agent 选择如何映射到 node/workspace”封装掉。长期代价是 M4 worker 只能做浅 UI，验收时真实环境空表或假数据 |
| 治本还是补丁 | `im: no spec delta` | ✗ 这是用“展示层”标签绕过契约更新，但本项目 IM spec 明确包含浏览器前端可依赖行为。长期代价是收尾无法归并 dashboard/F2 API，下一次改前端或 gateway RPC 没有 current contract 可对账 |

## Issues

- **[CRITICAL] [前端 / 契约层增量 / M4] Dashboard 只有前端组件，没有真实数据通道。** spec 要 IM 前端显示所有 skill 的来源、状态、use_count、趋势、agent 热力图和健康度（`spec.md:251`），design 只给 prototype 和 `IM/frontend/src/` 范围（`design.md:337`, `design.md:387`），同时声明 `im/gateway: no spec delta`（`design.md:346`）。但 `.usage.json` 在 agent workspace/gateway 侧，IM 契约要求跨机 workspace 内容经 gateway WS RPC 代理（`docs/specs/im/spec.md:125`）。不改的话，M4 worker 要么做假数据面板，要么越界让 IM/前端直接读本地文件，验收无法走真实用户旅程。退回补 IM HTTP API + gateway WS RPC/provider + 前端查询/空态/离线态设计，或把 dashboard 从本 unit scope 移出。

- **[CRITICAL] [F2 / 前端] F2 的 IM 会话选择与跳转场景漏设计。** spec 场景要求“用户在 IM 左边栏选择若干已结束 session，跳转到新对话并写意图”（`spec.md:217`），但 M3 只写“蒸馏 skill（SKILL.md）”（`design.md:386`），没有右键/多选入口、session IDs 如何进入新对话、transcript 权限与读取路径、PA/agent 级选择 UI。worker 按 design 实施会得到一个孤立 skill，用户无法从 IM 发起这条流程。退回补前端交互与 IM/gateway 数据流，或明确修改 spec 把 IM 交互移出本期。

- **[CRITICAL] [决策 7 / M2] Core Curator 到 platform F4 runner 的分层接口未闭合。** design 把 `maybe_run_curator()` 放 `core/skills/curator.py`（`design.md:277`），又在同一流程中启动 `platform/tools/builtins/f4_runner.py`（`design.md:298`, `design.md:304`）。按字面实现会让 core import platform，违反 `core` 不依赖 `platform` 的硬规则（`SPEC.md:145`）。退回把 core Curator 改为只返回确定性 transition + F4 trigger 列表，由 sdk/platform/gateway 调度层注入 runner 并启动 batch。

- **[CRITICAL] [决策 2 / Dashboard / Curator] Skill 来源模型不足，无法支持 F1/F2/F3/F4 面板和 Curator 管辖边界。** spec 要面板显示来源 F1/F2/F3/F4（`spec.md:119`），且 Curator 只管 F3/F4 自动创建 skill（`spec.md:66`）。design 的 `.usage.json` 只有 `created_by: "auto"`（`design.md:135`），也没有说明现有 `skill_manage(create)` 如何写 provenance（现有 schema 无该字段，`src/agent/platform/tools/builtins/skill_manage.py:166`）。不改的话，F1/F2 与 F3/F4 会被混淆，Curator 可能归档用户手工 skill，dashboard 来源列也只能猜。退回定义 `source: F1|F2|F3|F4`（或等价枚举）和每个写入路径的赋值规则。

- **[CRITICAL] [delta-spec] `im/gateway: no spec delta` 与本 unit 的前端范围冲突。** IM spec 的消费者包括浏览器前端/终端用户（`docs/specs/im/spec.md:5`），本 unit 新增 dashboard 和 F2 IM 交互是用户可观察行为；如果还声明 no delta（`design.md:346`），收尾归并时没有 canonical 锚，reviewer 也没有 API/WS contract 可验。退回新增 IM/Gateway delta-spec，至少覆盖 dashboard 数据读取、节点离线降级、F2 session 选择/跳转的可观察行为。

- **[WARNING] [决策 8] `skill_view.is_concurrency_safe` 自相矛盾。** 示例写 `False` 且说明 `bump_use` 写 `.usage.json`（`design.md:234`），理由段又说 `True` 因为“只读，不写文件”（`design.md:246`）。worker 可能实现成并发安全工具，导致并发 bump 覆盖统计。退回拍死为 `False`，或同时设计锁机制并解释为何可为 `True`。

- **[WARNING] [kernel delta-spec] Scenario 直接锚内部函数。** `kernel` delta-spec 的“内置工具注册列表”要求查看 `_register_self_evolution_builtins`（`specs/kernel/spec.md:35`），这是实现细节，不是消费者可观察 THEN。退回改成 `Kernel.list_tools` 或创建会话后的 tool catalog 可见。

## Recommendations（不阻断门禁，作者自行取舍）

- Dashboard 原型建议补一段“真实数据字段表”：`skill_id/name/source/state/use_count/last_used_at/session_refs/trend_buckets/agent_id/node_id`，避免 M4 worker 从静态 DOM 反推 schema。
- F4 batch 的失败语义建议补清：如果 batch 启动后失败，`uses_since_last_B` 已归零是否接受；若不接受，需要 pending/running/completed 状态。
- Runbook 里 IM 停止命令使用 `.im.pid`，但本 unit reviewer 可能用 `scripts/e2e-up.sh`，建议引用项目现行 e2e 脚本以减少端口污染风险。

