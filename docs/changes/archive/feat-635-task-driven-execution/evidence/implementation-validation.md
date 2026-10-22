# M1 实施与验证记录

## 实施边界

本记录仅涉及 unit 专属 worktree 与临时 E2E 栈，不代表生产部署。真实客户端使用专用虚构账号和任务；不提交原始运行数据库、模型日志或凭据。最终受审 SHA 在门禁报告中记录。

- IM 保存七状态、等待关联、原子暂停与幂等回执；等待写入在事务外检查原生 Schedule，提交时重查 revision 和未来时间。
- PA 解析当前产品身份与执行范围、检查等待健康、恢复责任与持久停止屏障。
- DSH 集成只使用公开生命周期、Inbox、followup/steer/pre-step、Schedule API；没有第二套 Agent Loop。
- Web/iOS 合并 doing + waiting 到进行中，等待事实与运行/连接信息分离；Goal 以显式 Feature 开启。

## 有效验证

| 范围 | 命令 / 证据 | 结果 |
|---|---|---|
| IM 等待、revision、幂等、全层责任、停止屏障 | `pnpm exec vitest run apps/im-server/tests/task-execution.test.ts` | 初始 3 项缺实现失败；实现后通过；追加真实 Gateway 写入跨客户端超时的暂停等待验证 |
| PA 独立审核后等待门禁 | `apps/im-server/tests/personal-disclosure.test.ts` | 通过；审核通过不替代真实 Schedule 检查，失败不落图 |
| PA 恢复 / 停止 | `packages/personal-assistant/tests/task-execution.test.ts` | UI 开始责任、旧会话安排失效、有效等待、离线停止持久恢复、确认重放通过 |
| 原生 DSH 续跑 | `packages/dsh-integration/tests/task-execution.test.ts` | 真实锁定版本 DSH 子进程；预入场刷新、并发人类输入保留、取消屏障通过 |
| 权限失败与末步交付 | 同上第二项 | 先复现失败：权限拒绝后额外启动第 3 次模型请求；修复后只产生拒绝动作及本轮阻塞回复，新 revision 才重新判断；任务退出责任后保留最终结果回复 |
| Single Thread 原生输入投影 | `packages/personal-assistant/tests/single-thread.test.ts` | 自动过程不推流、审批可见、NO_REPLY 保留已展示审批结果、不伪造入站回执 |
| Schedule 实证 | `packages/dsh-integration/tests/cron.test.ts` | 当前真实 owner/session/future 安排有效，错误 owner、已消费和禁用无效 |
| Goal 默认关闭 | `packages/dsh-integration/tests/goal-opt-in.test.ts` | 新旧配置默认关闭、明确开启、原生子 Agent、配置下一轮生效与竞争输入保留 |
| Web 快捷状态动作 | `src/features/tasks/task-graphs.test.tsx` | 真实 UI 发现缺少 change_note 导致 400；补齐协议字段并加入断言 |
| Web 运行信息 | `src/features/tasks/task-wait.test.tsx` | Global 使用 Work 事实；Single Thread 读取联系人连接事实，不请求不存在的 Global Work journal；不能核实执行时明确显示 unknown |
| iOS 初次完整测试 / Release 归档 | `src/IM/ios/scripts/build.sh test` / `archive` | 43 tests、0 failures；ARCHIVE SUCCEEDED；后续 UI 修正将另记录增量验证 |

## 真实模型 / 客户端发现与复验

2026-10-22，隔离 IM / node / DSH，DeepSeek V4 Flash 主模型，审核模型显式配置为已登记且支持 low 档位的模型。初始配置漏配审核模型，触发了可见且可操作的人工审批回退；该配置问题不作为产品缺陷。

1. Web 创建聊天并请求创建任务；真实 task_graph 写入、claim 和任务协作通知可见。
2. Single Thread 使用 Global `send_message` 路径会返回既有 `invalid_scope`；失败期间没有生成虚假的 waiting。该模式应通过聊天最终回复提出问题；Global 的显式出站另行验收。
3. 正在执行并等待审批时发送 `/stop`：取消当前操作、IM 将本人 doing 改为 paused，聊天确认“暂缓 1 项”。数据库真实状态与可见卡片一致。
4. Web UI 创建本人 doing 任务触发原生运行；模型成功创建真实 Schedule，但状态写入被既有权限规则拒绝，随后自动轮次曾热重试。此为本 unit 缺陷，已修复原生自动重试屏障并取得上述失败/通过证据。未修改生产授权策略或把系统提醒当人类授权。
5. Web “恢复推进”真实请求因缺 change_note 被拒绝，修复后待本轮复验；iOS 使用既有 applyTask 封装，已包含该字段。

