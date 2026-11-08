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

### 六项修复后七组补验（真实执行）

- 受测版本：`7d7e455aaadfe6c90e898c84b8e3ab898eb79f7d`；包含 `47ed3dc11` 的集中修复、RED 揭出的 volatile cursor reset 修复和增强 fixture。RED 临时适配已完整撤销，开跑前产品 diff 相对修复提交为空，没有兼容 adapter 残留。
- 命令与环境沿用本记录七组：`xcodebuild test -jobs 2 -parallel-testing-enabled NO -scheme NanoIM -destination 'platform=iOS Simulator,id=55763F8D-5385-47DF-A24F-F2461DCB2FFB' -derivedDataPath /tmp/nano-ios-714-resume`，逐组选中 Repository、StorageController、LocalFirst、AppLocalBootstrap、AttemptPersistence、SendRecovery、Session。
- 实际结果：**exit 0 / TEST SUCCEEDED；102 total = 101 passed + 1 explicit physical-device protection skip / 0 failures**。AppLocalBootstrap 5、AttemptPersistence 17（真机属性 1 skipped）、LocalFirst 20、Repository 32、StorageController 12、SendRecovery 9、Session 7。十条新增回归都包含在这七组内通过。
- 原始产物：`/tmp/feat714-review-fixes-7d7e455aa.log:643-997`、`/tmp/feat714-review-fixes-7d7e455aa.xcresult`。此前 baseline RED 的失败、compatibility adapters、诊断收集报错和强化 fixture 均如上保留，不删除断言、不扩大超时。
- 资源释放：两个 xcodebuild job 均已退出；`simctl list devices --json` 精确核对 557 名称 `feat-714-native-acceptance` 且 before/after 均为 Shutdown（exit 0），未删除或重置设备。无本批自建服务/模型/GUI 旅程。

本结果仅关闭“尚未 typecheck/build/XCTest”的证据空缺，不代表六项独立审查已关闭；由原 reviewer 针对冻结版本集中补验。原生真实在线→终止→离线旅程、真机飞行模式/保护属性、≥20 次首绘 p50/p95 与最终完整 CI 仍未新增证据。

## Round 2 存活 caller 修复与本批停止点

同一 reviewer 独立关闭 W3–W6（W6 限代码/状态层），W1/W2 仍有真实 caller 变体，原结论见 `review.md` Round 2。原生 Journey 的旧版本 build-for-testing 刚启动即因这一结论取消（SIGTERM）；未启动新 IM、prime 或离线阶段，未拿旧构建完成旅程。

### 新增真实 RED 与集中修复

- 在原产品 `7bce604c1` 上只加两条真实 owner 反例：held A/B draft flush 与实际 send B；实际 AppModel origin replacement 遇 policy IO 失败。**exit 65 / 2 tests / 4 assertion failures / 0 unexpected**，没有 baseline compatibility adapters。`/tmp/feat714-review-round2-red.log:292-307`、同 basename `.xcresult`。W1 实际在 held writer 时已 POST，恢复后 durable draft=b0 与 pending 双份；W2 实际替换了应保留的 client/controller。为使坏实现也只尝试 loopback 而非外部服务，切换目标固定为拒绝连接的 `127.0.0.1:1`；失败事实保留。
- W1：`persistAttempt` 先 flush，再把 pending 事务接到同一 draft write tail；请求在等待前冻结，owner/epoch/repository checks 保留。仓储只消费普通 frozen request 匹配的 composer text，较新的 draft 与 interaction 的普通 composer 独立保留。新增仓储事务回归覆盖这三种情况；该附加回归没有单独声称 RED。
- W2：`purge` 以 Bool 明确报告是否已完成全部 accepted intent/物理 close；失败 origin switch 不替换唯一保留 intent 的 controller，恢复其 session observer 并在 AuthView 报错。IO 恢复后，原 origin 登录会先重试清理再 seed。既有忽略返回值的非替换 caller 仍由原 controller 保留 intent。

### 修复后实际执行与异常停止

