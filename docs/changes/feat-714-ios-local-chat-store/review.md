# U1 实现审查

> 当前执行范围见[用户最新模拟器限定](M1-local-first-paint/recovery-validation.md#当前执行范围用户更正后仅模拟器)。以下各轮判断、拒绝和pending按当时事实保留；旧“未答／权限暂停”已被新澄清取代，真机项本轮UNVERIFIED/不执行且非模拟器交付门禁，不由此冒称通过或重开已关闭代码finding。

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

## Round 6 — 指定两阶段路径独立产物审查 PASS（产品旅程 / 限定体验，0C/0W）

- 原非作者reviewer加载 `product-journey-review` + `frontend-experience-review`，先独立read_image实际四图，再核raw log、attachment manifest、runner与binary App Info.plist；未修改文件/Git或启动任何构建/测试/设备/sim/GUI/服务/网络/模型/子作业，不是作者自检复述或全unit代码重审。
- `validated_at=1b62810227a0df8bb3233fbb0113d3ea8c550556`；实际受测`da47a48e5`，两者只有docs/+33、产品/UITests/project diff为空，tracked clean、原mock排除。独立核build log:255成功、binary bundle win.nanoim.ios/revision da47a48e5、两条raw命令指同runner/557UDID。旧journey-manifest.json是01f首轮产物，不冒充本轮；本轮由新raw命令、runner、build metadata及各attachments manifest交叉归属。
- **指定旅程PASS**：真实公开签出合成身份→真实用户名/密码登录→API列表/完整73字消息→terminate→owner只停原53703 IM→同bundle新PID冷启→5秒列表/全文谓词通过且无登录页→terminate。独立读取 online-reprime.log:64-148 和 offline-reprime.log:25-54，均1 test/0 failures/0 unexpected/exit0；offline未调用prime专用reset。服务停止/PID消失/connect61及收尾Shutdown依据owner当时工具回执复用，reviewer没有伪称自己事后实时探测。
- **限定体验PASS**：独立看同runtime四张实际命名附件（详见recovery-validation截图表）：online列表会话名/预览/时间可辨，timeline完整正文三行无截断遮挡；offline同内容保留，列表和timeline都有“Offline. Retrying · Updated 03:12”，timeline另有真实connection error。错误未挡住正文、未把离线谎称同步成功，用户可进入和阅读全文。重复反馈的风格合并是可选取舍，不在本场景列阻塞finding。并非只因测试绿或控件存在而推体验成立。
- **findings=[] / 0C0W**；只覆盖同fixture单会话单完整工作消息的停止origin跨进程阅读。保留旧729 FAIL/offline当时未执行历史；不证明第一帧无白屏/闪回、从图标到首绘耗时/20次p50p95、滚动/大窗口分页、网络恢复、空会话、发送/撤权全契约、真机flight/protection、完整CI或最终unit交付。原始log中的launch measurement warning也不是性能测量。其余缺口继续按独立证据处理。

## Round 7 — 日期/测量边界/空会话测试最小增量静态 APPROVED（0C/0W）

- 原非作者仅审 `1b6281022..b66289f3c08da896a2dec643aa250a07a08b8d53`，6 files/+49/-4；加载change-code-review与performance-review。只读源码、相关caller、既有原始log与文档，无新build/test/设备/服务/网络/模型/文件或Git写入；不重审全unit与已closed W1–W7。
- 日期修正正确使用传入now及同calendar比较当天、按calendar day减一天判断昨天，不用固定秒数，保留原HH:mm/Yesterday/旧日期文案。原RED及断言保留，新增精确昨天/older断言；不是把fixture改到host当天。默认真实caller仍用当前Date/Calendar.current。
- repository bootstrapSeed在函数体入口begin、defer end、唯一signpostID，覆盖controller首次seed及store后续seed。包含coordinated锁获取、policy读取/必要补应用、GRDB读取及DTO组装；不含进入actor前排队、open/migrate/legacy导入、UI发布/首帧或网络。与controller.open及旧store span存在包含关系，不能相加；后续需区分首次/后续、成功/失败，不能把失败短span当成功首绘。静态测量边界通过，性能目标仍UNVERIFIED。
- 新空会话UITest以正常登录fixture为前置，从真实列表进入专用title，正向等待既有conversation.empty，再核目标navigation title、无loading、capture与terminate，未改prime/offline全文、目标或timeout，无内部store/SQL注入。View仅成功empty状态提供该ID；静态通过不证明AX实际命中或真实画面。
- 独立核对原完整scheme175=169pass+5failedTests+1skip，保留TEST FAILED；4条WebKit缺资源控制流与既有build.sh生成前置相符，不能在修后运行前关闭。原da47四图/两阶段历史PASS可复用为当时指定路径证据，不冒称b662新实测，不验证空会话/性能/完整CI。
- **findings=[] / no spec delta / aligned**。本次仅窄代码与测量设计APPROVED；后续运行结果由owner另记，不把静态审查扩大为全unit交付。

## Round 8 — 成功空会话与完整native运行证据独立审查 PASS（0C/0W）

- 原非作者加载product-journey-review + frontend-experience-review，先实际read_image原始空会话图，再核rawlog/manifest/runner/build metadata/full测试summary；全程只读，无build/test/sim/设备/GUI/服务/网络/模型/文件或Git写入。`validated_at=089d58db54632b97ee7293e129d8fae883a69433`，b662→该head仅docs/+21，产品UITest实际b662，binaryInfo bundle/revision独立核实。
- **指定成功空会话旅程与限定体验PASS**：同53703/557、真实已有登录session、专用Release planning/c_drj7ef6y，正常API seed前置按owner receipt复用；runner无reset。empty-b662.log:22-60真实列表→进入→empty正向→标题→无loading→截图→terminate，1test/0fail/0unexpected/9.295s，不把test总时长当渲染耗时。实际原图与attachment manifest归属一致；标题与No messages yet清晰、无spinner或离线/需要连接占位、输入区保留，用户能分辨成功空结果而非仍等待。**W6真实画面pending关闭**，不只是静止截图猜导航或由绿test推体验；未扩为空会话发送/离线等其它场景。
- 独立核51条affected实际0fail、原4WebKit身份均PASS；full-assets summary **175=174pass+1physicalskip+0fail / Passed**，raw580-658对应XCTest148含1skip、SwiftTesting27pass。原日期及四WebKit身份亦在full实际PASS，唯一skip明确需要physical fileProtection。关闭前轮对应修后运行缺口，不改写首次full真实FAIL，不把skip变pass。
- 本批stop/PIDgone/connect61/557Shutdown复用owner当时receipt，不伪称reviewer实时操作。da47两阶段历史限定PASS保持；系统diagnostics warning没有被描述为不存在。
- **findings=[] / 0C0W / no spec delta**。本轮仅新增证据审查，不重审全unit、不重开W1–W7；旧构建升级与M2其它真实客户端矩阵、真机flight/protection/20次trace、Release与其它仓库CI、最终unit门禁/归并/归档/PR仍各自待证，不因本次PASS全部关闭。

## Round 9 — Membership UITest/helper静态窄审；async fail-fast论断后被实跑撤回

- 原非作者加载change-code-review，只读审`089d58db5..b18edba2b13e56c6e36ab93fc90537fc8fee5bd9`，3files/+84（UITest+68、docs+16），产品/project未变，当前可用非作者配置/无资源边界沿用。不重审全unit或已closed问题。
- 原静态结论APPROVED0C/0W：正常PATCH/DELETE真实API与membership发布契约吻合，A非creator/另合成operator有write前置正确；ID限ASCII字母数字下划线、http/127.0.0.1/显式port、专用Authorization token；async URLSession让出actor；完整正文/目标/15秒和5秒未弱化，无内部store/SQL/cache注入。阶段必须在线真实成功并terminate后再停止origin做offline，不以test排序假定前置。
- 原reviewer明确限定：静态通过不能证明新旅程PASS、每帧不闪回/≤1RTT/无瞬间重排或准确归因WebSocket而非其它sync。M2运行缺口仍pending。
- **实跑更正（已回到原reviewer且其明确接受）**：b18 online exit65在rename断言失败后仍继续后续操作，原报告「continueAfterFailure=false使async guard/assertion失败立即结束、不继续外发」论断撤回；不得再用该断言作为已证控制边界。原报告保留历史，但当前判定为online FAIL、offline未执行，失败后步骤不计有效验收。需要显式guard/throw，修后独立复核另记。详见[M2运行与RED证据](M2-partition-revocation/recovery-validation.md)。

## Round 10 — 可见detail修正与显式async边界窄审 REQUEST CHANGES（0C/1W）

- 原非作者只读审b18..1441ea83共6files/+70/-16；原rename路径根因与测试吻合，同ID/nil边界及async显式guard→XCTFail→throw、try传播/defer terminate静态通过，不再依赖continueAfterFailure。正文与超时未放宽；真实FAIL与offline未跑如实保留。
- **W8 CONFIRMED（静态）**：新增共享persistConversation的inspected同步也接受迟到/read旧DTO。membership成功不推进同代projectionRevision/snapshotSeq，旧/read仍过guard，将刚Renamed的可见detail回退Original。需正确发布边界及hold/read交错保护。此时65条修后测试绿不能关闭未覆盖竞态。

## Round 11 — W8集中代码closure APPROVED（0C/0W），runtime待证

- 同原非作者加载change-code-review，只读核`1441ea83..cf6869499c6e793f18ff45fd5c06e3112dfc093f`，2files/+16/-3；无build/test/服务/设备/GUI/网络/模型/jobs/文件或Git写入。不重审其它unit或已closed项。
- persistConversation恢复只处理原持久化/list投影；verifyAccess在权威GET成功、落库且第二次isCurrent通过后，仅对同ID inspected发布，赋值到清checking之间无await。其它目标或nil不覆盖/创建，inspectConversation原发布不变。因此保留rename校正且切断本次新增late/read detail回退。
- 既有rename测试保留全部原断言，新增真实markRead挂起旧/read→membership→release/await→detail仍Renamed，并查read_state=m3避免靠跳过boundary凑绿。复用hold seam，未删断言/扩大timeout/改生产API。独立核原RED日志295-303唯一late/read detail断言失败，1test/1failure/0unexpected，TEST FAILED保留；diagnostics utility72在测试后。
- **W8代码层CLOSED，findings=[]，no spec delta，corrected-delta aligned**。仅关闭新增可见detail回退，不宣称既有/read对list/持久化DTO语义或所有同代元数据竞态已解决。1441 async显式边界静态结论沿用；修后GREEN、invalid-token实际fail-fast、正常membership+offline在此轮尚待统一证据，不能据此称全unit或当前head全量通过。

## Round 12 — Membership实际功能/失败边界与W9撤权画面closure，限定PASS（0C/0W）

- 原非作者加载product-journey-review、frontend-experience-review、change-code-review，先独立read_image cf686的四张online与一张offline实际原图，再核三rawlog/summary、runner/manifest、无secret正常API前后状态receipt、65GREEN及95923 delta；后补独立read_image新版撤权图和对应连续log。全程只读，无build/test/sim/设备/GUI/网络/服务/model/jobs/文件或Git写入。
- cf686 before/after标题改名、全文/Morgan Review/时间清晰且采样位置稳定；online:30-69从列表真实进入/全文→PATCH→新标题全文→DELETE→撤权正文隐藏→返回列表无该群→terminate，1pass/0fail/0unexpected。正常API receipt title revised/两成员/A_access404支持真实撤权，不是内部store注入。offline:23-37新进程冷启→5秒其它Product launch正向/无登录/无revoked title及正文→截图→terminate，1pass/0fail；图中另两会话保留且Offline.Retrying/Updated明确。停服/PIDgone/connect61/Shutdown复用owner当时receipt，不伪称reviewer实时探测或真机flight。
- invalid与valid冻结runner唯一值差异为operator token。invalid真实进群/全文/before图后:40HTTP状态guard失败，:41terminate、:42teardown，未进入rename谓词/后续capture/撤权等待；summary确1failed/0passed/Failed，保留unexpected restart和diagnostics72。结合显式throw与状态receipt原title/三成员仍在，**预期失败控制边界成立**；不洗成测试绿，不声称包级网络审计证实零DELETE。W8增强交错实PASS及65/0/0原log独立核实，运行缺口关闭；同log仍有未致失败vnode/diskIO fixture diagnostics，不描述为没有或据此定性产品DB坏。
- **W9 WARNING/CONFIRMED（cf686实图）**：撤权详情同时给不可访问与连接后自动读取/Retry，误导用户做无法恢复资格的动作，属于状态语义冲突非纯风格。95923静态fix排除revoked通用empty分支、保留专用撤权和正常未revoked分支，两条requireFixture新增负断言不弱化原目标/正文/超时；静态0C0W/no spec delta，但当时仍画面pending。
- 后补95923实际closure：独立read_image `membership-online-95923-attachments/1A2F862B-D38C-4C68-8D33-A4189AD9D97A.png`确认正文、中央错误连接/自动加载建议与Retry消失，专用撤权说明/返回可达保留。另核raw28-69真实完整路径和两新判据，71-85为1/0/0/成功，summary/manifest同557/同test/同原图。build339成功，实际Info与fresh runner独立核win.nanoim.ios/95923c3f5/同53703；不伪称已推进的Products仍cf686。**W9体验CLOSED；指定旅程与限定体验PASS，当前范围findings=[] / 0C0W。** 原cf686体验FAIL保留。
- cf686 offline证据对95923继续有效：唯一产品修正只影响revoked detail空态，未改storage/tombstone/list/relaunch，offline不打开detail；不要求重复不相关矩阵。未证明全程每帧无瞬闪/≤1RTT，不关闭账号/服务/真实401/离线期间撤权/旧升级/物理保护/性能/其它CI或最终unit门禁。

## Round 13 — 真实pending/升级UITest静态窄审APPROVED（0C/0W），未运行

- 原非作者加载change-code-review，只读核95923..69ca74061，UITest+119及两docs共3files/+134/-6；产品不变，tracked clean/原mock不动。无build/test/parse/sim/设备/GUI/网络/服务/model/jobs/文件或Git写入。
- 停服握手在run marker前同URL /health200并限定http/127.0.0.1/显式port；run ID硬校验、FileHandle直接stdout，随后截止时间/取消检查/200ms让出，仅cannotConnectToHost或networkConnectionLost才成功，不把HTTP500/其它响应或timeout当停服。未证不可达就throw、不按Send；host只停自有PID/argv须另有实际receipt。
- 四phase真实UI操作，无内部store/JSON/cache注入，目标/全文/超时未弱化、requireFixture显式throw与defer terminate；optional reset需显式opt-in、精确旧fixture身份匹配、正常退出+确认硬guard。no spec delta/corrected-delta aligned，findings=[]。
- 此为静态批准，不证明typecheck/运行/迁移通过。需原旧JSON真实非空、同bundle不卸载/container保留、实际App版本、离线完整画面、联网前零新消息和显式Retry唯一等证据。测试负断言仅无指定title、CONTAINS计数不替代全屏/精确SQL与JSON审计；pending可见不证明零messages POST；纯文字仅覆盖附件空集合。实际运行因随后权限拒绝而未开始，见M1记录，未降低原M1⑤前置。

## Round 14 — 独立剩余矩阵fixture静态审REQUEST CHANGES（0C/1W）

- 同原非作者加载change-code-review，只读审`4dc09fcb6..92fb1218bfcf629b738b5de7ec6cef2232af200f`，3files/+94；产品未改，未重开任何原closed。无build/test/parse/服务/设备/GUI/网络/model/jobs/文件或Git写入。
- **W10 WARNING/CONFIRMED（静态）**：active401方法Home后直接activate，没有拒绝原App已结束。安装SDK公开XCUIApplication.h:65-72规定activate在not-running时会自动launch，故可能用冷启bootstrap拒绝替代已显示正文后的同进程清理。需激活前明确仍运行的有界失败边界，并由实际产物核PID连续；仅激活后foreground状态不足。
- 其余新增控制流静态通过：read-existing保留完整目标/nav/body；cold-convergence保留retained正向→15秒异步absent→retained/无登录/无降级/无正文，且不tap目标/不pullrefresh；依赖前阶段真offline全文、host在App停态DELETE及App首个/sync产物，源码absent本身不证明缓存前置或活跃重连30s。credential control helper先独立token `/auth/me`200→run-bound marker→只接受401，有界/错误或取消传播，不冒充App refresh401；共享登录断言不调用reset/signOut。no spec delta/corrected-delta aligned。
- 原非作者独立核完整native summary175=174pass+1physicalskip/0fail、raw720-798的XCTest148含1skip/0fail/0unexpected+Swift27pass/TEST SUCCEEDED及Release原log2182成功，均只归产品4dc，不代替新UI运行。
- 运行状态明确**尚未开始／当前权限阻塞**：临时observer write被拒，无服务/API/DB动作；准备与静态审不构成复用DB/port或启动/观察服务的许可。owner W10最小guard修正待集中closure，不因此运行被暂停矩阵。

## Round 15 — W10静态CLOSED / 窄增量APPROVED（0C/0W）

- 同原非作者加载change-code-review，只读核`92fb1218b..d0eb4c825b5fe2500cee345ac08e76fcdd7037ef`的3files/+20/-1；UITest仅新增9行，产品不变、tracked clean、原mock未动。独立核diff、实际源码与安装SDK公开state枚举；无文件/Git写入或build/test/parse/服务/设备/GUI/网络/model/jobs操作。
- **W10静态CLOSED，findings=[]**：协调后先硬guard原App仍runningForeground；Home后只接受公开runningBackground/runningBackgroundSuspended，5秒有界XCTWaiter必须completed否则throw；activate前再次硬guard仍在这两个运行态。guard到activate之间无await，不再靠activate后的foreground状态反推未重启。完整正文、15秒收敛/20秒登录判据及旧helper未改。
- 公开state为异步观察，不是PID身份receipt。真实同进程401仍须运行产物证明PID连续、App自身request/refresh401、purge及重开；静态closure不称这些已通过。随后owner独立build-only实际通过当前d0eb最后guard，见[M2运行证据](M2-partition-revocation/recovery-validation.md)，不是reviewer执行或真实UI通过。
- **no spec delta / corrected-delta aligned；本次窄静态APPROVED0C/0W**。两次实际权限拒绝及整组暂停保持；人类未答不是许可，不复用/换工具重试、不重开其它closed，不扩大为全unit或最终门禁PASS。跨包CI真实失败与隔离单例未复现的边界另见[M1证据](M1-local-first-paint/recovery-validation.md)。

## Round 16 — 升级前三段独立证据复核：各自限定PASS，整体仍PENDING

- 原非作者 `42a5c67d-5805-4598-b6d5-41ccd63bd851`只读核本次三张原始image、三组脱敏log/summary、安装/迁移/SQL摘要、完整7行audit与observer脚本；补充仅提取legacy/current xctestrun的TestHostPath/UITargetAppPath/DependentProductPaths，不读secret环境。无文件/DB/Git写入、服务/API/sim/build/test执行或凭据替代；owner执行时HEAD `ad68106602d4bc2e081524825cb06b1bc803adf4`，产品与UITest沿用d0eb。
- **U1 PASS**：实际legacy005a同bundle，target及dependent产品App均指旧App；当前TestHost仅是UITest runner。公开退出旧合成身份→正常登录迁移身份→目标全文→完整输入→owned origin停止/不可达→Send→未确认/Retry→terminate，1pass/0fail/0skip、exit0。亲读原图`413900B0-…png`确认既有全文与未确认正文/composer/Retry，未伪装为发送成功；真实旧JSON非空401bytes有SHA/key，而非空fixture。
- **U2 PASS**：正常覆盖currentd0eb、无uninstall/erase，旧401bytes/SHA保真；UUID改变不等于丢数据，原路径相等误断言保留。新版runner target/dependent均指current；离线UI与SQL摘要一致pending1/conv0/imported1/rejected0、同key及158bytes请求。亲读`C66817C5-…png`：1 unconfirmed sends、联网核验说明、离线错误可辨，空列表无虚构Upgrade rehearsal。对应1pass/0fail/0skip、exit0。
- **U3 PASS（限本窗口）**：正常联网恢复目标与既有全文，pending原文/Retry不变、未点Retry；亲读`DEE0F575-…png`无残留离线提示、无成功消息伪装。约09:45:18–09:45:28 UTC的App refresh/me/sync/messages GET200；native request/response.finish observer不改响应/路由，窗口内未记录完成messages POST。shutdown后只读SQL摘要仍pending1/同key与bodySHA/imported1/conv1/msg1。1pass/0fail/0skip、exit0。
- 身份由公开登录log+manifest user/chat/origin+分区+配置交叉支持，不凭故意无token/header/body的audit单独证明。reviewer核既有摘要字节/SHA/比较结果，未重读原SQLite或重新hash旧JSON；zero POST不外推无限时/全部底层发包。09:46:15 GET401在App已结束后来自host旧token，不能归App refresh/sync失败；旧版diagnostics72与SDK等warning保留。
- **前三段内无新阻断性产品问题；不扩大为完整upgrade或unit PASS。** 新host登录/token落盘拒绝后未换账号/工具/UI绕行；显式Retry、发送后服务端唯一消息、清pending及host最终计数均未验证，空attachments不证明媒体迁移。owner清场回执复用而非reviewer实时探测；真实pending保留获准恢复。完整证据路径/停止边界见[M1最新升级记录](M1-local-first-paint/recovery-validation.md#真实升级前三段限定pass显式retry因新拒绝未执行)。

## Round 17 — 账号／服务旅程fixture静态窄审

- 原非作者独立审查新增的真实账号切换、完整新账号收发、离线新开、真实设置切服务与持久偏好验证方法，并对照实际认证、个人页、会话和消息鉴权源代码；产品代码未变。**APPROVED，findings为空**，不代表运行PASS。
- 身份guard、正常退出确认、旧未确认与独立草稿正向前置、当次完整收发及旧内容负向组合合理；服务字段替换前后完整值guard不会掩盖输入失败，离线重开移除调试覆盖而非预填新服务；显式throw保留async失败后停止控制流。运行前仍须落实真正peer token与sender相等、原完整消息正向映射、全新隔离资源和精确停服绑定；构建与实际画面尚待运行。

## Round 18 — active pending冻结正文显示：静态修正成立

- 原非作者独立读取真实失败日志、summary与只读SQL摘要，并审查最小getter与对应测试差异，**APPROVED，存活findings为空**。原失败中未确认状态已出现但composer全文失败，库中完整pending与匹配ordinary draft消费符合源码因果；不应撤销消费或把冻结正文重写成普通草稿。
- pending正文优先的只读投影不改setter、请求身份或持久化；协调器程序性更新guard避免回写，确认后仅匹配普通草稿清理使较新内容保留，空正文pending不错误回退；原pending期间编辑、普通Send和附件禁用不变。完整内容断言未放宽，提前截图及任意pending-count负向检查增强证据。该轮仅静态批准，不先关闭真实RED。

## Round 19 — 独立M2三项目标真实证据复核：限定PASS

- 同一原非作者以产品旅程与前端体验方法亲读决定性原图、脱敏日志、summary、运行与精确停服回执、fixture归属；补读仅含请求状态/时间的原生observer审计，未运行API、服务、模拟器、构建或测试，未写源码/DB/Git。匿名运行结论见[M2本轮结果](M2-partition-revocation/recovery-validation.md#独立m2真实回归限定结果)。
- **active pending修正PASS**：原一失败结果保留；修后实际完整冻结正文、未确认说明、Retry与禁用Send可辨，一通过、零失败。结合已审getter修正与后续冷启原pending/独立完整草稿，显示缺陷关闭；修后新pending未取得新SQL，不声明payload hash复核。
- **正常账号退出→新账号收发→离线持久化PASS**：先正向证明旧专属history/pending/另一完整draft，经公开个人页、精确身份、正常退出确认与新登录；新列表/详情/composer无旧四类内容，当次公开发送与对方正常POST均完整出现，审计两次消息POST成功与UI顺序一致。仅停所属origin并终止后新开，两条完整消息及旧内容缺席成立，离线未强制退出。
- **同名账号真实切服务与离线偏好恢复PASS**：两个服务端身份与数据归属不同，真实连接设置完整替换地址后只见第二服务内容；两origin均停后只移除调试override、不预填偏好，新开仍只见第二内容。所有五个修后阶段各一通过、零失败、零跳过；存活产品findings为空。
- 独立审查发现安全输入事件的密码截断prefix漏脱敏，owner已整行清理全部相关SecureTextField事件并修正生成脚本；reviewer核修正版，无prefix写入仓库，不改原始测试结果。测试后的diagnostics警告保留。本轮不是全unit批准，不覆盖硬件、媒体、升级Retry/唯一性、401或离线撤权。

## Round 20 — 离线期间撤权与再次离线：限定PASS

- 原非作者直接阅读在线读取、离线读取、首次联网冷启自动收敛、再次离线四阶段的原图、脱敏log/summary/run、精确停服、正常成员API前后状态及只读cache摘要；四阶段各一通过、零失败、零跳过。受审实现未变，未执行API/服务/native/build/test或写文件/DB/Git。**本旅程PASS，存活findings为空**，不是全unit批准。
- 在线完整正文与真实停服后的离线完整正文均成立；App终止期间正常成员移除使目标访问从成功变为明确无权。首次联网冷启无目标点击、手动刷新或重登录，原其它群保留、目标自动消失。请求元数据中refresh/me/sync成功与库更新时间对应；目标conversation/message实际缺席并写snapshot_absent tombstone，另一群完整消息仍在，因此不是只做画面临时隐藏。再次实核两服务不可达后新进程离线仍不复现目标、不退出账号。
- 四张原图支持本范围体验：离线旧内容完整且离线状态明确；获知撤权后目标入口消失，其他聊天可辨，不要求用户手动刷新或重新登录。中间服务因runtime中断停止，不冒称主动停服或推测时刻；之后另有实际不可达核验，原始结果保留。
- 不声明observer包含同步snapshot正文，不外推30秒active reconnect保证、精确RTT、逐帧无闪回或媒体清理。新实际拒绝阻塞的401脚本与依赖旅程仍未执行、不通过，本结果不替代它。

## Round 21 — 目标分支同步后的原生持久化集成：源码问题关闭，真实补验单列

- 在既有实现与目标分支的合并工作树中，同一原非作者独立审查 execution cleanup revision、已删除成员、列表最新预览及 discard 的持久化/RAM 边界。未执行产品服务或写库；本轮匿名结论不包含测试身份、地址、设备或临时路径。先前真实账号、服务与撤权旅程只在未受影响的范围复用，不把它们冒充合并后全矩阵重跑。
- **W11–W14**：旧或等时且无身份的消息窗口可覆盖最新卡片/发送者；跨会话旧DTO可撤销已知永久删除；正常stale context和旧owner失败可错误降级存储；一条测试错误省略既有成员。四条新反例实际RED为四测试、十二断言失败。修正后相关三组实际七十七测试、零失败；原始失败保留。按本地合格消息身份维护preview，服务端无身份投影保留其权威性；永久删除只增不减，当前owner的真实IO错误才降级，测试使用完整既有成员。
- 后续核查确认 **W12仍有list更新已查看另一会话/degraded知识丢失变体**，另有 **W15 discard最新消息无法回退剩余预览**。补五测试实际RED为五测试、九断言失败（其中非最新discard原已通过），修后相关三组八十二测试、零失败。已知最新身份删除才重建剩余预览；未知服务端预览删除后等待新服务端投影，不让普通旧分页晋升。删除知识在同owner投影消失后仍保留、切owner清空。
- **W16**：discard前在途list/detail/snapshot仍可恢复旧预览。新增真实RED为两测试、十断言失败；源码修正将持久snapshot序列推进与discard放在同一事务，并使用独立discard read revision阻止ready/degraded旧响应发布，避免误取消正常冻结发送；正常资格过期重取而非报离线。原非作者集中审查相关caller后判 **源码CLOSED、0C/0W、存活findings为空**，不是完整unit批准。
- 首次完整原生运行的XCTest部分实际一百六十九测试、一项明确真机保护skip、六断言失败：新循环fixture重复事件游标造成四条断言失败，另有既有WebKit history图片两条。前者改为每分支唯一递增事件ID，保留原内容/存储断言，不改产品；后者重建当前受支持的iOS内嵌前端产物后，两个受影响测试实际补验均通过。不能据此声称已唯一证明WebKit失败根因或首次完整run通过。
- 修正fixture后的最终完整原生scheme实际 **exit0 / TEST SUCCEEDED**；xcresult summary为 **196 total = 195 passed + 1 explicit physical-device protection skipped / 0 failed**，其中XCTest169、Swift Testing27。受测产品与W16静态closure一致；此结果关闭该批源码的运行空缺，不替代真实cleanup UI、旧升级Retry/401或完整跨包CI。合并工作树的依赖安装、TypeScript build/typecheck、当前iOS内嵌前端构建、文档完整性和十三条运行时依赖边界测试也分别实际通过；尚无最终Release归档或PR交付结论。
- 新三阶段cleanup UI helper的独立静态审查未发现新增副作用越界，但指出阅读位置未同进程保持、命令消失缺正对照、负向Process检查缺可见目标约束。运行前修正可见性与mention输入，并明确排除未覆盖的命令/阅读anchor结论；真实模型来源及所属IM不可达仍须外部收据。此静态审查不是运行PASS；旧升级Retry与真实401拒绝边界不变。

## Round 22 — 新执行清理旅程失败与停止边界：独立产物核查完成

- 原非作者随后亲核最终helper及完整原生summary/raw，W16运行空缺关闭，**0C/0W、findings为空**；mention改用Agent ID符合当前token/过滤器，旧anchor及commands排除项不变。仅收口源码与原生测试，不批准完整unit。
- 真实prime随后一测试、一失败、exit65：正常登录、普通完整正文及公开Send已发生，但预期Agent回复在既定等待内未出现，Process正对照尚未建立；永久清理、候选收敛与offline两个phase未运行。Node日志`agent_disabled`仍只作线索，不先定为cache回归或已核模型根因。只读认证诊断遇新实际工具拒绝后立即停相应动作及依赖路径，没有换工具、数据来源或凭据绕过。完整匿名观察与资源边界见[M2最新执行清理结果](M2-partition-revocation/recovery-validation.md#目标分支集成后的执行清理旅程prime失败后续未执行)。
- 原非作者已直接核对真实FAIL、完整AX/脱敏log/summary/run/manifest、指定Node日志及所属栈停止收据，并核D15和匿名M1/M2记录：**prime实跑FAIL；后续NOT RUN，永久执行清理、mention收敛与清理后offline的产品验证为INCONCLUSIVE／未验证；根因INCONCLUSIVE**。源码及native closure保留，不被本次失败自动推翻，也不替代真实旅程；完整unit未批准、保持active，不归档、不宣称Ready PR。认证诊断拒绝依据owner原始操作回执复用，reviewer未为独立证明而读取凭据、调用API或重试。
