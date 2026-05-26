# refactor-382: LLM 模型清单从代码迁到 Gateway 配置 — 技术方案

> 对齐: motivation.md v1
> Unit branch: `unit/refactor-382-llm-models-to-gateway-config` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `src/agent/core/llm/model_registry.py`：硬编码 `_PROVIDER_MODELS`、`_PROVIDER_DEFAULT_MODEL`、`DEFAULT_PROVIDER` 三张表。导出 `ModelMetadata`、`list_supported_providers/list_provider_models/get_default_model/get_default_base_url/resolve_model_metadata` 五个函数 + 一个常量。
- `src/agent/core/llm/factory.py`：`LLMFactoryConfig.from_env()` 通过 `DEFAULT_PROVIDER`、`get_default_model()`、`get_default_base_url()` 读 env + registry，构造 LLM client。
- `src/agent/platform/llm/providers/anthropic/client.py:56-61`：`generate()` 调 `resolve_model_metadata()` 取 `extra_request_body`，与 per-call `request.extra_body` 合并。
- `src/agent/platform/http_api/routes/global_routes.py:143-168`：`build_capabilities_payload()` 把 `supports_*` 四件套和模型列表一起原样吐到 `GET /v1/capabilities`。
- `src/personal_assistant/reporter/upstream_reporter.py:107-126`：Gateway 心跳上报 capability 给 IM 时，调 `list_supported_providers()` / `list_provider_models()` / `get_default_model(DEFAULT_PROVIDER)` 构造 `models` + `platform_default_model` 字段。
- `src/personal_assistant/config/local_store.py`：Gateway YAML config 入口。已有 `NodeConfig` / `AgentWorkspaceConfig` / `ChannelConfig` / `KernelConfig` / `HeartbeatConfig` / `IMServiceConfig` 六个 dataclass + `LocalConfig` 聚合 + `load_local_config` / `save_local_config`。
- `src/personal_assistant/main.py:2468-2472`：`_spawn_process()` 用 `subprocess.Popen(shlex.split(command))` 起 Kernel 子进程，**继承父进程 env**——这是 Gateway → Kernel 传递配置的天然通道。
- `src/personal_assistant/kernel_app.py`：Kernel 进程的 uvicorn ASGI app 入口，`create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)`，无其它初始化逻辑。
- `src/agent/platform/http_api/app.py:44-90`：`create_app()` 没有 LLM 初始化钩子，目前 Anthropic client 在每次 `generate()` 时 lazy 查 `resolve_model_metadata`，未做进程级 init。
- `scripts/e2e-up.sh` + worktree config 派生（`AGENTS.md` 那段 `yq -i`）：worktree e2e 起 Gateway 时改写 `node.node_id` / `im_service.url` / `agents[].workspace_root`，**目前没改 `llm:`**——本 unit 落地后 worktree 起不来除非脚本同步加。
- `AGENTS.md` 的"最小可用 Gateway config 示例"：是新人第一份 config 模板，必须加 `llm:` 段。

### 既有约束

- **依赖方向**（`AGENTS.md`）：`coding_cli` / `personal_assistant` → `agent`（HTTP only，不直接 import 实现层）。本 unit 的 `LLMConfig` 数据结构若要在 Gateway + Kernel 两侧共享：方案 A 让两侧各自定义同形 schema（违反 DRY 但符合分层）；方案 B 把数据载体放进 `agent/core/llm/` 作为 core 暴露的 wire 类型（Gateway 解析后转换为它）。**选 B**：`agent.core.llm.config.LLMConfigPayload` 作为 wire schema 暴露给 Gateway，Gateway 的 `LocalConfig.llm` 直接持有 core 这个类型——属于 core 对外的契约，不是 Gateway 反向依赖。
- **kernel 不读 Gateway config**（明示于 `kernel_app.py` + `subprocess.Popen` 路径）：Gateway → Kernel 跨进程只有 env / 启动参数 / HTTP API 三种通路。本 unit 走 env（JSON 编码）。
- **`extra_request_body` 是 load-bearing**：bugfix-366/369/373/375 整条 thinking signature roundtrip 链路都建立在"模型级默认 `thinking: adaptive` + 调用现场可覆盖"契约上。本 unit 严格保真搬运。
- **不留 fallback**（motivation Q5）：config 缺 `llm:` 段、agent `default_model` 引用了 `llm.providers` 里不存在的模型，**Gateway 启动期硬失败**。Kernel 进程同理：env `NANO_MULTIAGENT_LLM_CONFIG_JSON` 不存在或解析失败，Kernel 拒启动。
- **三层架构**（`AGENTS.md`）：`core` 不能依赖 `platform` / `products`。`agent.core.llm.model_registry` 的工厂化重构必须保留 core 纯逻辑性质——不允许在 core 里读 env / 文件 IO；env 读取与 JSON 反序列化在调用 init 的边界（Kernel 的 `kernel_app.py`、Gateway 的 `main.py`）做。