- 同一 557 / DerivedData、`-jobs 2 -parallel-testing-enabled NO`，七组实际执行 **105 tests / 1 explicit physical-device protection skip / 1 assertion failure / 0 unexpected，exit 65**。原始产物 `/tmp/feat714-review-round2-green.log:451-798`、同 basename `.xcresult`。唯一失败是新增 owner fixture 把同一物理临时目录的 URL（有/无末尾 `/`）当不同值；不是内容/pending/fence 断言失败。其它六组 99 tests / 1 skip / 0 failures，包含 W1 send 反例和仓储新增回归，结果可复用但不能称本次七组全绿。
- 将该 fixture 的精确删除前置检查改为 standardized path guard，保留/加强“仅此测试 root 下的 blocker 可移除”，不修改产品、超时或内容断言。只重跑受影响 AppLocalBootstrap 六条，**exit 65 / 6 tests / 1 unexpected failure**，原始 `/tmp/feat714-review-round2-owner-recheck.log:209-243`、同 basename `.xcresult`。新 origin 反例已 PASS（:213-214）；既有 same-account 测试在 teardown 删除自身临时 root 时抛 NSCocoa513 / underlying EPERM（:221-224）。不得省略此失败或把累计回归写成 clean green。
- 本批按异常停止线不忙重试，不改 timeout/断言、不再启动 IM/原生旅程。只读 lstat 看到出错 root、partition、chat.sqlite 均本用户所有、0755/0644、flags=0；未从 host 删除/修理该目录。日志还含前一 fixture 的 vnode-unlinked，真实 same-account fixture 在多次 refresh 后仍可有有效 session update 未消费；这是异步 fixture teardown 的可疑边界，不将它先验定性成产品库损坏或已确认的 EPERM 根因。
- 仅追加 fixture 生命周期修正：保留本测试创建的 model，在 async teardown 先对合成 session signOut/完成 controller purge，再让原同步 teardown 删除自己的目录，避免 enabled owner 的迟到 refresh 重新打开已删目录。**此最后 fixture 修正尚未 typecheck/XCTest；后续必须在新协调窗口补验，不能用之前的新反例 PASS 覆盖它。**
- 所有本批 xcodebuild job 已收集退出；精确核对 557 名称与状态，before/after 均 Shutdown（exit 0）。没有新建/clone/erase 设备，没有自建 IM/Gateway/模型/浏览器，未访问生产或真实设备。hosted 测试仍有正常 sandbox 写入和旧 51396 refresh 失败，不宣传“零网络尝试”。

本批源修复及已运行反例交原 reviewer 集中静态 closure；完整绿色、最终原生旅程、成功空会话画面、真机 flight/protection、性能统计与完整 CI 均按各自缺口保留，未归档/未交付 PR。

## 受影响 App 组补验与 W7 fixture 收口

- `8a668d7c2` 的最后 fixture 实际补验：`/tmp/feat714-app-fixture-8a668d7c2.log:213-242`、同 basename `.xcresult`，**AppLocalBootstrap 6 / 0 failures / 0 unexpected / TEST SUCCEEDED，exit 0**。新 origin 与旧 same-account 均 pass。产品相对七组受测工作树未变，只有 App 测试的路径 guard / 生命周期修改，故其它六组 99 total / 1 skip / 0 failures 结果可复用；这不是伪称重新运行七组同次全绿。
- 原 reviewer 独立吸收新结果后维持 W1/W2 产品代码 closed / corrected delta aligned，新增 W7：安装 SDK 公开 `XCTest.framework/Headers/XCAbstractTest.h:118-134` 明确同步 tearDownWithError 在 async teardown **之前**。所以原分成两个 hook 的清理不能建立 await signOut→remove root 的顺序，单次 App6 PASS 不反证此契约；该次 log:220-225 仍有临时 fixture vnode-unlinked。Owner 亦独立读取同 header 核实；不将这个确定顺序缺陷夸成此前 EPERM 的唯一根因。
- W7 定点修正：将目录删除移入**同一个 async tearDown**，在 await 合成 model.signOut/控制器 purge 后执行，移除同步删除 hook。内容断言、timeout、错误传播均不变，不加 sleep、不吞清理错误、不从 host 修理失败目录。无产品源变化。
- 修正后只补受影响 App 组：`/tmp/feat714-app-fixture-ordered.log:297-322`、同 basename `.xcresult`，**6 / 0 failures / 0 unexpected / TEST SUCCEEDED，exit 0**。本次 raw log 搜索未见 vnode-unlinked 或 EPERM；这是此次实际结果，不宣称全部潜在 teardown 竞态或历史 EPERM 已唯一证明修复。等待同一 reviewer 对 W7 集中 closure。

### 原生旅程前置的真实结果

