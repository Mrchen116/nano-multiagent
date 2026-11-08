# U1 恢复修订验证记录

## 2026-11-09：独立缺陷修复窄回归

- 基线：`022e3c67465aeb6ae64e147d2c6e641ea7ce9ede`，在其上冻结当时待提交的 iOS 修复运行；同批源码随本记录提交。此提交中的 design 是目标方案，不代表新增 policy/handoff 已实现。
- 环境：Xcode 26.4.1；专用 iOS 26.4 模拟器 `55763F8D-5385-47DF-A24F-F2461DCB2FFB`；DerivedData `/tmp/nano-ios-714-resume`。无模型、真实服务、前台 GUI 或现有安装操作。
- 命令：`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test -jobs 2 -parallel-testing-enabled NO -project src/IM/ios/NanoIM.xcodeproj -scheme NanoIM -destination 'platform=iOS Simulator,id=55763F8D-5385-47DF-A24F-F2461DCB2FFB' -derivedDataPath /tmp/nano-ios-714-resume -only-testing:NanoIMTests/ChatRepositoryTests -only-testing:NanoIMTests/ChatStorageControllerTests -only-testing:NanoIMTests/ChatLocalFirstTests -only-testing:NanoIMTests/AppLocalBootstrapTests -resultBundlePath /tmp/feat714-storage-recovery-20261109.xcresult`。
- 实际结果：**exit 0 / TEST SUCCEEDED；39 tests / 0 failures**。分组 AppLocalBootstrap 2、LocalFirst 13、Repository 17、StorageController 7。
- 本机原始产物：`/tmp/feat714-storage-recovery-20261109.log:680-910`；xcresult 如命令。日志/数据库/截图不提交。测试后专用模拟器实查为 Shutdown，无仍运行的本次重型作业。

本组覆盖：真实 AppModel 本地阶段首绘零 HTTP 与稳定 UI owner；请求前捕获仓储上下文后的迟到详情/列表/分页拒绝；message.discarded 的事务删除与迟到分页/重开不复活；membership 核对临时失败后的兜底 full sync；打开/清理 drain 与同分区 activation 合并；非损坏 schema 错误保留可恢复数据与真实损坏隔离 fixture。

**证据边界**：这不是新增持久导入栅栏、typed cleanup 或 handoff 双代际方案的测试；这些机制在本次运行时尚未实施。不是原生 UI 在线→杀进程→离线真实旅程、真机飞行模式/保护属性或 ≥20 次首绘 p50/p95 的替代，也不是最终独立代码审查与 M1/M2 完成声明。此前真实原生在线阶段失败的事实保留，不能拿本组单元回归覆盖。

## Policy/handoff 集成 checkpoint：尚未验证

此后源码落实 Round 5 Approved 的 D12 修订：独立持久 import policy、typed revoke/discard 清理与双代际 handoff；Session 不再写删 legacy JSON。仓储在读取前补应用 policy，SQL receipt 与清理在同一事务；handoff 在 pending 与单条 marker 提交后删除。稳定 AppModel owner 和退出/重开序列接入同一分区边界。

补充反例包括：真实损坏重建不复活 legacy、SQL 清理失败后补应用、handoff 代际与重授予、pending 迟到读、已知清理意图失败后的 retry-before-seed、多会话 snapshot 清理中断，以及 logout/open 竞态。旧 SendRecovery fixture 改为新 handoff 入口；同账号重登录保留未知请求并只 lookup，不再把未确认请求误当退出清理。

**Checkpoint 当时的证据边界**：尚未运行本批 typecheck/build/XCTest；此前 39/39 结果不能归属到这一批。作者侧静态窄复核不构成独立实现 Gate；新增测试必须经实际构建与运行，再补结果。所有新文件操作仅用于源码与临时 fixture；未迁移、清理或改写现有安装数据，未部署。

### 首次编译尝试

