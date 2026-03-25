# M320 Re-fix unread badge that still persists after opening chat

## Context
- Milestone: `M320`
- Goal: 修复真实产品 URL `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb` 中会话已打开仍显示 `8 new` 的问题。
- Scope: `src/IM/frontend/dist/`, `tests/im_service/integration/test_messages_api.py`

## Roadpoints

### R1 Runtime-delivered unread semantics match source fix
- Status: TODO
- Acceptance:
  - 真实 URL 下，打开目标会话后 sidebar 未读角标及时清零。
  - 刷新后仍保持已清零，不回退为旧未读值。
  - 回归测试覆盖“运行时前端 bundle 未包含 unread read-ack 路径”这一真实失败模式。
  - 交付路径修复后，IM 实际对外提供的 bundle 包含 `mark_as_read` read-ack 语义。
- Tests Plan:
  - 在现有 `tests/im_service/integration/test_messages_api.py` 增加 runtime bundle 交付回归用例（先红后绿）。
  - 运行派发测试命令：`cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts && cd ... && pytest tests/im_service/integration/test_messages_api.py -k mark_as_read`。
- DoD:
  - C1/C2/C3 三提交完成。
  - 真实浏览器复验同一 URL 的 unread 角标行为通过。
  - `TASKS`/`PROGRESS`/`data/dev-tasks.json` 同步完成。
