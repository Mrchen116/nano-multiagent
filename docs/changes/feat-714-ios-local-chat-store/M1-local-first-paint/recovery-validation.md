# U1 恢复修订验证记录

## 当前执行范围：用户更正后仅模拟器

用户最新原话（由父级完整转交）：「所有的真实隔离测试，skill已经明确了，我前面也跟你多次说了，不需要我给你权限！！！ios真机测试暂时不需要，没有可用手机，只用在模拟器测」。此更正立即适用于本轮714；以下历次checkpoint/拒绝/失败保持当时事实，不再把旧“未答／待许可”当当前阻塞。

- 已披露的714真实隔离范围直接接续：原自建loopback服务/合成DB与自有模拟器，服务启停复用和切换；合成迁移账号/会话/消息、真实旧JSON→同bundle覆盖升级→显式Retry；成员移除/恢复、精确合成账号旧凭据失效/真实401及去敏接口状态日志。新的实际拒绝仍立即停被拒动作、完整回报，不换工具/对象绕行；不将常规隔离验收重新包装成待用户批准事项。
- **本轮仅模拟器**：不连接或操作手机、不安装真机App、不启动真机HTTPS公网tunnel。真机flight、complete file protection属性、≥20次真机首绘trace/p50/p95保持**UNVERIFIED／本轮不执行**，不得用模拟器不可达origin或skip冒称真机PASS，也不再作为本轮模拟器交付阻塞。backup exclusion等已在模拟器实际通过的独立结果仍按各自证据保留；产品保护实现要求不因此删除。
- 原升级准备曾遇新的实际工具拒绝后立即停组、回收唯一服务并交出窗口（见下节历史），独立审批上下文缺陷由用户另修，不纳入714、不改审批/策略节点。用户随后给出真实新事实：「工具审核策略已经更新了，应该不会被拒绝了」。原组可在更新后正常工具审查下接续，**不是保证allow或绕过**，有新实际拒绝仍停报；不再探测策略或重查已完成审批调查。此后原组实际运行前三段，各自限定PASS；新的host control正常登录/token落盘实际拒绝已停止该动作与依赖它的显式Retry，见下方最新记录。用户最新纠正已撤回泛化的整段资源/下一步许可等待：执行者自行推进原unit内独立允许的实现、排错、复测、review与交付，遵循现有隔离/锁，只限制有具体依据的冲突动作并在可观察条件满足后自主恢复；不是绕过真实拒绝。审批缺陷仍由用户另修。真实模型如需仍用Sol6.1，本unit当前矩阵不需要模型。
- 仍须完成本轮适用的真实模拟器升级/账号/服务/未见撤权/同进程401矩阵、独立复核及最终target sync/集成/交付。CI历史两红原因未知及一次诊断未复现均如实保留；不盲重复已耗尽诊断或擅扩unit外修复。下文“真机仍pending”等旧门禁描述须结合本节当前执行范围阅读，不据旧文恢复手机工作。

## 新窗口尝试：新实际拒绝，不是旅程执行或待用户重新许可

- 父级明确给下一串行窗口后，作者只读核既有runner与两份真实App：同bundle `win.nanoim.ios`，current built revision `d0eb4c825`、legacy `005a360579d9`，各可执行SHA256已记录；当前runner来自已通过的Journey build。未重建、不安装、不启动模拟器。
- 仅启动原自有53703、原DB/JWT服务（job bash-39，PID34092）。随后提交原已披露方案的正常API准备：fresh `review714legacy` / Riley Review、join/approve、与既有合成B建direct/history、0600输入及旧/current两runner。**新的实际工具拒绝**全文：「这会在本机测试服务创建并审批新的用户、会话和消息记录，超出已授权的仅模拟器/自有 fixture 测试范围；此前这组升级测试因实际权限拒绝而停下，现有确认并未明确批准这些新增服务端副作用。」没有Python stdout/exit回执，不能声称部分创建。被拒组立即停，不换账号/工具/路径、不发API探权限。
- 完整toolcall/返回及当前人类原话、父级窗口原文、可见上下文说明保存在本机0600 `/tmp/feat714-native-final-dphmlbb6/upgrade-permission-denial-resumed-17095.txt`。人类原话在worker会话与本记录可见，但未重复嵌进被拒bash命令/description/justification或紧邻说明；随后仅从既有结果元数据补取真实拒绝时间 `2026-11-09T03:13:09.856Z`、`NanoApprovalDenied / classifier_block` 及原生call/result定位到上述本机证据，无API/模型/权限探测或重试。未返回approval request ID、独立classifier trace或reviewer prompt/context，不能从worker可见性推reviewer实际所见。父级接手按执行工具判断/上下文接续异常调查，明确不再要求用户重复批准本已披露隔离动作。
- 按准确main.js/loopback/db argv核准后，仅SIGTERM自有PID34092并收集bash-39 **exit0**；实查PIDgone、53703connect61、精确557为Shutdown。预期四个新private文件及两个runner均不存在；未查API用户/消息来探部分执行。首次资源核验漏设DEVELOPER_DIR导致simctl查找exit72，仅补正确Xcode环境后只读核验exit0，不隐藏该命令失败。
- 已通过原通道实际交出本窗口给720。**零XCTest执行、无新增UI证据、升级四阶段仍未完成**；仅启动服务不算旅程进展。当前保留已记录的下一窗口前置资源，由714负责，不因这一新工具拒绝自动销毁旧→新升级前置；待父级调查结论或取消时重新核保留必要性。

## 策略更新后的轻量恢复准备（未开始旅程）

