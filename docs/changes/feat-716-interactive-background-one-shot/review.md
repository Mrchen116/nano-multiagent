# feat-716: Review

## 范围与版本

- 当前有效需求：`spec.md` 的多卡一次性规则；用户确认 A+B 一起携带并消费、下一条无新背景、仅重改 A 后只携带 A。旧单卡独占证据不代表本增量已验收。
- Gate 2：`design-review.md` R5，独立 Approved / 0 CRITICAL / 0 WARNING；设计审查不替代实施验收。
- 独立实现审查者：`67dd0842-5c6b-4237-8135-daee86b28cf3`，未参与受审实现或 R5 设计审查，加载 `change-code-review` 和 `agent-context-review`。
- 本轮受审范围：完整 `eeaea47921806936da20e78c9ed96167716f5037..5adda98f5527c951ffb8df9ba28c68b76ca998fc`，68 文件，包含旧单卡实施及多卡增量；非仅最后一个提交。`executed_base` / `validated_at` 分别为上述两值。
- 配置差异：当前派工工具未提供固定模型/effort参数或实际值。依据用户仅限本轮 #473、714、716、720 的例外，使用当前可用配置做独立审查；不冒称指定配置，也不豁免作者与审查者分离。
- `effective_base` / `effective_through`：尚未完成最终 sync 与实施验收，不给出最终有效性结论。

## 首轮审查结果（5adda98f5）

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 全部实现正确性、需求/设计覆盖、最终 delta | change-code-review；上述独立 reviewer；full | **REQUEST CHANGES** | 三项 P2 / CONFIRMED，见下；四份 delta 与实现对照，结论为 implementation-mismatch，不建议缩改契约迁就遗漏 |
| 多卡选择、逐卡有效性、64 KiB 总预算、无副作用失败、同键冻结、显式提交独立、来源与逐 Agent 过滤 | 同一独立 full code review | 静态检查未发现其他阻塞缺陷 | `pending()`、消息事务、attempt、relay 与客户端实际代码；复用 server 5 files / 75 tests、Web 3 files / 36 tests 的可信窄测试与类型检查；本轮未重复全量 |
| 模型可见信息的来源、选择、装配、失效与非授权边界 | agent-context-review；同一独立 reviewer；实施静态链核对 | **pending / inconclusive**（动态目标） | 静态链已核：中心派生→卡作者 relay→`withInteractionContext`→single-thread 或 Global Inbox 工具结果；数据非指令/非提交/非授权说明保留。尚未观察当前多卡真实双端、实际 `inbox(action=read)` 与后续模型步，不能整体 pass |

审查者仅进行只读代码/文档检查、`git diff --check`（0），以及一项实际模块 + fake IndexedDB 的纯内存复现；未改文件、启动服务/GUI/LLM，未读取旧 62814 来冒充本增量结果。

## Findings 与关闭

### F716-CR1 — 移动 Web 返回列表漏掉离开清除

- **P2 / CONFIRMED**；受审 `chat-workspace-page.tsx:387-388`，实际返回入口 `:1269`。
- 本端已保存 A 卡改动→手机返回 `/chat`→新 `conversationId` 为空，原判断跳过 discard 且 previous 被写空→再入聊天时保留了应清除的背景。超限提示建议的“离开此聊天”也无法由该入口完成。
- Reviewer 依据实际路由及生命周期调用链确认，未冒称 GUI 运行复现。
- Author resolution：移除“新 cid 必须非空”的条件，增加实际 mobile Back 集成测试。过载下首次红测在读取历史前置即失败，**不作为 CR1 的有效红证据**；资源释放后该返回按钮路径的窄集成测试通过，见 `/tmp/feat716-lifecycle-green.log`（29 项协调器 + 3 项 workspace 场景与 tsc-b exit 0）。尚未独立关闭。

### F716-CR2 — 启动恢复未完成时丢失离开意图

