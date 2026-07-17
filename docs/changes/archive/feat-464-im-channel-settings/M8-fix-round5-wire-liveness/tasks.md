# M8: Round 5 wire liveness and feedback closure — Tasks

> 对齐: ../design.md v16

## 目标

关闭 Round 5 发现的 wire response race，并补齐注册握手、控制帧重连和 removal transient feedback 的有界收敛。

## 退出标准

- [x] ACK、channel result 与 generic error 可在 owner phase=`sending` 时关联；send 返回后不会复活已结算 owner。
- [x] register send 与 ACK 共用默认 10 秒 deadline；timeout 后进入断开/重连，ACK 后 convergence 不被误取消。
- [x] register/heartbeat protocol rejection 在 reconnect 前走既有 backoff，backoff 只在 register ACK 后重置。
- [x] offline removal waiting notice 在节点恢复后的在线 retry/error 前清除。
- [x] 永久 asyncio/Vitest 回归、相关面、Ruff、test-size、full frontend/build 与 full backend gate 完成；原沙箱受限的 13 项在开放权限后精确复跑并全部通过。

## 测试策略

- backend 新建 `tests/unit/personal_assistant/test_gateway_wire_liveness.py`：既有 connection/status 文件已超过或接近 400 行，新文件承载同一 wire-liveness 主题且保持 304 行。
- deterministic fake 在 transport 已记录 frame 后阻塞 send coroutine，再并发交付 status result / heartbeat ACK；不是依赖真实网络概率的 flaky 测试。
- registration 覆盖 send timeout、ACK timeout、protocol rejection backoff 与 post-ACK slow convergence 四条边界。
- frontend 在同一组件实例内驱动 offline → waiting → online → generic retry error，断言 waiting 与 error 不并存。
- 最窄测试先行；收口轮只运行一次 full backend、full frontend/build、Ruff 与 test-size gate。

## Roadpoints

### R1 — Wire terminal response ownership

- 状态：DONE。
- 结果：response handler 以唯一 owner + type/request correlation 判定，不再把 `sending` 误当成无 owner；send completion 只推进仍存活的同一 owner。

### R2 — Registration and reconnect liveness

- 状态：DONE。
- 结果：register send/ACK 共享 deadline；ACK 即结束 deadline；control rejection normal return 被提升为 transient failure并走 backoff。

### R3 — Removal feedback owner handoff

- 状态：DONE。
- 结果：online retry 开始与非-offline error 都清理旧 waiting notice，receipt disappearance 的既有清理仍保留。

### R4 — Closure gates

- 状态：DONE。
- 结果：focused、related、frontend full、Ruff、test-size 与 backend 分段全量 gate 已完成；原 13 个受限用例开放权限后全部通过，Round 6 verification PASS。