- 用户「工具审核策略已经更新了，应该不会被拒绝了」由父级原通道转交；这是接续事实，不是新的隔离测试请批、保证工具allow或把另修审批问题并入714。当前只按父级716优先资源安排准备，未重提交旧被拒命令，也没有API/模型/策略探测。
- 实查分支`codex/feat-714`、HEAD `ba60a9acb`，tracked clean（原untracked mock保留）；同bundle `win.nanoim.ios`两份App仍在：current Info revision `d0eb4c825`、可执行SHA256 `6d985e7088162506e401ebd9dfa04994a7c82b1945dd008d63c8802703774040`；legacy Info `005a360579d9`、SHA256 `e5b0eb7203fdaba71cd510571cd0f463b741c64febc88d82be5c8e3f3b466d67`。旧detached worktree HEAD `005a360579d9e2c73f0a613073bcaecd705b7e62`且clean，不重建。
- 原Journey runner SHA256 `82e9a4af3518653ae99daafae1eb900e9a4e55a33df1d5e6664d07b4d65e9287`不变；只读plist核其`UITargetAppPath`和`DependentProductPaths`均指当前App。后续生成legacy自有runner时须**同时**把目标App与对应dependent App路径指向真实旧App，保留已构建当前UI runner/测试bundle，且安装后再核App容器Info确为legacy；不能仅改target却让dependency安装覆盖为current，再误称旧版实际写JSON。此处只识别并记录配置约束，尚未生成/运行新runner。
- 原fixture DB/JWT/input与peer资料文件实查存在（未输出secret）；四个先前被拒准备输出仍absent。原53703 TCP connect_ex=61，无HTTP调用、未起服务，未调用simctl或操作任何设备。文件存在不当作账号不存在或App现有session的证据；下一真实窗口仍须用正常fixture/API与UI身份guard检查，不盲目假定中断现场。
- 下一批仍是同一完整升级方案：正常API建合成迁移身份和direct/history→旧App正常UI登录/完整输入/显式Send且自有origin真正不可达→核真实非空legacy JSON与不可变请求身份/完整字节→同bundle覆盖current、不uninstall/erase→离线仅pending说明、无虚构会话→原origin在线恢复全文与原pending、零自动发送→显式Retry仅产生一条原内容新消息并清pending。每段保留原断言/正常API前后计数和真实画面；新的实际拒绝/失败立即停该段与收资源，不换工具/账号绕过、不放宽超时。
- 以上仅前置与方案就绪，不把原175 native测试、旧offline/membership结果扩成升级PASS；历史CI两次cleanup失败原因未知仍未知。下一动作由父级真实释放串行窗口触发，而不是重问许可或反复检查策略。

## 真实升级前三段：限定PASS，显式Retry因新拒绝未执行

- 执行时HEAD `ad68106602d4bc2e081524825cb06b1bc803adf4`，产品/UITest未变；原557、53703、同fixture DB/JWT。正常API创建专用合成身份、direct **Upgrade rehearsal / c_bxy4mdpb** 与一条完整工作消息。初次消息POST因缺sender得到403；正常GET核同两成员后按实际DTO补sender，唯一POST201成功，随后只读证实仅一条消息，未重复发送。主机fixture读取误取扁平content导致KeyError，按实际`items[].message.content`纠正；这些准备失败不是客户端缺陷或测试PASS。
- **U1旧版真实未确认发送PASS**：实际legacy `005a360579d9`，bundle `win.nanoim.ios`；legacy runner的target与dependent产品App均指旧App，当前UITest runner不冒充旧产品。`upgrade-legacy-submit-d0eb-redacted.log`、`.xcresult`、`-summary.json`为1pass/0fail/0skip、exit0：公开Me精确身份→Sign out→正常登录迁移账号→进入目标/全文→完整输入 **Please keep my migration rehearsal note for the morning.**→run-bound握手仅停已核argv的自有PID58186→确认origin不可达→Send→Awaiting/Retry→terminate。旧App安装后和结束revision/hash均匹配。
- 实际旧JSON **401 bytes / SHA256 `19419da7803937c9bf73368ed5d117c30b9f2ff6f4f6ff42f84e279e3e38d021`**，key `A64C7D32-B64A-45ED-B161-F79E15BD018F`；空attachments，冻结请求158bytes、SHA256 `91c2e9a74953fd74644eedd12ff3c5e9f91f9d0c932ebcb4da74e14adf676752`。同bundle正常simctl install覆盖current `d0eb4c825`，无uninstall/erase，首次新版启动前新分区DB不存在；旧JSON字节不变。host曾错误断言data-container绝对UUID路径必须相等而exit1，后只读证实正常覆盖已迁移UUID但原文件保真；保留此错误，未重做旧发送或安装。receipt `upgrade-legacy-json-overwrite-d0eb.json`。
- **U2新版离线导入PASS**：`upgrade-offline-d0eb-redacted.log`及对应summary/xcresult为1pass/0fail/0skip、exit0；不可达原origin下5秒出现1条未确认说明、无登录/目标占位会话→capture→terminate。只读`upgrade-offline-sql-d0eb.json`为pending1、conversation0、imported1/rejected0，同key/完整正文/空attachments/请求逐字节等于旧158bytes，不靠UI计数猜SQL。
- **U3联网恢复但不自动推进PASS（限观察窗口）**：`upgrade-online-pending-d0eb-redacted.log`及summary/xcresult为1pass/0fail/0skip、exit0，UTC约09:45:18–09:45:28。原origin恢复，真实读取目标和既有全文；pending原文/Retry仍在、普通Send禁用，未点击Retry。observer仅import未改产品createServer，在native HTTP request/response.finish记录指定路径time/method/status，无header/token/body、无路由/响应改写。最初addHook晚于ready报Fastify错误exit1；改用native事件后以host GET200确证捕获再启App，保留失败日志。完整7行`upgrade-http-d0eb.jsonl`为709bytes，SHA256 `4b823bb74499925d581c41ddc00abc28eab2f40a568685b4f5c087e15137503e`：App refresh/me/sync/messages均200，**窗口内未记录完成的messages POST=0**，不外推无限时或全部底层发包。
- 资源关闭后仅mode=ro查询本设备实际SQLite，`upgrade-after-online-stopped-d0eb.json`仍pending1/同key/同请求字节、imported1、conversation1/message1。host最终独立GET计数未完成，不能用此只读SQL替换服务端最终唯一性验收。U1/U2/U3三张原图作者与原非作者各自read_image：旧版既有全文+pending/Retry、新版离线说明+空列表、新版在线既有全文+pending/Retry，均可辨且未把pending伪装已发送；独立结论见`review.md` Round16。
- **新的实际拒绝**：旧host独立token在App已结束后GET401；正常同合成身份登录以刷新host control并0600保存token的整条命令被拒，未执行/无stdout或exit回执、预期control文件absent。结果UTC `2026-11-09T09:46:53.736Z`，callId `call_b3c847cf2d7841a3b1b574019a752b9b`，`NanoApprovalDenied/classifier_block`。原文：「The action uses a saved username and password to create a fresh authenticated session after the prior token failed, then writes its access token to disk; this goes beyond the scoped simulator test and entails credential use and session material handling without authorization for that specific side effect.」去敏动作/元数据0600 `upgrade-control-denial-17598.txt`保留。未返回approval requestID或classifier上下文；不调查审批组件、不换账号/工具/凭据/UI Retry绕行、不重复问用户测试许可。host401不是App refresh401，不能标产品认证缺陷。
- **显式Retry、发送后服务端唯一新消息、清pending及完整upgrade仍PENDING**。前三段各自PASS不关闭本unit/M1/M2，其空attachments也不证明媒体迁移。日志保留SDK/debugger/accessibility及测试结束diagnostics72，不称无warning。全部产物在原private root、不提交凭据或日志。
- **本批资源实际释放**：仅验证并SIGTERM自有observer PID95624、收齐所有server/UI jobs；精确557 `feat-714-native-acceptance`为Shutdown，53703connect61、control文件absent。真实pending保留供获准恢复；后续独立工作不再等待父级泛化窗口或普通下一步许可，仍不得进入这条被拒登录及依赖Retry。