### 可复用能力

- **现有 `_parse_agents` 验证模式**（`local_store.py:417-460`）：每条 agent 解析时对 `workspace_root` 做存在性检查、对 `features` 做严格 bool 校验、缺失关键字段抛 `ValueError`。新 `_parse_llm` 沿用同款"hard fail with field path"风格，与既有 parser 一致。
- **`agent.core.llm.__init__.py` 的 lazy import 桥**（`__init__.py:49`）：现有模式让 `import_module("agent.core.llm.model_registry")` 在首次访问时执行。这给"启动期 init"留了天然挂载点——init 函数会被显式调用，不依赖隐式副作用。
- **`AnthropicClient.generate()` 的 metadata 查询**：调用 `resolve_model_metadata("anthropic", model)` 拿 `extra_request_body`。本 unit 改成"工厂化 registry"后，这个签名不变，调用方零感知。
- **`scripts/e2e-up.sh` 的 worktree config 派生**：已经在用 `yq -i` 改写主 config 副本里的 `node_id` / `im_service.url` / `agents[].workspace_root`。加 `llm:` 段就在同一段加一行 `yq` 写入（或保留主 config 原样 `llm:` 段直接 cp 过去——主 config 已带就 cp 即可）。

### 相关历史

- **bugfix-366** (`docs/changes/bugfix-366-llm-output-limits-and-gateway-config/fix.md:80-89`)：首次引入 `ModelMetadata.extra_request_body`，给 K2.6 / doubao 默认 `thinking: adaptive`。`AnthropicClient.generate()` 的 metadata + per-call merge 机制建立于此。
- **bugfix-369** (`docs/changes/bugfix-369-gate-classifier-thinking-leak/fix.md:43-150`)：在 hook gate stage-1 调用现场用 `extra_body={"thinking": "disabled"}` 覆盖模型级默认。这条 per-call override 路径必须在本 unit 重构后继续工作。
- **bugfix-373** / **bugfix-375**：thinking signature 在 assistant 多轮 + 工具调用回传中的 roundtrip 修复——它们都假设"模型级 `extra_request_body` 在每次 generate 时自动合并"成立。motivation.md 的非目标段已显式声明"thinking 翻转"留给 follow-up unit。
- **refactor-381**：刚把 worktree e2e 工程化（`scripts/e2e-up.sh` + fixtures + auto-bind）。本 unit 的 worktree fixture 需要在 refactor-381 的产物上加 `llm:` 段；不要倒退到散文流程。

## 架构总览

