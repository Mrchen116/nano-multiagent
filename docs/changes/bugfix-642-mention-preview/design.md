# bugfix-642: As-built Design

本文在实现完成后整理，未补造事前设计流程。

## 实现范围与数据流

Base: `b6db5d02345b63691d6198ea3abe63c17a353e4e`。

`Messaging.conversation` 复用原有按会话、last_message_at、rowid 选择最后消息的系统通知查询，同时读取完整 content。用当前参与者字典把完整 mention 转为 `@人名`，未知成员保持 `@unknown`，随后限制为 120 字符；空正文仍回退到已存储附件预览。Web 与原生消费者继续使用原有字段。数据库 schema、写入、正文和实时事件保持原样。

修复在读取投影完成：已有截断预览和 fork 会话无需迁移或重新发消息即可恢复，也不会增加每会话查询数量。现有通知字段复用同一条消息结果。

## 验证

- 新增 messaging 回归先红：实际收到第二个 target_id 中途被截断的原始标签；修后通过。
- `pnpm exec vitest run apps/im-server/tests/messaging.test.ts apps/im-server/tests/message-attempts.test.ts apps/im-server/tests/e2e/system-notices.test.ts`：3 files / 12 tests 通过。
- 前端 sidebar、mention parser、global message toast：3 files / 47 tests 通过。
- `pnpm --filter @nano/im-server typecheck`、`git diff --check` 通过。
- 独立本地 IM + Vite，真实浏览器登录并刷新会话，列表和正文均显示两个完整人名；DOM 无原始标签。一次性截图：worktree `output/mention-preview/verified.png`，不提交。
- 独立静态审查见 `code-review.md`。未执行全仓 CI，未作线上验证；用户验收待完成。

## 风险与回滚

API 预览由 wire 文本变为可读文本；消费者仍接受字符串。正文存储不变，无数据迁移；回滚此提交恢复旧投影。

## Canonical 文档影响

最窄 delta 见 `specs/im/web-chat-ux.md`；待用户验收及快修收尾时归并。