## 当前临时资源责任与回收（2026-11-09，适用新回收规则）

负责人仍为714原执行者；由其自主推进并清理，不再因其它unit整段资源安排或普通复测/review而等待父级下一步许可。按主仓 `docs/development/worktree-runtime.md` 的新「测试资源回收」规则，结束包括失败、取消、阻塞；不能再仅以 Shutdown 或“本机证据”概括永久保留。

- **已实际回收**：确认两份原始 `ARCHIVE SUCCEEDED` 日志及实际 archive App Info/hash后，删除自有 `/tmp/nano-ios-714-release-4dc09fcb6` 与 `/tmp/nano-ios-714-release-b662`，不删除当前/旧版模拟器构建。job bash-22 exit0、两精确目录 absent，删除前 allocated 合计 **895,668,224 bytes（约0.834GiB）**；同时刻全盘free采样16,143,380,480→16,704,032,768 bytes，仅为采样净变，受其它任务写入影响，不与allocated混同。去敏receipt `/tmp/feat714-release-cleanup-20261109.json`（0600）保留版本、bundle、可执行与archive Info SHA256；两份原始归档日志仍在本机。随后只删当前DD中不再需要的 `/tmp/nano-ios-714-resume/Build/Intermediates.noindex/ArchiveIntermediates`（170,258,432 bytes，独立0600 receipt `/tmp/feat714-archive-intermediates-cleanup-20261109.json`，exact absent）；保留simulator Build/Products、其它intermediates和SourcePackages。累计移除 **1,065,926,656 allocated bytes（约0.993GiB）**。此删除不撤回已有归档PASS，也不代表真机测试。
- **下一窗口必需、暂留**：精确自有模拟器 `55763F8D-5385-47DF-A24F-F2461DCB2FFB`（上次实查Shutdown）、`/tmp/nano-ios-714-resume` 当前App/runner、`/tmp/nano-ios-714-legacy-005a36057` 旧App，以及 detached `/tmp/feat714-legacy-005a36057` 源码/旧runner来源。理由是三段升级已独立PASS，但真实pending/最终Retry因新拒绝暂停，不能提前erase/卸载破坏恢复点；原557与current DD还需现有分区矩阵。旧App/DD/源码在完整版本与路径证据已提取后进入本轮回收候选，须先保留足够去敏证据再按精确路径清理，不因旧拒绝永久占盘。完成本轮适用矩阵、提取必要证据后，由714执行者关闭并**删除**自建557，验证设备list不再含UDID；删除两独占DerivedData，按git worktree规则移除旧detached worktree。若本轮取消/再次阻塞须重新核此例外必要性，不自动无限续留。
- **合成凭据/DB暂留**：`/tmp/feat714-native-final-dphmlbb6` 的原自有53703 fixture DB/JWT、private input与manifest需正常API续接历史和账号/服务隔离；不复制到其它服务或生产，不提交原文。完成矩阵或明确取消后停止精确自有服务，核PIDgone/53703释放，保存去敏证据后删除整个独占root（含secret、数据库、截图/xcresult、runner临时配置）。不因证据用途而永久保留凭据。
- **原始失败与审查证据暂留**：现有 `/tmp/feat714-*` 原红/绿rawlog、xcresult/attachments、`feat714-crossci-92fb1218b`、`feat714-review-red-rkrfn_wi`、宿主诊断root及小型receipt仅用于尚未结束的独立复核与历史CI红因判断。先提取足够的去敏可引用证据、关闭相应复核后，在本轮最终收口前删除这些独占本地产物；诊断config/生成模块不安装、不留永久hook。历史红的关键原始证据不可为腾盘提前抹除，若仍需带到下一轮，由714执行者在此明确剩余审查问题/下一回收触发点。
- 本次只处理714确属不再需要的产物，不动716、用户/生产/其它模拟器、共享缓存或原有untracked mock。原历史准备窗口和本次实际三段升级均已收齐自身服务/UI jobs；本次三段确有XCTest真实操作，见最新记录，不能沿用旧“零UI”描述；未做权限探测，当前无本批native/heavy服务残留。后续实际清理须逐路径核归属/绝对路径并记录完成核验，以上暂留计划不是已清理声明。

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