```
┌──────────────────────── Gateway 进程（personal_assistant.main） ────────────────────┐
│                                                                                     │
│   ~/.nano-assistant/config.yaml                                                     │
│   ┌──────────────────────────┐                                                      │
│   │  node: ...               │                                                      │
│   │  agents: [...]           │     load_local_config()                              │
│   │  llm:                    │  ────────────────────────►   LocalConfig             │
│   │    default_model: ...    │                              ├── node                │
│   │    providers:            │                              ├── agents (验证 a.default_model ∈ llm.models) │
│   │      anthropic: ...      │                              ├── ...                  │
│   │      openai_compat: ...  │                              └── llm: LLMConfigPayload│
│   └──────────────────────────┘                                                      │
│                                                                                     │
│   启动顺序：                                                                        │
│   1. parse config → LocalConfig                                                     │
│   2. init_model_registry(config.llm)  ← Gateway 自身（upstream_reporter 要查）       │
│   3. 序列化 config.llm 为 JSON                                                       │
│   4. _spawn_process()，env['NANO_MULTIAGENT_LLM_CONFIG_JSON'] = <json>              │
│         │                                                                           │
│         ▼                                                                           │
│   ┌──────────────────────── Kernel 进程（uvicorn personal_assistant.kernel_app）──┐  │
│   │  kernel_app.py 顶部：                                                          │  │
│   │     payload = os.environ['NANO_MULTIAGENT_LLM_CONFIG_JSON']                    │  │
│   │     init_model_registry(LLMConfigPayload.from_json(payload))                   │  │
│   │     app = create_app(...)                                                      │  │
│   │                                                                                │  │
│   │  运行期：                                                                       │  │
│   │     AnthropicClient.generate() ──► resolve_model_metadata("anthropic", model)  │  │
│   │     ← 从已初始化的 registry 取 extra_request_body，合并 per-call extra_body     │  │
│   └────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Before**: `model_registry.py` 用模块级常量 `_PROVIDER_MODELS` / `_PROVIDER_DEFAULT_MODEL` / `DEFAULT_PROVIDER` 提供静态注册表，Gateway / Kernel 两侧 import 即得。

**After**: 模块级常量删除；改用进程内单例 `_REGISTRY` + `init_model_registry(payload)`。Gateway 启动时从 YAML 解析后 init 自己；Spawn Kernel 时把 payload 经 env 传过去，Kernel 启动时 init 自己。运行期访问函数（`list_supported_providers` 等）的签名不变。

## 关键决策

### 决策 1: `LLMConfigPayload` 放在 `agent.core.llm.config`（不放 personal_assistant）

- **选择**: 在 `src/agent/core/llm/config.py` 新建模块，提供三个 dataclass（`LLMConfigPayload` / `LLMProviderPayload` / `LLMModelPayload`）+ `to_json` / `from_json` 方法 + `init_model_registry(payload)` 函数。`personal_assistant.config.local_store` import 这些类型并直接持有。
- **理由**: 数据结构是 core 对外契约（Kernel + Gateway 两侧都要解析同一份 JSON），放 core 最自然。`personal_assistant` 持有 core 类型不违反依赖方向（personal_assistant → agent 是允许的）。如果放在 personal_assistant 下，Kernel 反过来 import 它就破层。
- **拒绝**: 在 `personal_assistant.config.local_store` 各自定义 dataclass，Kernel 侧另写一份并保持同形——违反 DRY，schema 漂移风险。
- **风险**: core 多了一份"看起来像产品配置"的 dataclass，可能让人误解 core 知道"Gateway YAML"。缓解：模块 docstring 明确"this is the wire schema for the LLM registry, not a Gateway YAML detail"。

### 决策 2: `model_registry.py` 工厂化（单例 + 显式 init）

- **选择**: 删除模块级 `_PROVIDER_MODELS` / `_PROVIDER_DEFAULT_MODEL` / `DEFAULT_PROVIDER`。新建模块内私有 `_REGISTRY: _RegistryState | None = None`。`init_model_registry(payload)` 把 payload 转成内部 `dict[str, dict[str, ModelMetadata]]` 写入 `_REGISTRY`。所有现有 free function（`list_supported_providers` / `list_provider_models` / `get_default_model` / `get_default_base_url` / `resolve_model_metadata`）改为读 `_REGISTRY`；未 init 时抛 `RuntimeError("model registry not initialized")`。原 `DEFAULT_PROVIDER` 常量改为 `get_default_provider() -> str`，从 registry 读出 default_model 归属的 provider。
- **理由**: 调用方签名不变，调用方零感知。"未 init 就硬失败"符合 motivation Q5 的精神（不留 fallback）。单例模式是 core 内部细节，外部仍是函数式 API。
- **拒绝**: (a) 把 registry 实例显式传给每个 caller（侵入式，需要改 `AnthropicClient.__init__` / `LLMFactoryConfig` / `upstream_reporter` 多处）；(b) 完全去掉单例，每次 `resolve_model_metadata` 都接收 config——违反 core 的"无状态注册表" 模式且 ripple 大。
- **风险**: 单元测试若依赖"import 即得 K2.6 metadata"，会因未 init 抛错。**缓解**：在 `tests/conftest.py` 或具体测试 fixture 里加默认 init（用一个固定 test payload）；同时 `model_registry.py` 暴露一个 `_reset_for_tests()` 私有辅助让测试切换 fixture。

### 决策 3: Gateway → Kernel 通过 env `NANO_MULTIAGENT_LLM_CONFIG_JSON` 传 payload

- **选择**: Gateway 在 `_spawn_process(command)` 时构造 env，把 `LLMConfigPayload.to_json()` 写入 `NANO_MULTIAGENT_LLM_CONFIG_JSON`，然后 `subprocess.Popen(..., env=env)`。Kernel 的 `kernel_app.py` 模块顶部读 env、`from_json()`、调 `init_model_registry()`。env 缺失/解析失败 → Kernel 顶层抛异常，uvicorn 启动失败，Gateway 健康检查超时报错。
- **理由**: env 是 Gateway → Kernel 已有的天然通道（`NANO_MULTIAGENT_LLM_BASE_URL` 已经用 env），不引入新机制。JSON 长度在合理 LLM 配置规模下（< 4KB）远低于 `MAX_ARG_STRLEN` / env 块限制。模块顶部 init 让 uvicorn 拒启动时立刻可见。
- **拒绝**: (a) 让 Kernel 直接读同一个 YAML 文件（破坏 kernel 进程对 Gateway config 的无知）；(b) Gateway 启动后 HTTP POST 配置给 Kernel（增加启动期同步复杂度，且 Kernel 端要先在"无 registry"状态启动）。
- **风险**: env 在进程列表（`ps eauxw`）里可见——但 LLM 模型清单不是敏感信息。`api_key` 已在用 env 传，无新泄露面。

### 决策 4: `base_url` 解析顺序：env > config > error

- **选择**: `LLMProviderPayload.base_url: str | None`。`factory.py` 构造 `LLMFactoryConfig` 时按顺序：
  1. env `NANO_MULTIAGENT_LLM_BASE_URL`（运行时覆盖）
  2. 当前模型所属 provider 的 `payload.base_url`（config 值）
  3. 都没有 → 抛 `ValueError("base_url unset for provider X")`（无 hardcoded fallback）
- **理由**: motivation Q4(a) 选"放 config，env 作 fallback"。但严格来说用户意图是"env 是 fallback"——本设计反过来让 env 优先：是因为 e2e fixture / worktree / CI 已经在用 env 切上游（`scripts/fixtures/`），保留 env 优先级让现有脚本不动。Config 是配置默认值，env 是临时 override（标准模式）。
- **拒绝**: config 优先 / env fallback——会让现有 fixture 失效，且 motivation 的 worktree fixture 改造负担加大。
- **风险**: 与 motivation Q4(a) 字面"env 没填时用 config 的值；env 还是能覆盖"完全一致，无偏离。

### 决策 5: 默认模型 = `llm.default_model`（YAML 必填）；默认 provider 推导

- **选择**: `LLMConfigPayload.default_model: str`（必填）。`get_default_provider()` 实现为：在 registry 里找 `default_model` 所属的 provider，找不到 → 抛错（解析时也校验过，但运行时再 guard 一次）。
- **理由**: motivation Q4(b) 选"显式写 default_model"。`default_provider` 是 `default_model` 的派生字段，不让用户单独填——避免两个字段不一致。
- **拒绝**: 额外加 `llm.default_provider` YAML 字段——冗余且容易写不一致（`default_provider: anthropic` + `default_model: codex_oauth:gpt-5.5` 这种不一致）。
- **风险**: 无。

### 决策 6: capabilities 死字段（`supports_text/image/tools/streaming`）顺手清除

- **选择**: `ModelMetadata` 删四字段。`global_routes.py:155-158` 的响应 dict 删四字段。`upstream_reporter.py` 不变（它本来就没读这些字段）。`im-agent-config-api.ts` 的 wire 类型同步删字段。
- **理由**: motivation Q3 确认是死代码，正好 schema 全部重做时一并清。
- **拒绝**: 保留——既然搬家而且确认无消费方，留着只是垃圾。
- **风险**: 任何外部消费方若曾依赖这四字段，会失效——核了下没有（除 frontend wire 类型，本 unit 同步改）。

### 决策 7: agent.default_model 验证：解析期硬失败

- **选择**: `load_local_config()` 在 parse 完 `llm` 后、调用 `_parse_agents()` 时把 `llm` 传进去；`_parse_agents` 遍历每个 agent 的 `default_model`，若非 None 则在 `llm.providers.*.models[*].name` 集合里查找，找不到抛 `ValueError("agents[i].default_model='X' not found in llm.providers")`。
- **理由**: motivation Q6 选 A。fail-fast 原则。错配出现在 config 解析期，比"启动后某 agent 第一次被使用时"早暴露。
- **拒绝**: 启动时只 warn（容错）；首次使用时报错（延迟暴露）。
- **风险**: 解析顺序耦合（必须 llm 在 agents 前解析）——在 `load_local_config` 里固定顺序即可，影响面小。

### 决策 8: 不留 backward compat fallback

- **选择**: 缺 `llm:` 段 → `_parse_llm()` 抛 `ValueError("config root must contain 'llm' section")`。不写代码 fallback。
- **理由**: motivation Q5 选 A。运维只有一个人（项目作者）。
- **拒绝**: 留一份 hardcoded 三模型默认作为 graceful fallback——违反 motivation 决定。
- **风险**: 升级期 Gateway 拒启动。**缓解**：本 unit 同步交付 `AGENTS.md` 模板（带 `llm:` 段）+ `~/.nano-assistant/config.yaml.example`（如果不存在则新建）+ commit message 明确写"升级需补 llm: 段"。

## 接口与数据流

### 新模块 `agent.core.llm.config`

```python
@dataclass(frozen=True, slots=True)
class LLMModelPayload:
    name: str
    extra_request_body: dict[str, Any] | None = None

