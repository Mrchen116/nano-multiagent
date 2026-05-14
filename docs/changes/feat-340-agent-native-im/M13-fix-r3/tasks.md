# feat-340-M13: fix-r3 (新建群聊后侧栏不显示) — Tasks

> 对齐: ../design.md v1 (M13 行)

## 目标

新建含无主 agent participant 的群聊后,`GET /im/v1/conversations` 立即能查到该会话;跨租户隔离不退化。

## 退出标准

- [x] POST /im/v1/conversations (含无主 agent 参与者) → 201; GET /im/v1/conversations 返回该会话
- [x] 单测覆盖 `caller_owner_id` 被正确写入 conversation.owner_id
- [x] 跨租户隔离:owner A 创群,owner B GET 不到
- [x] npx tsc -b 干净
- [x] vitest 全绿
- [x] pytest tests/im_service/ 全绿(pre-existing m103/m136 ignore)

## 测试策略

HTTP 集成测试(真打 TestClient):
- 注册 human user alice(有 owner_id)
- 创建 agent user(username=agent:bot, owner_id='')作为参与者
- POST /im/v1/conversations 创建含双方的群聊
- GET /im/v1/conversations 断言能看到该会话
- 跨租户:bob 注册后 GET 看不到 alice 的群聊

单元测试(repository 层):
- 直接调 ConversationRepository.create_conversation(caller_owner_id=alice.owner_id, ...)
- 断言 created.owner_id == alice.owner_id(不是随机 UUID)

## Roadpoints

### R1 — C1 红测试:HTTP 入口 + repository 单测

- 状态: DONE
- 步骤: 在 tests/im_service/integration/test_chat_flow_integration.py 追加 test_group_with_agent_appears_in_sidebar; 在 tests/im_service/unit/test_repositories.py 追加 test_create_group_conversation_owner_id_uses_caller
- 验证: pytest 这两个测试文件 → 两个新测试 FAIL ✓

### R2 — C2 实现:web_im.py + repositories.py + web_im_service.py

- 状态: DONE
- 步骤: routes/web_im.py 移除 del user,改传 caller_owner_id; web_im_service.py 透传; repositories.py create_conversation 接受 caller_owner_id 参数,caller 提供时直接使用
- 验证: pytest tests/im_service/ (ignore m103/m136) → 203 passed ✓; vitest 238 passed ✓; tsc -b 干净 ✓

### R3 — C3 文档:tasks.md 更新 + progress.md 补齐

- 状态: DONE
- 步骤: 更新本文件状态;补 progress.md 各段
- 验证: git log --oneline 显示 C1/C2/C3 三提交
