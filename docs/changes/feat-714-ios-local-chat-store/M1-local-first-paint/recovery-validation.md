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
