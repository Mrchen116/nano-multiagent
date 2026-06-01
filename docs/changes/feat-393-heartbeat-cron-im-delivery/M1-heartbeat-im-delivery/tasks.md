# feat-393-M1: heartbeat-im-delivery

## 目标

heartbeat run 结果真正回发到 (owner, agent) canonical 直聊，走与普通聊天相同的流式消息路径；
NO_REPLY/空内容静默；多单聊落最旧那条且不污染其它；无直聊时自动新建。

## 退出标准

- [reviewer] heartbeat 有内容时直聊出现 agent 汇报消息（含流式呈现 + 离线留存）
- [reviewer] 无事可报时直聊无新消息（静默）
- [reviewer] 多单聊时落最旧那条、其它不受污染 + 首次无直聊自动新建
- [reviewer] 用户只见汇报、不见内部触发指令
- [worker] 集成测试打真实 FK 强制的 IM message 路径，断言有内容时建真实 message 行、静默 tick 零 message
- [worker] 普通聊天流式路径无回归（eager 占位/`/sync` 行为不变）的断言通过
- [worker] `pytest -m "not e2e"` 全绿（含 IM_service）
- [worker] fresh-session 旁路已删、`origin=heartbeat` 门控为唯一开关

## 测试策略

后端 API 改动；入口测试通过真实 IM DB（FK 强制）+ 完整 gateway handler 路径验证。

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| heartbeat 有内容时建真实 message 行（FK 路径） | 集成测试：真实 sqlite DB（PRAGMA foreign_keys=ON），断言 messages 表有新行 | 是 |
| 静默 tick 零 message（NO_REPLY / 空） | 集成测试：断言 messages 表零新行 | 是 |
| turn_start to_user_id 模式解析 canonical 直聊 | IM gateway_handler 单元测试：with real DB，owner+agent users 已存在，断言返回 message_id | 是 |
| 首次无直聊时自动新建 | gateway_handler 测试：无 conversation 前提，turn_start to_user_id 后断言 conversation 被创建 | 是 |
| 多单聊时落最旧那条 | gateway_handler 测试：两条 direct conversation，断言用的是最旧那条 | 是 |
| 普通聊天流式路径无回归 | 现有 test_inbound_pipeline_streaming 通过 | 是（现有） |
| fresh-session 旁路已删 | 代码审查 + scheduler 测试证明 | 是 |

## Roadpoints

| ID | 标题 | 状态 | 描述 |
|---|---|---|---|
| R1 | IM turn_start to_user_id 分支 + 集成测试 | DONE | 扩展 gateway_handler._handle_streaming_delta：新增 to_user_id 模式；写红测试先 |
| R2 | heartbeat observer 惰性 turn_start + run_context_store 播种 | TODO | main.py: observer origin 门控；heartbeat run 在专属 :heartbeat session + 等终态消费；删 fresh-session 旁路 |
| R3 | 全套回归验证 | TODO | 跑全量测试树；补普通聊天流式无回归的断言；更新文档 |
