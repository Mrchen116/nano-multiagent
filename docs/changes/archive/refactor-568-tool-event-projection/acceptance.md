# refactor-568 — 验收报告

> Round 1 / full；2026-09-19。
> 对齐 motivation.md 三项用户侧不变性。
> Validation snapshot: `4394ad424 → 151928fed7d894114b89c851cce8b621872e64d7`。

## Verdict

**fail**。1 个 major 阻塞项：真实运行中的工具在 `/stop` 成功应答后仍以 running 保留在历史中。Highest Required Action: **fix-implementation**。不根据 seam 回归通过降低真实产品验收标准。

## 用户旅程体验

环境由 caller 管理：`/tmp/nano-refactor568-acceptance`，IM `http://127.0.0.1:58043`，Gateway PID `26383`。已核实进程 cwd 为该临时目录，进程 `PYTHONPATH` 指向本 unit worktree 的 `src`；验收时 HEAD 为 validated_at，源码无 dirty。专用登录 `nano`，实际 owner `u_aa0px7a7`、Agent `e2e`。使用既有 IMClient 调用真实 HTTP/WS，与 Web 客户端读取相同历史；未作视觉原型验收。LLM 真实调用工具；没有外发真实飞书。caller 负责栈清理。

既有创建直聊 API 返回同一会话 `c_kpmkqxsw`，所以三条旅程以不同消息/tool ID 区分，未假设会话隔离。

1. **正常 read**：把未知随机 token 写入临时文件，要求 Agent 用 read 读取。真实回复命中 token；REST 历史气泡 `bf555b5532ef4546b64da74c22347d1d` 的工具 `call_00_bpkDpnJ23PgkLTGHxMcS0271` 为 `read/completed`，原 input.path、文件行数摘要、detail 的 path/total_lines/offset/limit/truncated 均存在，duration_ms=45，emoji/approval/reason 为 null。判断不只依赖最终 token。
2. **失败 read**：请求读取随机不存在路径且不重试。气泡 `a792b89b2b77476aa242f8eb9244e80b` 的工具 `call_00_ET_KqYcnBKtkoqr9qZSnrl17979` 为 `read/failed`，input.path 与 output 路径保留，detail.error.message 为 `file does not exist`，duration_ms=50；最终正文明确失败。用户可以回看具体失败工具。
3. **真实 stop**：先完成独立 `echo REF568_READY`，再执行 `sleep 45`。通过 REST 工具字段确认 sleep 的 status=running 后，于 `2026-09-19T05:40:00.499556Z` 发送 `/stop`；收到气泡 `9dfc100009954dbcac518e423aa79127` 的固定应答「已停止当前操作。」。2 秒后的历史和稍后重新 GET 的历史均仍显示下列状态：

```json
{
  "message_id": "6c40b6db9595465582757711faf7bb41",
  "delivery_status": "running",
  "tools": [
    {"id":"call_00_nNDfVEAkFD8LBrfFD4Wz1357","name":"bash","status":"completed","input":{"command":"echo REF568_READY","description":"输出 REF568_READY"}},
    {"id":"call_00_W27HBQnrNSWYDKWw0lQr1782","name":"bash","status":"running","input":{"command":"sleep 45","description":"等待45秒验收中断","timeout":60000},"output":"等待45秒验收中断","detail":{"command":"sleep 45"},"reason":null}
  ]
}
```

初次探针曾误把用户提示词中的 sleep 和气泡 running 当作工具开始，已废弃该尝试的 stop 判定；以上失败证据来自修正后逐工具检查并确认真实在飞调用的独立第二次请求。

4. **离线 shadow 与恢复**：按 design runbook 的允许边界使用真实 `ExternalShadowSagaStore` SQLite、observer 与 `IMShadowConversationSync`，IM 发送采用既有 `httpx.MockTransport` seam，外部事件合成，不宣称真飞书网络覆盖。无 IM manager 时记录一条 completed read 和一条在飞 bash，异常终止后后者为 failed/interrupted，保留 command/description/detail/emoji，completed read 不被改写。恢复时观察 HTTP PUT 的 tool_calls 与离线 SQLite 快照逐字段相等，持久状态变为 reconciled。相同探针在 `git archive 4394ad424` 的旧源码执行，旧/新 tool_calls、恢复请求内容一致（仅排除实际运行耗时 elapsed_ms）。