@dataclass(frozen=True, slots=True)
class LLMProviderPayload:
    name: str  # "anthropic" / "openai_compat"
    base_url: str | None  # None 时由调用方走 env fallback
    models: tuple[LLMModelPayload, ...]

@dataclass(frozen=True, slots=True)
class LLMConfigPayload:
    default_model: str  # 必须出现在某个 provider.models 里
    providers: tuple[LLMProviderPayload, ...]

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, raw: str) -> "LLMConfigPayload": ...
```

### `model_registry.py` 修改后的 API

```python
def init_model_registry(payload: LLMConfigPayload) -> None: ...  # 幂等：重复 init 抛错
def _reset_for_tests() -> None: ...  # 测试辅助

# 既有 API（签名不变，内部从 _REGISTRY 读）
def list_supported_providers() -> tuple[str, ...]: ...
def list_provider_models(provider: str) -> tuple[ModelMetadata, ...]: ...
def get_default_model(provider: str) -> str: ...
def get_default_base_url(provider: str) -> str: ...
def resolve_model_metadata(provider: str, model: str | None) -> ModelMetadata: ...

# 新增（替换原 DEFAULT_PROVIDER 常量）
def get_default_provider() -> str: ...

# ModelMetadata 删 supports_text/image/tools/streaming 四字段
```

`DEFAULT_PROVIDER` 常量删除；`factory.py` 调用方改 `from .model_registry import get_default_provider` + `LLMFactoryConfig(provider=get_default_provider(), ...)`。`upstream_reporter.py` 同样改 `get_default_model(get_default_provider())`。

### `local_store.py` 新增

```python
@dataclass(frozen=True, slots=True)
class LocalConfig:
    ...
    llm: LLMConfigPayload  # 必填，无默认