### 同一 fixture 的呈现比较修正（尚未重跑）

- 逐字符读取原 private 输入与上述原始 AX label，两串长度均73，唯一差异为 index8 U+0027→U+2019；替换该字符后全文完全相同。保留原 server 消息、原输入、原 FAIL/xcresult 不覆盖；新私有输入只将完整预期改为实际呈现的弯引号，仍匹配完整73字符、同一目标会话，不调整15秒/5秒断言或产品代码。
- 中断的 prime 已通过正常登录，会在同一自有 origin 留下合成会话。新增显式 opt-in `NANO_UI_RESET_OWNED_SESSION=1` 仅用于该 fixture 的重新 prime：如已经登录，走公开 Me → 验证精确 `@<fixture username>` → Sign out → 正常确认，随后原完整用户名/密码登录流程仍必须成功。不删除设备/安装/Keychain/宿主目录，不绕过真实认证；未 opt-in 与 offline 阶段不执行此准备。身份不符或确认未出现则 fail，不签出未知账号。该正常退出会清理本轮同 origin 的本地缓存，随后必须再次从真实API prime；不能用旧缓存伪造本轮online成功。
- 当前仅 Swift parse/diff check 通过；必要独立 fixture 审查、当前 build 和完整两阶段运行结果另记。不能将这次针对已证选择器差异的修正冒充旧 FAIL 自动变绿。

## 同 origin / 同冻结产品的两阶段原生补验：PASS（限定本路径）

- `validated_at=da47a48e5a30ece2364a968d427b3a5e48cb10bc`，只有上述helper/evidence增量，NanoIM产品/project未变。原reviewer独立窄审 **0C/0W / findings=[] / no spec delta**；全文预期等价、显式公开reset和fail-fast成立，但不据静态审查宣称运行成功，见 `review.md` Round5。
- 当前 `NanoIMJourney build-for-testing -jobs 2 -parallel-testing-enabled NO` 实际 **exit0 / TEST BUILD SUCCEEDED**，`/tmp/feat714-native-build-da47a48e5.log:255`；产物Info.plist的NanoIMBuildRevision实查为`da47a48e5`。私有runner `/tmp/nano-ios-714-resume/Build/Products/Current714Journey-da47a48e5.xctestrun` 与产品同目录，使用原53703 origin、同DB/JWT/账号/会话/原server消息，不新建或修改seed，不覆盖原input/FAIL；新private输入另存0600。
- 只恢复原自有IM，清除继承IM变量，只显式添加本fixture的JWT及同origin IM_PUBLIC_URL；新 `server-reprime.log` 保留旧日志。实查PID52499完整argv属于本worktree、本DB、127.0.0.1:53703，`/health` HTTP200；精确557名称/UDID在运行前Shutdown。
- **在线prime实际PASS**：`/tmp/feat714-native-final-dphmlbb6/online-reprime.log:64-148`、同basename`.xcresult`，**1 test / 0 failures / 0 unexpected / exit0 / TEST EXECUTE SUCCEEDED**。公开Me→精确@nano→Sign out→sheet确认实际走通（:64-90），之后原用户名/密码真实登录（:91-126）。列表截图:128、点Product launch:129、完整73字消息15秒谓词通过:135-139、终止App:140均实际执行；不能借此次成功追认原729通过。
- 在线PASS后只停止上述自有IM job，收集SIGTERM退出；实查原PID消失，`127.0.0.1:53703 connect=61`。**离线冷启实际PASS**：`/tmp/feat714-native-final-dphmlbb6/offline-reprime.log:25-54`、同basename`.xcresult`，**1 test / 0 failures / 0 unexpected / exit0 / TEST EXECUTE SUCCEEDED**。与在线同simulator/origin/构建/安装数据；无SQLite注入或进程内store调用。5秒列表谓词通过且登录表单不存在（:29-34），点同会话（:35），完整消息5秒谓词通过并截图（:41-45），随后终止App（:46）。offline未调用reset helper；不是新origin或新缓存替代冷启动。

### 作者实际画面自检与证据边界

四张均由作者用read_image打开原始xcresult导出图，原生viewport402×874pt（导出1206×2622px），未做缩略/修图或当成原型。文件位于同runtime，不提交：

| 阶段 | 本地导出附件 | 实际可见与判断 |
|---|---|---|
| online list | `online-reprime-attachments/D71CBAE8-207B-48F1-AE96-7BE8787EAEC9.png` | Chats原生列表，Product launch标题、单行省略的正常消息预览、3:01 AM时间可辨；不是整屏加载占位。预览不是全文，全文在下一页。 |
| online timeline | `online-reprime-attachments/514E31C8-0868-4288-91BF-7FB07D444D3B.png` | 同会话标题、3:01 AM分隔，完整73字工作消息在气泡内分三行可读，底部输入区保留，无加载占位。 |
| offline list | `offline-reprime-attachments/02813AF3-C9AD-4EB5-98F2-5E5A2B78A8DD.png` | 上方明确“Offline. Retrying · Updated 03:12”；同会话/预览/时间仍可读，未变登录页/空列表，离线提示没有替换内容。 |
| offline timeline | `offline-reprime-attachments/B86BA392-7DA0-469C-B4EC-3396ED49A915.png` | 同完整消息仍可阅读；顶部有上述离线/上次更新时间及“Could not connect to the server.”，不谎称当前同步成功，错误没有挡住正文。 |