后续真实等待、停止、改派、重连、两端界面对照及独立验收结果追加在此与 acceptance 报告中。

## 实际复验（2026-10-22 后续）

- Web 恢复按钮成功：同一任务 revision 2 paused → revision 3 doing，原生 task-execution 自动启动。隔离审批配置将 deny_limit 设为 1，仅用于直接进入人工审批覆盖；不是跳过权限，也不修改生产配置。
- 真实自动 turn 25：读任务 → 创建 after 600 秒 Schedule → 请求 task_graph 写入 → 自动轮次审批卡可见 → Allow once → revision 4 waiting。持久 wait 包含真实 schedule_id、owner_agent_id、session_id 与未来 next_check_at。
- 模型随后正常结束并返回 NO_REPLY。审批结果及工具轨迹保持可见，未移除已展示的卡片；没有为例行等待生成新的文本催促。
- Web 与 iOS 详情通过真实 inspect 显示有效 Next check、保留业务原因；iOS 点击 Pause 后 revision 5 paused，wait 字段被清除。
- Goal：Web 初始 unchecked → 开启并保存；iOS 读取 Value 1 → 关闭并保存，显示节点确认及下一轮生效。Web 重新读取确认关闭。默认/native 生效边界另由真实 DSH 测试覆盖。
- Web 全量：103 files / 960 tests passed。Python 非 E2E：62 passed，31 deselected。ruff check 与 format check 通过；前端 critical audit 通过（无 critical，有既有 low/moderate/high 项）。
- 后端全量：118 files / 550 tests passed，workspace-tools 一项 90s 超时；同一源码单独复跑 1/1 passed，38.29s。未放宽超时或改动该测试。
- 后续原生权限回归扩展：自动审核拒绝与人工拒绝均阻止相同责任的 idle 热重试，3/3 native Task tests passed。


## 独立审查后的收口

- R1 静态审查发现模型配置修复后的 error fence 与首次启用 Task 的 scope 发现遗漏，已修复并补真实 RuntimeClient 配置恢复回归。
- 真实原生回归覆盖工具 A 已进入时撤回 A、B 继续并最终交付；stop fence 随 runtime 重启恢复，真人输入和旧 native Schedule 在确认前均不进入模型；Schedule 消费后修复为新的有效安排并静默。原生可能分别处理 held 真人和 Schedule，且进行中一轮会消费新的责任 delta；这些不等于新的 Task 自动循环。
- 新增负责人只读观察 API，IM 测试验证先读 ACL、实际 assignee、无权限不发 runtime 请求及失败 unknown；native 工具挂起时 running、结束后 idle；Web 6 tests passed，构建 passed。iOS 与独立产品复验待最终冻结构建。
- 2026-10-22 修复批次：全包 build passed；9 files / 89 tests passed。范围含 Task IM/PA/原生、审批来源、群聊控制/个人权限边界；新增 UI 恢复来源和 @Agent stop 最后一轮重验另记。

- 最后增量复验：原生 Task + Global @Agent 命令 2 files / 51 tests passed，真实 native 首次责任输入携带一次 host human-task-control 恢复事实；审批来源测试已在 89 tests 批次中覆盖与普通系统/peer claims 的区分。


## 最终冻结树 `567785b58`

- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`：通过；node installer metadata 对应完整 `567785b58bef199399bc005082e383bde6e3b2ed`。
- 后端全量 `pnpm exec vitest run --maxWorkers=2`：119 files，559 passed / 1 failed；唯一失败是既有 Cron 测试 20 秒超时。同期 Web 全量与原生构建争用资源，原因尚不能仅凭时间认定。停止并发构建后原样单独运行 `packages/dsh-integration/tests/cron.test.ts`：2/2 passed，10.10 秒；未改超时或断言。之前冻结树 e1e187e 的全量 552/552 passed 仍作为基线证据，不冒充本树全量通过。
- Web 全量：103 files / 960 tests passed；生产构建通过；依赖审计 critical gate exit 0（既有 5 low / 2 moderate / 1 high，不在本单元改依赖）。
- Python：62 passed / 31 deselected；ruff check / format 通过。
- canonical 归并逐项核对：四份 delta 中 ADDED/MODIFIED 正文与目标完全相同，REMOVED 消失，未涉及 Requirement 保持原文；包索引数量同步。docs-check：259 maintained Markdown sources / 67 required routes 通过。
- iOS Debug simulator build 与 Release device archive 通过。最终原生测试与产品 R2 结论见交付记录；运行中不能用编译成功代替真实点击验收。

### 最新 main 集成后的最终本地验证（2026-10-22 15:34）

- 产品冻结版本：`30cd2e0a1272ec0a157337ebe644ad11e642809c`，包含 `origin/main=0904bc49c`；人工合并保留原生紧凑布局/状态定位和 `isHumanSource` 资格判断，Task 特有状态与授权边界继续有效。
- 全部后端：`pnpm exec vitest run --maxWorkers=2`，121 files / 575 tests pass，215.11秒。无超时阈值修改。
- Web：103 files / 963 tests pass，38.93秒；生产构建通过。
- iOS：44项XCTest + 22项Swift Testing = 66项通过；Release `ARCHIVE SUCCEEDED`，生成arm64 unsigned IPA。
- Runtime dependency contract：13项通过。完整TS build/typecheck与相关9 files / 86 tests在合并代码树提交前通过；产品源码与30cd一致，旧build日志stamp为当时HEAD `0e5405c79`，不冒称该日志版本号为30cd。提交后重建node installer，stamp为30cd。
- `pnpm check:ios-runtime`通过；docs-check通过258份受维护Markdown及67个入口。之前62项Python与ruff证据保持原范围，Python实现未改。
- 独立静态R3：findings=[]，verification 0C/0W/0S，corrected-delta aligned。产品R2旧环境证据与最终迁移复验由acceptance报告分别记录，不以单测替代。

### 配置修复时保留输入的唤醒（2026-10-22 15:21）

真实模型403失败时，分配通知已进入native next-turn；切回有效模型后，Task仍doing但未继续。原因是配置恢复清除了error，随后poke因队列非空让位，缺少唤醒。修复仅在无拒绝工具、未停止、有效Task配置的idle会话中，以task-change唤醒保留输入。真实native用例分别覆盖抛异常、错误finish与错误finish加待处理通知；第三种先复现未恢复，修复后3项通过，并验证通知只消费一次。其余6项Task native用例在同批运行通过。原生567版本最终43项测试通过，后续main整合涉及iOS时需重新验证受影响部分。

## 最终交付收口

- 最后同步确认 origin/main 仍为 `0904bc49c1e913f602ced4fad1689b1c8eab2ba1`，已包含在受审产品树 `30cd2e0a1272ec0a157337ebe644ad11e642809c`。后续仅报告、首文档状态及完整目录归档，不改变产品代码；静态 R3 和产品 R3 结果保留至交付 head。
- 四份 delta 的 16 项变更由独立 verifier 逐条核对，canonical 已归并且保留最新上游条目。产品 R3 全场景及 must-match 最终结果见 acceptance.md；此前轮次失败与证据边界保留。
- 专用隔离栈已通过 `e2e-down.sh --wt /tmp/nano-feat635-runtime` 停止；53674 无监听，IM/node/DSH 三个所属 PID 均退出。专用 430 模拟器已 shutdown/delete；本次两个有界测试浏览器已关闭。用户日常浏览器、主仓 dirty 内容与生产服务未作清理。旧本地原型的应用内 file URL 标签受浏览器策略限制，不能自动关闭，已告知用户手动关闭。

## PR CI 首轮失败与有界修复

PR #385 首轮 head `42aa1f9af`，run `39743385436`：Web 与 iOS tests/Release archive 通过；后端 573/575 通过，以下两项失败。未重试掩盖问题，也未放宽超时。

- Goal fixture 用旧 `nano-human` 过滤已迁为 `user` 的真人输入，未实际进入挂起等待，导致“忙时尚未撤掉 Goal”断言有时提前看到已应用配置。fixture 改为识别最后用户消息的明确 `hold` ID；产品权限逻辑没有改变。
- 冷会话恢复时，原生 Schedule 的 `resolveAgent` 与产品 `session.ensure → create` 分别持有恢复/创建 Promise，竞争同一个 session 写句柄。原测试偶发失败；将真实公开 `session.observe` 与 `session.ensure` 并发，原实现稳定复现 `session "s" is already owned by an active write handle`（`/tmp/feat635-cold-race-red.log`）。已绑定会话先经 `resolveAgent` 加入同一原生恢复，再由 `create` 校验 cwd/preset；仅 `session/not-found` 继续既有创建路径，不吞其他错误。无 DSH patch/private import。
- 修复后原生 Task+Goal 2 files / 10 tests 全通过（`/tmp/feat635-ci-race-green.log`），含真实进程重启、旧 Schedule、未确认 stop 屏障、保留真人输入和确认后交付。冷绑定/来源回归、静态增量复审与后续 CI 结果继续记录；旧 R3 产品视觉与其他旅程不按提交号机械重跑。

- 修复冻结树 `1bd82f9ebbec17b85868640eb1c5e78733c0c709`：`pnpm test` 全量 121 files / 575 tests PASS，93.05 秒；额外 5 files / 15 tests 冷绑定、Cron、supervisor、model policy、native human 回归 PASS；typecheck、runtime contract 13 项、docs-check PASS。独立 R4 code review findings=[]，verifier 0 CRITICAL / 0 WARNING，aligned / no new spec delta。原 R3 真实产品证据按未变范围保留，新冷恢复并发保证由实际原生进程测试补证。最后 origin/main 仍为 `0904bc49c`。后续报告提交不改变产品源码。

## 交付时主干文档同步

在 head `6fc583424` 的远端 CI 全绿后，main 合入 #386 至 `866877a83dc50da34b84386ed7207e45473da05b`，仅修复 active feat-635 design 的 bugfix-633 相对链接。本分支已经整体归档，保留 archive 内同级 unit 的正确相对链接，解决同一行的移动/编辑冲突。与此前受审 head 比较，产品代码、测试、delta 与 canonical 均无变化；R4 静态、R3 产品及全部运行验证 retained，仅重跑文档与归档检查。effective_base 更新为 866877a83，effective_through 见 PR 最终 head。

## 用户反馈修订：Goal 工具逐项选择

- 用户明确要求不增加 DSH Goal Feature，仅默认关闭三个工具并允许逐项开启；Gate 2 Round 4 通过该修订，历史 Feature 验收不再作为当前配置结论。
- 冻结实现 `30a53c204`。先将目录和原生选择测试改为最新要求，旧实现真实失败：目录仍含 Feature，单选 get_goal 被总开关拦截。删除 Feature、三工具联动和额外 Goal disarm/filter 插件；未配置名单排除三工具，显式名单逐项有效。
- 原生回归覆盖缺省/空/各单项/全部/Global 默认、子执行默认、实际 get_goal dispatch、prompt 及运行中立即撤销/idle 新增；从未配置名单增加 Goal 不提前生效。4 文件 12 测试通过；Web 配置相关 2 文件 28 测试通过；全仓 typecheck、runtime dependency contract 13 项及 docs-check 通过。独立静态 R5 findings=[]、verifier 0C/0W，18 项 delta/canonical 一致。
- 首次本地全量与 Xcode 冷构建同时执行：后端 573/575，两项 personal-security/workspace-tools 分别超时 30/90 秒；Web 962/963，chat-workspace 等待 Reply draft 超时。未改代码或延长超时，降低并发单独复验：后端 2 文件 7 测试通过（43.04 秒），Web chat-workspace 59 测试通过（11.95 秒）。此为失败项复验通过，不将首轮全量写成全绿，也不外推资源争用已被证明为根因。
- iOS 编译与原生回归 TEST SUCCEEDED。随后用户明确要求提高效率、优先 Web；本轮不再做原生界面实测，已关闭并删除独占测试模拟器。原生逐项选择的界面不冒充独立实测通过；源码与编译回归保留。
- root 在真实隔离 Web `e2e` 配置确认无 Goal Feature，三工具默认未选；仅点击 get_goal、保存、重开后仅 get_goal 为 pressed，另两项仍未选，页面显示 No changes。浏览器会话已立即关闭，后续独立产品复验单独记录。
- 本 unit 53 张图片完整保存仓外并从当前树移除，报告只保留本地证据文件标识；后续整理本 PR 提交历史，不改 main 既有历史。
- 产品 R4 在同一 `30a53c204` 上完成有界 Web 验收并 pass：新建默认、create/update/get 分别选择与取消、1280/390 保存重开；真实 get_goal 返回 null，provider 工具集合仅包含 get_goal，取消后为空。未变 Task 的 28 项 Scenario 保留 R3；原生 UI 按用户范围不重复。详情见 acceptance.md 和 acceptance-r4/journeys.md。
- 交付采用同一最终树基于 main `866877a83` 整理为新提交，避免本 PR 中间提交携带图片；源码与实际受审 `30a53c204` 相同。最终 head、无新增图片对象核对及 CI 以 PR 记录为准，历史验收 hash 仍表示实际执行的版本。
