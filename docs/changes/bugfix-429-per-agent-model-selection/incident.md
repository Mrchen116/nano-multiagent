# bugfix-429: IM 上为 agent 选择的模型不生效，对话实际仍跑全局默认模型

## Relations

- Related: refactor-406（决策5：model 锁在 kernel 级，本 bug 的架构根因来源）
- Related: bugfix-424（动态 agent workspace 隔离，与链路B 的动态 agent 持久化相邻）

## 原始报告

> （触发本单元的指令）修复这个链路，我要 IM 能正常切换模型

对话中用户逐步暴露问题的原话（按时间顺序）：

> LLM_PROXY 那边今天调好了，可以用 anthropic 格式调用 gpt 了。我们的内部 IM 上是不是还不能选择 gpt

> （指向 LLM proxy 日志 `logs/session/2026-06-23_17-28-35_833_sess_09a39c6ce61b2161/2026-06-23_17-31-10_519-req-anthropic_messages.json`）是这个请求嘛，这不是跑 kimi 去了吗

> 所以问题是前端选了之后，gateway 本地的配置文件没更新？

发现过程中确立的证据：在 IM 上创建了 agent `gpt-probe`，`default_model=codex_oauth:gpt-5.5`，创建返回 201、`GET /im/v1/agents/gpt-probe/config` 回读确为 gpt-5.5；但 LLM proxy 日志显示该 agent 处理对话时所有请求 `model` 字段均为 `kimiCoding:K2.6`（全局默认），`_upstream_profile=kimiCoding`。

## 澄清记录

- Q1: "切换模型"的粒度——per-agent 配置时选定就够，还是要对话中途临时切？
  A(原话): 对，但是如果用户在配置页换了，后面我再去之前的聊天历史聊的话，要能用新的模型
  Agent 解读: 粒度是 per-agent（在 agent 配置页选模型），不要求同一对话内手动临时切。但有一条强约束：改了 agent 配置里的模型后，**回到已存在的旧会话/聊天历史继续发消息，也要用新模型**——即模型按"当前 agent 配置"路由，不能在会话创建时一次性固化、之后旧会话永远用旧模型。

- Q2: 能选且能生效的模型范围，是不是 config 里 `llm.providers` 声明的所有模型，且跨 provider 类型（anthropic / openai_compat）都要正常？
  A(原话): 是
  Agent 解读: agent 配置页模型下拉里列出的每一个模型（来自 `kernel.list_models()`），选了都要真生效，无论属于 anthropic（kimi/doubao）还是 openai_compat（gpt-5.5）provider。"能选"集合 == "能生效"集合。

- Q3: 没显式选模型的 agent（default_model 为空），是否保持回退到全局默认模型？
  A(原话): 我觉得对于内核来说，不应该有一个默认的model，产品层可以有默认的model
  Agent 解读: 用户可观察行为保留——agent 没选模型时仍用一个默认模型兜底（不报错/不空跑）。但架构职责重新划分（实现层约束，交 design）：**内核不持有全局默认 model**，每次对话由产品层显式传入要用的 model；"agent 没选 → 用全局默认" 的兜底逻辑放在产品层（Gateway）。这正是本 bug 根因（refactor-406 决策5 让内核固化全局 model）的修复方向定调。

- Q4: 在 IM 上新建/改 agent 的模型后，要写回 Gateway 的 config.yaml、重启后保留，对吧？
  A(原话): 对
  Agent 解读: per-agent 模型选择要持久化。在 IM 动态新建的 agent（含其 default_model）要落进 `~/.nano-assistant/config.yaml`，Gateway 重启后该 agent 和它选的模型都还在、继续生效。这覆盖链路B 缺口（动态新建 agent 当前不写回 config，重启即丢）。

- Q5（design 阶段对齐时新增）: 内核跨 provider 怎么发请求？IM 上要不要展示模型的格式/provider？
  A(原话): 每个模型名多个请求格式，是LLM proxy仓库的设计，和这个仓库无关，我们在注册模型的时候就应该要明确一个模型名是哪个格式的，IM上展示的也是应该展示上格式。
  Agent 解读: 两层结论。①架构原则：模型名 ↔ provider/请求格式在 config 注册时一一绑定，内核严格按注册的 provider 用对应 client/格式发请求，**不依赖** LLM_PROXY「一个模型名多格式通吃」的能力（那是 proxy 仓库的设计，本仓不利用）。②新增用户可观察需求：IM agent 配置页模型下拉要在每个模型旁展示它注册的 provider/格式。

