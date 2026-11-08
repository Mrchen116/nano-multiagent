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

## Round 2 — REQUEST CHANGES（0 CRITICAL / 2 WARNING）

- 同一独立非作者 reviewer 对六项做集中 closure + 实际修复 delta review，不是新全量审查；owner 串行归集。
- `validated_at`：`7bce604c12ff130973ed42d4eed97bc11ac8b1aa`；`executed_base` 不变。增量 `cc6e1572e..7bce604c1`，15 files / +568/-90，连同真实调用者审查。
- 方法、当前可用配置与排除项沿用 Round 1；reviewer 全程只读，无构建、测试、设备、GUI、服务、模型、网络、文件或 Git 操作，也未启动后台作业。

### Closure disposition

| ID | 独立判断 | 决定性依据 |
|---|---|---|
| W1 | **still_open，部分修复** | flush-vs-flush 单链和失败保留已修，但真实 `send` 未进入等待链，旧 flush 仍能在 pending 事务删除 draft 后回写。详见下表。 |
| W2 | **still_open，部分修复** | 同 controller 的 failed purge / nil retry / superseded intent 已修；真实切 origin 路径会丢弃唯一 retained intent。详见下表。 |
| W3 | **closed** | AppModel disabled publish / 冷启显式传目标分区，fresh controller 无须曾打开即可清理。`AppLocalBootstrapTests.swift:81-115` 真实旧 pending、legacy 原字节、零 HTTP、reenable 不复活回归；green log:630-631。 |
| W4 | **closed** | 完整分页的不完整事实与页内容同事务持久化；普通小于 trim 阈值的分页可跨 reopen 恢复，sparse append 不标完整，terminal page 与独立 trim 状态相容。repo:484-517,955-963；store:626-639,1000-1003；green log:740-741,776-777。 |
| W5 | **closed** | 枚举仅真实 missing 接受空；ENOTDIR / IO 退出导入事务不写 marker，DecodingError 才逐文件 rejected。真实恢复 fixture 保留 frozen body 和 legacy 原字节；green log:768-771。 |
| W6 | **closed，仅代码/状态层** | 成功空页有首结果完成状态，View 显示 No messages yet，未加载/离线无缓存分开；held→empty→reset→offline 回归 green log:744-745。**真实画面/操作仍 pending**。 |

以上 green 定位均指 `/tmp/feat714-review-fixes-7d7e455aa.log`。Round 1 表保留当时 open 的历史判断，以本轮 disposition 为当前关闭结果。

### 存活 findings（CONFIRMED 静态控制流）

| ID | 严重度 | 决定性位置与 failure_scenario | 状态 |
|---|---|---|---|
| W1 | WARNING | `ChatStore.swift:310-318,821-843,1015-1020`，`ChatRepository.swift:586-598`。F1 取走 A=a0/B=b0 并停在写 A；真实 send B 不等 tail，pending insert + DELETE draft 后 owner 置 `drafts[B]=""`、queued nil；F1 恢复处理 B 时 guard 仍成立，又写回 b0，重开形成 frozen pending 与旧 draft 双份。design D3:120-123 已要求发送前 flush 与单链。原两条新测试只覆盖 flush-vs-flush / 写失败，未覆盖此 caller。 | open |
| W2 | WARNING | `ChatStorageController.swift:35,202-204,215-232`，`NanoIMApp.swift:177-189`，`ChatAttemptPersistence.swift:140-145`。A 的 purge 在 policy write 前发生可恢复 IO 故障，requiredPurges 只在原 controller；authenticate 无条件替换 controller。故障恢复后返回原 origin，同账号可从无 purge fence 的旧库 seed 内容与 pending。D12:318 要求保留可重试意图并向 caller 报错，不能丢掉唯一 intent。原三个新 controller 回归均复用同一实例，不能反证此路径。 | open |

### 证据审计、delta 与剩余验证

- 独立读取 baseline-compatible RED 的 raw log:685-744、manifest 和精确 patch，确认 10 tests / 26 assertion failures / 0 unexpected；compile adapters 与合法排序披露准确，**不是纯 cc6 head**。后来的增强 fixture 新断言不能冒称已逐条 RED；:745-746 的 diagnostics utility 72 未混作断言根因。
- 独立读取 green log:627-997 与 summary，确认 **102 total = 101 passed + 1 explicit physical-device protection skip / 0 failed / TEST SUCCEEDED**；7d7e..validated_at 只改证据文档，产品/测试证据有效，不覆盖上述两个 caller 变体。
- hosted XCTest 同 bundle 安装更新与正常 sandbox 写入、旧 51396 refresh 失败、自有设备 Shutdown 的边界披露准确；不得宣传零网络尝试或不碰 sandbox。临时 fixture vnode-unlinked 仍为非阻塞 teardown 建议，不夸成产品库损坏。
- **no spec delta；corrected-delta result 仍为 implementation-mismatch（W1/W2），不是 delta-mismatch**。未受影响原判断保留；不降低 spec/design/delta 合理化存活问题。
- 最终原生在线→终止→离线、成功空会话真实画面、真机 flight/protection、≥20 次首绘 p50/p95 与完整 CI 仍 pending（七组未含 ChatPhase/ChatState/Timeline 等）。本轮不批准实现 closure，不宣布完整 unit/M1/M2 通过。

