# LLM Integration

本文记录 nano-multiagent 开发和真实链路验收使用的本地 LLM 代理入口、当前配置、协议、交互日志和验证方法。Gateway 的 `llm:` 配置结构见 [`../operations/gateway.md`](../operations/gateway.md)。

## 调研与诊断入口

- LLM_PROXY 代码：`/Users/czj/Repos/LLM_PROXY`
- 协议与启动说明：`/Users/czj/Repos/LLM_PROXY/README.md`
- 按 session 聚合的交互日志：`/Users/czj/Repos/LLM_PROXY/logs/session/*_<session_id>/`
- 按协议保存的原始捕获：`/Users/czj/Repos/LLM_PROXY/logs/raw/<protocol>/`

Nano 的 DSH integration 在公开 `llm/stream` 与 HTTP dispatcher 扩展点透传请求标识：`X-Session-Id` 使用产品绑定的主 session ID，让主 Agent 和它的 fork/background 子 Agent 归入同一 Inspector timeline；`X-Agent-Session-Id` 保留实际发起请求的原生 session ID，供原始请求 header 区分来源。原生 session 的存储、恢复与上下文身份不变。并发主会话各自归档，普通工具或附件 HTTP 不附带这些标识。

先从全局 Agent 工作视图或自动化 fixture/结果取得主 session ID；其他产品路径没有直接暴露 ID 时，用发生时间、模型和消息中的唯一标记缩小日志目录，再从目录后缀确认 ID。缺少标识的历史原始请求不会因加载修复而自动回填。

已知 session id 时直接定位：

```bash
nano_session_id="sess_..."
find /Users/czj/Repos/LLM_PROXY/logs/session \
  -mindepth 1 -maxdepth 1 -type d -name "*_${nano_session_id}"
```

只知道发生时间时，先查看最近写入的 session，再打开候选请求核对模型和脱敏后的消息标记：

```bash
ls -td /Users/czj/Repos/LLM_PROXY/logs/session/* | head
```

session 目录中的 `*-req-*` 是代理收到的请求，`*-downstream-res-*` 是返回调用方的响应，`*-non-stream-res-*` 是聚合后的非流式结果。需要排查协议转换或 session 未被识别时，再按时间和协议查看 `logs/raw/`；Session Inspector 也从 `logs/session/` 构建 timeline。

Session 请求证明代理入口收到什么；若发生协议转换，需再核对 raw 中同时间戳的 upstream-req，才能判断提交给 provider 的实际结构。请求日志本身不证明模型已成功响应、正确消费或产品已持久化/送达，仍需结合响应、后续调用和 Gateway/IM runtime evidence。原始内容可能含 prompt、工具参数和第三方数据，不提交进本仓；unit 中只记录 session id、时间范围、要证明的 claim 和必要的脱敏摘要。日志会按 LLM_PROXY 的 retention 配置清理，长期回归应进入测试。

## 观察实际 Agent Context

设计判断见 [Agent Context Engineering](agent-context-engineering.md)；这里仅维护取证操作。先记受审 commit、Agent/主与子 session、模型/provider、配置代次、任务唯一标记和时间段。优先创建合成任务，使用 [隔离运行环境](worktree-runtime.md)，不要为审查扫描所有生产会话。

### 从装配到 provider 请求

1. 沿 `apps/node/src/configuration.ts::runtime`、integration 的 `agent-config.ts` / `capabilities.ts` 定位配置与过滤；`session.capabilities` 和 `configuration.preview` 可查看 Prompt 组装、工具/Skill 目录，但它们是预览。DSH `llm/stream` 是适配前内容，也不能证明 wire 序列化保真。
2. 运行已限定的任务，从 Work 视图或 fixture 获取主 session ID，按本页入口找到该 session 的 `*-req-*` 与对应响应。**只检查需要的轮次**：首次请求、工具执行后的下一请求、配置变化后的下一新回复，以及受影响的恢复点。工具结果通常在后续模型请求中；最后一个工具事件没有后续请求时，不能声称它已被模型消费。
3. 当前代理在 `logs/raw/<bucket>/` 保存同一时间戳的 `*-upstream-req-*`。Session req 是代理入口；转换后的 upstream-req 才是发往 provider 的 payload。用文件时间戳和返回链路关联，检查实际协议而不是假定两份 JSON 相同。缺失记录可能源于日志保留或写入失败，标明缺口，不能由 preview 补证。
4. Anthropic 入口重点看 `system/messages/tools`；OpenAI Chat 看 `messages/tools`；Responses 上游看 `instructions/input/tools`（本机 Codex 桥接也会将 system 内容放在 `input` 的 system 消息中，不能只查 `instructions`）。检查完整的相关字段及顺序：最终身份/规则、实际可调用 schema、Skill 目录与加载正文、消息/提醒/结果和来源表示。PTC/代码执行呈现时，工具说明和结果可能在 wrapper 或系统文本里，不能只数 `tools` 名称。native source 元数据也可能投影为文本，需追踪其最终表示。
5. 对照响应中的实际工具调用、后续请求与产品事实：参数是否来自正常可获得的信息、模型如何解释结果、是否采取正确下一步、是否真的交付。请求存在仅证明交付内容；需要响应/实际行为才能判断消费。UI presenter 与内部返回值只作辅助。

