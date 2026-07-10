# refactor-382: LLM 模型清单从代码迁到 Gateway 配置

## Relations

- Depends on: 无
- Blocks: refactor-TBD-thinking-as-call-site-concern（待立单：把 `extra_request_body={"thinking": {"type": "adaptive"}}` 从模型元数据搬到调用现场显式声明）
- Related: bugfix-366（首次引入 model-level `extra_request_body` 机制）、bugfix-369 / bugfix-373 / bugfix-375（依赖该机制的 thinking 行为链）

## 原始诉求

> 我觉得每个gateway的模型列表不应写在代码中，而是放在gateway的配置文件中

## 澄清记录

- Q0: 类型归属——按 refactor 还是 feat？
  A(原话): ok
  Agent 解读: 按 refactor。端用户行为零变化（IM 模型下拉来源换了但展现一致），运维可编辑 YAML 是搬家的副产物，不是用户喊出来的新能力。

- Q1: 运维的目标旅程——是不是"想加新模型时，改 `~/.nano-assistant/config.yaml` 的 `llm:` 段、重启 Gateway，完事，不动代码、不重装包"？其他衍生（热加载、IM 前端的模型管理页、per-node 模型差异化展示）都不在范围。
  A(原话): 对

- Q2: 运维在 YAML 里新增一个模型条目时该填哪些字段？
  A(原话): extra_request_body 这个没必要吧，anthropic都是统一模式，openai也是统一模式的。而且也不是说用到这个模型就必须思考，分场景的，代码里就有思考和不思考的
  Agent 解读: 用户首次表达"thinking 该是调用现场决策，不该绑模型"。但后续 Q3 收尾时确认本 unit 范围内 `extra_request_body` 不动，留 follow-up 单做语义重构。

- Q3: capabilities 四件套（text/image/tools/streaming）保留吗？
  A(原话): capabilities我觉得也没有太大必要啊。
  Agent 解读: 核了 grep，capabilities 四个标志只在 `model_registry.py` 定义后由 `agent/platform/http_api/routes/global_routes.py:155-158` 通过 HTTP 接口原样吐出，**没有任何 runtime 分支基于它做决策，IM 前端也未消费**。属于死代码字段，砍掉对行为零影响。

- Q3-补: 上一轮我把"thinking 分场景"误读成"`extra_request_body` 也是死代码、本 unit 直接清掉"，让用户澄清。
  A(原话): 在 model_registry.py 里 kimiCoding:K2.6 和 volcanoArk:...doubao 两条都挂着 extra_request_body={"thinking":   {"type": "adaptive"}}。这次重构搬到 config 时,这个字段直接消失。当然不是啊。你先看之前实现这个功能的unit。和对应的代码。你没理解我意思
  Agent 解读: 用户纠正——`extra_request_body` 是 load-bearing。`AnthropicClient.generate()`（`client.py:56-61`）默认合并模型元数据上的 `extra_request_body`，再叠 `request.extra_body` 做 per-call override（bugfix-369 gate 用 `thinking: disabled` 覆盖）。bugfix-366/369/373/375 整条 thinking signature roundtrip 都依赖"模型级默认 + 调用现场可覆盖"契约。直接砍会让主 agent loop 退回不带 thinking，相关 bug 链复发。

- Q3-定: A=严格搬家保真 `extra_request_body` 进 config / B=同步翻转 thinking 为调用现场决策 / C=本 unit 选 A，"thinking 翻转"另立 follow-up unit。
  A(原话): C

- Q4(a): provider 的 `base_url` 放 config（env `NANO_MULTIAGENT_LLM_BASE_URL` 作 fallback）还是继续完全靠 env？
  A(原话): 都同意你的推荐
  Agent 解读: 选"放 config，env 作 fallback"。运维一个文件看全 LLM 状态。

- Q4(b): `default_model` 在 config 里显式写一行，还是省略、代码自动取 `providers` 第一项第一条？
  A(原话): 都同意你的推荐
  Agent 解读: 选"显式写"。`llm.default_model: <model_id>`。

- Q5: 运维拉新代码但 config 还没加 `llm:` 段时——Gateway 拒启动报错（A）还是静默用内置 fallback（B）？
  A(原话): 不考虑后向兼容。
  Agent 解读: 选 A。代码里不留 fallback 清单。

- Q6: agent 的 `default_model` 引用了 `llm.providers` 里不存在的模型时——拒启动报错（A）还是回落到 `llm.default_model` 并 warning（B）？
  A(原话): A

## 现状痛点

LLM 模型清单当前硬编码在 `src/agent/core/llm/model_registry.py:24-63` 的 `_PROVIDER_MODELS` 字典里，配套写死的还有 `DEFAULT_PROVIDER`、`_PROVIDER_DEFAULT_MODEL`、以及每个 provider 的 `default_base_url`。运维（目前主要是项目作者本人）想增减一个模型，必须：