Owner 接收两项剩余真实 caller 缺陷，先集中补 owner 回归与实现，再冻结交同一 reviewer 一次 closure；旧版本 Journey build 已取消，未拿旧构建运行旅程。

## Round 3 — W1/W2 CLOSED；REQUEST CHANGES（0 CRITICAL / 1 WARNING，仅 fixture）

- 同一独立非作者 reviewer 集中关闭 W1/W2，并核对实际小增量 caller/delta；不是新全量审查。
- `validated_at`：`8a668d7c2175050a6f2739e5036c8aad9764d04b`；`executed_base` 仍 `eeaea4792`。增量 `7bce604c1..8a668d7c2`，9 files / +200/-18；tracked clean，原 M1/mock untracked 排除。
- 实际配置与只读边界沿用本轮批准的非作者 DSH 配置；不声称可选择精确模型/effort。无文件/Git修改或构建、测试、sim/设备、GUI、服务、网络、模型、子作业操作。

| ID | 独立判断 | 决定性依据 |
|---|---|---|
| W1 | **closed** | `ChatStore.swift:1007-1034` 的真实 persistAttempt 先 flush，再捕获当时最新 tail，把 pending transaction 自身接链；以后 flush 排在其后，先进入的新 flush 被一起等待。冻结请求不因等待重建，owner/session/context/epoch/projection/repository/权限检查仍在，失败不推进 POST。`ChatRepository.swift:586-601` 与 RAM 仅消费匹配普通文本，newer draft/interaction composer 独立。真实 held A/B→send 的 RED 复现 premature POST + b0回写，修后 log:547-548 PASS；事务新增回归 :589-590 PASS。 |
| W2 | **closed** | `ChatStorageController.swift:88-95` 明确报告全部 retained purge/物理 close 完成；`NanoIMApp.swift:177-191` 失败 guard 早于 generation/client/storage replacement，保留唯一 intent owner、恢复原 observer并向认证界面报错。恢复后同 origin login 由同 controller retry-before-seed。新 owner 反例 RED 的两 identity 断言实际失败，补验 log:213-214 PASS；URL等价误判与后续EPERM未伪称通过。其它 purge caller 不替换 controller，忽略返回值不丢 intent。 |

W1 的 green 定位指 `/tmp/feat714-review-round2-green.log`；W2 补验指 `/tmp/feat714-review-round2-owner-recheck.log`。W3–W5 保留 Round 2 closed，W6 保留代码/状态层 closed、真实画面待验。**产品 live findings=[]；本轮增量 live findings=[W7 fixture WARNING]**。本节使用 reviewer 吸收最新 App6 与 hook-order 证据后的最终集中报告，取代其先前未吸收更新的临时报送，不重开已关闭产品问题。

### W7 — WARNING / CONFIRMED：fixture 删除顺序仍错误

- 受审 `AppLocalBootstrapTests.swift:15-22` 把 signOut 放 async tearDown，却仍在同步 tearDownWithError 删除 root。Reviewer 独立读取安装 SDK 公开 `XCTest.framework/Headers/XCAbstractTest.h:118-134`：同步 error hook 在同步 tearDown 后，async teardown 在两者之后。因此实际为 **remove root → async signOut/purge**，不是注释所述的预清理。
- 测试结束仍有 repository 或 enabled session publish 时，可先 unlink 活跃 SQLite，再由 async hook 清理；最新 App6 PASS 的 log:220-225 仍有临时 fixture vnode-unlinked，与错误顺序一致，但不证明 EPERM 全部根因或产品库损坏。
- 必须把目录删除与 await signOut/drain 移到同一个 async teardown，直接按代码顺序表达，移除竞争的同步 remove hook。不得吞 EPERM、sleep、扩大 timeout 或删除内容断言。Owner 已接收，集中修正后只补 App 组并交原 reviewer 关闭。

### 证据与 delta 裁决