- **P2 / CONFIRMED**；受审 `interaction-background.ts:193-196,227-231,278-291`，调用 `chat-workspace-page.tsx:375-388`。
- 刷新前本端保存 T1→刷新后 hydration 未完成即离开→空 watermark 导致 `enqueueDiscard(undefined)` 返回且未记录 intent→恢复后只有水位，无待重试离开→返回发送仍携带。
- Reviewer 用实际 TS 模块 + fake-indexeddb 纯内存复现：`restoredWatermark=T1`、`discardRequests=0`。
- Author resolution：新增 4 项启动恢复专属测试，修复前 3 项有效失败（`/tmp/feat716-hydration-leave-red.log`）。初次修复通过这 4 项但使既有迟到 save 串行顺序用例失败（`/tmp/feat716-hydration-leave-green.log` 实为 25/26，不能记为全绿）；已调整为只有本地 through 尚空时关联启动快照，并保留账号/撤权 fence、回访后新编辑与发送屏障。调整后 22 项既有协调器、5 项 hydration（含撤权后不能重用启动快照）及 2 项恢复测试全部通过，见 `/tmp/feat716-lifecycle-green.log`；尚未独立关闭。

### F716-CR3 — 离线恢复没有自动重试草稿

- **P2 / CONFIRMED**；受审 `chat-workspace-page.tsx:375-379`、`interaction-background.ts:145-157`、`interactive-card.tsx:115-125` 及 `transientOffline` 文案。
- 草稿 PUT 离线失败后 Send 禁用；网络恢复、用户不再编辑且不手点 Retry 时无恢复调用，不能兑现文案与 delta 的“自动放行”。仅有 discard 的 foreground 重试并不足够。
- Author resolution：新增当前会话 transient-only、有界一次、同时 online/foreground 合并的恢复入口；不自动重试 conflict，不循环。新增 workspace 两个事件场景的修复前有效红测均为 flush 0（`/tmp/feat716-workspace-leave-recovery-red.log`）；增加协调器范围/并发合并测试。2 项协调器范围/并发测试及 2 项实际 workspace 事件入口场景均通过，见 `/tmp/feat716-lifecycle-green.log`；尚未独立关闭。

## 首轮后的待办（历史；当前状态见第二轮）

- 三项 findings 的作者修复已通过上述最窄绿色验证，待冻结后交原独立审查者补验；尚未宣布关闭。
- 当前可信窄证据：`/tmp/feat716-multi-regressions.log` server 75/75；`/tmp/feat716-web-multi-regressions.log` Web 36/36；server full tsc noEmit、frontend tsc-b、interactive assets check exit 0。这些均适用于 `5adda98f5`，不自动覆盖后续修复。
- iOS 新增 422 保留正文/附件和新键重试单测尚未编译运行；原生多卡三消息 case 已准备但尚未运行。当前资源已沿原通道接续，作者仅串行运行单组低并发窄验证，不叠加构建/GUI；原生验证尚待本次后续单组执行。
- 多卡实际模型输入：须证明首条 A+B、次条无新块、仅重改 A 后只 A；历史块保留，不将历史当作新注入。Global Inbox 每部分 6000 字符、每次最多 4 fragments，有 `partial` / `next_cursor`；不得宣称 64 KiB 一次读取保证完整。当前未取得该增量的动态观察。
- Web/iOS 超限窄屏可读性与恢复、原生 transient 保存失败恢复仍未观察。新增原生预算恢复 case 的 edit 被权限工具拒绝，未写入、未执行、未换路径重试；父级要求先修正测试对象与自有隔离实例的可靠绑定，再据具体对象处理权限，不把环境变量 + loopback 等同合成数据证明。
- 旧 62814 单卡预览保持不动；旧单卡 native/模型证据仅可按未变机制 retained，不用于当前多卡验收。
- 首轮最终 delta 校对为 implementation-mismatch；当时未归并 canonical、未归档、未创建 PR，不能宣布交付。

## 第二轮独立补验（fc5e19066，当前结论）

同一独立审查者沿原线程执行 closure + patch / corrected-delta：实际核对 `5adda98f5..fc5e19066046920f8a6bfa3245bd63a9f718d8ed` 的全部 8 文件及相关调用方，保留前次完整审查；`executed_base` 仍为 `eeaea47921806936da20e78c9ed96167716f5037`，本轮 `validated_at` 为 `fc5e19066046920f8a6bfa3245bd63a9f718d8ed`。模型/effort 仍未提供，沿本轮例外如实记录。未修改文件、报告或提交，未起服务/GUI/LLM，未接触其他 checkout 或旧预览。