1. 编辑 `model_registry.py` 源码加/删条目；
2. 由于本项目通过 `pip install -e .` 安装，源码改动通常立即生效，但仍需重启 Gateway 与 Kernel 进程；
3. 若操作来自另一台机器/容器，还要重新分发代码。

这与 Gateway 已有的其它 per-node 配置（`agents`、`channels`、`kernel.base_url`、`im_service`）形成不一致：那些是 YAML 字段，模型清单却是源码常量。语义上模型清单也属于 per-node 能力——不同 Gateway 可能连接不同 LLM 上游、需要不同模型集——但代码层级的硬编码强行让所有节点共用同一份。

附带的死代码：`ModelMetadata.supports_text/image/tools/streaming` 四个布尔字段只被 `agent/platform/http_api/routes/global_routes.py:155-158` 原样吐回 HTTP 响应，无任何 runtime 分支与前端消费方读取它们。

## 目标状态

`~/.nano-assistant/config.yaml` 增加一个顶层 `llm:` 段，与现有 `node` / `agents` / `kernel` / `heartbeat` / `im_service` 平级。结构示意（具体 schema 与默认值由 design 阶段拍板）：

```yaml
llm:
  default_model: kimiCoding:K2.6
  providers:
    anthropic:
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
          extra_request_body: { thinking: { type: adaptive } }
        - name: volcanoArk:doubao-seed-2-0-code-preview-260215
          extra_request_body: { thinking: { type: adaptive } }
    openai_compat:
      base_url: http://127.0.0.1:4000
      models:
        - name: codex_oauth:gpt-5.5
```

运维加模型 = 在 `models` 数组末尾加一项 + 重启 Gateway。不动代码、不重装包。`base_url` 缺省允许 env `NANO_MULTIAGENT_LLM_BASE_URL` 兜底。

`model_registry.py` 由"硬编码常量表"退化为"从 config 注入构造的注册表"，对外接口（`list_supported_providers` / `list_provider_models` / `get_default_model` / `resolve_model_metadata`）保持稳定，调用方（`upstream_reporter`、`AnthropicClient.generate`、`global_routes`）零感知。

死字段 `supports_text/image/tools/streaming` 在本 unit 顺手清除——既然 schema 全部重做，没必要把死字段也搬过去。

## 范围与非目标

**范围**：
- 引入 `llm:` config 段及对应 dataclass / parse / save 链路。
- 重写 `model_registry.py` 为 config 驱动；保留对外接口签名以减少 ripple。
- 清除 `ModelMetadata` 的 capabilities 四件套（死代码）。
- 错配硬失败：缺 `llm:` 段、agent 引用了不存在的模型，都在 Gateway 启动期拒启动并明确报错。
- 更新 `AGENTS.md` 最小可用配置示例 + worktree e2e fixture（`scripts/e2e-up.sh` / config 派生逻辑）补 `llm:` 段。

**非目标**：
- **不做** thinking 语义重构（把 `extra_request_body` 从模型元数据搬到调用现场）——`extra_request_body` 在本 unit 严格保真搬进 config，作为可选字段。该清理留给 follow-up unit。
- **不做** 热加载——运维改 YAML 后必须重启 Gateway 才生效。
- **不做** IM 前端"管理模型"页面——前端继续靠 capability heartbeat 拿到 `model_options`，零改动。
- **不做** per-node 模型差异化在 IM 前端的额外展示。
- **不做** 后向兼容——升级后 config 必须有 `llm:` 段，否则 Gateway 不启动。

## 用户侧验收标准（不变性）

本 unit 是面向内部的搬家。**端用户（IM 聊天用户）**的可观察行为应当与变更前完全一致；**运维**多了一个新工作流（在 YAML 里加模型），这条新行为也要可验。

### Requirement: 端用户在 IM 里看到的模型选择行为不变（回归基线）

#### Scenario: 模型下拉选项保持原有三条
- **GIVEN** 运维拉了重构后的代码，且在 config 的 `llm:` 段照搬了代码原值（K2.6 / doubao / codex_oauth:gpt-5.5）
- **WHEN** 端用户在 IM agent 设置页打开模型下拉
- **THEN** 看到的选项与变更前一致：`kimiCoding:K2.6`、`volcanoArk:doubao-seed-2-0-code-preview-260215`、`codex_oauth:gpt-5.5`

#### Scenario: "平台默认"标签仍指向 K2.6
- **GIVEN** 同上 baseline 配置
- **WHEN** 端用户在 IM 模型下拉里看到"平台默认"标签
- **THEN** 标签仍贴在 `kimiCoding:K2.6` 那条