- Reviewer 独立核对原产品直接加入两反例的 **2 tests / 4 assertion failures / 0 unexpected**，无 compatibility adapters；附加事务测试未单独声称 RED。
- Reviewer 独立读取首次修后七组 **105 total / 1 skip / 1 assertion failure / 0 unexpected，整体失败**；仅非 App 的六组 **99 total = 98 pass + 1 skip / 0 failures** 可复用。又核对 App6 补验的新 origin 已 pass、旧 same-account teardown 真实 EPERM / 1 unexpected，不将其归成产品损坏或默认已修。
- Reviewer 已独立读取 `/tmp/feat714-app-fixture-8a668d7c2.log:213-242`：**App6 / 0 failures / 0 unexpected / TEST SUCCEEDED**，新 origin 与旧 same-account 都通过。因此“最后 fixture 未 typecheck/XCTest”缺口现已关闭；可以复用产品未变的后六组 + App6 定向补验，不改写前两次失败或声称七组同次 clean green。此 PASS 不反证 SDK 明确的 W7 hook 顺序，也不证明 EPERM 全部根因已闭合。
- **no spec delta；本次受影响契约 corrected-delta = aligned**。D3 单链/冻结转移、D12显式失败/保留重试、readonly legacy、policy/handoff、零自动 POST 与隔离/撤权均未放宽。未重审未变全 unit，不重置已有效判断。
- 本轮裁决是 **W1/W2 独立产品代码 closure、唯一新必须修项 W7**，不能无条件批准整个受审增量；不是七组单次全绿、fixture 根因全部已证、完整 Gate/unit/M1/M2 或原生体验通过。最终原生在线→终止→离线、成功空会话画面、真机 flight/protection、20 次首绘 p50/p95 与完整 CI 仍需对应证据；两次旧失败与取消 Journey build 保留。

## Round 4 — W7 CLOSED / 本次 closure APPROVED（0 CRITICAL / 0 WARNING）

- 同一 reviewer 只集中关闭 W7，未重审已关闭 W1–W6 或全 unit。`validated_at`：`01f34d32ec74acdbfddd94f93389d4813b2721df`；`executed_base` 仍 `eeaea4792`；增量 `8a668d7c2..01f34d32e`，3 files / +42/-2。确认整个 NanoIM 产品、UITests、project diff 为空，tracked clean，原 mock 排除。
- 配置与只读方法沿用：未改文件/Git，未运行构建、测试、设备/sim、GUI、服务、模型、网络或子作业，不声称可选择精确模型/effort。
- **W7 closed**：`AppLocalBootstrapTests.swift:15-23` 在同一个 async teardown 内 await 合成 owner signOut/控制器 purge，再释放引用，最后 throwing remove 自己的 root；同步 remove hook 已移除，顺序不再依赖 SDK 反证的跨 hook 假设。没有产品修改、host 目录修理、sleep、吞错、timeout/范围/内容断言变动。
- Reviewer 独立读取 `/tmp/feat714-app-fixture-ordered.log:294-322`：**App6 / 0 failures / 0 unexpected / TEST SUCCEEDED**，新 origin 与旧 same-account 均 pass；对整份 log 独立搜索未见 vnode-unlinked、EPERM、Operation not permitted、TEST FAILED、error。该实际结果关闭 W7 确切顺序缺陷，不宣称旧 EPERM 全部根因已唯一证明或所有潜在竞态永久消失。
- 先前 URL 等价断言、真实 EPERM 和 8a App6 虽 pass 仍有 vnode 的历史均忠实保留；本次是 App6 定向验证，不是七组同次全绿。未变产品的其余六组 99 total / 1 skip / 0 failures 依原版本映射复用，不因 reviewer 交接重跑。
- **live findings=[]；no spec delta；此前产品契约 aligned 判断保持。** 本次 W7 closure 增量可批准，W1–W6 关闭判断保持；不把这一窄批准扩大成全 unit/Gate/M1/M2、UI、真机或性能验收。Journey 的前置构建和首次 IM 配置失败不是 prime/offline 证据；真实旅程、成功空会话 UI、真机 flight/protection、20 次首绘统计、完整 CI 按各自后续证据判断。

## Round 5 — 同 fixture UITest/helper 窄增量 APPROVED（0 CRITICAL / 0 WARNING）

- 同一独立非作者 reviewer 只审 `adfe4d4ce..da47a48e5` 的2文件/+24，`validated_at=da47a48e5a30ece2364a968d427b3a5e48cb10bc`；产品与project diff为空，tracked clean，原mock排除。配置/只读边界沿用，无测试/构建/设备/GUI/服务/网络/模型/文件或Git修改，不重审已关闭问题/全unit。
- 独立读取原/新private输入、原失败AX全文并逐字符核实：73字符唯一index8 U+0027→U+2019，新预期与原AX全文相等，旧输入和FAIL保留。完整正文CONTAINS、目标会话、真实用户名密码登录、online15秒/offline5秒与terminate路径不变；不是短关键词、server改文或追认旧FAIL通过。
- 显式opt-in reset仅prime调用，offline不调用；Me存在→精确fixture用户名→公开Sign out→确认的顺序成立。SDK公开 `XCTestCase.h:136-148` 与现有 `continueAfterFailure=false` 证明身份断言失败立即停止，不会继续签出未知账号。无erase/delete/Keychain注入/内部store调用；正常签出清缓存后仍需真实API重新prime。
- `app.sheets.buttons["Sign out"]` 的实际AX定位仅可由后续运行验证，reviewer没有把静态源码当运行PASS。原 `online.log:123-131` 的1 test/1 assertion failure/0 unexpected及offline未执行保留；reviewer未核并行build与未来运行。
- **findings=[]，no spec delta，窄fixture审查通过**，W1–W7关闭判断保持。不是两阶段旅程、成功空会话UI、真机flight/protection、20次统计、完整CI或unit验收通过。