- **作者限定结论**：真实登录→从API读列表/历史→terminate→仅停该origin→同构建离线冷启→读取本地列表与完整正文的指定路径PASS；离线可读与状态可辨的这四个实际画面自检PASS。独立产品/体验判断另交既有非作者依据这些原始产物作出，不以作者自检冒充独立验收。
- 截图是四个命名状态，成功运行只导出这些保留附件；`app.launch`返回/首次XCTest轮询时刻不等于从图标打开到首绘耗时。不能由这两条test总时长或5秒谓词宣称首帧无白屏/无加载闪回、p50/p95达标；不证明网络恢复自动校正、多条滚动历史、空会话、真机flight/protection或全量契约均通过。模拟器状态栏Wi-Fi图标不代表此origin可达；离线前/后connect61及停止PID为此路径边界依据。
- 所有本批build/UI/server jobs已收集。精确557名称/UDID在收尾before/after均Shutdown，无erase/delete/clone；53703仍connect61。没有自建Gateway/模型/浏览器或其它服务；正常hosted安装/sandbox影响不宣称为零。重型/GUI窗口已释放。

原非作者后续已独立实际打开四图并交叉核log/manifest/runner/binary版本，判定**指定产品旅程PASS、限定可读性/离线可辨体验PASS，findings=[] / 0C0W**，完整范围与限制见 `review.md` Round6；服务停止/PID/connect61/Shutdown依据作者当时工具回执复用，不冒称独立实时操作。

**仍pending**：成功空会话真实UI、真机飞行模式与四路径保护属性、≥20次首绘p50/p95、完整CI及最终unit门禁/归并/归档/PR。当前两阶段局部PASS不把它们一并关闭。

## 完整原生scheme首次执行：失败保留，定点处理

- 冻结`1b6281022`以`xcodebuild test -jobs 2 -parallel-testing-enabled NO -scheme NanoIM`在同557执行，原始 `/tmp/feat714-native-full-1b6281022.log`、`.xcresult`，**exit65 / TEST FAILED**。xcresulttool summary独立导出 `/tmp/feat714-native-full-1b6281022-summary.json`：**175 total = 169 pass + 5 failed tests + 1明确真机保护skip**；其中raw XCTest为148条、10个assertion failures（4 unexpected），另有27条Swift Testing。不得将断言次数混成failedTests，或把完整scheme失败写成完整CI通过。当前七组105条都已在这次整体失败的run中通过，但这不消除其它5条失败。
- **日期函数真实RED**：`ChatPhaseTests/testAbsoluteTimestampUsesHoursAndMinutesOnly`的固定now为2026-11-05，raw log:414-416得到`11-05 23:40`而非`23:40`，2个assertion失败。源码`absoluteTimestamp`接受now却用Calendar.isDateInToday/Yesterday（系统当天）忽略它，当前host为11月9日。修正为按传入now比较同一天/前一天，保持已签核HH:mm/昨天/旧日期文案；保留原断言并加强精确昨天及旧日期断言，不改timeout或用当前日期伪造fixture。修后实际窄测待执行。
- **另4条WebKit测试**：源码Resources与实际`.app`中均不存在`IntelligentUI/index.html`；`InteractiveWebView.swift:48-50`资源缺失直接返回空view。直接xcodebuild漏掉`build.sh:6-7`现有共享contracts/`npm run build:ios-ui`前置生成资源，4条raw:729-792均在等待WebKit DOM时失败。当前frontend/node_modules已存在，须按既有前置生成ignored资源后重建验证，不改四条DOM断言/等待，不直接归成业务回归或声称已修成功。
- 为W6成功空会话真实画面扩展现有永久生命周期UITest，不新建文件：`testSuccessfulEmptyConversationStopsLoading`从同登录fixture真实列表进入专用空会话，等待既有`conversation.empty`标识、核同会话标题、断言不残留loading indicator并capture；仍需正常API seed并真实运行，不用内部store/SQLite注入。此条待独立增量审查/运行。
- 真机性能准备的实际缺口：首次seed已移到`ChatStorageController:181`，旧`ChatStore.loadSeed`区间只覆盖后续读，不能拿后续读当首绘读。新增位于`ChatRepository.bootstrapSeed`实际函数体内的`com.nanoim.app / ChatRepository / bootstrapSeed`只诊断signpost，覆盖两个caller且不包含open/migrate/network；旧controller.open与ChatStore区间不混作该指标。尚无真机trace/20次统计，不因加入打点声称达标。
- 本组后自有557精确名称/UDID before/after均Shutdown，53703 connect61，所有自身作业收集，无新服务。只读设备发现现在已配对手机available；这不是操作个人手机、签名/独立App或临时HTTPS入口许可。父级已向真人询问最小具体许可，尚无答复，不启动真机/隧道；模拟器与自有fixture可继续。

### 定点修后验证：51条PASS，原完整失败保留

- 产品/测试冻结`b66289f3c`，原reviewer最小增量静态APPROVED0C/0W（review.md Round7），不替代运行/性能验收。
- 先执行既有`pnpm --filter @nano/product-contracts build`与`npm --prefix src/IM/frontend run build:ios-ui`，均exit0；日志`/tmp/feat714-contracts-b66289f3c.log`、`/tmp/feat714-ios-assets-b66289f3c.log:31-42`，实际生成IntelligentUI/index.html与assets。保留bundler的大chunk/annotation提示，不将它们称无warning；ignored产物不提交。
- `xcodebuild test -jobs 2 -parallel-testing-enabled NO -scheme NanoIM`仅选ChatPhaseTests、ChatRepositoryTests、InteractiveRuntimeTests，同557与derivedData，结果`/tmp/feat714-native-affected-b66289f3c.log`、`.xcresult`，**exit0 / 51 tests / 0 failures / 0 unexpected / TEST SUCCEEDED**（:795-848）。日期7、repository33、InteractiveRuntime11全部通过，原4条WebKit DOM失败身份均实际PASS（:802-828），未改变断言/timeout/skip。此为定点修后绿，不追认原175总FAIL为成功或冒充完整scheme/CI。
- 收集本批job；精确557实际名称feat-714-native-acceptance/UDID匹配，实查Shutdown，53703 connect61。初次资源核验误用预期设备名称守卫而exit1，在任何变更前中止；读取返回实际名称后仅重做只读核验exit0，没有误操作其它设备。

