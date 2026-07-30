# PROGRESS: M249 personal_assistant 聊天历史落盘

## 当前状态: DONE

### 预存失败
- tests/im_service/integration/test_m103_im_gateway_e2e.py::test_group_chat_uses_live_updated_profile_after_config_sync_in_same_conversation
- 原因：与本 milestone 无关的集成测试，预存失败

---

### R1 chat_history.py hook 实现

- Context:
  - `after_agent_reply` 事件不存在于 HookEventType（core/ 禁止修改）
  - 需要用 input + message_end + agent_end 三事件组合实现同等语义
  - workspace_root 通过 `ctx.metadata.get("cwd")` 获取（runtime 在 hook_metadata 中注入）
- Decision:
  - 模块级 `_pending: dict[str, dict]` 存储跨 hook 状态
  - input handler: 返回 None（不拦截），仅侧效存储 user_text
  - message_end handler: 存储最后一条 assistant content（覆盖写，只保留最终回复）
  - agent_end handler: 写 JSONL，清理 _pending
- Rationale: 三事件串联是在不修改 core 情况下唯一可行的方案；module-level dict 无需锁（GIL 保护简单 dict 操作）
- Evidence:
  - Tests: `PYTHONPATH=src python -m pytest tests/unit/ -x -q` → 624 passed（含 5 新增）
  - Entry: `_simulate_turn` 驱动三事件链，断言 JSONL 内容/路径/追加语义全部通过
- Rollback: 回到 1bd2822（计划提交），C1=8da7345 可安全回到红态
- Commits: C1=8da7345, C2=990f19b, C3=（本次提交）
- Next: 合并到 main