| 问题 / 要求 | 能力与模式 | 独立判断 | 决定性证据 / 限制 |
|---|---|---|---|
| F716-CR1 | code review closure | **closed** | `chat-workspace-page.tsx:391-398` 包含 previous→undefined 的显式 leave；mobile Back 实际按钮集成验证清除 c1；可信 3 项 workspace 窄绿 |
| F716-CR2 | code review closure + Context 生命周期 | **closed** | `interaction-background.ts:207-217,234-243,303-319,367-374` 启动快照带 session、send 屏障、回访后 T2 不被清、hydrate 中/后撤权；5 项新回归及 22 项既有协调器全绿 |
| F716-CR3（Web） | code review closure | **closed** | online / visible foreground 当前 cid 恢复；transient-only 一次 pass，promise 合并并发，不重试 conflict，不循环；2 项恢复与 2 项事件入口场景绿 |
| 3 项修复与 test-only 新影响 | code review patch | **Approved，存活 findings=[]** | 全部 8 文件与调用链静态核对；复用 29+3 窄绿及 tsc-b，保留 React act 警告，不重复全量 |
| 四份最终 delta | corrected-delta | **aligned**（实现/契约静态层） | 既有 implementation-mismatch 已由实现补齐，不缩改契约迁就遗漏；未变服务端预算/attempt/source/per-Agent 结论及可信 75+36 窄测试保留 |
| 实际多卡消费与模型输入 | agent-context-review 实施动态目标 | **pending / inconclusive** | 真实双端、relay 三消息 A+B/空/A、实际 `inbox(action=read)` 与下一模型步等尚未取得本增量观察；代码 Approved 不等于整体门禁通过 |

### iOS 自动恢复 lead 的核对

作者仅看 coordinator 的 grep 曾提出 iOS 是否同因缺少自动重试；独立核对为 **refuted，不列 finding**。`ChatStore.run:113-114` 每次正常 sync / stream 重连前，对当前会话 transient 调用 `flushDrafts`；`ConversationView:131-135` 每次 active 同样有 bounded 恢复，`NanoIMApp:181-183` 确实按 scenePhase 启停 run。`InteractiveRuntime.flush:276-277` 对 conflict 直接返回，不自动合并/丢弃；成功路径清 failure 并通知 composer。混合 conflict 时优先呈现冲突，会话依法仍被显式冲突阻塞；现无证据足以另认定契约失败。

### 原生编译证据与安全边界

审查者另实际读取 `/tmp/feat716-native-multi-build.log`：IM server build 与 `NanoIMJourney build-for-testing`、jobs 2、`NANO_IM_BUILD_REVISION=fc5e19066046` 成功（exit 0），新多卡 case / fixture guard **已编译，未运行**。Swift 5 StrictConcurrency 对 XCTest setup / teardown 的 MainActor 调用仍有未来 Swift 6 错误警告；不宣称 warning-free，不把未来语言模式警告当作当前构建失败。

后续同一独立审查者只读核对 `/tmp/feat716-native-multi-recovery.log:277-313` 及对应源码：同一冻结产品版本的 `NanoIMTests/SendRecoveryTests` **10/10 通过、0 failures、exit 0**，其中 422 用例 `testOversizedBackgroundKeepsDraftAndAttachmentsWithoutRetryingTheRejectedAttempt` 在 288–289 行通过。断言覆盖正文与附件保留、pending/磁盘 attempt 清理、不做 lookup，以及再次发送采用新幂等键并成功。xcresult：`/tmp/nano-ios-feat716/Logs/Test/Test-NanoIM-2026.11.09_01-09-54-+0800.xcresult`。因此关闭“原生 422 单测未执行”缺口；这是受控 transport 单测，不代替实际服务预算恢复、窄屏体验、多卡或模型 Context 观察。

Manifest guard 不代表实际服务/数据库绑定，更不代表人类授权；执行前仍须 host 核对自有 PID/出生时间/cwd/端口、合成 owner 与新卡片来源、唯一聊天标题。被拒预算恢复 case 未写、未执行、不因本轮 Approved 获得新权限。

## 第二轮之后的执行事实（owner 记录；下节限定独立预复核）