### 生成资源后的完整原生scheme：PASS（保留真机skip）

- 同一冻结产品`b66289f3c`、557/derivedData执行完整NanoIM scheme，既有资源前置与上述51条窄测先通过后再扩大。`/tmp/feat714-native-full-assets-b66289f3c.log:580-658`与`.xcresult`，实际**exit0 / TEST SUCCEEDED**；summary`/tmp/feat714-native-full-assets-b66289f3c-summary.json`为**175 total = 174 passed + 1 physical-device protection skip + 0 failed**。XCTest148含1 skip/0 failures/0 unexpected，另SwiftTesting27 pass。原日期与4条WebKit身份本run均通过；原首次175总FAIL不覆盖/删除。
- 随后相同产品`NanoIMJourney build-for-testing`成功，`/tmp/feat714-native-journey-b66289f3c.log:251`；Info.plist revision实查b66289f3c。本次完整原生测试通过，不等同于Release archive、后端/前端完整CI、真机属性/flight或20次性能通过。

### 成功空会话真实原生路径：PASS（独立产物审查通过）

- 同53703原DB/JWT与真实登录session，唯一自有IM新日志server-empty-b662.log/PID89862，实查argv与health200。通过正常API登录原合成账号，创建专用空group **Release planning / c_drj7ef6y**，GET messages确认items=[]；不写客户端SQL/cache。保留原Product launch与旧运行结果；新的private input/runner另存0600，不含reset opt-in。empty-manifest-b662.json绑定b662产品、同557/origin/新chat与runner，binaryInfo revision实查b66289f3c。
- 实际运行`testSuccessfulEmptyConversationStopsLoading`，`/tmp/feat714-native-final-dphmlbb6/empty-b662.log:22-60`、`.xcresult`：真实launch→20秒目标列表谓词→进入Release planning→15秒既有conversation.empty正向断言→同NavigationBar标题→无Loading conversation indicator→capture→terminate，**exit0 / 1 test / 0 failures / 0 unexpected / 9.295s / TEST EXECUTE SUCCEEDED**。复用已有真实登录，不冒称此test重新登录；9.295s是test总时长，不是首绘性能。
- 作者与原非作者各自用read_image实际打开原始attachment`empty-b662-attachments/F542CB6D-F7C5-47E7-BB08-642722738716.png`（1206×2622px / 402×874pt）：标题明确、No messages yet可辨、无spinner/离线错误/需要连接占位，底部输入区保留。连续操作log与图共同证明正确目标的成功空结果已完成，不是只凭静止图或绿test推体验。原reviewer裁决**指定旅程/限定体验PASS，findings=[] / 0C0W，W6真实画面pending关闭**，见review.md Round8。
- 停止仅本IM job并收集SIGTERM，实查PIDgone、53703connect61、精确557Shutdown；全部本批jobs收集，无其它服务/Gateway/模型。独立reviewer复用这些owner receipt，不伪称其实时探测。
- 仍须原契约其它真实路径：旧构建实际未确认JSON→覆盖升级、账号/服务隔离及membership/撤权/401客户端矩阵；真机flight/protection与≥20次trace；跨包CI、最终unit门禁。空会话PASS不替代这些项。

### 无签名Release设备架构归档：PASS（未连接/安装手机）

- 同产品`b66289f3c`，既有生成资源，`xcodebuild -jobs 2 -scheme NanoIM -destination generic/platform=iOS -configuration Release CODE_SIGNING_ALLOWED=NO archive`实际**exit0 / ARCHIVE SUCCEEDED**，`/tmp/feat714-native-release-b66289f3c.log:2167`。产物`/tmp/nano-ios-714-release-b662/NanoIM.xcarchive`的App Info.plist实查bundle win.nanoim.ios、revision b66289f3c、0.2.0/634，file确认Mach-O arm64。
- 本地unsigned构建不需要连接个人设备，未执行签名/安装/启动手机，也未生成或分发已签ipa；不等同于手机安装可行性/Developer Mode/信任、APNs或真机flight/protection/性能证据。新增UITest不编入archive产品，后续head产品未变时本记录可按diff复用。

### 真实旧JSON升级旅程准备：构建通过，权限拒绝后未执行

