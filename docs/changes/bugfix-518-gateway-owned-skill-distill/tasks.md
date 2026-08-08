# bugfix-518-M1: Gateway 读取本地 transcript 并蒸馏 — Tasks

> 对齐: [design.md](design.md) v3

## 实施清单

- [ ] 移除 IM `Conversation` 的 `source_jsonl_path`、repository 本机 JSONL 扫描和其 API/frontend
  投影；仅投影 source Agent 与 `source_node_id`。
- [ ] 为 execution conversation 的首次 send 增加 one-shot typed `distillation_request`；由
  `WebIMService.create_distillation_message` authoritative 校验 owner、source/executor 同 node、source idle、
  direct participant，再经 single-target relay 持久化 frozen identity-only payload；既有浏览器 capability 读取
  只保留为创建对话前的 preflight。
- [ ] 修改 sidebar/dialog/composer 状态：同 Gateway selection、cross-node 禁选说明、同 node executor；保留
  可见的 distiller-command 预填和普通聊天的意图补充/结果显示，但删除 draft 中的路径。
- [ ] 新增 Gateway-local `GatewayDistillationSources`：从 exact durable binding 取得本机 JSONL、
  all-or-nothing materialize source context；在 `InboundPipeline` typed guard 后由 coordinator before-submit
  hook 以本地 runtime 做最终 distiller/tool 复核；malformed/capability/source failure 均由
  `fail_distillation_before_submit()` 走 existing normal reply + failed receipt，成功以 internal `/skill:` command
  + trusted context 激活 run。
- [ ] 更新 builtin `conversation-skill-distiller`，只消费 Gateway-provided context，不再接受或读取
  `source_jsonl_paths`；保留现有 evidence 和 `skill_manage(create)` 约束。
- [ ] 更新 delta-spec、i18n 和 `M1-gateway-owned-distill/progress.md` 的真实浏览器/真栈证据。

## 测试策略

- 保护的回归风险与可观察 seam: source conversations 的 REST projection 与 canonical direct relay payload
  不泄露 path；一个 Gateway 能按 source identity 读取自己的 binding/JSONL、激活 distiller 并产生普通回复；
  跨 node/坏 source 会得到 failed receipt 和可理解回复，且不会写 partial skill。
- 已有保护与处置: `tests/im_service/integration/test_users_conversations_api.py`(rewrite-merge),
  `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx`(rewrite-merge),
  `tests/unit/personal_assistant/test_gateway_session_binder.py`(keep);同一失败原因不再以 IM
  repository scan、路径 prompt 和 Gateway private state 平行保护。
- 落层/目录/marker: 在 `tests/im_service/integration/` 扩展一次 direct typed send → frozen relay payload；
  在既有 Gateway relay/inbound coordinator test 扩展 typed guard、activation 和 failure reply/receipt；
  Gateway local resolver 在 `tests/unit/personal_assistant/`；browser selection 在现有 frontend Vitest。这是
  分别能暴露公开 API、delivery lifecycle、local ownership 和用户交互的最低 seam。两 root 真栈是 progress
  evidence，不添加常驻 E2E pytest。
- 文件归属: 扩展上述已有 API/frontend 文件；新增
  `tests/unit/personal_assistant/test_gateway_distillation_sources.py`，因为它保护新深模块的公开
  materialize outcome，而不是一个 milestone 名称的临时集合。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): 隔离双 Gateway 真栈脚本/浏览器截图与
  脱敏 relay payload 检查；结论记录在 progress.md。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| conversation API 不泄露 Gateway 文件位置 | `tests/im_service/integration/test_users_conversations_api.py` 的 source JSONL assertions | rewrite-merge | 同一 API seam 改为 source agent/node；路径断言删除，新的 response assertion 防止字段复活。 | focused pytest |
| sidebar 选择与生成 draft | `chat-workspace.integration.test.tsx` 的 `source_jsonl_paths` draft assertion | rewrite-merge | 保留选择、scope、可见 distiller-command 预填与普通 composer 旅程；改断言为同 node identity request/no path。 | focused Vitest |
| capability failure 与普通 sidebar | 同一 `chat-workspace.integration.test.tsx` 的 distill mode journey | rewrite-merge | execution Agent 缺 distiller/required tools 时不创建或跳转新对话；normal mode 不显示 running/cross-node label。 | focused Vitest |
| 绑定的 stable identity | `tests/unit/personal_assistant/test_gateway_session_binder.py` | keep | conversation-to-kernel binding 仍是 Gateway local resolver 的前置保障，风险未变。 | focused pytest |
| typed relay 到 Gateway 的失败可见性 | 现有 relay/inbound coordinator tests | rewrite-merge | 以 canonical relay、Gateway local capability guard、normal failure reply 与 failed receipt 保护 action lifecycle，不以 adapter 私有调用次序建平行测试。 | focused pytest |
| IM 扫目录、私有 helper / lock、绝对路径 text | source-log resolution correction tests | delete | 已退役的实现而非当前行为；identity-only API、new source module 和 browser journey 分别替代真实风险。 | collection + focused suites |
