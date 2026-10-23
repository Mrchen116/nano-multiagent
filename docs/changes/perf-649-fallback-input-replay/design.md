# perf-649: 单遍重放本轮输入归属

## 设计目标与现状

current 契约见 `docs/specs/gateway/agent-capabilities.md` 的模型备用链。现有 ModelFallback 在每个 turn/end，提取全部 inbox 插入 ID（包括重复 ID），为每个 ID 全量调用 inputEvidence，选取最终 turn 等于本轮的输入。inputEvidence 重放两条 inbox 的 splice，claim 后但 user/message 前也会归属 turn；canceled removal 不重新赋予 turn；user/message 更新最新 turn。顺序为历史第一次插入的顺序。恢复时 attach 也通过 observe 进入这一逻辑。

## 决策与数据流

新增同模块内部消费者使用的 `inputIdsForTurn(events, inputTurn): string[]`，只在 ModelFallback 的 turn/end 调用；不变更现有 inputEvidence 或 session.lookup。单次从头重放快照，维护 next-turn/next-step 两个 ID 队列、当前 turn、按首次插入排序的 Set、每个 ID 的最后归属 Map。splice 使用原生数组语义，包括默认 removedCount、负下标、多插入、重复 ID；非 canceled removal 将 removed ID 归到当前 turn（可能 undefined），user/message 同样赋予当前 turn；turn/end 清空当前 turn。最后按插入 Set 的顺序选 Map 中等于目标 turn 的 ID。只出现 user/message、从未 inbox 插入的 ID 不成为 ModelRun 输入，与现状相同。ModelFallback 继续排除 nano-fallback 前缀并去重追加到 run.inputs。

选择单遍而非常驻增量索引：无需订阅初始化顺序、快照截断检测、缓存淘汰或额外持久 schema。已有单 ID inputEvidence 保持原样，降低 session.lookup 兼容风险；不强制其他 unit 使用新 API。此 helper 仅投影归属，不承担 accepted/consumed/terminal 证据查询。

复杂度为 O(E + S + I)，E 为事件数，S 为原生 splice 的队列移动及插入/删除工作量，I 为不同插入 ID 数；不是忽略巨大队列 splice 本身的严格 O(E)。临时状态 O(I + U + Q)，U 为仅出现在 user/message 的 ID 数，Q 为 pending queue 长度，函数返回后可回收，无跨轮常驻历史副本。已有 runs 持久化、账单、安全审核、故障恢复顺序不变。实际 fallback 的 schedule 对本 run 输入做证据查询保留（仅故障路径，非全部历史输入循环），本项不扩展到该路径的优化。

## 接口与测试边界

- inputIdsForTurn 输入只读 SessionEvent 数组和 number turn，返回首次接受顺序的去重 IDs。
- differential regression 用旧提取循环 + inputEvidence 作为 oracle，逐前缀比较两条队列、splice replacement/negative start/duplicate IDs、cancel、claim 未消费、out-of-turn user message、同 ID 后续 turn、重复 terminal、多个 attempt。输入证据现有测试继续运行。
- ModelFallback 实际 runtime 测试补普通成功、无备用成功/失败、历史输入不混入本轮与多个 fallback attempt；保留原有 prepare/finish/exhausted/context/published/tool/cancel/new-input/restart/pre-step 覆盖。
- 合成 benchmark 500/1000/2000 历史输入，固定每轮事件与一个末轮输入：旧 oracle 与新 helper 结果一致，记录事件访问计数、中位耗时及临时状态边界；至少 95% 访问减少、2000 输入同机中位数至少快 5 倍。以计数作为稳定回归门禁，墙钟为实验结果，不设易抖动 CI 阈值。

## 契约层增量

no spec delta：只替换内部计算，保持 gateway 既有备用链及输入证据外部契约。无前端变化，无原型。

## 风险与回退

最主要风险是 claim 未消费与 canceled removal 的不同归属、重复 ID 最后归属及首次插入排序。用逐前缀差分测试保护，而不简单只看 user/message。无新数据格式，回滚仅撤销代码。合成 benchmark 不证明生产耗时比例。

## Runbook for Reviewer