可先对**已定位的单份请求**做不输出正文的结构检查（仓库根运行；参数换成该任务的真实文件）：

```bash
python3 - /absolute/path/to/one-req-anthropic.json <<'PYCTX'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
messages = payload.get("messages", payload.get("input", []))
tools = payload.get("tools", [])
print({"keys": sorted(payload),
       "instruction_chars": len(json.dumps(payload.get("system", payload.get("instructions", "")))),
       "message_count": len(messages) if isinstance(messages, list) else None,
       "tool_count": len(tools),
       "roles_or_types": [item.get("role", item.get("type")) for item in messages if isinstance(item, dict)]
                         if isinstance(messages, list) else []})
PYCTX
```

这只确认结构，语义仍需在本机读取相关片段并核对预期。不要把原请求、headers、认证配置或整段对话粘进报告。按 [Evidence](evidence.md) 保存小型脱敏结论、命令、session/请求时间戳、字段位置及限制；单独的哈希或“有该字段”不能替代语义证据。

### 可复用 seam 与代表性任务

以下是按 Surface 找现场的入口；执行前核实锁定版本与测试名，不把测试源码当执行结果。测试 import 构建产物时先确保 `pnpm build` 对应受审版本。

| 需要观察什么 | 入口 | 证据边界 |
|---|---|---|
| 真实 adapter 序列化的 system/tools/messages、主/子请求归属 | `packages/dsh-integration/tests/llm-attribution.test.ts` 的本地 HTTP provider | 真 DSH + HTTP 捕获，响应为 stub，不能证明真实模型选择 |
| 任务结果未知、重试与动态反馈 | `packages/dsh-integration/tests/task-feedback.test.ts`；`features/task-graphs.ts` 的 output.render/deferContext | 模拟结果与 llm/stream 捕获；产品事实和真实 wire 需另对照 |
| Inbox wake/read/持久摄取、发送结果 | `packages/personal-assistant/tests/{global-agent,inbox,tool-references}.test.ts`；`global-agent.ts` / `inbox.ts` / integration `global-mode.ts` | 宿主行为和投影；不等于模型已消费 |
| 配置、Feature 与 Skill 变化 | `packages/dsh-integration/tests/{capabilities,native-human-source,communication-native}.test.ts` | 区分预览断言、模拟输入与最终请求；真实选择需代表性任务 |
| Memory、原生换窗及 Skill 恢复 | `packages/dsh-integration/tests/{knowledge,agent-context-default}.test.ts`；`features/memory-curation.ts` / `compaction.ts` | 选当前实际 engine 的路径；工具可用不证明等待事项已恢复 |

普通窄回归可直接运行，例如：

```bash
pnpm exec vitest run packages/dsh-integration/tests/llm-attribution.test.ts packages/dsh-integration/tests/task-feedback.test.ts
pnpm exec vitest run packages/personal-assistant/tests/inbox.test.ts packages/personal-assistant/tests/global-agent.test.ts
```

真实模型任务复用 `scripts/e2e-up.sh --profile daily --wt <绝对目录>` 的独立身份，从 Web/其真实 API 发合成请求，读 Work 和本机请求；结束执行配对的 e2e-down。例如让 Global Agent 读 Inbox 后向来源聊天交付一个可核对结果；再在同一 Agent 空闲后切换 Skill/Feature，通过正常任务观察下一请求。不要为了制造“通过”给出内部参数、正确解释或伪造模型响应。