- 待验证提交：`3a33cc144a06f9a1c1312b84422132e982005e84`。沿用上文环境与专用模拟器，`-jobs 2 -parallel-testing-enabled NO`，测试范围为 Repository、StorageController、LocalFirst、AppLocalBootstrap、AttemptPersistence、SendRecovery、Session 七组。
- 实际结果：**exit 65，构建失败，零测试执行**。新增 LocalFirst snapshot 清理反例的两处 GRDB fixture `write` 被解析为 async API，缺少 `await`。原始日志 `/tmp/feat714-policy-integration-3a33cc144.log:394-407`；xcresult `/tmp/feat714-policy-integration-3a33cc144.xcresult`。
- 修正：`c883d6fef359e549eb1db99fa7f0afefb14b62d0` 仅给这两处 fixture 写入补 `await`；未更改产品行为、测试断言、超时或范围。后续串行补验结果单独记录，不把本次失败或产品文件未出现编译 error 解释为测试通过。
- 第二次尝试 `c883d6fef` 同样 **exit 65 / 零测试执行**：接续的 Repository 测试编译阶段暴露同类四处 async fixture write 缺 `await`（`/tmp/feat714-policy-integration-c883d6fef.log:218-245`，xcresult 同 basename）；仅补齐四处 await。已检查测试目录的其它同步 GRDB write，余下一处属于同步测试，不能机械加 await。

### 首次运行与重复撤销反例

- `b5ef411fff9b418b7575a95b277169be21eae9a4`：**exit 65 / 88 tests / 4 assertion failures**，全部失败在 AttemptPersistence 同一文件保护属性测试的四条路径：模拟器均返回 `protectionKey=nil`，backup exclusion 断言通过。其它六组 72 tests 均通过。原始日志 `/tmp/feat714-policy-integration-b5ef411ff.log:664-1013`，xcresult 同 basename。
- 测试边界修正：backup exclusion 独立测试保留四条路径断言；complete protection 的四条原断言移入单独真机测试，模拟器明确 `XCTSkip`。这与设计已有「模拟器无法提供保护属性证据」条款一致，不是产品保护判据降低；真机保护属性仍 **pending**，不能将后续 simulator green/skip 当作它的 pass。
- 同期作者发现已存在 SQL tombstone 不代表没有更晚的 handoff。补真实 SQL receipt 失败反例后，detail 再次拒绝、snapshot 再次缺席，以及没有 SQL 行的未导入 handoff 三条均复现：**exit 65 / 3 tests / 6 assertion failures**（`/tmp/feat714-repeat-revoke-red-split.log:216-246`；xcresult 同 basename）。前两条复用了旧 generation，重开恢复新近被拒绝的请求；第三条漏把独立 handoff 命名空间纳入 snapshot absence。
- 修复范围：同一协调锁内检查新 pending/handoff，重复拒绝存在新请求时旋转 generation；snapshot 将未导入 handoff 的会话身份也纳入 accepted cleanup intents。无新请求的重复拒绝继续幂等；未变更发送策略、请求字节或零自动重发约束。后续七组补验结果单列。

### 修复后七组实际补验

- 受测版本：`a65d35a7a9f28f5db664bfe1da96602479493e62`；同一专用 iOS 模拟器、DerivedData、七组与 `-jobs 2 -parallel-testing-enabled NO`，无额外服务、GUI 或模型联调。
- 实际结果：**exit 0 / TEST SUCCEEDED；92 tests / 1 explicit physical-device protection skip / 0 failures**。AppLocalBootstrap 4、AttemptPersistence 17（其中真机属性 1 skipped）、LocalFirst 16、Repository 30、StorageController 9、SendRecovery 9、Session 7。三条新 red 反例均在本次 Repository 组内通过。
- 原始产物：`/tmp/feat714-policy-integration-a65d35a7a.log:509-871`、`/tmp/feat714-policy-integration-a65d35a7a.xcresult`。前两次编译失败及首次运行失败如上保留，没有扩大超时、删断言或用旧 39 tests 冒充本批结果。
- 资源释放：XCTest 已退出；专用模拟器 shutdown 请求报告 already Shutdown 后，`simctl list devices` 再实查为 Shutdown（exit 0）；无本批自建服务或残留重型作业。

**该版本结论仅为本地窄回归通过**。原生真实在线→终止→离线旅程尚需在最终版本重跑；真机飞行模式、保护属性和 ≥20 次首绘 p50/p95 仍无新增证据；不得据此宣布 M1/M2、完整 unit 或 PR 已交付。

## Round 1 六项实现修复 checkpoint：待运行与独立关闭

`review.md` 的六项 WARNING 已全部接收，作者集中修复，不降低 delta 或把旧绿色证据覆盖到新版本：

