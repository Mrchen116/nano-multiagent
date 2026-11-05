# bugfix-713 独立 code review

## 范围

- 模式：full（Bugfix lite 唯一门禁）。
- 受审 diff：`005a36057..ce84855b3`（5 个 commit：投影恢复实现、fix.md 回填、插入顺序修正、未读水位会话限定、记录补充）。审查期间分支 head 前移，审查者按最终 HEAD 内容复核；本次记录的处置结论适用于 `ce84855b3`。
- 未纳入：工作区中用户自己的 `.gitignore` 修改与其他未跟踪文件（`.agents/skills/.usage.json`、`.pnpm-store/`、`:memory:`、`docs/research/...`、`packages/trajectory-ui/...`）。
- 审查者：与被审实现无关的独立静态审查者（独立 subagent，只读，不修改被审对象）。

## Findings

无 CONFIRMED / PLAUSIBLE 缺陷，结论 APPROVE。审查者按 CLAUDE 契约逐条核对了不变量 1-6，并复跑 `discarded-message-projection`（当时 5 passed）与 `messaging` / `chat-contracts`（8 passed）。

非阻塞观察与处置：

| 观察 | 处置 |
|---|---|
| 测试里 `broadcast` 是裸 spy，把广播移回事务内也会通过 | 已补：广播回调内记录 `db.isTransaction`、消息行是否已删除、tombstone 是否已存在，并断言 `open:false, row:false, tombstone:true`。已验证把广播移回事务内该用例失败（`open:true`）。 |
| 未覆盖「`last_read_message_id` 指向已丢弃消息」的回落分支 | 已补用例：读占位→丢弃→再来真实消息→再丢弃，断言真实未读保留（1 而不是 0）。 |
| 未在 HTTP 层断言附件名 / mention 预览回落 | 已补用例：附件名回落 `report.pdf`；mention 预览由剩余消息解析为 `@Carol please review`。 |
| `discard()` 对已不存在的行仍会写 tombstone（今天不可达，重放会增长 `conversation_events`） | 不改：调用方先经 `records.message(p.message_id)` 对已删消息 404，本 unit 保持该边界（fix.md 明确不做丢弃幂等改造）；为不可达路径增加返回值和分支属死代码。 |
| 每个参与者一次 `COUNT`，位于 `BEGIN IMMEDIATE` 内 | 接受：会话参与者数量级小，`messages_by_conversation` 索引可用。 |
| `gateway-relay.md:159` 还要求同事务删除 message-scoped 过程事件 | 本 unit 明确不做，已在 fix.md 的「未做」段落记录并给出核对结论，verifier 不应读成回归。 |

## 结论

APPROVE。上表三项已补的用例只增测试、不改产品行为；`discard()` 签名与过程事件清理保持原边界，因此不需要针对产品行为的复审。