def _parse_llm(payload: Any) -> LLMConfigPayload: ...  # raises ValueError on missing/malformed
def _parse_agents(payload: Any, llm: LLMConfigPayload) -> tuple[AgentWorkspaceConfig, ...]: ...
    # 多接 llm 参数，用于校验 default_model
def save_local_config(...): ...  # 序列化 llm 段
```

### Gateway → Kernel 数据流

```
main.py:
  config = load_local_config(...)
  init_model_registry(config.llm)            # Gateway 自己 init
  env = os.environ.copy()
  env["NANO_MULTIAGENT_LLM_CONFIG_JSON"] = config.llm.to_json()
  subprocess.Popen(shlex.split(kernel_command), env=env, ...)

kernel_app.py:
  import os
  from agent.core.llm.config import LLMConfigPayload
  from agent.core.llm.model_registry import init_model_registry

  _raw = os.environ.get("NANO_MULTIAGENT_LLM_CONFIG_JSON")
  if _raw is None:
      raise RuntimeError("NANO_MULTIAGENT_LLM_CONFIG_JSON must be set when launching kernel")
  init_model_registry(LLMConfigPayload.from_json(_raw))
  app = create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)
```

### `factory.py:LLMFactoryConfig.from_env()` 改造

```python
provider = os.getenv("NANO_MULTIAGENT_LLM_PROVIDER", get_default_provider())
model = os.getenv("NANO_MULTIAGENT_LLM_MODEL", get_default_model(provider))
metadata = resolve_model_metadata(provider, model)
base_url = os.getenv("NANO_MULTIAGENT_LLM_BASE_URL", metadata.default_base_url)
# metadata.default_base_url 来源已变：现在是 registry 里 provider.base_url（init 时从 payload 注入）
# 若 payload.base_url 是 None 且 env 也无 → 抛错
```

### 心跳上报数据流（保持不变）

`upstream_reporter._build_model_names()` 继续调 `list_supported_providers()` + `list_provider_models()`，得到的字符串列表内容现在跟着 config 走。心跳 payload 字段（`models` / `platform_default_model`）格式不变。IM 后端 / 前端零代码改动（除前端 wire 类型清死字段）。

### YAML schema 示例

```yaml
llm:
  default_model: kimiCoding:K2.6
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
          extra_request_body:
            thinking: { type: adaptive }
        - name: volcanoArk:doubao-seed-2-0-code-preview-260215
          extra_request_body:
            thinking: { type: adaptive }
    - name: openai_compat
      base_url: http://127.0.0.1:4000
      models:
        - name: codex_oauth:gpt-5.5
