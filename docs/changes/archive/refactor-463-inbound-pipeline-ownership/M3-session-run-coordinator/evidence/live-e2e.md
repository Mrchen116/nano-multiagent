# M3 验收证据对账

Date: 2026-07-15
Milestone implementation head: `ef25d3b1f`

## 证据分层

本文不把 fake kernel 或可控 adapter 写成“真进程”。端口、进程、IM 可见结果和真 LLM 调用只记在“真栈”；需稳定制造精确 race/stall/failure 的路径记在“可控协议边界”。

| 行为 | 真栈证据 | 可控公开边界证据 |
|---|---|---|
| 同 session active stop | 真 IM 先观察 tool call，再发 `/stop`，固定 ack 可见且 45s 任务哨兵未冒泡 | public coordinator 断言 `submit -> interrupt -> append`、original reconcile 和 idle direct 提示；max=1 + 另一 session 施压时 stop 也不可绕过 pre-submit owner |
| 跨 session / 连续 steer | 真群内 A -> B directed mention 通路通过，非 mention agent 保持静默 | public coordinator 稳定制造 lost-steer，证明同 session FIFO、跨 session 并行、两次 steer 共享 original stream |
| 群背景 / sender / image | 真群定向 mention 与静默路径通过 | public facade/coordinator 验证 sender prefix，group destructive drain 和 image resolve 恰好一次 |
| quiet / stall | 真 Gateway heartbeat 连续三次执行且返回 `HEARTBEAT_OK`，时间为 10:34:48Z / 10:35:19Z / 10:35:50Z | public coordinator 用真 async event 时序证明 heartbeat 跨过 idle window；无任何 event 时 cancel + stalled reconcile + failed lifecycle，随后同 session 下一 turn 可运行 |
| `NO_REPLY` / terminal failure | 本次未伪造真 LLM 必然返回值 | public coordinator 验证 group/external 两个 delivery boundary 零外发；failed terminal 的 lifecycle/reconcile/marker cleanup |
| external / shadow | 无可用的真飞书凭据，不冒充真飞书验收 | `InboundMessage` 公开入口 + controllable shadow adapter 验证 trigger source、shadow conversation 与原 target；飞书 external identity 与 shared group key 另有 integration contract |
| 启动 / 停止 / 重连 | 真 Gateway 重启后上下文连续；真 IM kill/restart 后 Gateway 不重启自动回 online；Gateway 先于 IM 启动也能恢复 | shared-deadline seal/settle/drain 和资源图顺序有永久 shutdown tests/contract |

## 完整真栈门禁

```bash
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-critical.sh -q -m 'not slow'
```

```text
...............                                                          [100%]
15 passed, 2 deselected in 251.42s (0:04:11)
```

```bash
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-critical.sh -q -m slow --timeout=210
```

```text
.x                                                                       [100%]
1 passed, 15 deselected, 1 xfailed in 229.46s (0:03:49)
```

`--timeout=210` 只用于让 heartbeat case 内已定义的 180s 等待完整结束，不改产品配置或测试期望。slow 结果中的 pass 是 cron push，xfail 是已登记 #126 heartbeat bubble。

## 真 IM + Gateway + Kernel + LLM

Command:

```bash
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-critical.sh -q \
  -k 'stop_run or group_chat_directed_mention or restart_session_continuity or bash_background_notify'
```

Result:

```text
......                                                                   [100%]
6 passed, 11 deselected in 102.13s (0:01:42)
```

六条永久 case 为 background Bash completion、directed group A -> B、unmentioned-agent silence、restart generation 就绪判定、restart 后 context continuity 和 active `/stop`。运行由 `e2e-up.sh` 为 pytest temp workdir 分配高位端口、隔离 config/node/workspace，且通过当前 127.0.0.1:4000 LLM proxy 门控。

## 真 IM/Gateway 瞬断与启动顺序

Command:

```bash
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
  ./scripts/e2e-critical.sh -q -k gateway_im_resilience
```

Result:

```text
.                                                                        [100%]
1 passed, 16 deselected in 23.76s
```

该 case 内部启动真 IM + Gateway 两进程，验证两场景：IM kill/restart 时 Gateway 不重启便重连为 online；Gateway 先起、IM 后起时 Gateway 不崩溃且节点最终 online。

## Heartbeat 已知边界（#126）

`test_heartbeat_bubbles_actionable_message` 已是 `strict=True` xfail，理由明确指向 #126 的 K2.6/openclaw heartbeat prompt 死反射。首次使用仓库默认 `--timeout=90` 探查时，Gateway 并未停止 tick：`sess_b6e621d60902dc41` 在 10:34:48Z、10:35:19Z、10:35:50Z 三次提交哨兵 `HB7B6C0379`，真模型三次均返回 `HEARTBEAT_OK`；只是 case 内 180s 等待被全局 timeout 先中止。最终门禁以 `--timeout=210` 重跑，case 完整走到 strict xfail，pytest 退出码为 0。

结论：这是已登记的用户可见冒泡缺陷，不是 M3 composition 让 heartbeat loop 没启动；M3 不越界修改 #126，也不把这次探查记成 pass。

## 可控公开边界门禁

Permanent owner tests:

- `test_session_run_coordinator_admission.py`：same/cross session、continuous steer、submit-marker 线性化、prepared parts exactly once、bounded registry 下的唯一 transition owner。
- `test_session_run_coordinator_terminal.py`：quiet liveness、stall cancel/reconcile/release、active+idle stop、terminal failure、group/external `NO_REPLY`。
- `test_gateway_inbound_ownership_contract.py`：narrow facade、coordinator-only runtime lifecycle、heartbeat public busy query、无 private post-wiring。
- `test_gateway_shutdown_resource_graph.py` / `test_gateway_shutdown_timeout_isolation.py`：shared deadline 与 drain 顺序。
- 32 个旧 `InboundPipeline` 文件的行为映射见 `test-coverage-inventory.md`。

## Self-review 并发修复证据

Review 用最小 `max_transition_locks=1` 制造 A session 持有 pre-submit image gate、B session 也进入 pre-submit gate，然后对 B 发 public `/stop`。旧 LRU 会把 B 刚新建但未 acquire 的 lock 当成 idle 淘汰，stop 拿到另一把 lock 并误报 idle；red 结果为：

```text
Failed: DID NOT RAISE <class 'TimeoutError'>
```

`ef25d3b1f` 用 lease refcount 覆盖等待 acquire、持有与 waiter 全阶段，trim 只删除零 lease + unlocked entry。同一 public case 修后 `1 passed`；最终全量为：

```text
3358 passed, 1 skipped, 22 warnings in 31.61s
```