完整 locator 与证据边界见 [多卡真实旅程与 Context 观察](evidence/multi-card-validation.md)。以下只更新第二轮之后发生的事实，不追改独立 reviewer 当时的判断。

- 新 UUID daily `59469` 已通过自有进程/新合成 owner/direct 会话/A、B 实际 PA 卡来源/唯一标题/Sol 工作与审批配置绑定；旧 `62814` 不动。绑定是对象证明，不是权限。
- **Web 作者真实执行成功**：A4+B5 → 第一条 relay 两项；未编辑第二条无新背景；只将 A 改6 → 第三条仅 A。精确消息 `d5d36e7b…` / `18c3de44…` / `991e05d4…`，真实 UI 输入与 Send、relay 完成、既有 native `inbox(action=read)` raw/projected 结果及下一模型 `send_message` 一致。没有 HTTP/provider wire capture；其限定充分性已由下节独立只读预复核核对。
- **原生未通过**：首次同路径在 B 编辑前失败，0 native-multi Send；AX 树与截图证明旧 helper 把 App 高874之外 y1161–1207 的 WK 字段误当可见，A 仍占键盘焦点。只修 UI 测试可见性/正常 Done/可见区内有界滚动，编译 exit0；未改产品，未增加等待/超时。
- 修正后针对既有 simulator 的整条命令曾被拒，彼时未执行其前置复核或原生测试、未重试；设备未证独占的风险保留。其后负责人明确纠正真实隔离测试不需再逐项请示、本轮只需模拟器，遂用已安装 runtime 实际新建空设备 D65（不 clone），对象绑定与受保护运行配置检查均通过后执行一次窄 multi 测试。
- 新空设备运行 **exit65**：启动/测试阶段132.412s，case26.804s；正常登录后被迟到的系统“保存密码？”弹层覆盖聊天列表，入口 not hittable，未进卡片、未 Send。截图与 AX 树已核；仅将相同弹层处理移到列表 ready 后并断言可点，未改多卡断言或 timeout，此修正尚未编译/运行。
- 当前批已按 UDID 删除自建 D65、核实 Xcode/runner/App 退出；保留348KiB必要失败证据，删除本次完整 xcresult/附件与302MiB独占 derivedData及凭据 xctestrun。曾一次工具存储 ENOSPC，后续读取/导出/清理成功且 Data卷有17Gi可用，不据此归因 UI 失败。后续复验等串行资源窗口，不是人类权限等待；详见新 evidence。

## 限定独立只读预复核（未冻结版本，不是最终 unit gate）

原 reviewer `67dd0842-5c6b-4237-8135-daee86b28cf3` 沿既有线程完成轻量预复核，返回本范围 **clean / 新存活 findings=[]**，明确不给整体交付 Approved。受审为 `HEAD=29f402e29616e090aaa2eda2c682d25c0b12a6a0` 加上述 7 项未提交报告/helper 更新；产品仍 `fc5e19066046920f8a6bfa3245bd63a9f718d8ed`。实际核对 evidence SHA256 `7105c68d64b6393ec126651e9310c899361d8440b17ded13b1e6c36a60e0d35b`、UITest SHA256 `665c785b03d79a272737a91879a12a23549edbad49db0a1a4cd2641360303f50` 与 `git diff --check`。审查模型/effort 未暴露，沿本轮配置例外，不冒称 Sol/high。本节由 owner 串行归集返回结果，后续报告编辑不自动属于该已审哈希版本。

| 目标 | 独立结论 | 直接证据与边界 |
|---|---|---|
| Web→中心→Global 实际两卡消费 | **有直接证据支持** | reviewer 实际只读新 `59469` 的精确 session，核对 `inbox(action=read)` seq96/97/100/104、128/129/132/136、160/161/164/168：raw/projected 分别 A4+B5、无新块、仅 A6；各 projected 首段与 raw 逐字一致，解出的 contexts 与对应 completed relay 逐项一致；自然正文未给人数答案，下一模型真实 `send_message` 与已存回复一致。结合作者真实 DOM 输入/Send 记录支持本次 AB→none→A-only，不是仅数卡片数量。 |
| 两次原生失败归因 | **与直接证据一致，均未验证多卡派生** | reviewer 实际 `read_image` 核对首 run 的 A 键盘/B 屏外、新 empty 的系统保存密码遮罩，并核对日志/AX；合成会话 native-multi sends=0。未将工具 ENOSPC 或后置 diagnostics 当 UI 失败根因，既不判产品红也不判通过。 |
| test-only helper delta | **静态 clean；运行修复未证实** | 正常 Done、完整 viewport 可见性和最多8次区内手势；原 chat20s、弹层3s、field10s、send20s、allowance120s不变。viewport 补丁只有 build green；新 empty 未走到该 helper。最后弹层顺序修正尚未编译/运行，晚弹层/动画的恢复前置仍需实际结果，不凭推测立 finding。 |