```

注：YAML 里 `providers` 是 list（每项含 `name`）而非 dict——避免 YAML 解析时 provider 名作为 dict key 出现非字符串 / 顺序丢失问题，与现有 `agents:` 风格一致。

## 风险与回退

### 风险 1: 测试套件依赖 import 时即可用的 registry

**症状**：本 unit 落地后，所有现有用 `resolve_model_metadata` / `list_provider_models` 的测试在 fixture 不到位时抛 `RuntimeError("not initialized")`。

**缓解**：在 `tests/conftest.py` 顶层 autouse fixture 里 init 一个**与原硬编码值完全等价**的 LLMConfigPayload。失败的测试可以显式覆盖该 fixture。

**回退**：若 fixture 改造工作量爆炸（> 30 处测试），把 `model_registry.py` 改成"未 init 时返回原硬编码默认 + warn log"，本 unit 保留 Gateway/Kernel 路径，测试 fallback 留待 follow-up——但这违反 motivation Q5 决议，需要重审。

### 风险 2: env 长度限制 / 特殊字符

**症状**：JSON 串包含 shell 元字符（虽然 dict 编码后不会），或 env 块逼近系统上限。

**缓解**：JSON 通过 `os.environ` 字典而非 shell 字符串传递（`subprocess.Popen` 接收 `env=dict`），绕过 shell 转义。规模上限以现有配置（< 1KB）远低于 Linux `ARG_MAX` 数 MB。

**回退**：极端情况下改用临时文件传 path：`NANO_MULTIAGENT_LLM_CONFIG_PATH` 指向 `/tmp/llm-config-<pid>.json`。本 unit 不预实现，遗留为已知降级路径。

### 风险 3: thinking signature roundtrip 链路意外回归

**症状**：`extra_request_body` 搬家过程中漏配/格式错位，主 agent loop 工具调用后卡住（bugfix-373/375 症状复发）。

**缓解**：
- `_parse_llm` 对 `extra_request_body` 透传 `dict[str, Any]`，不做语义校验（不解释 thinking 字段含义，保留原样）。
- 测试加一条"K2.6 加载后 `resolve_model_metadata` 返回的 `extra_request_body` 等于 `{"thinking": {"type": "adaptive"}}`"的固定保真断言。
- e2e fixture 在 worktree 起 Gateway 时拿主 config 副本（决策 3 路径），不重写 `llm:` 段。

**回退**：revert 本 unit PR。配置文件多出的 `llm:` 段在 revert 后被解析器忽略（旧 `local_store.py` 没这字段），运维无需手动清理。

### 风险 4: agent default_model 验证误伤

**症状**：某 agent 在历史上写了一个 typo 或已删除模型作为 `default_model`，新 parser 拒启动，运维卡在升级期。

**缓解**：错误消息明确指出"agents[i].default_model='X' not found in llm.providers.*.models（available: kimiCoding:K2.6, ...）"，运维一眼能改。

**回退**：临时把 agent 的 `default_model` 删掉（让它回落到 `llm.default_model`），先恢复服务再修。

## Runbook for Reviewer

本 unit 改动覆盖 Gateway + Kernel 两个常驻服务；IM 是被动消费方（前端展示模型下拉），重启 IM 也合理但只为隔离 stale 状态。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| Gateway + Kernel（worktree e2e 范式） | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh`（自动起 IM + Kernel + Gateway，并 auto-bind） | `source .e2e-ports.env && curl -s "$API_URL/v1/health"`；以及 `tail -f .gateway.log` 看到 capability 心跳成功 |
| IM 服务（worktree e2e 范式） | （同上一行 `e2e-down.sh` 一并清掉） | （同上一行 `e2e-up.sh` 一并起） | `source .e2e-ports.env && curl -s "$IM_URL/im/v1/health"` |

