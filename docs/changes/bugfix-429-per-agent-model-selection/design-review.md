# Design 评审:bugfix-429-per-agent-model-selection

**结论**:Issues Found

## 核实台账(逐条核过的承重原子;结论附证据)

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| loop 单共享、`model=self._model` 全局固化 | 读 loop.py | ✓ `self._model=model`(loop.py:90),generate 处 `model=self._model`(loop.py:302);override 模式(available_tools_override/system_prompt_override)与 per-session dict(`_last_real_prompt_tokens`:111)先例都在 |
| runtime `_run_locked` 按 session 取配置、`reconfigure_llm` 全局换 | 从 run 追到 loop.run | ✓ runtime.run:243 → _run_locked:299 → _execute_loop:1686 → `self._loop.run`:1709;reconfigure_llm:870 |
| `create_session` 不收 model(决策5) | 读 kernel.py | ✓ 签名无 model,docstring「model is *not* taken here(决策5)」(kernel.py:704-724) |
| `submit` 是 per-turn 入口、透传到 runs_registry | 读 kernel.py | ✓ submit:831 → `runs_registry.submit`:853 |
| `SessionConfig` 无 model 字段 | grep session | ✓ create_session 仅传 skills/tool_allowlist/metadata(kernel.py:776-782) |
| factory client 在 build 时按 provider 绑定 | 读 factory.py | ✓ `create_llm_client` 按 `config.provider` 解析单 client(factory.py:25-54),`_PROVIDER_CLIENTS` 映射 anthropic/openai_compat |
| model_registry 无 `provider_of` 反查 | 读 model_registry.py 全文 | ✓ 结构是 provider→{model→meta},无 model→provider 反查,design 说要补——成立(model_registry.py:26) |
| `inbound_pipeline` submit 不传 model、register_agent 实时更新 | 读 inbound_pipeline.py | ✓ submit 两处(:285 主轮 / :705 /stop)均无 model;register_agent 写 `self._agents[id]`(:777),每轮读最新 |
| 链路B `_persist_agent_config` 依赖 source_path | 读 main.py | ✓ persist_path 取 source_path 否则 default_local_config_path()(main.py:678-682) |
| **`list_models()` 返回 `list[str]`,需改成带 provider** | 读 kernel.list_models + 下游 | ✗ **现状误判**:`list_models()` 已返回 `ModelInfo(name, provider, is_default)`(kernel.py:1033-1070,**已带 provider**)。真正丢 provider 的是 `upstream_reporter._models_from_kernel` flatten 成 `m.name`(upstream_reporter.py:87)+ IM `models: list[str]`(agents.py:157 / nodes.py:94)→ 接口清单点错层 |
| `submit` 调用点全集 | grep 全仓 | ✗ 接口清单只覆盖 inbound_pipeline;遗漏 main.py:2001(heartbeat/cron 通用 submit 包装器)与 **registry.py:642 内核自身 continuation self-submit** |

### 决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 决策1:model 走 per-turn submit 透传 | 拍死?数据流闭合? | ✓ 拍死;但 submit 是异步排队(registry `_run_worker_async` 后台 create_task 再调 runtime.run:612),model 仅作透传参数、未入 RunRecord——见决策2 冲突 |
| 决策2:内核零默认 + model 必填 | 拍死?自洽?数据流闭合? | ✗ 与内核自身 continuation submit 冲突(见 Issue 1);且明文「与决策3 一并定 reconfigure_llm 命运」把命运甩给决策3 |
| 决策3:多 client 按 provider 路由 | 拍死? | ✗ 主体(多 client/provider_of 路由)拍死,但「reconfigure_llm **退役或重构**为多 client 基座」未二选一(见 Issue 2) |
| 决策3 否决选项A(单 client 通吃) | 有据? | ✓ 与 incident Q5 用户拍板「不依赖 proxy 多格式」一致 |

### spec 约束(incident 目标状态)

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Req 选定模型真实生效 / 跨 provider | design 落点 | ✓ 决策1+2+3 覆盖 |
| Req 改模型后旧会话用新模型 | design 落点 | ✓ 决策1 per-turn 重读(incident:104-108 ← design 决策1理由) |
| Req 没选模型默认兜底 | design 落点 | ✓ 决策2 `agent.default_model or product_default`(产品层兜底,符合 Q3) |
| Req IM 展示 provider/格式 | design 落点 | △ 意图覆盖,但落点层指错(见 list_models 行) |
| Req 模型选择持久化 | design 落点 | ✓ 链路B(决策正文 + delta gateway) |
| Req 切换边界:run 进行中改 model | design 落点 | △ per-turn 注入天然满足(进行中 run 已携自身 model),但 design 未显式点这条 Scenario——可接受 |
| Req 上游不可达复用既有错误 | 非目标核对 | ✓ incident 列非目标,design 风险段未新增特殊 UI |

### delta-spec

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| kernel delta 改决策5 表述 | 锚 canonical 在否 | ✓ 决策5「model 维持 kernel 级」实存(kernel/spec.md:80,224),应 MODIFIED——design 已注明 |
| kernel 现存 reconfigure_llm Scenario 命运 | delta 是否锚定 | ✗ canonical Scenario「切换 provider/model 后查询反映新值」(kernel/spec.md:230-232)在决策2/3 后悬空,delta-spec 未锚定 MODIFIED/REMOVED(见 Issue 6) |
| im / gateway / cli delta | 覆盖 / no-delta 注明 | ✓ 三包 delta 意图列出,cli 显式 "no spec delta" |

### milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Milestones 拆分决策 | 看 §Milestones | ✗ **空白「（对齐后填）」**(design.md:189-191)——无任何 milestone 决策,orchestrator 无法派发(见 Issue 3) |

### 常规完整性

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 章节齐整 | 通读 | ✗ "## Runbook for Reviewer" 重复两次(:173 已填 / :185 占位「（对齐后填）」);Changelog 段空(:8) |

---

## Issues(按 CRITICAL > WARNING)

- **[CRITICAL] [决策2 / 决策1 数据流]**:内核自身在 `registry.py:642` 有一处 continuation self-submit(后台任务注入 stranded 消息后 `self.submit(origin=BACKGROUND_TASK)` 续跑),**无任何 consumer 参与、无 agent.default_model 来源**。决策2 定「submit 的 model 必填、内核零默认」,而 model 又只作透传参数、未存进 RunRecord——这条内核内部续跑路径拿不到 model,与决策2 直接冲突。不改 → worker 照决策2 字面实现会卡在这处必填参数无值可传,只能私自塞默认(违背「内核零默认」)或漏掉续跑路径(BACKGROUND_TASK 续跑跑错/崩)。需在 design 拍一条:in-flight run 的 model 存入 RunRecord/controller,续跑复用原 run 的 model(且 submit 是异步排队,model 本就必须落进 RunRecord 才能在后台 `_run_worker_async`→`runtime.run` 时取到——透传链描述里缺这一环)。

- **[CRITICAL] [决策3 / 决策2]**:`reconfigure_llm` 命运「退役**或**重构为多 client 基座」二者未拍死(决策2 还明文把它甩给决策3,决策3 也没二选一)。`reconfigure_llm` 当前唯一调用方是 CLI `/model`(commands.py:511),退役=删 `kernel.reconfigure_llm`+`runtime.reconfigure_llm`+`loop.bind_llm_client` 并重写 CLI、删 kernel spec 对应 Scenario;重构=保留方法改多 client。两条建出完全不同的 API surface / CLI 路径 / spec delta。不改 → worker 只能猜,两个 worker 各建一套互不兼容。`get_llm_config` 在 model 转 per-turn 后「当前 active model」也失语义,需一并定命运。

- **[CRITICAL] [§Milestones]**:Milestones 段是空占位「（对齐后填）」,无 milestone 拆分决策(连「单 M1」都未声明)。不改 → orchestrator 无可派发对象,门禁 2 无法进入实施。design 未定稿,至少需补一条 milestone 决策(本 unit 跨 kernel/gateway/IM 后端/IM 前端 + CLI,需举证是单 M1 垂直切片还是按可并行无交集模块拆)。

- **[WARNING] [现状分析 / 接口改动清单 — list_models]**:design 称「`Kernel.list_models()` 返回从 `list[str]` 改为携带 provider 的结构」属现状误判——`list_models()` 已返回带 provider 的 `ModelInfo`(kernel.py:1033)。真正把 provider flatten 掉的是 `upstream_reporter._models_from_kernel`(只取 `m.name`,upstream_reporter.py:87)与 IM `models: list[str]`(agents.py:157 / nodes.py:94)。不改 → worker 照接口清单去动 list_models(改已正确的东西)、且可能漏掉 upstream_reporter 这个真正的丢失点,导致「展示 provider」落空。请把接口清单的落点改到 upstream_reporter + IM capabilities 序列化 + 前端。

- **[WARNING] [submit 调用点 — heartbeat/cron]**:`main.py:2001` 是 heartbeat/cron 用的通用 submit 包装器,接口清单未覆盖。决策2 让 model 必填后,此处无 `agent.default_model` 直接来源(包装器只收 session_id/parts/origin/workspace_root)。不改 → worker 撞到必填参数无值,需自行决定「按 session→agent→default_model 解析」还是「调用方串入 model」,这是 design 该拍的边界。请补一句此路径的 model 解析方式。

- **[WARNING] [delta-spec kernel]**:kernel/spec.md:230-232 现存 canonical Scenario「切换 provider / model 后查询反映新值」(经 `reconfigure_llm`),在决策2/3 后会与「内核无对话默认 model + reconfigure_llm 退役」矛盾。delta-spec 只锚了「修订决策5 表述」,未锚定这条 Scenario 做 MODIFIED/REMOVED。不改 → 收尾并入长青契约层后,canonical 里同时存在「reconfigure_llm 切 model 生效」与「reconfigure_llm 退役」两条自相矛盾。

## Recommendations(不阻断)

- 决策1 透传链写「约 5 处签名」,实际还要穿过 `registry._run_worker_async`(后台 create_task 闭包)这一环,且 model 必须落进 RunRecord(异步排队所致)——补全这一环顺带解掉 Issue 1。
- 清理重复的 "## Runbook for Reviewer" 标题(删占位的那个)与空 Changelog 段。
