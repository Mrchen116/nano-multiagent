# feat-716 — 恢复实施记录

> 本页下文为早期单卡集成与恢复阶段的历史记录，不代表当前多卡增量状态。当前独立结论见 [review](review.md)；新隔离59469的 Web/原生完整多卡三消息、实际 `inbox(action=read)`/后续模型步、原生transient真实保存恢复，以及Web73,021-byte预算拒绝的限定独立支持见 [多卡验证](evidence/multi-card-validation.md)。用户更新工具策略后已正常执行新context的Web连续失败/保留正文附件/缩短重发/nextnone，并获原reviewer限定SUPPORTED；原生预算连续失败/同正文同图片恢复/nextnone现已真实绿色，待原reviewer冻结补验，整体未验收/交付。[两次精确拒绝与恢复点](evidence/budget-tool-refusals.md)保留旧未执行调用及当时资源状态，不倒算旧清场成功。旧58项待验、旧模型配置缺口等历史描述不得覆盖 review 中后到的实际结果。

## 当前恢复节点（2026-11-09）

- 交互卡片背景一次性消费（716）已自行解除父级后到明确撤回的泛化资源等待；本轮仅推进本事项，不联系或并行其他需求。原生正常Photos选择自制图、真实73,021-byte拒绝、同正文图片保留、正常CAS缩短、不重填重选重发、nextnone已实际完成：host `c5de4112-95fb-40be-b9c7-0520741040f4`，1 test / 0 failures / 57.915s / exit0。helper仅修异步精确回执等待，产品fc5不变；真实relay/Inbox/模型步与画面证据已补入多卡验证，待原独立reviewer冻结补验。旧失败与工具拒绝继续保留历史，不追改为通过。
- 最终目标同步尚未发生。对已获取的 `origin/develop` `68e65a880625cc0d19b034213c90f46fee3062c0` 作不改变 branch/index/worktree 的 `git merge-tree --write-tree HEAD origin/develop` 预演，返回 1（内容冲突，不是已执行的 merge 失败）：27 个共同修改路径中有 9 个冲突路径，覆盖服务端幂等/消息创建、Web composer/卡片、iOS ChatStore/InteractiveRuntime。当前 HEAD 仍为 `29f402e29616e090aaa2eda2c682d25c0b12a6a0`。旧完整旅程不能直接声称适用于该最终集成树，须实际解决冲突并按影响复验。
- 集成时保留新基线的引用回复、消息列表/附件可见性、执行清理等既有行为，同时保留本 unit 的中心派生背景、原请求幂等、会话级保存屏障与显式冲突采用；`merge-tree` 无冲突的文件同样需要语义核对。冻结与实际同步前不改运行 fixture 的版本绑定，不把预演对象当成执行过的最终版本。

## 版本与范围

- 当前集成基线：`origin/develop` `eeaea47921806936da20e78c9ed96167716f5037`，PR 目标 `develop`。旧 `unit/feat-716` `6e42f0fd8` 与全部 dirty 留在 `.worktrees/feat-715-integrated-bg`，额外备份 `/tmp/feat716-recovery.rXzQ9G`。新专属树 `.worktrees/feat-716`，分支 `codex/feat-716`，三方干净应用本 unit 已有提交差异和 Web WIP；没有 reset 或改主树用户 dirty。
- 范围以原 spec + 人类恢复决定为准：只修重复注入；Work/原生轨迹实际模型输入的可见性是正确行为，不做任何呈现修改。
- 旧 Gate 2 的目标与大体边界仍适用；已按负责人确认纠正最新卡失效后旧卡复活的 SQL 设计（见 design Changelog）。不得把历史 M1 证据或自检直接当当前独立实施门禁。

## 实施与测试策略

- M1 server 派生与 CAS/幂等底座迁入当前 develop；两端删除客户端选最近三张卡的权力。服务端自然消息与附件快照决定幂等身份，既有请求冻结背景由中心保存，旧指纹按共同字段比较。
- Web 继续保存真实改动；发送前 flush、冲突三列比较与显式采用、切会话串行清除及迟到自有保存补清除。复用既有 `im-message-attempts` IndexedDB，v2 仅追加 `watermarks` store，不新建独立数据库或迁移/改写旧 attempts；按 origin + account 隔离、单调 max、128 条上限，logout/revocation fencing。
- iOS 由独立实施执行者 `576bfcf4-453d-49c5-8ef8-f1fe431232cd` 负责同一 worktree 的 `src/IM/ios/**`，只改该范围，主执行者集成提交。两端改动不涉及 Work 展示。
- 既有行为保护的处置：Web `message-pane*`、`interactive-flow`、`interactive-card`、`chat-api`、`send-attempt-store` 重写旧 contexts 参数断言，保留真实私聊保存/群聊隔离/冻结请求/账号隔离等风险；删除卡片局部“直接载入最新”的绕过行为，冲突恢复集中到 composer 的只读比较→警示采用。`interaction-background.test.ts` 保护 coordinator 的持久化/清除链；`draft-failure-notice.test.tsx` 从真实卡片和 composer 接线保护失败恢复，不与 server pending SQL 重复。

## 有意义的失败复现与修复

以下为本次当前集成树新增红测，不冒称旧 M1 曾遵循 red-first：