同一证据只声称实际覆盖的状态。未走到的 unknown/拒绝/恢复分支可先用既有确定性 fixture 检查机制，报告中保留真实模型未验证的范围。已有观察能力足够时不另建 Snapshot 平台；具体盲区先记录缺失层级和受影响判断，再考虑最小只读诊断。

## 本地代理接口
- Base URL: `http://127.0.0.1:4000`
- 健康检查：`GET /health`
- OpenAI Chat Completions：`POST /v1/chat/completions`
- Anthropic Messages：`POST /v1/messages`

## 当前配置与模型

### 隔离环境的模型目录

`scripts/e2e-up.sh` 默认从 [`config/e2e/gateway.yaml`](../../config/e2e/gateway.yaml) 复制模型目录，不从正式 Gateway 或代理动态发现模型。只修改个人 Gateway 配置或临时 `.gateway-config.yaml` 不会更新下一个 worktree 的默认目录。

升级正式环境的推荐模型时，同一次变更必须同步该模板的型号、context window 和 reasoning 声明，并通过当前代理验证真实流式回复。保留 DeepSeek 等各档模型的用途；不要把已被替换的推荐型号继续留作新 E2E 的默认候选。2026-10-13 核对的 GPT 候选为 GPT-6.1 Sol、GPT-6 Astra、GPT-6 Luna，型号参考 [OpenAI 模型文档](https://learn.chatgpt.com/docs/models#recommended-models)。历史验收记录及刻意验证旧型号兼容性的测试不随目录升级改写。

已启动环境持有自己的配置副本，需要更新其中的模型目录并重启对应隔离 Gateway，再检查 `/im/v1/agents/<agent_id>/capabilities` 的 `models`。不要为刷新目录重新运行 `e2e-up.sh`，它会重建测试数据库；不得复制正式环境的身份、凭据、channel 或运行数据。

### 本机代理配置

- LLM_PROXY 默认配置文件：`/Users/czj/Repos/LLM_PROXY/upstreams.json`
- 配置结构说明：`/Users/czj/Repos/LLM_PROXY/README-zh.md` 的“上游配置”
- 实际进程设置了 `UPSTREAM_CONFIG_PATH` 时，以该路径为准。

`defaultProfile` 指定默认 profile，`profiles.<name>.defaults.model` 记录该 profile 的默认模型，`profiles.<name>.capabilities.ingress` 记录它支持的入口协议。请求中的模型 ID 使用 `profile:model`；`codex_oauth` profile 还支持可选的 `@effort` 后缀。

用下面的命令只查看非敏感的模型路由字段：

```bash
llm_proxy_config="${UPSTREAM_CONFIG_PATH:-/Users/czj/Repos/LLM_PROXY/upstreams.json}"
jq -r '
  .defaultProfile as $default
  | .profiles
  | to_entries[]
  | [
      .key,
      (.value.provider // ""),
      (.value.defaults.model // ""),
      ((.value.capabilities.ingress // []) | join(",")),
      (if .key == $default then "default" else "" end)
    ]
  | @tsv
' "$llm_proxy_config"
```

输出依次是 profile、provider、默认模型、支持的入口协议和是否为默认 profile。配置文件可能包含鉴权信息，不要把完整文件复制进本仓、change evidence 或聊天记录。

## 快速验证

### 1) 健康检查

```bash
curl -sS -i http://127.0.0.1:4000/health
```

先从当前配置中选择支持目标入口协议的 profile 和模型，再设置：

```bash
nano_smoke_model="<profile>:<model>"
```

### 2) OpenAI Chat Completions

```bash
nano_smoke_session_id="nano-smoke-openai-$(date +%Y%m%d-%H%M%S)"
curl -sS -i http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: ${nano_smoke_session_id}" \
  -d "$(jq -nc --arg model "$nano_smoke_model" \
    '{model:$model,messages:[{role:"user",content:"reply with one word: pong"}],stream:false}')"
```

### 3) Anthropic Messages

```bash
nano_smoke_session_id="nano-smoke-anthropic-$(date +%Y%m%d-%H%M%S)"
curl -sS -i http://127.0.0.1:4000/v1/messages \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: ${nano_smoke_session_id}" \
  -d "$(jq -nc --arg model "$nano_smoke_model" \
    '{model:$model,max_tokens:64,messages:[{role:"user",content:"reply with one word: pong"}]}')"
```