证据限制：这不是 provider wire，也不证明转换后 HTTP payload 序列化保真；小结果文本为955/41/649字符，未触及6000字符 parts / 4 fragments 的分页，不能泛化为近64KiB组一次 read 完整。同作者良性 fixture 不新增证明跨 Agent 负向隔离、恶意注入或业务授权；历史块仍在并非新注入。第二条“收到”不单独证明无新块，缺块结论来自 raw/projected 与 relay。该 reviewer 未修改受审文件、启动服务/browser/Xcode/sim/LLM/worker，未碰旧 `1CE` 或 `62814`。

## 原生首条实发与限定独立补验（不是最终 unit gate）

原 native/heavy 窗口重新分配后，用实际新建空设备 CEF24（不 clone）重新验证同一三消息 case。最新两项 helper 已 build-for-testing exit0；运行 **exit65 / case97.391s / 测试阶段365.560s**。这次正常关掉密码Sheet、A7→8、Done、真实滚动B、B5→8并完成**第一条 Send**；两个旧前置缺口在本次已走过。唯一新失败是回执断言用超过128字符正文作 XCTest identifier 查询，触发框架 `NSInternalInconsistencyException`，不是 Send/产品失败；第二/第三条尚未执行。仅将共享 send helper 改为精确 `label == %@` 谓词匹配，未延长 timeout、未降低断言，此新修正尚未编译/运行。