1. Web 采用远端草稿 GET 失败：旧 `load()` 吞异常，采用句柄仍清冲突，发送按钮错误恢复。`draft-failure-notice.test.tsx` 的 `keeps the conflict and local edit when fetching the draft to adopt fails` 修复前实际失败（send 未 disabled）；修复后通过，保留本机编辑、正文和会话拦截，读取失败可再试。
2. Web 发送等待卡片保存期间输入新正文：旧实现 await 后取 live snapshot，旧发送成功把新正文清空。`message-pane-composer-draft.test.tsx` 的 `does not clear text edited while the submitted message waits for its card save` 修复前实际收到空值；修复后通过，await 前冻结正文/附件/composer revision。
3. 水位账号切换两条 race：`does not persist a save under an account selected while IndexedDB is opening`（错误写入 u2）与 `ignores a previous account discard completion instead of deleting this account watermark`（错误删除 u2）。修复前二者均红；修复后 coordinator tests 通过，持久化捕获 account/session、事务完成才 resolve，晚到旧 session 不改变新账号。
4. 服务端日期：`normalizes ISO offsets before comparing and ignores non-ISO date strings` 修复前非 ISO `11/05/2026` 被接受；修复改严格 ISO + canonical UTC 再比较，窄测试通过。
5. 唯一替换：`does not resurrect the earlier card when the latest edit becomes read-only or superseded` 修复前返回旧 A 非 null；负责人确认按原目标纠正设计与候选 SQL，最新失效直接 null，不回退旧卡。关联显式提交消耗另卡但不重复注入的测试保留通过。
6. iOS composer conflict、等待保存时错取新正文、foreground误把saved当leave、clear后旧send复活均有真实Xcode红→绿；最终编译57相关测试通过，owner已核验日志并集成 `7f109fdca`，见 implementation-validation。Web补同义持久化明确leave intent与hydration撤权race，两项真实红后修复，coordinator22/workspace61/failure5共88项和tsc通过。

## 已观察验证与限制

- 本机：`python3 scripts/dev_host.py check` 成功，Air、Node24.22.1、pnpm11.7.0；`pnpm install --frozen-lockfile`、contracts build、frontend npm ci 成功。依赖 audit 现有11项风险，无额外升级。
- Web 窄测试中的 coordinator19、composer18、send-attempt3、interactive-card14 已绿；composer conflict5/interactive-flow7 最后发现用呈现 prop `isDirectChat` 代替会话 type 会把测试中的 direct 当 group，现已改为显式 conversation type 透传，串行复验12项通过；`npx tsc -b` 通过。随后 `npm exec -- vitest run --maxWorkers=1` 前端全套 115 files / 1110 tests 全绿（202.93s，exit0，`/tmp/feat716-web-tests.log`）。
- 服务端新增唯一替换测试红后已修；`pnpm exec vitest run --maxWorkers=1 apps/im-server/tests/interactive-background.test.ts apps/im-server/tests/interactive-messages.test.ts apps/im-server/tests/message-attempts.test.ts`：42项通过，exit0。
- 共享主机存在其他任务；所有后续重测试低并发，Xcode `-jobs 2 -parallel-testing-enabled NO`，Vitest `--maxWorkers=1`。不停止其他任务进程。
- 已起真实隔离 daily 栈并按用户要求保留 preview：`.e2e-daily.json`，`http://127.0.0.1:62814/chat/c_4db28b34c71b`。真实 Web 改卡立即发→再发、双浏览器真实409→只读三列→显式采用、503拦截→手动重试、390窄屏实际画面已有证据。实际 Global native `inbox(action=read)` 输入与随后模型步支持一次性选择；没有本次HTTP/provider序列化抓包，方法调整由负责人明确决定，详见 [implementation-validation](evidence/implementation-validation.md)。iOS真实SwiftUI/WK只读渲染不替代完整App点击旅程，后者仍缺。当前独立门禁、canonical归并/归档/PR仍未完成。
- 独立门禁配置阻塞：可用 native subagent 接口没有 `model`/`reasoning_effort` 参数，不能显式选择当前适配表要求的固定审查模型。已向主 PA 报告，其明确：继承 + 记录差异不能等价门禁，不自审或造 CLI 替代协议；冻结时交事实包和具体配置缺口，由主 PA 处理所需的人类决定。

## 当前冻结与恢复条件

- `a1620db28`：server + Web 首轮集成；`7f109fdca`：iOS 57相关测试已绿的客户端实现；`2bdd02091`：Web明确leave-intent/异步hydration撤权保护（88项 + tsc已绿，最终bundle已构建）。
- `6deb4bdd4`：**WIP**，根据714只读兼容观察修正716自身的卡片ledger首绘主线程I/O；init空值、Session actor认证fence异步恢复、发送/切走屏障与reconcile预加载。新增测试预计使相关组58项；旧init真实红见 `/tmp/feat716-ios-hydration-red.log:189`。前一恢复草稿编译/签名已过，但simulator runner未启动（Invalid device state / Mach -308 server died）；之后补的prepare/立即leave测试未重编，**完整6deb4bdd4没有编译/测试green**。
- 负责人因共享host高负载要求暂停新重型测试/构建，等待其协调单组窗口。自有Xcode job `bash-297` 已收集为 killed/SIGTERM，精确PID12102已不存在；不停止其他任务。完整输出 `/tmp/feat716-ios-hydration-final.log`、恢复命令在首行；不把环境失败当代码根因、不反复重跑。
- 两个自建浏览器已关闭；daily preview按原用户要求保留。尚缺：58项green、完整原生App交互旅程、选定配置独立审查、最终同步/证据有效性、canonical与归档、本地CI及Ready PR(develop)。这些缺口不以“交事实包”替代。
- 与714组合需保留其repository pending与resetProjection，不恢复旧selection；会话撤权需要独立card-ledger cleanup接口而不能误删旧attempt JSON。目前只给接口设计结论，不改714树、不代其执行被拒持久化/删除操作。细节见implementation-validation。
