# bugfix-426-M3: fix-steer-drain-race — Tasks

> 对齐: ../design.md（M3 行：fix-steer-drain-race, post-acceptance fix round 1）

## 目标

群聊运行中并发两条消息走 mid-run steer 快路径时，发言人前缀与缓冲上下文不再被瓜分：
两条 steer 各自携带完整的 buffered 群聊上下文（按 drain 串行化语义，一条拿走当前 buffer、
另一条拿到自己到达时的 buffer），不会出现一条 drain 走全部、另一条 drain 得空。

## 退出标准

- [x] steer 路径「has_active_run 判定 + _build_message_parts(drain)」对同 session 串行，
      不与并发 steer、也不与正常路径（_run_turn 内）的 drain 交错
- [x] 新增并发回归单测：复现旧瓜分（修前能触发/红）、修后绿
- [x] 全测试树 `pytest tests/ -m "not e2e" -p no:cacheprovider` 全绿，collect 数 == 跑完数

## 测试策略

- 被测行为（来自退出标准）：
  - 并发两条群聊 steer 消息时，两次 drain 不交错——各自拿到的 buffered context 不被瓜分。
- 已有测试在：`tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py`（扩展，
  已有 `test_group_steer_preserves_sender_prefix_and_buffered_context` 单条 steer 用例）。
  理由：drain 串行是 gateway 行为，FakeKernel + GroupContextStore 已具备复现 race 的全部基础设施。
- 落层/目录/marker：tests/unit/personal_assistant/，marker：无
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无（回归测试永久保留）

前端 UI：N/A（纯 gateway 后端并发修复）。

## Roadpoints

### R1 — steer drain 串行化 + 并发回归单测

- 步骤:
  1. C1：新增并发回归单测，让两条群聊 steer 协程在 drain 处交错，断言两条各自携带完整 buffered
     context（修前应红——一条瓜分走全部、另一条得空）。
  2. C2：在 InboundPipeline 引入 per-session asyncio 锁，把 steer 决策的
     「has_active_run 判定 + _try_steer_active_run(含 drain + kernel.submit(steer))」整段
     纳入该锁；normal 路径 `_run_turn` 的 drain 也进同一把锁。修后单测转绿。
  3. C3：补 progress.md 证据 + tasks 状态。
- 验证: `pytest tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py -q` 全绿，
  全树 not-e2e 全绿。