关键离线记录：completed read 保留 `approval=" auto_allow "`、emoji `📖`、detail `{path:"a.py",content:"hello"}`；interrupted bash 保留 emoji `💻`、input/detail `{command:"sleep 45",description:"Waiting"}`。影子记录继续省略未提供的 duration/approval；真实 IM 返回 nullable 字段，未强行统一两种 schema。

独立辅助回归：`test_tool_delivery_projections.py`、`test_reconcile_preserves_tool_input.py`、`test_gateway_shadow_sync.py`、`test_tool_end_detail_passthrough.py` 共 **54 passed**。包含明确的权限 verdict/whitespace、emoji、缺省字段与 live-only pending_revalidation 差异断言；不把这些测试当成真实 stop 成功证据。未进行真实人工权限拒绝旅程。

本机原始证据（不提交临时运行数据）：`/tmp/nano-refactor568-acceptance/product-evidence/{read,failure,stop-before,stop-after,stop-later,shadow-recovery}.json`，旧基线 `product-evidence-base/shadow-recovery.json`；临时脚本 `/tmp/ref568-product-probe.py`、`/tmp/ref568-stop-probe.py`、`/tmp/ref568-shadow-probe.py`。报告已摘录判定所需字段。

## Reference Artifacts Reviewed

N/A。motivation/design 未引用前端原型或 must-match 视觉合同；本次是工具事件历史不变性，验收读取 Web 消费的真实历史数据，未宣称浏览器像素/交互覆盖。

## 问题清单

| # | Severity | Regression Relation | 期望与实际 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| A1 | major / blocking | unclear | 已在飞 sleep 应在 stop 后收口；实际应答成功但工具与原气泡仍 running。上文有完整消息/tool identity 和字段证据。 | fix-implementation | 直接违反 motivation「运行中工具被终结」；owner 定位原因并决定归因，reviewer 不读实现定位根因，不以可能既存排除阻塞。 |

## 验收标准覆盖

### Requirement: 工具过程和结果可回看 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 正常与失败工具 | motivation.md；docs/specs/im/tool-timeline.md | 真实 IM + Gateway + LLM 正常与失败 read；历史完整字段核对；旧/新 seam 比对与既有字段契约回归 | 旅程 1、2、4；read/failure.json；54 项回归 | pass | 真实 read 的 emoji/approval 均 null；非空值和 verdict 通过 seam 核对，未宣称真实人工授权卡覆盖 |

### Requirement: 中断可收口 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 运行中工具被终结 | motivation.md；docs/specs/im/tool-timeline.md | 真实先完成 echo、等待 sleep 工具 running，再发送 /stop 并重读历史 | 旅程 3；stop-before/after/later.json；A1 | fail | 已完成 echo 未改写，sleep 原参数仍存在，但 running 未收口 |

### Requirement: 外部历史不依赖 IM 在线 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| IM 离线与恢复 | motivation.md；design.md Runbook for Reviewer | 真实 SQLite store + IM HTTP transport seam；旧/新源码执行相同离线终止恢复探针 | 旅程 4；shadow-recovery.json 与基线逐字段一致；恢复 reconciled | pass | 明确不是实飞书网络；seam 范围符合 design runbook |

## 上层文档同步

- [x] `SPEC.md`：无需更新，跨包边界不变。
- [x] `docs/specs/gateway/routing-delivery.md` 与 `docs/specs/im/tool-timeline.md`：无需更新目标契约；A1 为未满足现有合同，不能通过改合同消除。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

需 owner 处理 A1 并复验。此轮未创建外部 issue；服务由 caller 保持与清理。

---

## Round 2 — targeted A1 复验

> Validation snapshot: `151928fed7d894114b89c851cce8b621872e64d7 → 34ff1a2cedfac2224ec88661bc19b54d4dded4c0`。
> 2026-09-19；保留 Round 1 全部记录，不覆盖失败历史。

### Verdict

**pass**。A1 已关闭，未发现新阻塞项。Highest Required Action: **pass**；open issues: 0；needs_re_review: false。

### 实际环境与范围

caller 重启的同一专用临时栈：IM `http://127.0.0.1:59005`，Gateway PID `28264`，owner `u_8n1sm0d0`、Agent `e2e`。已独立核实 HEAD 为本轮 validated_at、开验时源码 clean，运行 Gateway 的 `PYTHONPATH` 指向该 worktree `src`。复用既有 IMClient，真实 HTTP/WS + Gateway + LLM + bash。仅写隔离测试资源，没有真实飞书外发；caller 负责清理。