- W1：owner draft flush 使用单一等待链；写失败保留最新待写文本并显式降级，retry 的 seed 不覆盖未提交的清空/编辑。新增重叠 A/B flush 与真实 SQL DELETE 失败回归。
- W2/W3：已接受的分区 purge 意图与 UI publication generation 分开；在任务创建/partition=nil 之前登记，未开始/失败/被新登录取代也必须在后续 seed 前补完；nil partition 可重试清理。disabled stored owner 从实际 AppModel 冷启入口显式提供目标分区，不要求曾经 open。新增 policy IO 失败后同账号重登、nil retry、未启动 purge 被同账号登录取代、disabled 冷启后 reenable 的临时 fixture 回归。
- W4：完整消息端点分页把“仍有更早消息”的事实与页内容写在同一事务的 `cache_meta`，不增加 schema 迁移、不持久缓存网络 cursor；稀疏单消息校正不改变完整性，终止页可确认起点，已确认起点不被普通最新一页否定。分区/会话清理同步移除该事实。新增无 trim 的普通分页 close/reopen 与 owner reset/offline 反例。
- W5：legacy 枚举只有真实 ENOENT 当空；目录/祖先被普通文件阻塞等 IO 抛错、回滚导入 marker，恢复后仍按原字节导入。单文件 IO 同样可重试，真正解码损坏仍逐件 rejected。新增真实 ENOTDIR fixture 验证 marker 缺席与恢复导入。
- W6：会话首个成功消息结果与尚未加载分开，合法成功空页显示“还没有消息”，无缓存且失败仍说明需要连接。新增 held 首请求→成功空页→reset→离线失败状态回归；真实画面/操作仍需原生旅程补验。

这些新回归在 checkpoint 时**未运行**，没有 typecheck/build/XCTest 红绿结论，也未由独立 reviewer 关闭。作者只做 Swift frontend parse 与 diff 静态检查；首次 docs check 使用系统 Python 缺少 PyYAML，改用项目已有 `.venv/bin/python` 后 docs check 283 sources / 69 routes 通过，不安装依赖、不改变环境。后续必须在协调的本地资源窗口实际运行，再交同一独立 reviewer 补验失效判断。此前 a65 的 92 tests 结果仍只归属原版本。

### 六项定向 RED（真实执行）

- 基准为 `cc6e1572e01822093bfb57146d7d0864204ec7a9` 的七个相关产品文件，测试保留 `47ed3dc11ccf7a09573a2ad0167925fe6b4395fc` 新增十条。为使新测试在旧实现编译，只补三处 compatibility adapters：旧 draft flush 接收同一真实仓储 writer seam、按排序选择一种原本合法的字典迭代顺序（仍无等待链/错误保留）；消息 phase 查询镜像旧 View 的实际分支（不补成功空结果状态）；仓储接受但忽略新分页完整性可选参数。`ChatTimelinePhase` enum 仅作编译桥接。**这是明确适配的 baseline RED fixture，不是宣称纯 cc6 head 的新测试可直接编译。**
- 实际结果：**exit 65 / 10 tests / 26 assertion failures / 0 unexpected**；十条全部失败，分别复现旧 draft 覆盖/失败清空丢失、三条 partition purge 问题、disabled 冷启未清理、两条普通分页完整性缺失、legacy ENOTDIR 被吞并永久写空 marker，以及成功空页仍 loading。
- 原始产物：`/tmp/feat714-review-red-rkrfn_wi/targeted-red.log:685-744`、同目录 `targeted-red.xcresult`；`manifest.json`、`repair-product.patch`、`red-vs-47ed.patch` 保留精确源差异。测试完成后 Xcode 诊断收集另报 simctl utility 72（日志 745-746），发生在十条测试与 26 条断言已明确执行之后，不将它冒充上述断言根因，也不隐藏。
- RED 同时揭出 `resetProjection` 漏清内存 `before` cursor：它不是新的进程状态，不能拿仍残留的 cursor 假装重开。修复该真实遗漏，保留离线 hint 断言；同时增强两条 purge fixture，让旧 draft 与 pending 同时存在、disabled 冷启旧库确有 pending，不删除或弱化原断言。恢复所有 RED 产品文件到修复版后才运行后续七组。

本组仍使用确由 714 早先 `simctl create feat-714-native-acceptance` 返回的新设备 `55763F8D-5385-47DF-A24F-F2461DCB2FFB`（原 receipt `/tmp/feat714-native-18vslzip/device`）。这是 hosted XCTest：会安装/更新同 bundle `win.nanoim.ios` 并写该测试设备的正常 App sandbox，**不是“不碰 App sandbox”或“零网络尝试”**；原生 fixture 的旧 loopback 51396 refresh 失败按日志保留。仅临时 fixture，无生产/个人设备、其它模拟器或新增 GUI 旅程、模型、真实服务操作。