reviewer 跑用户旅程前**必须**按上面顺序无脑停-起。worktree e2e 内的 config 是从主 config 派生的副本（脚本会处理），主仓 `~/.nano-assistant/config.yaml` 不会被污染。

走旅程时使用 `http://127.0.0.1:$IM_PORT/`，登录 `nano` / `nano1234`，进 agent 设置页验证模型下拉。

## Milestones

单 M1。理由：本 unit 三块改动（YAML schema + parse、registry 工厂化、Gateway→Kernel env 注入）必须**作为一个原子提交**落地——单独落 schema 不通 Kernel，单独改 registry 不解析 YAML，单独加 env 注入两边都没用。每块独立都通不过 unit 测试。不满足 §4.2 任何拆分硬触发条件。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| refactor-382-M1 | impl | — | A | `src/agent/core/llm/config.py`（新）、`src/agent/core/llm/model_registry.py`、`src/agent/core/llm/factory.py`、`src/agent/platform/http_api/routes/global_routes.py:143-168`、`src/agent/platform/llm/providers/anthropic/client.py`（仅适配 metadata 字段）、`src/personal_assistant/config/local_store.py`、`src/personal_assistant/main.py`（spawn env 注入 + Gateway 自身 init）、`src/personal_assistant/kernel_app.py`、`src/personal_assistant/reporter/upstream_reporter.py:107-126`、`src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`（清死字段 wire 类型）、`AGENTS.md`（最小可用 config 示例加 `llm:` 段）、`scripts/e2e-up.sh`（worktree config 派生保留主仓 `llm:` 段，或显式带 `llm:` 段）、`tests/conftest.py`（autouse fixture 初始化 registry） | `[reviewer]` 覆盖 Scenario：`Requirement: 端用户在 IM 里看到的模型选择行为不变`（4 个 Scenario：下拉三条、平台默认 K2.6 标签、不填 default_model 走 K2.6、thinking + 工具调用多轮）；`Requirement: 运维通过编辑 YAML 增减模型`（2 个 Scenario：加 / 删）；`Requirement: Gateway 在 LLM 配置错误时立即报错`（2 个 Scenario：缺 llm 段、agent 引用不存在模型）。<br>`[worker]` `pytest -m "not e2e"` 全绿；`pytest tests/contract/` 全绿（依赖方向硬规则不破）；`pytest -xvs tests/unit/personal_assistant/config/` 含新 `_parse_llm` 单测全绿；`pytest -xvs tests/unit/agent/core/llm/` 含 `init_model_registry` + `_reset_for_tests` + 未 init 时硬失败 + `extra_request_body` 保真传递的单测全绿；`pytest -m e2e` 走 `scripts/e2e-up.sh` 范式至少跑通一次心跳 + 一次 chat send（K2.6 thinking adaptive 路径）；`ModelMetadata` 不再含 `supports_text/image/tools/streaming` 四字段（grep -r 验证）；`DEFAULT_PROVIDER` 常量被 `get_default_provider()` 函数完全替代（grep 验证零残留）。 |

```mermaid
graph LR
  M1[refactor-382-M1: impl]
```