本 unit 无新增产品常驻服务；验收会启动本 unit 专属 IM、Gateway/DSH 和一个临时 HTTP 模型 fixture。复用 `scripts/fixtures/anthropic_sse_ok_recording.py` 的 `_sse_ok` 编码，新增仅本次验收的 `stub.py`（本机 `/tmp/perf649-environment/`，不进长期测试套件）：model `fail` 固定返回 Anthropic JSON 401，`ok` / `backup` 返回含模型名的 `PERF649-ACK-*` SSE，`slow` 记录请求后等待本目录 release 文件（最长 45 秒）再成功。使用 ThreadingHTTPServer，取消的连接不阻塞后续请求。2026-10-23 已本地启动并检查 fail=401、ok/backup=200 SSE；源脚本无凭据。该临时 fixture 的准备、清理与结果摘要属于 M1 验收辅助范围。

构建：专属 worktree 中使用 Node 24.22.1 执行 `pnpm install --frozen-lockfile && pnpm build`。使用主仓 `.venv/bin/python` 处理 YAML/HTTP。配置从 `config/e2e/gateway.yaml` 复制到本次 runtime 目录，agents 只选本地 `e2e`、`e2e-peer`，工具为空，model catalog 为 `ok/fail/backup/slow`，Anthropic base_url 指向 fixture 的随机空闲端口；保留源配置的隔离测试身份 nano/nano1234。不读取个人配置。

| 组件 | 启动 | 停止 / 健康证据 |
|---|---|---|
| HTTP fixture | `python /tmp/perf649-environment/stub.py <unit-worktree> <free-port> <runtime>/requests.jsonl` | caller 记录并 terminate 本进程，wait 后确认端口释放；GET / 为 200 |
| IM + Gateway/DSH | `PATH=<main>/.venv/bin:<node24-bin>:$PATH ./scripts/e2e-up.sh --wt <unit-runtime> --main-config <unit-runtime>/source.yaml` | `./scripts/e2e-down.sh --wt <unit-runtime>`；GET /openapi.json，登录后 GET /im/v1/nodes 为本次 node online |

**Review 驱动方式**：真 IM/Gateway/DSH 栈；不改客户端面。用 `tests/e2e/critical_paths/_im_client.py` 的 IMClient 发送前端同一 HTTP API，所有最终结论来自 GET /im/v1/conversations/{id}/messages，模型请求记录只用于确定故障/等待条件，不替代用户结果。

- 普通成功：e2e 默认 ok、无备用；同一 conversation 连续发两条，分别观察一条 ACK，不出现历史重复回复。
- 无备用失败：经 IMClient.update_agent_config 设置 fail、model_fallbacks=[]；新 conversation 发消息，观察 fail 模型失败提示且无 ACK，无 backup 请求。
- 实际备用：同接口设置 fail + [backup]；新 conversation 发消息，观察失败提示、独立切换说明、backup 正文；后续消息直接 backup 且无重复说明。模型配置 PATCH 需带当前 profile_version，使用已有 helper。
- 取消：配置 fail + [slow]，新 conversation 发消息；等待 HTTP 记录出现本次 slow 请求（备用已进入且尚无成功正文），通过 send_message 发送 `/stop`；观察停止确认后 release fixture，旧请求不产生成功正文；新普通请求能继续。该真实产品场景验证取消后的结果；更细的 claim/pre-step/new-input 边界由已有 runtime 原生测试保护。
- 恢复：备用成功后调用已有 `tests/e2e/critical_paths/_im_gateway.py::restart_gateway(runtime, im_port)`，使用返回的 generation floor 和 IMClient.wait_for_node_reconnect 确认新一代；同一 conversation 发新消息仍从 backup 回复且无重复旧输入。切换中强制中断的恢复另复用 runtime 原生 restart 用例（model.check gate），不把这条 runtime 证据描述成完整栈用户观察。

用户侧“恢复或取消”细化为稳定可观察的恢复后续聊和备用在途取消；没有新增产品恢复保证。原始分工要求的关键中间恢复、claim/消费与输入归属仍由 runtime tests 覆盖。所有端口、JWT、数据库、模型请求及进程归本 unit runtime；caller 集中准备环境，reviewer 独立发起观察，结束由 owner 清理。无 live 模型/生产凭据前置；合成模型不证明真实上游延迟、能力或生产占比。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-linear-replay | 替换全输入回放并验证 | 无 | 单组 | packages/dsh-integration/src/{input-evidence,model-fallback}.ts、对应 tests、合成 benchmark | [worker] 差分语义、runtime 回归、计数与计时目标、typecheck/相关 CI 通过；[reviewer] motivation 的普通成功、无备用失败、备用成功、恢复/取消旅程保持 |

## Changelog
