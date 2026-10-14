# perf-609: Code Review

## Review scope

- Base / executed_base: `247ae97ae358b66d7637b1cdfd5f910bf1a06cc9`。
- Review mode: `full`。
- Branch: `codex/compact-tool-references`。
- Included dirty files: 本分支对 base 的全部 diff，包括本 unit 文档及 `packages/personal-assistant/{src,tests}`、`packages/dsh-integration/{src,tests}` 中本次修改；原 main 的 dirty/untracked 未复制。
- validated_at / Head: `f50e958b2dcb63efa5e90eba324776f013cdf3c0`。

## Round 1

- Status: 1 个 CONFIRMED P2，已由主 Agent 修复，待 closure。
- Reviewer: 独立 `review_compact_references`，`gpt-6.1-sol/high`，使用 `change-code-review`。
- Finding: `global-agent.ts` 的 Inbox 图片来源按 URL 单独 `.find`。同一页两条消息复用图片 URL 时都返回第一条 messageId；reviewer 用真实 NodeStore/InboxStore/GlobalAgent 复现。
- Resolution: 内部 `inbox.image` RPC 同时携带页面中的 message_id 和 URL，宿主仅从已保存页面匹配二者。补充同页复用图片的两条消息及伪造 message_id 拒绝回归；不更改模型工具参数。
- Reviewer checks: 4 相关测试文件 / 40 测试通过；`git diff --check` 通过。
- 自动化：完整构建、类型检查及 83 文件 / 312 测试已通过。
- 补充门禁：56 Python 测试通过（31 e2e deselected），docs-check（235 maintained sources / 64 required routes）通过，ruff check / format 通过，安装包候选构建通过但未发布。

## Closure

- 用户实际验收：未确认；保持 active。
- 未执行生产部署、真实飞书发送或 UI 实机验收。
- 审查和适用门禁完成后记录结果；用户确认后再归并 canonical 与归档。