首消息 `90b8a94e…` 唯一 completed relay 精确 A8+B8；真实 `inbox(action=read)` seq192→raw193/projected196（contextItem47）确有独立两来源，下一真实模型 seq200 确认A8/B8，已存回复 `f5dd9591…` 一致、seq209 turn/end；正文未给人数答案，仍不是provider wire。只支持原生首条多卡实发/消费，不足以关闭完整三消息目标。自建CEF24已精确删除，Xcode/runner/App均已退出；必要小证据与回收边界见 [本批 evidence](evidence/multi-card-validation.md#再次空设备复验实际完成第一条多卡-send后置测试查询失败)。未发生新工具拒绝，未碰旧1CE/62814。

原 reviewer 随后完成限定只读 patch/evidence 补验，**clean / 新存活 findings=[]**，不给整体 Approved。核对同一 HEAD/7项dirty、UITest SHA256 `3fb8d168ba8cb391522cf26730d16efd20d555acdd8fc5e78a770223cd84c2ea` / evidence SHA256 `7fdfb3dd13bb5651bfb1a9ed0699f0792e3dd0e9f41160485e47c41c03e9732f` 及 diff-check exit0；实际 model/effort 未暴露的本轮例外不变。其实际只读原DB核对上述精确 journal、唯一 relay `73f4776f8c3e4e54a3ebf04c23482629` 的 status/receipt completed、投递对象与数组逐项一致、消息及已存回复，确认**原生首条真实编辑→A8/B8派生→Global消费/回复有直接证据支持**。输入结果的通用 `channel=web` 不能改称native；原生来源依据本次XCTest真实输入/Send、唯一marker和消息时间的关联。

审查者实际看三张新图/日志/异常原文，确认两个旧前置本次已走到首Send、不重复套用旧失败原因；新精确 label 谓词保留完整正文、参数化精确相等和所有等待/断言，**静态无明显新增阻塞风险，未编译运行**。首Send之后才触发框架查询异常；既不记产品发送失败，也不记整case绿。后两条、预算恢复与native transient仍未验证；未读取已删产物、未改文件或起服务/GUI/模型。此结论只覆盖给定哈希和证据，后续文档更新不倒算已审。

## 原生完整多卡与 transient 的限定独立关闭

原reviewer沿原线程继续只读复核，原生多卡结论 **SUPPORTED / findings=[]**。实际三消息case PASS82.282s、总108.986s；执行helper `9ac8d5fb…`，HEAD29f/产品fc5不变。独立读完整日志、3个completed relay、实际Inbox raw/projected/下一模型步与最终画面，严格支持`[A7,B9]→[]→[A9]`真实编辑/Send及模型消费。前两条被同一read批取，同turn9内311拟发送received被312/316 **held_for_revalidation，未送达**；第三条后329read、337send A9，338/341 sent及已存128e回复一致。不是三个独立模型turn/三个回复。最终图显示本次三条完整正文及空composer，不含后续A9回复；第二receipt图仍旧位置，不称每次回执完整visible。后续flag-before-tap与transient绑定测试小修不倒算旧9ac8执行哈希。

同一reviewer随后实际读当前helper `6df15658b61ed2b23cedb24e0012f80b175e8e5b16087707c8e03d1e21e1b039`（与实际ownership执行hash相等）、新runner/build/日志/ownership/DB proof与两图，限定 **native transient SUPPORTED / findings=[]；必要失败/手动恢复画面局部体验 PASS**。自有63068合成SQLite副本、完整source provenance、仅持有Popen停启68559→70326、同DB恢复均有直接支持；原59469/62814未停。真实A9→5在服务down时保存失败，整会话Send禁用与完整正文保留；同副本恢复后手动Retry、正式GET同字段=5、Send解阻/正文不变，case50.815s/总76.721s/exit0。保留proof源/副本message21/attempt21/relay12及空discard相同，副本5rev9而源9rev8未改。copy与全量产物已按owner最小保留规则删除，reviewer不冒称对已删DB重做SQL。

边界：transient未实际按恢复后的Send，不证明该正文投递/消费/下一模型步；明确手动Retry，不证明自动online/foreground触发。两图顶部仍为Disconnected.Reconnecting，不把保存成功解阻写成WS重连成功。当前仅在原窗口继续预算旅程，不自动关闭预算/整个unit。详情与必要本地产物/资源归属见[多卡证据](evidence/multi-card-validation.md)。

## Web预算拒绝分支的限定独立复核

原reviewer沿同线程实际只读原截图 `page-2026-11-09T06-01-19-952Z.png`（SHA256 `4e50784df391a4dd3c71f6eb47a3bf792910e8b7515c8f127d76bb4d21275e11`）、原DOM/console、binding/fixture脚本/expanded/rejected记录与新59469 SQLite，返回 **SUPPORTED / findings=[]；390×844拒绝/保留状态局部体验PASS**。不是预算全流程或最终unit Gate。产品fc5/HEAD29f/helper6df未改，未起API/browser/Xcode/sim/服务/模型或新worker、未改文件。

- 实际图中错误说明完整可读：消息未发送、缩减重试/已编辑设备离开清除、正文/编辑保留；完整预算正文、`716-budget-5601.txt`及移除入口同时可见，Send可重试。丙卡显示short，不冒称12000字符由UI键入；大草稿由正常CAS准备且只读DB独立证实。
- 独立按三卡Input/TextArea source、state、executor、短摘要和updated_at毫秒重建投影：state丙/甲/乙12032/12030/12028bytes、context24343/24339/24335bytes，73017+括号2+逗号2=**73021bytes**；与生产完整JSON预算一致。本fixture无choice-options、摘要短/BMP，故readDraft withOptions及Python/JS摘要差异在此无影响；不推广任意Unicode/其他投影或65536精确边界。
- console实际messages POST 422、真实UI专属背景过大文案与chat-api.ts映射/生产pending一致；不是把准备脚本或两个记录冒称Send响应。没有原始HTTP response body/wire，不称捕获完整HTTP JSON。
- 独立SQL仍message25、caller-key attempt25、relay13，精确生产localHumanAt排除delegation后仍05:55:25.012Z，空discard；无预算正文message或relay，三卡rev2/updated_at及submission null不变。结合生产pending位于insert/saveAttempt/enqueue之前，支持本次无部分创建/水位推进、草稿保留；不把此前附件上传也说成零写入。
- shrink+同composer恢复Send被工具拒绝，未执行/未证明；nextnone未验证，原生预算未写/未执行。本批sim/DD清场也被拒，不能记回收完成。原拒绝调用/原文、实际Shutdown但目录仍在与DD仍在、无batch App/Xcode进程、恢复点见 [工具拒绝记录](evidence/budget-tool-refusals.md)。父级持有实际阻塞，不另行绕过或调查其根因。

## 更新策略后Web预算连续恢复的限定独立复核

用户后到实际答复“工具审核策略已经更新了，应该不会被拒绝了”后，父级沿原事项接续。正常检查下新连续Web恢复已实际执行，没有新拒绝；旧两条被拒调用仍保留为未执行历史，不能倒填旧清场成功。

原reviewer沿原线程实际读新失败图09-24-18-185Z/DOM、原59469 SQLite、before/rejected/reduced/relay proof、原node.sqlite3精确raw/projected与模型结果，以及最终图09-31-32-794Z，结论 **SUPPORTED / findings=[]；该连续恢复局部体验PASS**。只读、未运行API/GUI/服务/模型/新worker，未改文件。HEAD29f/产品fc5保留；owner后来新增Photos picker probe使helper变2fe14e73…，此Web结论不覆盖新probe、不迁移旧native执行哈希。

- 新browser context实际composer空，不称旧44byte附件跨关闭保留。作者在此新context重建相同完整正文及新52byte自制附件，再触发73021-byte 422；从该次失败开始连续保持正文/附件，正常CAS缩短→真实同composer Send→next。作者连续操作记录补足“中间未清/未重填”，前后图/DB不单独证明无中间动作。
- 拒绝前后25messages/25caller-key attempts/13relays、floor、空discard、draft revisions/times均相同；缩短后三卡rev3、完整1195bytes。[丙f3ad…,甲63de…,乙dc9c…]完整出现在recovery e83e… @09:25:18.734/relay9f1… completed，next1aa… @09:27:04.130/relayf55… completed无新contexts。当前29/29/15与新增2human+2agent/2relay相符。
- 独立核同52byte image44c4…/storage4864…/sha2566c074992…，唯一持久行与message/caller_payload/relay/Inbox attachment URL/type/name精确相等；支持同已保留upload身份被携带，不由此声称全部upload HTTP从未重试、附件正文已被模型读取。
- 409read→410/413 item102，raw/projected首text字节相同且1195byte组逐项等relay；同read两fragment分别正文+完整背景、附件，无nextcursor。416/417实际模型send三卡2→418/421 sent b01…，DB09:25:33.494 completed；441read→442/445 item110无新块→448/449 send received→450/453 sent f892…，DB09:27:16.830 completed、458turn/end，无held。不称provider wire；人数与初始2相同，不能仅据回复断言数值只可能来自新背景。
- 最终390×844图（SHA8ecc26e1…）完整同时呈现正文+已发同附件、三卡回复、next正文/received、空composer。上方XXXX仅旧大备注渲染，未声称外设备CAS后UI已刷新short；旧阅读位置空composer图不当成功消息画面。browser本批已close、未新建native资源。

## 当前流程收口

- 冻结产品独立代码补验仍为 **Approved / 存活 findings=[]**，静态 corrected-delta **aligned**；后续限定只读预复核本范围 clean，不代替最终冻结后的 unit gate。
- 422原生单测已由可信执行与独立只读核对关闭；Web两卡/实际Global消费、原生完整多卡/实际消费、原生transient手动保存恢复与Web预算完整失败/恢复/nextnone均获上述限定独立支持。原生预算后到真实绿色（host c5de4112…，1 test / 0 failures / 57.915s / exit0）、完整同正文图片恢复及nextnone/relay/实际Inbox已由owner补入[多卡验证](evidence/multi-card-validation.md#原生预算连续恢复后到的真实绿色执行)，**待原reviewer冻结补验**，不把作者证据冒充独立关闭；整体尚未完成最终集成验收。
- 旧单卡证据仅可就未变机制 retained，62814 保持不动；新多卡证据仅按其实际覆盖范围使用。
- 尚未最终 sync、canonical 归并、归档、PR / CI；不宣布交付。