targeted 范围为 A1 中断收口以及新增清理准入带来的晚到正文/reset 风险。正常/失败 read 与 shadow 字段投影复用 Round 1 有效证据；没有将旧版本运行证据伪称本轮重跑。

### 用户旅程与 A1 关闭证据

会话 `c_j8fvget5`，气泡 `4bdd5f71d083425aaaa68c4eda44a8c0`。让 Agent 先独立完成 `echo REF568_R2_READY`，再调用 `sleep 30`，要求全部完成后才回复随机 `LATE_...` token。实际历史中确认具体 sleep 工具 `call_00_ET_2r4IgkO8rVCWEBJwJuko5066` 为 running，随后发送 `/stop` 并收到固定「已停止当前操作。」应答。

| 观察项 | stop 前 | stop 后 |
|---|---|---|
| 原气泡 delivery_status/content | running / 空 | completed / 空 |
| sleep 工具 status/reason | running / null | failed / interrupted |
| sleep input | `{command:"sleep 30",description:"等待30秒验收中断",timeout:60000}` | 逐字段不变 |
| sleep detail | `{command:"sleep 30"}` | 逐字段不变 |
| sleep output | 等待30秒验收中断 | `[Request interrupted by user for tool use]`，既有停止文案 |
| 已完成 echo | completed，exit_code=0，stdout=REF568_R2_READY，duration_ms=37 | 整个工具记录字典相等，未被改写 |

停止后持续检查 **35 秒**（超过原 sleep 30 秒时长），历史未出现 Agent 的晚到随机 token 正文。原气泡已收口且 content 为空，没有补出虚假最终正文。显式 stop 的气泡合法终态是 completed，工具为 failed/interrupted；验收不要求把整个气泡改成 failed。

原始证据：`/tmp/nano-refactor568-acceptance/product-evidence-r2/stop-before.json`、`stop-after.json`、`stop-late-window.json`；探针 `/tmp/ref568-round2-probe.py`；执行日志 `round2-probe.log` 最终明确 `PASS stop fields preserved, completed calls unchanged, no late body through 35 seconds`。首个本轮探针曾过严地要求气泡 failed，修正为验证合法非 running 终态后重新走完整实际旅程；这不是产品失败。

独立辅助验证：`test_im_reply_image_delivery.py`、`test_reconcile_preserves_tool_input.py`、`test_session_reset_delivery.py` 共 **21 passed**。其中 stop→reset/generation advance→late cancelled→reconcile 的确定性 seam 场景仅保留原 tool_start，无新增 cleanup/body，且不能重新发布；另覆盖错误气泡、非空晚到正文、新成功工具结果与 turn_start 均不得借清理通路发布。**此 reset 证据为 transport seam，不宣称真实 UI `/reset` 旅程或网络竞态覆盖**。

### 场景覆盖与问题继承

| Scenario | 来源 | 本轮方式与证据 | 结果 |
|---|---|---|---|
| 正常与失败工具 | motivation.md | retained：Round 1 真实 read 成功/失败历史与字段证据；本轮未改变投影合同 | pass |
| 运行中工具被终结 | motivation.md；Round 1 A1 | 本轮真实运行工具→stop→原历史收口；原参数/detail、已完成工具逐字段比对；35 秒晚到正文窗口 | pass |
| IM 离线与恢复 | motivation.md；design runbook | retained：Round 1 真实 SQLite + HTTP seam 的旧/新恢复字段比对；本轮不改变 shadow schema | pass |
| stop 清理不得绕过 reset 或发布晚到正文 | design A1 补充约束 | 本轮真实 stop 35 秒正文观察 + 21 项回归中的 reset/late-cancelled seam 反例 | pass |

| 问题 | 上轮结论 | 本轮处置 |
|---|---|---|
| A1 / major blocking | stop 应答后工具和原气泡仍 running | closed：真实 sleep 变 failed/interrupted，原气泡 completed；字段保留、已完成工具不变 |

Reference Artifacts Reviewed: N/A，未新增视觉原型。上层文档检查保持 Round 1 结论：SPEC/current specs/AGENTS/文档规范均无需修改现有行为合同。本轮仅追加验收报告，未修改实现、测试或受控配置；依 caller 指示报告不单独提交，由 root 统一交付。