#### Scenario: agent 不填 default_model 时仍用 K2.6
- **GIVEN** 某 agent 的 config 没填 `default_model`，且 baseline 配置生效
- **WHEN** 端用户在该 agent 上发起一次对话
- **THEN** 实际调用 `kimiCoding:K2.6`，thinking adaptive 默认开启，与变更前一致（bugfix-366/369/373/375 行为链不回归）

#### Scenario: agent 的多轮 thinking + 工具调用对话路径保留
- **GIVEN** baseline 配置 + 某 agent 用 K2.6
- **WHEN** 端用户与该 agent 进行带工具调用的多轮对话
- **THEN** thinking signature roundtrip 行为与变更前一致：模型返回带 thinking 块的 assistant 轮被正确回传，工具结果能喂回模型，不出现"卡在工具调用后无最终答案"

### Requirement: 运维通过编辑 YAML 增减模型，不动代码

#### Scenario: 加新模型走 YAML
- **GIVEN** 运维拿到一个新 LLM 上游接入（代码 0 改动）
- **WHEN** 运维在 `~/.nano-assistant/config.yaml` 的 `llm.providers.<P>.models` 末尾加一条新模型并重启 Gateway
- **THEN** Gateway 起来后，IM agent 设置页的模型下拉里出现这一条新模型；运维全程未编辑 `src/` 下任何文件、未重新 `pip install -e .`

#### Scenario: 删模型走 YAML
- **GIVEN** 某条模型不再需要，且无 agent 的 `default_model` 引用它
- **WHEN** 运维从 YAML 里删掉这一条并重启 Gateway
- **THEN** Gateway 起来后，IM 模型下拉里这一条消失

### Requirement: Gateway 在 LLM 配置错误时立即报错而不是静默起来

#### Scenario: config 没有 llm 段
- **WHEN** 运维启动 Gateway，但 `~/.nano-assistant/config.yaml` 没有 `llm:` 段
- **THEN** Gateway 拒启动；stderr/日志报错明确指出 `llm` 段缺失

#### Scenario: agent 引用了 llm.providers 里不存在的模型
- **GIVEN** config 里某 agent 写了 `default_model: foo:bar`，但 `llm.providers.*.models` 里没有这条
- **WHEN** 运维启动 Gateway
- **THEN** Gateway 拒启动；报错明确指出是哪个 agent 引用了哪个不存在的模型

## 影响范围

- `src/personal_assistant/config/local_store.py`：新增 `LLMConfig` / `LLMProviderConfig` / `LLMModelConfig` dataclass、`_parse_llm()`、`save_local_config` 序列化、`LocalConfig.llm` 字段（必填）；agent 的 `default_model` 一致性校验也接入 `_parse_agents`。
- `src/agent/core/llm/model_registry.py`：删除 `_PROVIDER_MODELS` / `_PROVIDER_DEFAULT_MODEL` / `DEFAULT_PROVIDER` 常量；改为"从 config 注入构造注册表"的工厂；`ModelMetadata` 删除 `supports_text/image/tools/streaming` 四字段。
- `src/agent/platform/http_api/routes/global_routes.py:155-158`：移除对死字段的响应输出。
- `src/personal_assistant/reporter/upstream_reporter.py:107-126`：调用方零接口改动，但底层 registry 改成"按当前 Gateway config 实例化"，能力上报内容随 config 走。
- Gateway 与 Kernel 进程边界：Kernel 当前不读 Gateway config（独立进程），需要新增"Gateway 把 `llm:` 段传给 Kernel"的通路（具体形式由 design 定）。
- `src/personal_assistant/main.py`：启动期把 `llm:` 段注入 Kernel；`save_local_config` 写回路径也要带 `llm:` 段（agent 增删时不能丢）。
- `AGENTS.md`：最小可用 config 示例补 `llm:` 段。
- `scripts/e2e-up.sh` / worktree config 派生（`yq -i` 那段）：补 `llm:` 段，否则 worktree e2e 起不来。
- 测试：现有依赖硬编码模型清单的单测/集成测试需要改成读 config-driven registry。

## 迁移与回滚策略

**升级路径**（运维侧）：
1. 拉新代码后，**Gateway 不会启动**（缺 `llm:` 段会硬失败）。
2. 在 `~/.nano-assistant/config.yaml` 末尾追加 `llm:` 段（README / AGENTS.md 提供 copy-paste 模板，与原硬编码值一致）。
3. 重启 Gateway，行为恢复与升级前完全一致。

无渐进灰度——本项目目前是单运维（项目作者）单机部署，"刚性升级 + 显式报错"比"留 fallback"更符合"模型不该在代码里"的初衷。

**回滚**：revert 本 unit 的 PR。`config.yaml` 里多出的 `llm:` 段对 revert 后的代码是 unknown key，YAML parser 直接忽略，运维无需手动清理。

**配套交付**：`AGENTS.md` 的"最小可用配置示例"必须更新为带 `llm:` 段的版本，否则新手按文档操作会一拉到"Gateway 拒启动"。