## 现象与复现

复现步骤：

1. Gateway config 中 `llm.default_model: kimiCoding:K2.6`，`llm.providers` 含 `anthropic`（kimi/doubao）与 `openai_compat`（gpt-5.5）两类。
2. 在 IM 上创建/编辑一个 agent，模型下拉选 `codex_oauth:gpt-5.5`（或任何非全局默认的模型）。创建返回 201，`GET /im/v1/agents/<id>/config` 回读 `default_model` 确为 `codex_oauth:gpt-5.5`。
3. 与该 agent 直聊，发任意消息，等它回复。
4. **期望**：发给 LLM 的请求用 `codex_oauth:gpt-5.5`。
5. **实际**：LLM proxy 日志里该 agent 全部请求 `model=kimiCoding:K2.6`、`_upstream_profile=kimiCoding`——所选模型从未被调用。

附加现象（链路B 持久化）：通过 IM 动态新建的 agent 不会出现在 `~/.nano-assistant/config.yaml`（仅 default-agent/Arch/ArchA 在内，且它们 `default_model` 均为 None），Gateway 重启后动态 agent 与其模型选择一并丢失。

环境：主仓 IM(8011) + Gateway，最新代码（main `ae65219f` 当时）。

## 影响范围

- **谁受影响**：所有在 IM 上为 agent 选择非全局默认模型的用户。
- **多严重**：per-agent 模型选择功能**完全不生效**——UI 能选、能存、能回读，但实际对话永远用全局默认模型。IM 的模型下拉是"空壳"。用户最初想用 gpt 的诉求（IM 选 gpt）当前无法满足。
- **误导性**：用户以为在用所选模型（如 gpt），实际跑的是全局默认（kimi），可能据此误判效果/成本。
- **数据损坏**：无。
- **持久化缺口**：IM 动态新建的 agent 重启即丢，模型选择即便将来生效也会被重启打回默认。

## 根因分析（RCA）

### 链路A（核心）：内核没有 per-agent / per-session model 入口

`agent.default_model` 字段在产品侧全链路（IM 表单 → IM sqlite profile → Gateway `AgentWorkspaceConfig`）都正确存着，但**到内核边界被丢弃，从未接进 LLM 调用**：

- `kernel.create_session()` 签名里**没有 model 参数**（`src/agent/sdk/kernel.py:709-716`），docstring 明确：`model is *not* taken here — it stays kernel-level (决策 5)`。
- `AgentLoop` 构造时把全局 `llm.default_model` 固化进 `self._model`（`src/agent/core/agent/loop.py:90`），每轮请求直接 `model=self._model`（`loop.py:302`）——`run()` 调用链无任何 per-session/per-run model 入参。
- Gateway `inbound_pipeline` 创建/复用 session 时也没传 `agent.default_model`（`src/personal_assistant/gateway/inbound_pipeline.py:489-497`）——本质上也传不了，因为内核不收。

**为什么这种错能进来**：

- refactor-406「决策5」当初有意把 model 定为 kernel 级共享基座属性（`build_kernel()` 一次性固化），面向单模型场景。per-agent 模型选择的 UI 与存储是后来加的，但内核传导链从未补齐，形成「UI 在、存储在、生效不在」的空壳。
- 测试缺口：没有端到端断言「agent 选了模型 X → 实际 LLM 请求 model 字段 == X」。CI 与新环境都只用单一默认模型，这类用例跑不出来。

**原始设计意图 + 必须保住的不变量**（修复不得破坏）：

- 决策5 的意图是让模型配置集中、避免散落。修复要保住「可选模型仍由 config 的 `llm.providers` 集中声明」，不是让任意调用方随手塞模型名。
- 必须保住：agent 没选模型时仍有默认可用（产品层兜底，不能丢）。
- 必须保住：内核仍是单一共享基座（不为每个模型起一个 kernel，除非 design 论证那确实是更优解）。

### 链路B（次要）：动态新建 agent 不持久化

- `save_local_config` 的 `default_model` 序列化本身正确（`src/personal_assistant/config/local_store.py:487-488`）。
- 缺口在写回路径：`_persist_agent_config` 写回 path 依赖 `_local_config.source_path`，为 None 时落到 `default_local_config_path()`，可能不是用户实际的 `~/.nano-assistant/config.yaml`（`src/personal_assistant/main.py:678-682`）；且 `reconcile_all_agents` 只遍历启动快照的 `config.agents`，跳过动态新建 agent（`main.py:2340-2347`）。

