# M163 Task — 修复真实群聊浏览器 mention 规范化与多 Agent 路由

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M163`
- 已确认 branch：`milestone/M163`
- 已确认约束：仅在该 worktree 实施修复；不创建嵌套 worktree；不修改 `data/dev-tasks.json`
- 失败验收线索：
  - 浏览器手打 mention 首条可达，但同线程第二个不同 Agent 被错误路由回首个 Agent。
  - mention picker 插入 `@agent:<agent-id>` 后，后端 payload 记录成未规范化 token，路由回退到默认/首个 Agent。
  - NO_REPLY 在真实群聊产品路径未保持静默，本质上是群聊路由命中了错误 Agent。
- 首轮阅读：
  - `src/IM/application/relay_service.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `src/personal_assistant/channels/web_relay_adapter.py`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`

## 目标
修复真实浏览器群聊里的 mention 规范化与多 Agent 路由闭环：手打 `@agent-x` 与 picker 插入 `@agent:agent-x` 都必须归一成同一个被点名 Agent；同一线程里连续点名不同 Agent 时要各自命中；NO_REPLY 在真实群聊产品路径保持静默。

## 明确问题
1. `relay_service.py` 当前直接把 mention token 去掉 `@` 后写入 `mentioned_agent_ids`，会把 picker token `agent:agent-x` 原样入库，导致后续 agent 快照选择失败并回退到首个参与 Agent。
2. `inbound_pipeline.py` 当前在群聊里优先相信 payload 里的 `agent_id`，当上游 payload 已经漂移或与 mention metadata 冲突时，会把同线程后续消息继续投递给错误 Agent。
3. 当前测试覆盖了手打 mention 和群聊 NO_REPLY，但没有把“typed / picker 两种 token 归一为同一 agent id”以及“group path 在 agent_id 冲突时仍以 mention 语义为准”锁进回归门禁。

## Scope
- 统一后端群聊 mention token 归一规则，兼容 `@agent-x` 与 `@agent:agent-x`。
- 调整 Gateway 群聊路由优先级，使 mention 语义在群聊中优先于漂移的显式 `agent_id`。
- 增加聚焦单测 / 集成测试，覆盖 mention 规范化、同线程多 Agent 路由与 NO_REPLY 静默。
- 更新 `TASKS/M163-*.md` 与 `PROGRESS/M163-*.md`，记录 Roadpoints、验证命令、证据与回滚点。

## 非目标
- 不修改 `data/dev-tasks.json`。
- 不新建额外浏览器 e2e 套件。
- 不改动无关的直聊路由或工作区设置流程。

## Roadpoints

### R1. 收口 IM relay mention 规范化
- Status: DONE
- Acceptance:
  - 手打 `@agent-x` 与 picker `@agent:agent-x` 进入 relay payload 后都规范为同一个 `mentioned_agent_ids=["agent-x"]`。
  - relay payload 的 `agent_id` 与被点名 Agent 一致，不再因为未规范化 token 回退到首个参与 Agent。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/unit/test_relay_service.py -q`
- DoD:
  - relay service 有稳定的 mention 归一 helper，并用单测锁定 typed / picker 两种形式。

### R2. 收口群聊 Gateway 多 Agent 路由与 NO_REPLY 语义
- Status: DONE
- Acceptance:
  - 群聊里 mention 语义优先于漂移的显式 `agent_id`。
  - 同一线程里连续点名不同 Agent 时，各自命中正确会话与回复。
  - 被点名 Agent 返回 `NO_REPLY` 时，真实群聊产品路径保持静默。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/unit/personal_assistant/test_gateway_pipeline.py -q`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/integration/test_m136_group_chat_flow.py -q`
- DoD:
  - Gateway 群聊路由与 NO_REPLY 行为有聚焦回归保护。

### R3. 验证、文档与收口
- Status: DONE
- Acceptance:
  - 记录聚焦验证命令、结果、提交哈希与回滚边界。
  - worktree 可干净提交，并给出是否 ready to merge 的判断。
- Tests Plan:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M163/src/IM/frontend test -- --run src/features/chat/components/message-pane.test.tsx`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/unit/test_relay_service.py -q`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/unit/personal_assistant/test_gateway_pipeline.py -q`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/integration/test_m136_group_chat_flow.py -q`
- DoD:
  - PROGRESS 写清根因、修复点、验证结果与后续的 M141 合并后复验要求。

## 当前结果
- 已完成 relay mention 规范化：手打 `@agent-x` 与 picker `@agent:agent-x` 现在都会落成同一个 `mentioned_agent_ids=["agent-x"]`。
- 已完成群聊 Gateway 路由收口代码与测试补齐，待最终验证记录与文档收口。

## 回滚点
- 若需回滚本 milestone，预计只需撤回：
  - `src/IM/application/relay_service.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `TASKS/M163-修复真实群聊浏览器mention规范化与多Agent路由.md`
  - `PROGRESS/M163-修复真实群聊浏览器mention规范化与多Agent路由.md`

## 验证命令
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M163/src/IM/frontend test -- --run src/features/chat/components/message-pane.test.tsx`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/unit/test_relay_service.py -q`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/unit/personal_assistant/test_gateway_pipeline.py -q`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/integration/test_m136_group_chat_flow.py -q`

## 提交计划
- C1: 文档建档与 Roadpoints 冻结
- C2: relay mention 规范化与聚焦单测
- C3: gateway 群聊路由收口、集成验证与 PROGRESS 归档
