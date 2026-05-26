# refactor-382 — 验收报告 Round 1

> 对齐: motivation.md v1（8 个 Scenario，3 个 Requirement）
> 验收日期: 2026-05-26
> review_round: 1

## Verdict

**pass-with-issues**

所有核心 Scenario（回归基线的 Scenario 1-3、运维 YAML 增删的 Scenario 5-6、配置错误拒启动的 Scenario 7-8）均 pass 或 pass（带可接受的 inconclusive 说明）。Scenario 4（thinking + 工具调用多轮路径）因无真实 LLM 上游无法端到端验证，标 inconclusive，但保真前提条件（extra_request_body 传递）已在 registry/config 层和 JSON roundtrip 层完全验证。无 blocking issue；发现 1 个 minor issue（Runbook for Reviewer 未说明需要先确认主 config 有 llm 段）。

## 用户旅程体验

### 旅程 1 — 回归基线（Scenarios 1-3）

**环境准备**：
- 将主 config `~/.nano-assistant/config.yaml` 加入 llm 段（运维升级步骤）
- `./scripts/e2e-up.sh` 一键起 IM + Kernel + Gateway，节点 `wt-unit-refactor-382-21429` auto-bind 成功
- `curl $API_URL/v1/health` → `{"healthy":true}`

**旅程**：
- 打开 `http://127.0.0.1:60762`，用 nano/nano1234 登录
- 进入 Agents → default-agent 设置页
- 找到 "Default Model" 下拉，展开后看到 4 条选项：
  1. `Platform default (kimiCoding:K2.6)` (当前选中，value="")
  2. `kimiCoding:K2.6 (default)` (value="kimiCoding:K2.6")
  3. `volcanoArk:doubao-seed-2-0-code-preview-260215`
  4. `codex_oauth:gpt-5.5`

截图证据：`/tmp/model-dropdown-area.png`（"Default Model: Platform default (kimiCoding:K2.6)"）

capabilities API 验证：
```json
{"active_provider": "anthropic", "active_model": "kimiCoding:K2.6",
 "providers": [{"provider": "anthropic", "default_model": "kimiCoding:K2.6", "models": [...]},
               {"provider": "openai_compat", "default_model": "codex_oauth:gpt-5.5", "models": [...]}]}
```
无 `supports_text/image/tools/streaming` 死字段。

### 旅程 2 — 配置错误拒启动（Scenarios 7-8）

**Scenario 7**（缺 llm 段）：
```
ValueError: config root must contain 'llm' section with default_model and providers
```
错误消息明确，Gateway 拒启动。

**Scenario 8**（agent 引用不存在模型）：
```
ValueError: agents[0].default_model='foo:bar' not found in llm.providers
(available: codex_oauth:gpt-5.5, kimiCoding:K2.6, volcanoArk:doubao-seed-2-0-code-preview-260215)
```
错误消息明确指出 agent index、引用的模型名，以及可用模型列表。

### 旅程 3 — extra_request_body 保真验证（Scenario 4 前提条件）

通过 Python 直接测试 config parse → registry init 链路：
- `kimiCoding:K2.6`: `extra_request_body == {'thinking': {'type': 'adaptive'}}` ✓
- `doubao`: `extra_request_body == {'thinking': {'type': 'adaptive'}}` ✓
- `codex_oauth:gpt-5.5`: `extra_request_body == None` ✓
- JSON roundtrip 保真 ✓

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 | minor | design.md §Runbook for Reviewer 未提示 reviewer 需要先确认主 config 有 llm 段才能运行 e2e-up.sh。在本次验收中，主 config 缺 llm 段导致 e2e-up.sh 在提取 LLM 配置时失败（第 136-143 行 load_local_config 抛 ValueError），reviewer 需要额外时间判断并手动执行升级步骤。 | fix-implementation（Runbook 补一行"确认主 config 已含 llm 段，否则按 AGENTS.md 示例先补"） |

## 验收标准覆盖

### Requirement: 端用户在 IM 里看到的模型选择行为不变（回归基线） — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 模型下拉选项保持原有三条 | motivation.md Scenario 1 | 旅程 1：playwright 获取 `select` 元素 options | `select options: [{value:"", text:"Platform default (kimiCoding:K2.6)"}, {value:"kimiCoding:K2.6", text:"kimiCoding:K2.6 (default)"}, {value:"volcanoArk:doubao-seed-2-0-code-preview-260215", ...}, {value:"codex_oauth:gpt-5.5", ...}]`，截图 `/tmp/model-dropdown-area.png` | pass | 3条用户可选模型 + 1条平台默认，完全一致 |
| "平台默认"标签仍指向 K2.6 | motivation.md Scenario 2 | 旅程 1：下拉第一条选项文本 | `Platform default (kimiCoding:K2.6)`，截图 `/tmp/model-dropdown-area.png` | pass | 文字标签明确标注 K2.6 |
| agent 不填 default_model 时仍用 K2.6 | motivation.md Scenario 3 | 旅程 1：default-agent 的 default_model 字段 + capabilities API active_model | IM API: `"default_model": null`；Kernel capabilities: `"active_model": "kimiCoding:K2.6"` | pass | null = 使用平台默认，正确走 K2.6 |
| agent 的多轮 thinking + 工具调用对话路径保留 | motivation.md Scenario 4 | 旅程 3：config → registry → extra_request_body 保真验证 | K2.6 `extra_request_body={'thinking':{'type':'adaptive'}}` 通过 registry、JSON roundtrip 验证保真；无真实 LLM 上游，端到端 LLM 调用路径未跑 | inconclusive | 保真前提条件完全满足；"端到端 thinking roundtrip" 需真实 LLM 上游，本轮不具备。不影响本 unit 的 refactor 目标（搬家保真），此 Scenario 本质上是 integration smoke test。 |