## 目标状态 / 验收标准（用户可观察）

### Requirement: agent 配置选定的模型真实生效
#### Scenario: 选定非默认模型后对话用该模型
- **GIVEN** 全局默认模型是 kimiCoding:K2.6
- **WHEN** 用户在 agent 配置页把某 agent 的模型设为 codex_oauth:gpt-5.5，并与它对话
- **THEN** 该 agent 的回复由 gpt-5.5 产生（实际发给 LLM 的请求模型是 gpt-5.5，而非全局默认）

#### Scenario: 跨 provider 类型都能生效
- **WHEN** 用户分别为不同 agent 选 anthropic provider 的模型（kimi/doubao）和 openai_compat provider 的模型（gpt-5.5）
- **THEN** 各 agent 对话都用各自所选模型，不因 provider 类型不同而失效

### Requirement: 改模型后旧会话也用新模型
#### Scenario: 回到历史会话继续聊
- **GIVEN** 某 agent 之前用模型 A 聊过一段、存在历史会话
- **WHEN** 用户在配置页把该 agent 模型改成 B，然后回到那段历史会话继续发消息
- **THEN** 新消息由模型 B 产生回复（不被旧会话固化的 A 锁住）

### Requirement: 没选模型时有默认兜底
#### Scenario: agent 未设模型
- **GIVEN** 某 agent 的 default_model 为空
- **WHEN** 用户与它对话
- **THEN** 用全局默认模型正常回复，不报错、不空跑

### Requirement: IM 模型选择展示 provider/格式
#### Scenario: 模型下拉标注各模型的格式
- **WHEN** 用户打开 agent 配置页的模型下拉
- **THEN** 每个可选模型旁展示它在 config 注册的 provider/格式（例：`codex_oauth:gpt-5.5` 标注 `openai_compat`、`kimiCoding:K2.6` 标注 `anthropic`）

### Requirement: 模型选择持久化
#### Scenario: 重启后保留所选模型
- **GIVEN** 用户在 IM 上新建了一个 agent 并选了模型 B
- **WHEN** Gateway 重启
- **THEN** 该 agent 仍在、其模型仍是 B，继续用 B 对话

### Requirement: 切换边界行为可预期
#### Scenario: 改模型时该 agent 正有回复在进行
- **GIVEN** 某 agent 正在生成一条回复（run 进行中）
- **WHEN** 用户此刻改了它的模型
- **THEN** 进行中的这条回复不受影响（用原模型跑完），其后的新消息才用新模型

#### Scenario: 所选模型上游不可达
- **WHEN** 用户所选模型对应的 provider 当前不可达
- **THEN** 对话失败信息按内核既有 LLM 错误方式呈现给用户（本单元不新增特殊错误 UI / 重试策略）

## 范围与非目标

非目标（本单元不做）：

- 对话中途手动临时切模型（在聊天框加模型切换控件）——不做。
- 模型上游不可达时的专门错误提示 UI / 重试 / 降级策略——不做，复用内核既有 LLM 错误呈现。
- 改动可选模型的来源——仍来自 config 的 `llm.providers` 声明，不新增别的模型来源。
- 改 LLM_PROXY / provider 侧配置——不在本单元范围。

## 修复方向（高层，行级方案留 design / milestone）

- **链路A**：内核去掉「自带全局 model」。为对话路由提供 per-session / per-run 的 model 入口（具体接口形态留 design 拍）；`AgentLoop` 改为按当前 agent 配置解析模型，而非构造时固化。Gateway `inbound_pipeline` 在创建/复用 session 及每轮发消息时，按 agent 当前 `default_model` 把模型传给内核；agent 没设则**产品层**兜底全局默认。相应修订 refactor-406「决策5」在 kernel 契约层（`docs/specs/kernel/spec.md`）的表述。
- **链路B**：修动态新建 agent 的 config 写回（持久化 `default_model` 与 agent 本身），确保写回用户实际 config 路径、重启保留。
- **测试**：补端到端断言「agent 选模型 X → 实际 LLM 请求 model == X」，覆盖跨 provider 与「改模型后旧会话生效」两条关键路径。
