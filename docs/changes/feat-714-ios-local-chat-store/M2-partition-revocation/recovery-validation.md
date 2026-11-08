# M2 真实客户端隔离与撤权验证

## 范围与授权

沿用 design.md M2 退出标准，不新增产品目标。父级核对用户原话「714没做完…继续做」「所有feature开发都可以自己开独立的测试服务测试吗」，明确第二自有loopback origin属于原工程fixture范围；同557、纯合成数据、串行单IM，无新增Gateway/模型/设备。个人真机和公网HTTPS入口仍为独立未获答许可，未操作。

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
- 最小产品修正：persistConversation在当前请求guard后更新list时，仅当inspected ID相同也更新detail；不覆盖其它查看目标，不加网络请求/全量sync，不改变权限/持久化语义。修后窄测/真实UI待执行。
- 新async UITest各关键前置、动态ID、loopback URL、HTTP状态及rename/revoke结果改用显式guard→XCTFail→throw，保证控制流终止而非假定XCTest自动中断；defer terminate。正文/目标/15秒与5秒判据不放宽。helper边界需实际受控失败验证与独立复核，尚不因源码存在称已通过。
- 只读Python sqlite查询原DB曾返回unable to open database file；文件metadata/header正常但原因未定，不据此称数据库损坏、不做修复/重建或修改DB。需要核fixture后果/恢复时使用本origin正常API，不将失败查询当完成。

## 未完成

新fixture fail-fast窄验、修后membership在线→停止同origin→离线冷启、账号切换、第二origin服务切换、旧构建真实JSON升级、真实401与离线期间撤权恢复矩阵、真机flight/protection/20次trace及其它CI/最终unit收口。以上不由原174pass或空态图自动关闭。
