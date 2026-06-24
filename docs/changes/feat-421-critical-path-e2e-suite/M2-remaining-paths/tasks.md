# feat-421-M2: remaining-paths — Tasks

> 对齐: ../design.md v1

## 目标

在 M1 已落地的底座（`tests/e2e/critical_paths/conftest.py` 起栈 fixture + `_im_client.py`
黑盒客户端 + 奠基 2 条）之上，补齐 spec 11 条关键路径里其余 9 条经真 Gateway 进程的黑盒
e2e；填全 `docs/e2e-critical-paths.md` 四列 catalog（9 条 TODO 换真实测试函数名）+ 从
`AGENTS.md` 关键文档索引挂链。完成后 `scripts/e2e-critical.sh` 一条命令跑通全部 11 条
（cron/heartbeat 走 `@pytest.mark.slow`，`-m "not slow"` 可筛掉）。

## 退出标准

- [x] 9 条 test 文件落地，每条一文件一用户旅程，鲁棒断言（哨兵 token + 协议级状态，群聊 @ 只认 XML 标签）
- [x] 经真 IM + 真 Gateway 进程 + 真 LLM 跑通（`scripts/e2e-critical.sh`）；cron/heartbeat `@pytest.mark.slow`。10 条真绿（含 cron[slow]）；heartbeat 因产品 openclaw 心跳前缀触发 K2.6 死反射端到端不冒泡（#126），保留旅程，标 @pytest.mark.xfail(strict,#126)，移 catalog backlog（M3 由 skip 改 xfail）
- [x] `docs/e2e-critical-paths.md` v1 段四列无 TODO，每条挂真实测试函数；backlog 段保持（heartbeat 在 backlog 带 #126）
- [x] `AGENTS.md` 关键文档索引加一行指向 catalog

## 测试策略

- 被测行为（来自 spec Requirement，逐条）：
  - bash 前台超时不卡死会话（工具按超时收口、用户仍收回复）
  - bash 后台任务完成后送达跟进通知（第二条 agent message）
  - 前台子 agent 可用且产出回带
  - /stop 中止正在执行的 run（ack + 不再继续产出）
  - cron 定时任务自动推送（slow）
  - heartbeat 有内容时主动冒泡（slow）
  - 群聊人@agent 再 agent@agent 双向定向唤醒 + 未点名不抢话
  - 权限审批 approve（工具执行、产出结果）/ deny（工具不执行、run 收口）
  - 经 IM 建 agent 落地上线后可聊
- 已有测试在：`tests/e2e/critical_paths/`（M1 建目录 + conftest + _im_client + 2 条）；本 milestone **新建 9 个 test 文件**（design 决策：每条路径一文件一旅程，catalog 已锁文件名）
- 落层/目录/marker：`tests/e2e/critical_paths/`，marker：`e2e`（父 conftest 自动打）+ cron/heartbeat 额外 `slow`
- 可选依赖 importorskip：`websockets`（已在 `_im_client.py` 顶层 importorskip，本 milestone 复用，不重复）
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真跑 log / WS 事件摘录写进 progress.md，不落 tests/

前端：N/A（本 unit 走 API 级 IM HTTP/WS，design 决策 7 明确不做前端 UI 自动化）。

## Roadpoints

| R | 标题 | 范围 | 状态 |
|---|---|---|---|
| R1 | 工具循环 3 条 | bash 前台超时 / bash 后台通知 / subagent 三条 test 文件 | DONE |
| R2 | 控制流 2 条 | /stop / 经 IM 建 agent 两条 test 文件 | DONE |
| R3 | 群聊 + 权限 2 条 | 群聊双向定向@ / 权限审批 approve+deny 两条 test 文件 | DONE |
| R4 | 时间驱动 slow 2 条 + catalog | cron[slow] 绿；heartbeat 定性真产品 bug(#126)→xfail(strict)+backlog；catalog 四列填全；AGENTS.md 挂链 | DONE |

每个 R 走 C1（test，对真栈应红/失败前置能力缺失）→ C2（实现/旅程脚本调通真跑绿）→ C3（progress.md 补证据）。