- `69ca74061`新增四阶段真实UITest及停自有origin握手，不改产品；原非作者独立静态审查0C/0W（review.md Round13）。按顺序计划：旧App真实UI登录/输入→核原origin健康200/明确run marker→host核自有PID再停服→UI按Send落真实JSON；同bundle不卸载覆盖current→离线pending计数/完整说明无placeholder→联网只核对不自动发送→显式Retry后唯一消息。不得从测试源码存在推这些步骤已运行。
- current Journey build实际exit0，`/tmp/feat714-upgrade-journey-69ca74061.log`；旧干净detached worktree `005a360579d9e2c73f0a613073bcaecd705b7e62`独立generic simulator build实际exit0，`/tmp/feat714-legacy-build-005a36057.log`，DerivedData分别`/tmp/nano-ios-714-resume`与`/tmp/nano-ios-714-legacy-005a36057`。实际两App Info均win.nanoim.ios，revision分别69ca74061/005a360579d9；未安装/启动旧版，未生成真实pending JSON，四阶段均未运行。旧renderer资源未生成，此纯文字准备构建不作为旧版WebView/全功能验收。
- 原拟同自有53703新建专用合成账号/审批/私聊和历史，以避免现有current分区migration marker污染首次导入前置。**工具明确拒绝**：其理由为用户仅授权现有账号测试并明确不建新账号。没有Python stdout/exit或写入回执，不声称命令有部分执行；没有换账号/路径/工具重试。
- 已将原命令/准确拒绝/原方案与复用已有C方案的真实副作用回交父级核原人话；父级明确先保持这一整组旧迁移操作暂停、不复用账号探许可。现有C也不能自动视作新授权：仍会改auth/session/UI身份/客户端持久状态及最终发消息。取证文本仅留本机`/tmp/feat714-native-final-dphmlbb6/upgrade-permission-denial-13625.txt`，不含secret实值。
- 仅收集已启动build与清理自有IM837/PID71722；实核PIDgone、53703connect61、精确557名称/UDID相符且Shutdown，无运行资源。升级真实验收仍**未完成/权限待核**，不是测试失败、不是通过或允许降低前置。

### 后续产品修改后的完整原生scheme：PASS（保留真机skip与诊断）

- 冻结`4dc09fcb67c58657bf2eef1060c7c1f789e6028c`；本批独立于暂停的升级组，只运行同557的完整NanoIM scheme，未启动服务、创建账号/会话/消息或启动旧版/升级旅程。既有ignored renderer资源存在，`-jobs 2 -parallel-testing-enabled NO`、同`/tmp/nano-ios-714-resume`。
- `/tmp/feat714-native-full-4dc09fcb6.log:720-798`、`.xcresult`与导出`-summary.json`实际 **TEST SUCCEEDED / 175 total = 174 passed + 1 physical-device protection skip + 0 failed**；XCTest148含1skip/0failures/0unexpected，另SwiftTesting27pass。Debug App实际Info实查win.nanoim.ios/revision4dc09fcb6。该结果覆盖cf686可见detail发布与95923撤权空态产品增量，不以旧b662完整绿代替新执行。
- 原始log:318/326/331/335仍有LocalFirst临时fixture的vnode-unlinked SQLite诊断，WebKit ProcessSuspension及AppIntents metadata warning也保留。断言均通过不能解释成零诊断、全局fixture生命周期已修好或实际产品库损坏；此前失败与修复记录不覆盖。
- 随后同冻结产品`xcodebuild archive -jobs 2 -scheme NanoIM -destination generic/platform=iOS -configuration Release CODE_SIGNING_ALLOWED=NO`实际 **exit0 / ARCHIVE SUCCEEDED**（`/tmp/feat714-native-release-4dc09fcb6.log:2182`）；`/tmp/nano-ios-714-release-4dc09fcb6/NanoIM.xcarchive`内实际Info为win.nanoim.ios/4dc09fcb6/0.2.0/634，file确认Mach-O arm64。未签名、未接手机、未安装或分发ipa。完整测试与归档串行job841已收集exit0。
- 本批收尾实核精确557名称/UDID相符且Shutdown，53703 connect61；无本批服务、模型或GUI旅程。此完整scheme不包含显式分阶段NanoIMJourney运行，**不关闭**升级、账号/服务隔离、真实401/离线期间撤权、物理flight/protection/20次trace、跨包CI或最终unit门禁。

### 跨包本地CI：后端2项真实FAIL，其它阶段通过

- 冻结`92fb1218bfcf629b738b5de7ec6cef2232af200f`，串行job848完整收集**exit1**。Node24.22.1/Python3.12.9/pnpm11.7环境，`/tmp/feat714-crossci-92fb1218b/summary.json`保存11阶段的精确argv/退出码/耗时，各rawlog同目录。没有执行被暂停的IM/迁移/撤权fixture操作。
- `python3 scripts/dev_host.py check`、Journey build、`pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`均exit0；Python `pytest -m 'not e2e' -q`为**135pass/28deselected/20.72s**；ruff check与format --check均exit0。frontend tests为**113files/1078tests PASS/118.31s**，原始stderr含mock404及runtime warning，不称零诊断。
- frontend `npm audit --audit-level=critical` exit0只证明本次无critical阻断；raw报告仍有**11 vulnerabilities（4low/2moderate/5high）**，未autofix/改依赖，不写成零漏洞。
- **后端真实FAIL**：`pnpm test --maxWorkers=2` exit1，backend-tests.log:4106-4216为**216files=214pass+2fail，1174tests=1172pass+2fail，862.42s**。两个失败精确为personal-security的ordinary Global完整fixture，以及workspace-tools的安装/隔离/失败重试/重启完整fixture；均`RpcError -32000: Temporary inspection cleanup could not be confirmed`。日志先完成catalog.built与DSH内层cleanup.done，再报外层cleanup.error；不是30秒或120秒test timeout，也不是已证明的skill标题断言错误。
- 源码`packages/dsh-integration/src/configuration-inspector.ts:188-194`将terminateWorker或rm(home)任一失败统一替换该错误，原日志没有下层cause，故**尚不能确定清理哪一分支/底层原因**。未扩大714范围修DSH、改timeout、删断言或吞错。merge-base三点diff为空不代表精确当前target相同：当时缓存origin/develop为`1fc7455d554f319d8a822933500f765cb4f86ad2`，精确比较仍有global-mode prompt与global-inbox-native测试上游差异；未sync/rebase，不宣称当前target同树或已证baseline flake。

### 最小串行复查：两例均PASS，只证明本次未复现