### Requirement: 运维通过编辑 YAML 增减模型，不动代码 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 加新模型走 YAML | motivation.md Scenario 5 | config parse + registry 层验证（load_local_config + init_model_registry + list_provider_models） | 在 providers 末尾加 `new-model:v1.0`，parse 后 registry 列出该模型：`['kimiCoding:K2.6', 'new-model:v1.0', 'volcanoArk:...']` | pass | 未验证完整"重启 Gateway → IM 前端下拉出现"路径（需真实 LLM 上游才能走 Kernel 路径），但 config 驱动的 registry 机制已由旅程 1 的 e2e 服务验证 |
| 删模型走 YAML | motivation.md Scenario 6 | config parse + registry 层验证 | 从 providers 删 doubao，parse 后 registry 只有 `['kimiCoding:K2.6']`（anthropic provider 下）；doubao 不再出现 | pass | 同上注，完整重启路径限于 LLM 上游 |

### Requirement: Gateway 在 LLM 配置错误时立即报错而不是静默起来 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| config 没有 llm 段 | motivation.md Scenario 7 | 旅程 2：传不含 llm 段的 config 调 load_local_config | `ValueError: config root must contain 'llm' section with default_model and providers` | pass | 报错明确，指向 llm 段缺失 |
| agent 引用了 llm.providers 里不存在的模型 | motivation.md Scenario 8 | 旅程 2：传 agent.default_model='foo:bar' 调 load_local_config | `ValueError: agents[0].default_model='foo:bar' not found in llm.providers (available: codex_oauth:gpt-5.5, kimiCoding:K2.6, volcanoArk:doubao-seed-2-0-code-preview-260215)` | pass | 报错明确，含 agent index、引用模型名、可用模型列表 |

## Issues

### Issue 1

- **Severity**: minor
- **Recommended Action**: fix-implementation
- **Action Rationale**: design.md §Runbook for Reviewer 没有提示 reviewer 需要先确认主 config 有 llm 段。这是本 unit 交付物（AGENTS.md 模板、migration 说明）已有覆盖但 Runbook 本身漏掉的一个小疏漏，实现层可以一行补齐。
- **Reproduction**: reviewer 在主 config 无 llm 段时运行 e2e-up.sh，脚本第 136-143 行因 `load_local_config` 抛 ValueError 而退出。

## Side Findings

- aiohttp 模块未安装导致 `tests/unit/personal_assistant/test_internal_dispatch_endpoint.py::test_dispatch_handler_build_aiohttp_handler_returns_callable` 测试失败，1 个 FAILED。这是预存在的依赖缺失问题（aiohttp 不在 requirements 里），与本 unit 无关。建议 out-of-unit 补依赖，此处仅记录。
- capabilities API 响应已清除 `supports_text/image/tools/streaming` 四个死字段，变更前后对比：后者更干净，无副作用。
- `DEFAULT_PROVIDER` 常量已完全删除（grep -r 零残留），全部改用 `get_default_provider()`，符合 design.md 决策 2。

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新（本 unit 不改顶层架构，只是配置从代码移到 YAML）
- [x] `docs/内核设计SPEC.md`（agent 内核）：无需更新（model_registry 对外接口签名不变，内部改为 config 驱动是实现细节）
- [x] `AGENTS.md` / `CLAUDE.md`：已更新（worker 已在 AGENTS.md 里加了含 llm 段的最小可用配置示例 + 升级注意事项）
- [x] 相关产品 SPEC（CodingCLI / NodeGateway / IM 等）：无需更新（CodingCLI 不走 Gateway config，NodeGateway-SPEC.md 的"配置字段"章节视需要可补 llm 段说明，但属于后续文档维护，不 block 本 unit）

## 澄清说明

本次验收中主 config `~/.nano-assistant/config.yaml` 缺少 llm 段，reviewer 按 AGENTS.md 示例和 motivation.md §迁移策略补全了 llm 段（运维升级步骤），这是本 unit 设计的预期升级路径，不是 bug。e2e-up.sh 的 --main-config 参数允许传替代 config，但 design.md §Runbook for Reviewer 未提示此前置条件，已记为 minor issue #1。
