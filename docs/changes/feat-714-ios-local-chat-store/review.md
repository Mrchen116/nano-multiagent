# U1 实现审查

## Round 1 — REQUEST CHANGES（0 CRITICAL / 6 WARNING）

- Reviewer：独立非作者 `42a5c67d-5805-4598-b6d5-41ccd63bd851`；以下由 owner 串行归集其原结论。
- `validated_at`：`cc6e1572e01822093bfb57146d7d0864204ec7a9`。
- `executed_base`：`eeaea47921806936da20e78c9ed96167716f5037`（当时缓存 `origin/develop` 的 merge-base）。
- 范围：完整 33 文件 diff（+6430/-221）、首文档、完整 design/D12、Round 5 Gate 2、delta/current iOS spec、全部修改的实现与测试及相关调用者。原未跟踪 M1/mock 排除。
- 方法：只读静态代码/控制流与既有证据审查；未修改文件、构建、运行测试/模拟器/GUI/服务/网络或修改 Git。
- 配置：本轮人类明确批准用当前可用配置做独立审查；执行者使用当前 DSH 非作者 harness，工具不暴露/不可选择精确模型和推理档位，未声称使用原流程指定配置。仅适用于本轮批准的范围。

### Findings

各项均为 **confirmed 静态控制流缺陷**，并非审查者新执行的运行时复现。修复与新的运行证据、独立关闭结论另记，不能以作者自检关闭。

| ID | 严重度 | 受审位置 | 审查判断与影响 | 状态 |
|---|---|---|---|---|
| W1 | WARNING | `ChatStore.swift:259-283`；`NanoIMApp.swift:302-305`；`ConversationView.swift:172-175` | flush 先取走/清空 queuedDrafts，逐 ID await，无 D3 要求的单一等待链。F1 的 A/B 旧快照 await A 时，F2 可取走并提交新 B，F1 再看 queued B 为 nil，随后提交旧 B；重开恢复旧文本。现有测试只验证顺序仓储写，非 owner 竞态。另 `try?` 吞写错且消费队列，需保留可重试状态。 | open |
| W2 | WARNING | `ChatStorageController.swift:74-76,101-120,182-206` | move(nil) 先置 partition=nil，purge policy IO 失败时旧 openedPartition/activeRepository 仍在，但没有 partition purge intent。retryOpen 因 nil 返回；同 A 再登录走 close/reopen 而非重试 purge，重新首绘旧内容与 pending。相关时序变体：未开始的 purge 也可被同分区 activation 的 token 取代而跳过。必须在任何 seed 前补完明确清理意图。 | open |
| W3 | WARNING | `NanoIMApp.swift:138-146`；`ChatStorageController.swift:194-201` | 冷启 storedUser 已 disabled 时未注册分区，直接 purge 的新 controller 无 openedPartition/location，实际零清理。Session 已保存 disabled 凭据、AppModel purge 前崩溃的下次启动会落此路径；旧内容/请求仍可在重启用后恢复。需要显式目标分区 cleanup 与 owner 反例。 | open |
| W4 | WARNING | `ChatRepository.swift:922-947`；`ChatStore.swift:535-578` | 普通首次 60-of-many 的 next_before 只在内存；无 trim 的库被判完整。重启离线时缺少“更早内容需联网”的诚实提示/入口。不是强制保留某种 cursor，但必须持久保存不完整事实；仅 >300 trim 测试不足。 | open |
| W5 | WARNING | `SendAttemptStore.swift:35-39`；`SendAttemptsMigration.swift:20-25,58-59` | legacy 目录枚举任意失败都转 []，导入仍永久写成功 marker；临时 IO 恢复后也永不再导入，未确认请求虽原文件仍在却从本版本计数/UI/恢复消失。应区分真实不存在与枚举错误，错误可重试且不提交完成 marker。 | open |
| W6 | WARNING | `ConversationView.swift:58-69`；`ChatStore.swift:535-549` | 新条件在 items=[] 且无 error 时一直显示 Loading conversation。成功空消息页仍为空/online/no error，无“首个结果已完成”状态，合法新会话永久 spinner。需要区分未加载、离线无缓存与已确认空结果，补状态/视图回归。 | open |

### Delta 与有效结构

Reviewer 结论：**implementation-mismatch，不是 delta-mismatch**。delta 正确保留 local-first/offline、清理/隔离、冻结身份、零自动 POST、已清理请求不复活；不得将 W1–W5 写成可接受退化。W6 为额外引入的可观察缺陷。

已实现的主要结构包括准确 GRDB 7.12 pin、actor/queue、full-sync authority 与 seq/epoch、持久 discard IDs、库外 typed cleanup/SQL receipt、代际 handoff/只读 legacy、稳定 AppModel store 与无网络本地 bootstrap；这些正确结构不抵消六项遗漏。

### 既有证据与边界

- Reviewer 独立读取 `/tmp/feat714-policy-integration-a65d35a7a.log:509-871`：92 total / 91 pass / 1 明确真机属性 skip / 0 failures；核对 a65..cc6e 只改证据文档，产品/测试相同。未自行重跑。
- 独立读取 `/tmp/feat714-repeat-revoke-red-split.log:216-246` 的真实 3 tests / 6 assertion failures，以及最终日志对应的绿色反例；认可 recovery 文档保留两次编译失败/零执行测试和保护属性红测。
- backup 四路径断言实际运行；四条 complete protection 真机断言保留，模拟器明确 skip，属于诚实的边界适配，不是 finding。
- 当前七组不含 ChatPhaseTests/ChatStateTests/TimelineTests，不能视为最终完整 CI。最终版本原生在线→终止→离线旅程待验；旧 prime 失败不得复用为通过。真机飞行模式/保护属性、≥20 次首绘 p50/p95 仍 pending。
- 可选非阻塞建议：临时 fixture teardown 前关闭 repository/排空任务，减少 `vnode unlinked while in use` 日志；不将这些临时目录诊断夸大为产品库损坏。

## Owner disposition

六项均接收为待修复问题；先做定向反例与集中实现修复，再按资源协调运行，交同一独立 reviewer 复验受影响范围。当前完整 unit 未通过、未归档、未交付 PR。
