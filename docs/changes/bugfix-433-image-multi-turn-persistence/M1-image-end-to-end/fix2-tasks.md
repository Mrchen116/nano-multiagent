# bugfix-433-fix2 — Tasks（reviewer 反馈循环，scope B 限定 image）

> §FL 小修快车道（复用原 worker 上下文）。不新建 milestone 目录，fix 记此文件 + progress 续段。
> worktree `.worktrees/bugfix-433-fix2`，从 `unit/bugfix-433` 切，改完 merge 回 unit。

## 目标（leader scope B 限定）

含 image parts 的 user turn 触发 provider error 后，**后续历史重建不再重发其 image block**（保留文本），使下一轮模型只见文本、会话不卡死。**不动纯文本 provider-error 既有行为**（纯文本更广恢复 + 当轮 vision-不支持友好提示留 out-of-unit #147）。

## 退出标准

- [ ] image turn 触发 provider error → 后续 build_chat_messages strip 其 image block、保留文本
- [ ] image turn 无 provider error → image 仍重放（不过度 strip）
- [ ] 纯文本 user turn（含曾触发 provider error 的）→ 行为零改动
- [ ] 红测守护上述三条
- [ ] 三旅程真栈 live：① 损坏图→固化文案+后续文字不空（回归）② 合法图发非 vision 模型→provider error 但后续文字正常不空（B 核心）③ 合法图发 vision 模型→正常答色（不误伤）
- [ ] `pytest -m "not e2e"` 全绿、ruff clean

## 实现方向（对齐 CC normalizeMessagesForAPI errorToBlockTypes）

CC 源码核实（src/utils/messages.ts:2275-2420）：API-build 时遍历历史，遇 synthetic provider-error 消息→反向找最近的前置 user turn→strip 其对应 block 类型（image）、保留其余（text）；persisted 历史不动，只动「重放给 API」的投影。

本仓对应落点 = `build_chat_messages`（已在过滤 is_provider_error 的同一处）：遇 is_provider_error 消息→反向找最近含 image parts 的 user Message→标记→生成该 user 的 LLMMessage 时去掉 image block、保留 text。persisted JSONL 不动（决策4 历史完整）。

- 只 strip image（scope 限定）：纯文本 user turn 无 image block → 天然不变；纯文本 provider-error → 无前置 image turn → 天然不变。
- strip 后若该 turn 只剩文本 → content 为 text block list 或回退 str 投影（保留真实文本，不是 placeholder）。

## 测试策略

- 被测行为：上述退出标准 1-3。
- 已有测试在 `tests/unit/test_build_chat_messages_images.py`（扩展，新增 fix2 段 3 用例）。
- 落层：tests/unit/，marker 无。
- 一次性 live 验收证据：scratchpad live 脚本（不入库），结论记 progress。

## Roadpoint

单 roadpoint DONE：C1 红测 → C2 build_chat_messages strip 实现 → C3 progress + live（三旅程全 PASS）。