- 当前 `8a668d7c2` 产品的 IM API 重建与 `NanoIMJourney build-for-testing` 均实际 exit 0，日志 `/tmp/feat714-native-final-api-build-8a668d7c2.log`、`/tmp/feat714-native-final-build-8a668d7c2.log`。后续 W7 只改 App 单测，不以它重开未变产品问题；正式运行仍核对当前冻结构建。
- 本轮新建唯一临时 runtime `/tmp/feat714-native-final-dphmlbb6`，新 loopback origin `http://127.0.0.1:53703`，合成 IM DB/JWT/账号独立于旧 fixture。首次 IM **exit 1、未监听、零 prime**，原因是排除继承 IM 环境时未声明当前 server 强制的 `IM_PUBLIC_URL`。原始 `server.log:1` 保留；实查端口 connect=61、557 Shutdown，无服务残留。该配置遗漏不是权限拒绝或新增数据范围。
- Parent 明确允许同窗只补 `IM_PUBLIC_URL` 为本轮同 origin、自主恢复已定位且范围不变的测试配置遗漏；不引用生产配置、不换 DB/JWT/origin、不扩大 timeout/断言。后续真实旅程结果另记，不能把 build 或准备完成当作 prime/offline 通过。

## 冻结版本真实原生旅程：online assertion FAIL，offline 未执行

- 原 reviewer Round 4 独立关闭 W7，**0C/0W / live findings=[]**（范围仅 W7 closure，不把已关闭产品问题重审成全 unit 背书）。产品/UITest 未变，最终 `01f34d32e` build-for-testing 实际 exit 0，`/tmp/feat714-native-final-build-01f34d32e.log`。
- 补本 origin 的 `IM_PUBLIC_URL` 后，唯一自有 IM 实际监听 53703（`server-configured.log:1`）；保留首次失败 `server.log` 不覆盖。health check 误用不存在的 `/openapi.json` 得到404、尚无登录/seed副作用；读取实际 `server.ts:285-286` 后改为 `/health` 明确健康。只纠正自有fixture检查URL，不改服务/客户端/断言。随后真实API创建一条 Product launch 群会话及普通工作消息，private输入与同目录 xctestrun 变体不提交。
- 真实 UI prime 命令：`xcodebuild test-without-building -jobs 2 -parallel-testing-enabled NO -xctestrun /tmp/nano-ios-714-resume/Build/Products/Current714Journey-01f34d32e.xctestrun -destination 'platform=iOS Simulator,id=55763F8D-5385-47DF-A24F-F2461DCB2FFB' -only-testing:NanoIMUITests/LocalFirstLaunchUITests/testPrimeFromRealServer -resultBundlePath /tmp/feat714-native-final-dphmlbb6/online.xcresult`。**exit65 / 1 test / 1 assertion failure / 0 unexpected**；raw `online.log:123-131`。真实登录、列表读取与点击会话已发生，message整串CONTAINS在既定15秒未匹配，未执行成功后terminate步骤；**offline阶段未运行**，不把它标通过或使用此失败prime假造离线结果。
- 已导出 xcresult 26个attachments（本地 `online-attachments/manifest.json`）。作者用 read_image 实际检查 `A6DF14CB-568B-4928-B7A5-6FED1FA54067.png`：原生 Chats 列表展示 Product launch、完整可辨认的消息预览、时间，无整屏加载；只证明这个online列表状态，不冒充冷启动离线或timeline画面。保留录屏与失败AX hierarchy；没有为截图再启动/重试App。
- 决定性失败取证：`online-attachments/D1B7EA16-A07B-47AD-802B-7ADD25F0C1B1.txt:14-32` 显示已进入 Product launch，message正文完整存在，但AX label为 `Tomorrow’s design review is at 10:30. Bring the revised launch checklist.`（U+2019），fixture/测试输入为 ASCII `Tomorrow's ...`（U+0027）。当前测试用原文本整串CONTAINS，因此这处标点呈现差异足以解释该次选择器未匹配；不将日志里的“The real message endpoint must decode and render”断言标题反向当作端点未返回/未渲染的事实。此证据仍**不把失败改写成自动通过**，也未据此扩大为产品正文损坏结论或改变核心断言/timeout。
- 按本轮真实旅程超时停止线停止该批，不忙重试、未跑offline。唯一IM job已收集SIGTERM退出，实查 `53703 connect=61` 无监听；精确557名称/UDID已核为Shutdown（exit0），未erase/delete/clone。所有本批构建与UI作业已收集，无自建服务/模型/Gateway/浏览器残留。

当前代码 finding closure通过，复用的后六组与最终有序App6定向回归有效；但完整两阶段原生旅程仍 **FAIL / offline未验证**。需要后续获准窗口以避免标点呈现歧义的正常fixture文本或有等价性证明的选择器完成同一行为判据，不能通过放松内容断言或改timeout收口。成功空会话真实画面、真机flight/protection、≥20次首绘统计和完整CI依旧单列pending。
