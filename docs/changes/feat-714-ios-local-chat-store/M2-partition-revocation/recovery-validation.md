# M2 真实客户端隔离与撤权验证

## 范围与授权

沿用design.md M2产品判据，不新增目标。当前按[用户最新更正与本轮模拟器范围](../M1-local-first-paint/recovery-validation.md#当前执行范围用户更正后仅模拟器)执行：已披露的隔离服务/合成账号DB/成员与凭据失效矩阵直接接续，旧拒绝与“未答”仅属历史，不再作为当前许可阻塞。仅自有557/loopback/合成数据，无生产或手机/tunnel。父级随后已给714单批窗口；原升级准备遇新的实际工具拒绝，未运行UI即停服并交出窗口给720，详见[新窗口实际拒绝与回收](../M1-local-first-paint/recovery-validation.md#新窗口尝试新实际拒绝不是旅程执行或待用户重新许可)。父级处理工具判断/上下文接续异常，不再向用户重复请批；当前只做独立静态/材料，被拒升级组不动，其它真实矩阵另协调窗口。

## 首次真实membership旅程：online FAIL / offline未执行

- 产品/UITest `b18edba2b13e56c6e36ab93fc90537fc8fee5bd9`，`NanoIMJourney build-for-testing`实际exit0，`/tmp/feat714-native-membership-build-b18edba2b.log:254`。新UITest/helper经原非作者最小静态审查APPROVED0C/0W；其关于async fail-fast的一项论断随后被实跑反证撤回，见review.md Round9。不能将原静态APPROVED当运行通过。
- 同一53703/原DB/JWT/账号A nano，原先会话保持。唯一自有IM正常API注册B Morgan Review与C Taylor Review、申请并批准公司成员；B创建三人private group **Launch coordination / c_mf20miw6**，A不是creator。B正常发送完整工作消息 **The release checklist is ready for review. / 9c5f182b602d4b1abef2f80c8273b46e**；A的GET messages确认唯一message/content。私有账号/token/runner另存0600，不提交，`membership-manifest-b18.json`为无secret归属记录。
- 实际`testMembershipRenameThenRemovalUpdatesVisibleConversation`：`/tmp/feat714-native-final-dphmlbb6/membership-online-b18.log`、`.xcresult`、`membership-online-b18-summary.json`，**exit65 / 1 failed test / 0 passed / result Failed**。真实列表→进入→完整正文通过→普通API PATCH完成后，新navigation title在15秒仍未出现（:44-93）。没有把timeout扩大或换短关键词重试。
- 作者实际read_image导出的`membership-online-b18-attachments/0A0B908E-5F50-4535-B161-B231FE6F5533.png`，仍为旧Launch coordination标题、全文可读；失败AX `FB530AAA-01B2-4228-ABBB-B398DC97BC8A.txt:14-35`同样旧title与完整message。因此不是弯引号/selector纯差异，确有标题未校正的用户可见结果。保留21个原始attachments及录屏，不覆盖原FAIL。
- **async fixture边界反证**：虽然continueAfterFailure=false，失败:93后仍在:94-99检查全文并截图，:100 TearDown后:101进入下一撤权等待，最终unexpected restart。故不能依赖该属性阻止async方法后续fixture写入；原reviewer已明确撤回该静态论断。失败后的步骤不计有效验收，offline未运行。
- 立即停止唯一自有IM job778并收集SIGTERM；实核PID5474 gone、53703connect61、精确557名称feat-714-native-acceptance/UDID匹配且Shutdown，无其它自身服务/GUI/模型残留。diagnostics utility72在测试后，不当assertion根因。

## 原因复现与最小修正

- `ConversationView`优先使用同ID的`inspectedConversation`，真实`openConversation`通过detail请求设置它。membership `verifyAccess`只经persistConversation更新list row，未更新仍优先显示的detail，因此列表可改名而当前标题一直旧。
- 复用并增强既有`ChatLocalFirstTests/testMembershipRenameRechecksWithoutClearingTheTimeline`：初始detail=Original→真实store.openConversation→确认detail与3条timeline→正常membership事件→保留原Renamed list、timeline及messageReadCount==1断言，新增可见detail也应Renamed。未改产品时实际 **RED / 1 test / 1 assertion failure / 0 unexpected / exit65**，`/tmp/feat714-membership-detail-red.log:298-316`，唯一失败为Original≠Renamed。这确定了该路径缺陷，不把所有事件传输问题都归于它。
- 首轮修正1441ea83f把同ID detail更新放在共享persistConversation；修后LocalFirst21+Repo33+State11共65测试0失败0unexpected、Journey build exit0，日志`/tmp/feat714-membership-detail-green-1441ea83f.log:497-507`与`/tmp/feat714-membership-journey-1441ea83f.log:248`。这些没有覆盖下一条迟到/read交错，不能据此宣称修正已收口。
- 原reviewer在1441提出W8（0C/1W）：共享writer也由markRead调用，旧/read DTO可覆盖刚由membership校正的可见detail。将既有rename测试继续增强为open Original→hold旧/read→membership Renamed→release旧/read，并检查确认的read_state仍记m3。未改产品实际RED：`/tmp/feat714-late-read-detail-red.log:295-303`，1 test/1 assertion failure/0 unexpected/exit65，唯一失败为late read后detail Original≠Renamed。
- 后续最小修正cf6869499把同ID inspected发布移到verifyAccess成功且当前请求guard后；共享persistConversation不再改detail。原inspectConversation发布、/read列表/持久化与已确认boundary语义保留；不新建全局新旧排序协议，不加请求/全量sync，不覆盖其它查看目标。修后同65测试 **0 failures/0 unexpected/exit0**，其中增强rename实际PASS（`/tmp/feat714-late-read-green-cf6869499.log:280-281,501-511`）；Journey build exit0（`/tmp/feat714-membership-journey-cf6869499.log:139`），实际bundleInfo revision cf6869499。原reviewer代码层关闭W8/0C0W，见Round11；真实UI另记。
- 新async UITest各关键前置、动态ID、loopback URL、HTTP状态及rename/revoke结果改用显式guard→XCTFail→throw，保证控制流终止而非假定XCTest自动中断；defer terminate。正文/目标/15秒与5秒判据不放宽。helper边界需实际受控失败验证与独立复核，尚不因源码存在称已通过。
- 只读Python sqlite查询原DB曾返回unable to open database file；文件metadata/header正常但原因未定，不据此称数据库损坏、不做修复/重建或修改DB。需要核fixture后果/恢复时使用本origin正常API，不将失败查询当完成。

## cf686真实运行：边界与功能通过，实际画面发现恢复建议冲突

- 正常API确认首次b18失败后确已将A移出（B视角title revised、members仅B/C，A GET404）。首次复查碰到已过期B access token401，正常B用户名/密码登录刷新后处理；未用旧token反复重试或改库。用B正常POST participants恢复A、PATCH回原title，A正常GET核三人/全文/唯一消息；`membership-restore-cf686.json`留无secret前后状态。旧FAIL/私有输入未覆盖，新input/runner0600。
- 受控invalid operator：唯一更改token为无效值，其他完整目标/正文/客户端不变。`membership-invalid-cf686.log:25-43`先真实列表和全文、before截图，HTTP状态guard在:40失败，:41立即terminate、:42 teardown，没有进入after-rename/撤权等待或后续截图。实际exit65、summary1failed/0passed；保留unexpected runner restart与diagnostics72，不称测试绿。正常API随后核原title+三成员仍在（`membership-invalid-state-cf686.json`）。结合显式throw静态控制流，这是预期失败停止边界证据，不是产品acceptance PASS或独立网络请求审计。
- 有效operator真实online：`membership-online-cf686.log:35-85`与`.xcresult`/summary，**1 test/0 failures/0 unexpected/exit0**。真实进群→全文→PATCH改名→新title和全文→DELETE移出A→撤权说明/全文消失→返回列表无群→terminate。正常API随后核title revised、两成员、A GET404（`membership-online-state-cf686.json`），非本地store注入。
- 只停止本批唯一IM job803/PID37884，实核PIDgone、53703connect61，未改origin/DB/JWT/账号；同bundle offline relaunch `membership-offline-cf686.log:20-53`与summary实际 **1 test/0 failures/0 unexpected/exit0**。5秒内原Product launch仍在、无登录、revoked群/正文不在→截图→terminate。收尾核精确557/feat-714-native-acceptance Shutdown、origin仍不可达；没有真机flight等价声明。
- 作者实际read_image四张online原图及一张offline原图。前后rename全文可读、标题确已更新；online/offline列表保留两条其它会话，无已撤权群，offline有未连接+更新时间。**但online撤权画面`membership-online-cf686-attachments/7E83AA5D-9E18-4617-9507-EBBC79D60991.png`同时出现红色不可访问与中央“连接后自动读取”/Retry。** 用户已确定失去权限，却被建议靠重连恢复，属于真实体验FAIL，不能由功能测试绿盖掉。
- 原因：revocation清timeline并设置errors后，通用empty分支把`timelinePhase.needsConnection`当作缺缓存，未排除revoked。最小修正仅在已revoked时不画通用empty/needsConnection占位，保留专用撤权说明/正文隐藏；原正常empty/无缓存offline不变。既有membership UITest增强“不出现连接恢复建议/Retry”的真实画面断言。此修正以实际截图为失败证据，修后构建与对应旅程/独立体验复核待执行。

## 95923实际复验与独立限定closure

- 95923c3f5 Journey build实际exit0（`/tmp/feat714-membership-journey-95923c3f5.log:339`）；沿同origin/DB/JWT正常B登录恢复A+原群名，核三成员/同一全文唯一消息。新私有input/runner0600，原产物保留。
- `membership-online-95923.log:28-85`与`.xcresult`/summary实际 **1test/0failure/0unexpected/exit0**；完整改名/撤权/返回列表过程未弱化，新增无错误连接建议/无Retry断言在capture前实际通过。作者和原reviewer分别read_image `membership-online-95923-attachments/1A2F862B-D38C-4C68-8D33-A4189AD9D97A.png`：专用撤权说明保留、正文隐藏，中央假恢复建议与Retry消失，返回可达。
- 同原reviewer加载产品旅程+体验+代码能力，独立核新版image/rawlog/summary/manifest/fresh runner/buildInfo，同ID/bundle win.nanoim.ios/revision95923c3f5，**W9实际CLOSED / 指定旅程与限定体验PASS / 0C0W**，见Round12。cf686 offline列表证据可复用：本次仅影响revoked detail空态，未改storage/tombstone/list/relaunch，且offline测试不打开detail。不推全程每帧无闪回或≤1RTT。
- 额外同源正常empty回归`empty-95923.log/.xcresult`实际1test/0fail/0unexpected/exit0；作者实际read_image `empty-95923-attachments/6A533628-9A8E-40C9-91E1-85E2B0470852.png`：Release planning/No messages yet/composer正常，无spinner或缺缓存提示。新revoked排除未破坏正常成功空态。
- 本批自有IM819/PID53681已停止并收集SIGTERM，实核PIDgone、53703connect61、精确557名称与UDID相符且Shutdown，无本批运行资源残留。该receipt不是reviewer独立实时探测，更不是物理flight证明。

## 独立剩余矩阵准备：尚未运行

- 在升级整组保持暂停的前提下，继续原授权的其它独立部分；不建新账号/会话/消息，不用已有C绕行升级。拟复用53703已存在A/B和同一Launch coordination群/完整唯一消息，用正常成员API恢复A后先真实读取并terminate；只停自有origin后离线新进程确认该群全文仍可读并terminate；恢复origin且A App仍不运行时由B正常移出A，随后A首次联网冷启收敛，最后再次停服/冷启确认已知撤权不回归。
- 新增现有UITest文件内的真实读取、冷启收敛、已显示正文后401及后续重开登录四个方法，复用既有完整正文/实际UI/显式throw/defer terminate；未改产品。收敛test只停留列表，不tap已撤权详情或pull-to-refresh，避免把detail403或普通/conversations缺项冒充首个/sync权威差分；正向保留其它会话后15秒异步等目标消失，再核无登录/无降级/无目标全文。**源码存在及断言等待不是已验证≤30秒活跃重连，也不是从首次/sync起的精确计时证据。**
- 401仍须按design既有自有合成DB的auth_epoch或会话吊销构造，再由客户端真实refresh401进入.credentials路径；host另行login/logout只撤其自己的sid、UI Sign out会提前本地清理，两者均不能替代本项。新增active方法先核真实全文，再用run-bound stdout marker与独立A control token `/auth/me`从200变401协调epoch已生效，随后Home→activate触发真实前后台重新核权，等待登录表单/旧内容消失；control请求不冒充App请求。后续重开方法复用同登录断言。仍需真实服务端App refresh401及重开/文件边界证据，不能仅凭登录页认定purge完成。
- `92fb1218b` Journey build-for-testing实际exit0（`/tmp/feat714-crossci-92fb1218b/journey-build.log`）；真实UI仍未运行、未恢复成员/撤权/改认证DB。原非作者仅静态审查发现W10：active401直接activate可在原进程已死时自动冷launch，伪装同进程清理；owner核安装SDK公开XCUIApplication.h:65-72确认。最小修正增加协调后仍前台、有界等待后台/挂起、activate前仍运行的显式guard；实际验收还须核PID连续，不凭activate后foreground状态证明没重启。此最后guard的build/独立closure另记。
- **新的实际权限拒绝**：尝试write临时observer脚本时被拒，准确理由为“该脚本会用已有验收数据库在原端口启动 IM 服务，并记录认证与同步请求状态；这涉及共享服务及账号会话行为，而现有授权要求的是隔离测试且禁止在未确认前启动服务，不能据此授权复用该数据库和原服务端口。” 脚本仅拟import未改产品createServer、同自有DB/53703、onResponse留时间/路径/状态、无token/body/新路由；write未成功，随后glob确认文件不存在，没有服务启动/API或DB副作用。本机完整参数/内容/拒绝回执保存在`/tmp/feat714-native-final-dphmlbb6/matrix-permission-denial-14960.txt`。
- 两次实际拒绝相关本地组均保持停止，不去掉observer或换工具/端口/DB重试；父级已向真人合并询问具体本地fixture许可，**尚无人类答复，不是放行**。跨包CI和静态修正独立继续；升级、手机/公网原边界保持，不将新UI准备或静态审查当运行许可或通过。

## W10最后guard：独立静态closure与当前构建通过，真实UI仍暂停

- 原非作者对`d0eb4c825`最小9行guard集中复核，W10静态CLOSED、APPROVED0C/0W、findings=[]，见review.md Round15；不将公开state等同于PID身份、App refresh401或清理证据。
- owner串行job856第一阶段仅执行当前`NanoIMJourney build-for-testing -jobs 2 -parallel-testing-enabled NO`，**exit0 / TEST BUILD SUCCEEDED**（`/tmp/feat714-independent-recheck-d0eb4c825/journey-build.log:250`）；实际Debug App Info为win.nanoim.ios/revision d0eb4c825，覆盖最后guard的typecheck。保留旧setUp actor-isolation/Swift6及scheme/AppIntents warning，不称无warning。未执行任何Journey UI或启动IM；后续阶段为独立后端单例CI。
- job856全部已收集exit0。实核精确557名称feat-714-native-acceptance/UDID匹配且Shutdown、53703connect61；未恢复成员、改认证DB或运行升级。上述构建/静态结果不解除两次拒绝相关本地组暂停。

## 当前未完成

账号切换、第二origin服务切换、旧构建真实JSON升级、真实401与离线期间撤权恢复矩阵、最终target sync/适用集成门禁及交付；CI历史两红未知保持如实披露，按最终版本评估有效CI，不盲重复核因。以上不由限定membership/empty PASS、最后guard构建或单例补验自动关闭。旧文暂停已由最新用户澄清解除，不再等用户重复给测试许可；本次新实际工具拒绝及回收状态以上方当前范围链接为准，原升级组停待父级工具上下文调查，其余真实矩阵再协调窗口。

真机flight/protection/20次真机trace仍UNVERIFIED、本轮不执行，不作为本轮模拟器交付门禁，也不冒称由模拟器证明。