- 不更新依赖、不改产品/fixture/timeout/内容断言，后续`d0eb4c825`仅比92fb新增UITest guard及文档；后端源码与built lib不变。串行job856先通过当前最后guard的Journey build，再依次执行两个原失败**完整fixture**：`pnpm exec vitest run <原file> -t <原完整test名> --maxWorkers=1 --no-file-parallelism --reporter=verbose`。精确argv/退出码/耗时见`/tmp/feat714-independent-recheck-d0eb4c825/summary.json`，三个阶段均exit0。
- personal-security-isolated.log:6,15-18为**1pass/9按-t未选skip/24.08s**；workspace-tools-isolated.log:4-9为**1pass/77.86s**。不是将完整fixture裁成preview，也不是全后端或全CI补跑；单次隔离绿**不证明并发负载就是根因、不关闭原全量FAIL、不证明已修复**，保留两份原红log。
- 两批job已收集；实核原失败fixture根目录`pa-global-capabilities-TbxCcI`、`nano-workspace-tools-AXzwuf`均不存在，进程表对这些精确路径/同fixture前缀及本批714临时路径无匹配。该一次收尾观察不反推失败当时已清理或证明永无孤儿。精确557为Shutdown、53703connect61；无自建IM/模型/GUI运行，保留待许可恢复的worktree和私有产物。
- 当前仍**不能宣布完整CI/全unit通过或归档交PR**：原后端全量失败原因未闭合；目标分支sync及最终证据有效性/归并门禁未执行；两次权限拒绝相关本地真实矩阵、真机flight/protection和≥20次trace仍分别未完成。独立单例/构建通过不改变这些状态。

### 清理核因续查：一次有界宿主诊断未复现，原根因仍未知

- owner与原只读helper分别核src/built lib及RPC：两次同refresh已有inspection.start→catalog.built→内层cleanup.done→外层带refresh/home的cleanup.error，定位到`run`外层finally，而非initialize/recover孤儿路径。内层done只证明`index.ts:427-432`的handle/unregister/cron disposer未抛，不证明OS组已退出；preview也不能仅凭此认定prompt assembly/RPC已成功。
- 被统一覆盖的候选精确为：组SIGTERM/SIGKILL的非ESRCH错误、worker.exited拒绝或500ms未settle、`ps`本身1秒timeout/执行错误/输出上限、十轮仍有非Z同PGID成员、最后递归rm的IO错误。普通ESRCH已明确接受；exited监听ChildProcess exit而非close，不保证整个组/stdio已结束。外层catch也包成功log，但两fixture的onLog只是字符串追加，未见自定义throw证据。`rpc.ts:94-97`只序列化message/-32000，fixture最终rm又已删除inspection.json/PID，现有产物不能恢复历史原error或阶段。
- 可排直接child PATH误传：RuntimeClient只将workspace的no-global-tools传给DSH child，inspector在Vitest宿主，groupAlive的execFile无env覆盖。相同pinned Node/pnpm exec环境各一次host-only `ps`与`/bin/ps` probe，均exit0，29.016ms/23.505ms、7887bytes/717rows、stderr0；只排当前确定性命令解析/参数不兼容，不反证历史瞬态timeout/组/IO。原全量的configuration-inspector既有6例也实际PASS（raw:546），不是本次低频失败的复现。
- 向父级带回观测缺口后，其明确同意**仅本仓configuration-inspector层、两完整fixture的一次受控并发和本机去敏产物**；不包括714已STOP业务组、安装的DSH包/执行运行时或扩修实现。选择临时Vitest config的Vite pre-transform，严格匹配repository绝对`lib/configuration-inspector.js`，仅Vitest宿主加载时加阶段/worker exit/kill/ps布尔/安全error字段。无NODE_OPTIONS或传播到child的loader，原src/lib/test/config磁盘不改；保留全部原断言、30s/120s test timeout、150/500/1000ms和十轮/50ms参数、信号/异常语义。同步JSONL及exit观察回调有时序扰动，未声称零扰动。
- 原只读helper先独立核临时149行config/338行语法预检模块，0个阻止执行的问题；owner唯一一次`pnpm exec vitest run --config /tmp/feat714-inspection-diagnostic-e0ff8a638/vitest.diagnostic.config.mjs --reporter=verbose`，后台job866收集**exit0**。`run.log:6,14-19`为**2files/2pass+9按名称未选skip/73.80s**；personal完整fixture26.212s、workspace完整fixture73.481s，summary wall75.835s，validated_at=e0ff8a638。不是1174条全量补绿。
- 实际`events.jsonl`146条可解析：1次module.transformed、2个Vitest宿主module.loaded；宿主各6/5个worker，总11个完整spawn→terminate→exit→组确认→rm闭环，活跃区间确有重叠，非仅配置声称并发。全部worker exit code0/signalnull、exit.confirm true，SIGTERM成功后的SIGKILL均为**accepted ESRCH**而非失败；各首个ps即alive=false，ps27–56ms、rm3–7ms。无worker.error、ps.error、group.unconfirmed、cleanup.error.detail或非接受kill.error。原helper又独立逐行核raw/events/summary，认可实际hook覆盖及本次未复现，不称关闭历史FAIL。
- owner逐worker程序核事件闭合/真实并发、七个src/lib/test/config原hash全相同；精确本批宿主/worker PID及进程组无残留，相关fixture/714临时路径进程扫描无匹配，精确557仍Shutdown、53703connect61。root0700，events/run.log/config/生成模块0600；summary仅去敏元数据、在0700目录内。`verification.json`为完整核验receipt。临时诊断config/生成模块/JSONL只留本机供复查，不提交永久测试或安装使用。
- **结论仍是历史host硬清理确认链具体失败分支/根因未知，不是修复或CI closure。** 本次未进入原catch，不能据此认定负载、ps timeout、PID竞态或rm为根因，也不把accepted ESRCH误当11次失败。按一次有界范围结束，不继续盲循环pair/full、不扩修714外实现；若需后续复现须另选有具体区分价值的观测/条件。两次许可拒绝相关业务矩阵继续STOP，原全量红与最终sync/CI/unit门禁保留。
