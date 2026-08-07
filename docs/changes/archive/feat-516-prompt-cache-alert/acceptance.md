# feat-516 — 验收报告

> 对齐: `spec.md` 的验收标准

> Validation snapshot: `b95e19f15 → uncommitted unit worktree (2026-08-07)`

## Verdict

**pass**

- Highest Required Action: `pass`
- 验收轮次: 1
- Issues: 无（blocking 0 / major 0 / minor 0）

## 用户旅程体验

### 旅程 1：高成本缓存未命中可直接排查

在隔离的真 IM + Gateway 栈中，以 Web IM 实际使用的消息接口登录、创建直聊并发送
`CACHE-ALERT-PROMPT-MUST-NOT-LEAK`。确定性 Anthropic SSE fixture 在真实的
`message_start` 帧提供 `input_tokens=30001` 与明确的缓存读取 `0`，并在
`message_delta` 帧提供输出 usage。

用户侧正常收到 `ACK-1`。Gateway 写出的唯一告警为：

```text
low prompt cache hit rate | agent_id='e2e', cache_hit_rate_percent=0.0, cache_read_tokens=0, input_tokens=30001, model='deepseek:deepseek-v4-flash', session_id='sess_8abd8b1ea10e1b96', ...
```

该行不含发送的 prompt。用日志中的 `agent_id=e2e` 和 session id 实际找到了
`.gateway-workspace/e2e/.nanoassistant/sessions/sess_8abd8b1ea10e1b96.jsonl`；该 JSONL
包含用户消息和 `ACK-1`，说明运维者可从告警继续定位会话。

证据：在 `/tmp/feat516-acceptance.W9yyUv/test_gateway_logs_low_prompt_c0/stack/` 保存的
隔离运行产物；命令
`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q --basetemp <temp> tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py`
通过（1 passed，8.91s）。该测试自行启动并清理 fixture、IM 与 Gateway。

### 旅程 2：正常边界与未知缓存数据保持安静

使用 Gateway 相同的 per-call hook 日志接口覆盖四种不应写告警的调用：输入恰为
30,000、命中率不低于 80%、provider 未给缓存读取字段、以及无 Gateway `agent_id` 的运行。
四项均未产生 `low prompt cache hit rate` 记录。

证据：
`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/test_agent_loop.py -k cache_alert`
通过（4 passed）。完整的 provider 归一与真栈组合回归也通过：73 passed。

### 旅程 3：既有启动方式无需新增告警配置

旅程 1 以既有 Gateway 配置启动完整隔离栈；没有 cache-alert 专用配置项，固定规则即已生效。
这一条关键路径已登记到 `docs/development/e2e-critical-paths.md` 第 15 项，后续可在不连接真实 LLM proxy 的情况下复跑。

## Reference Artifacts Reviewed

N/A。此 unit 没有原型、设计稿或视觉对齐契约；用户可观察产物是 Gateway 日志。

## 问题清单

无。

## 验收标准覆盖

### Requirement: 高成本低缓存命中模型调用产生可排查告警 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 单次模型调用输入大且缓存命中率低 | `spec.md` | 旅程 1：真实 IM + Gateway + Web relay 消息入口 | 真实 `.gateway.log` 一条 warning，含 model、agent_id、session_id、input/cache tokens、0.0%；JSONL 可定位，且告警行无 prompt | pass | fixture 使用真实 Anthropic start/delta usage 分帧；用户仍收到回复。 |
| 新对话或缓存命中正常时不误报 | `spec.md` | 旅程 2：per-call 边界行为回归 | `test_agent_loop.py -k cache_alert` 4 passed：30K 边界与 80% 边界均静默 | pass | 覆盖低于/等于阈值的严格比较。 |
| provider 未报告缓存命中数据 | `spec.md` | 旅程 2：per-call 数据缺失回归 | `test_agent_loop.py -k cache_alert` 4 passed；provider streaming/mapper 回归随 73-test 集合通过 | pass | 未把缺失数据当作 0 命中而误报。 |

### Requirement: 告警规则无需额外配置即可一致生效 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
| 运维者按既有方式启动 Gateway | `spec.md` | 旅程 3：隔离真 Gateway 使用既有配置启动 | 新 critical path 通过（1 passed），未提供 cache-alert 配置仍按 30K/80% 规则写出 warning | pass | 测试配置只用于隔离 IM/fixture，不增加产品 cache-alert 设置。 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；没有改变跨包职责或依赖方向。
- [x] `docs/specs/gateway/`（长青行为契约层）：已反映本 unit 行为增量；`service-lifecycle.md` 新增 warning Requirement，`spec.md` 索引为 6 项。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；项目工作约定不变。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；没有改变文档体系规则。

## 最终树状态

验收针对 `unit/feat-516` 上尚未提交的实现工作树；除本报告外，工作树保留待 orchestrator 统一提交的 M1 实现、测试和规范归并改动。验收期间没有修改源码、测试、配置或产品规范。

---

# Round 2 — 2026-08-07

> Revalidation mode: targeted
>
> Focus: code-review 修正后，warning 是否在模型流结束时立即可见，而不受慢工具结果等待影响；并确认原有真 Gateway 用户旅程没有回归。

## Verdict

**pass**

- Highest Required Action: `pass`
- Issues: 无（blocking 0 / major 0 / minor 0）

## 定向复验旅程

在具有慢工具调用的模型回复中，模型流一结束就检查同一 Gateway agent 的日志记录，随后才放行工具结果。告警已经出现，说明运维者不会因为工具执行慢而错过或延迟看到本次高成本低命中模型调用。

同时重新跑隔离真 IM + Gateway + Anthropic SSE fixture 的主旅程：Web IM 用户正常收到回复；日志写出一条低命中 warning，包含 model、`agent_id=e2e`、session id、输入/缓存 tokens 与命中率，且不包含 prompt。

证据：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/unit/test_agent_loop.py -k cache_alert \
  --basetemp <temp> \
  tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py

5 passed, 23 deselected
```

此次真栈日志产物：

```text
low prompt cache hit rate | agent_id='e2e', cache_hit_rate_percent=0.0, cache_read_tokens=0, input_tokens=30001, model='deepseek:deepseek-v4-flash', session_id='sess_950f22d995654ad0', ...
```

运行产物位于
`/tmp/feat516-acceptance-r2.Nz4k13/test_gateway_logs_low_prompt_c0/stack/.gateway.log`；fixture 测试已负责停止本轮启动的隔离服务。

## 覆盖表更新

| 已复验 Scenario / 关注点 | 证据 | 结果 | 备注 |
|---|---|---|---|
| 单次模型调用输入大且缓存命中率低 | 真 IM + Gateway critical path 通过；真实 `.gateway.log` | pass | 原 Round 1 的字段、无 prompt、JSONL 定位结论保持有效。 |
| warning 不被工具结果等待推迟 | `test_loop_warns_before_waiting_for_a_tool_result`（纳入上述 5 passed） | pass | 定向新增的用户可观察日志时序保障。 |
| 30K/80% 边界、缓存数据缺失及无 Gateway agent 时静默 | 其余 cache-alert loop tests（纳入上述 5 passed） | pass | 原 Round 1 的静默结论保持有效。 |

## 上层文档同步复核

- [x] `SPEC.md`：无需更新。
- [x] `docs/specs/gateway/`：Round 1 已归并的 warning 契约仍适用，无新增产品语义。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 最终树状态

定向复验针对同一未提交 M1 实现树；本轮只追加了验收报告，未改实现、测试、配置或规范。
