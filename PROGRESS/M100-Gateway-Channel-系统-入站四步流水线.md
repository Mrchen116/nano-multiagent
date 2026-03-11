# M100 进展记录 - Gateway Channel 系统 + 入站四步流水线

## 目标
对齐 `NodeGateway-SPEC.md` §3/§4，补齐 Node Gateway 的 Channel 适配器框架、入站四步决策流水线、会话键绑定、同会话串行队列与原通道回发能力。

## 基线
- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M100`
- branch: `milestone/M100`
- baseline 命令：`python -m pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M100/tests`
- baseline 结果：664 passed / 4 failed / 4 skipped
- baseline 失败与 M100 无直接业务关系，但阻断总绿：
  - `ToolRegistry` 缺少 `get()`，导致 resolver loader 覆盖测试失败。
  - `ToolRegistry.list_specs()` 做了按名称排序，破坏 builtin → product → user 的层级顺序断言。

## 实施摘要
1. 为 `personal_assistant` 新增 `channels/base.py`，定义 `ChannelAdapter`、`InboundMessage`、`ReplyContext`、`OutboundMessage`。
2. 新增 `gateway/channel_registry.py` 与 `gateway/bootstrap.py`，统一注册、启动、停止 Channel。
3. 新增 `gateway/session_keys.py`，实现群聊/私聊 session key 规则与进程内 `session_binding_store`。
4. 新增 `gateway/run_queue.py`，采用每 session 一条 FIFO 队列，天然支持跨 session 并行。
5. 新增 `gateway/outbound_router.py`，严格按原 `reply_context` 走原通道回发。
6. 新增 `gateway/inbound_pipeline.py`，按四步执行：Agent 路由 → session key → queue → outbound reply。
7. 增加 `tests/unit/personal_assistant/test_gateway_pipeline.py`，覆盖：
   - start/stop channel 生命周期
   - 群聊/私聊 session key 规则
   - 四步流水线完整 happy path
   - 显式 agent / channel 绑定 / 默认 agent 路由优先级
   - session binding 复用
   - 同 session 串行与跨 session 并行
8. 修复 `src/agent/core/tools/registry.py` 的兼容回归，恢复 `get()` 并保持 `list_specs()` 为注册顺序，满足 resolver loader 的层级覆盖断言。
9. 同步在 `src/agent/platform/http_api/routes/global_routes.py` 保留 capabilities 输出按工具名排序，避免对外 API 展示顺序因内部注册顺序调整而漂移。

## 商业化视角补充审视
- 当前 v1 reply 路由仍是纯内存绑定，进程重启后不会恢复历史 `session_key -> kernel_session_id`；这符合本 milestone 最小集，但上线前需要持久化，否则用户会感知到“重启后会话断档”。
- 当前 pipeline 直接从 `get_run()` 读取 `output_text`，适合模拟链路；后续真实产品还需处理 run 状态轮询、失败回执、空回复提示和有限重试，否则运维可观测性不足。
