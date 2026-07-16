# M10 真 Kernel：无 observer 的 Cron 真实终态

## 目的

验证投递 adapter 缺席时，Cron owner 仍会消费真实 Kernel terminal，并让公开 `cron runs` history 收敛；非 completed 终态不得写成功 awareness。

## 隔离环境

- Kernel：`build_pa_kernel()` 真实进程内 Kernel，未使用 fake kernel。
- 产品入口：`make_cron_tool()` 的公开 `add`、`run`、`runs` action。
- LLM：`scripts/fixtures/anthropic_sse_error.py`，仅监听高位端口 `127.0.0.1:61369`。
- 投递：`CronRunTerminalConsumer(observer=None)`；没有 IM observer/delivery adapter。
- Workspace/HOME：均为 `/tmp/refactor463-m10-*` 隔离临时目录。
- 用户代理：`127.0.0.1:4000` 的 `LLM_PROXY --ui` 全程保持 PID `9321` 监听，未停止或重启。

## 执行与结果

1. `cron add` 创建 job，返回 `ok=true`。
2. `cron run` 返回 `accepted=true` 与 request id `87dfff14aec345fb9ff5b4ffc0121d27`。
3. owner 提交真实 Kernel run `run_714ee7cb3c419816`；fixture 收到真实 `/v1/messages` 请求。
4. 当前 fixture 的 `overloaded_error` 在 Anthropic client 中会进入 retry，因此验证通过公开 `kernel.cancel(run_id)` 快速产生 typed `cancelled`，而不是把中间 `running` 误作 pass/fail。
5. mandatory terminal consumer 在无 observer 情况下消费该终态；`cron runs` 返回：

```json
{
  "request_id": "87dfff14aec345fb9ff5b4ffc0121d27",
  "kernel_run_id": "run_714ee7cb3c419816",
  "trigger": "manual",
  "status": "cancelled",
  "finished_at": "2026-07-16T10:38:45.265271+00:00",
  "result_summary": null,
  "error": null
}
```

6. 隔离 session transcript 中 `is_cron_awareness` / `System (untrusted)` 命中数为 `0`。
7. 验证脚本所有断言通过并以 exit code `0` 退出。

## 证据矩阵

| 风险 | 永久回归 | 真运行证据 |
|---|---|---|
| no-observer 仍消费 terminal | `test_cron_execution_owner_chain.py` 覆盖 completed/failed/cancelled | 本文覆盖真实 Kernel cancelled → public `cron runs` |
| missing terminal 不伪 completed | `test_cron_execution_owner_chain.py` 覆盖 stream ended → `failed/stream_failed` | 不把 fixture retry 中的 `running` 当结论 |
| 非 completed 不写 awareness | owner-chain 覆盖 failed/cancelled | transcript awareness 命中数 `0` |
| heartbeat 快终态与异常终态 | `test_heartbeat_scheduler.py`、`test_heartbeat_session_trim.py` | 公共 runner 生命周期回归驱动 |

## 清理

- fixture 进程已发送 `SIGINT` 并退出；`lsof -iTCP:61369 -sTCP:LISTEN` 无监听。
- `/tmp/refactor463-m10-live.*` 与 `/tmp/refactor463-m10-kernel.*` 已删除。
- `LLM_PROXY --ui` 仍由 PID `9321` 监听 `127.0.0.1:4000`。
