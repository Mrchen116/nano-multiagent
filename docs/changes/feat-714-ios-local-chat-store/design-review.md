# feat-714 设计审查

## Round 1

- reviewer: 独立 `change-design-reviewer`（未参与 feat-714 设计与实施；本仓 / 本机）
- review_target: `docs/changes/feat-714-ios-local-chat-store/`（design.md、specs/im/ios-client.md delta、M1/M2 骨架），首文档 `spec.md`（origin/main `005a36057`）
- reviewed_head: `unit/feat-714` @ `fe2c8fa60`，工作树 clean
- review_mode: full
- mode_reason: 首轮，无历史 Round，需覆盖现状断言、设计决定、用户约束、delta-spec 与 milestone 全部面
- started_at: 2026-11-05T15:42:00+08:00
- completed_at: 2026-11-05T15:53:00+08:00
- duration: ≈11 min

### Verdict

**Issues Found（Changes requested）— 2 CRITICAL / 7 WARNING**，另 6 条 Recommendations。

Gate 2 未通过。两个 CRITICAL 都在"未确认发送记录迁移一条不丢"（spec.md:126-138）这条唯一带数据风险的需求上：一条会让迁移在真实升级路径上整体失效，一条让设计的兜底回退路径不成立。

### Coverage 与证据

| 面 | 覆盖 | 结论 |
|---|---|---|
| 首文档对齐 | spec.md 的场景/范围/非目标 ↔ design 的 D6/D7/D8/D10/D12/D13 | 一致；U1 只承担症状 1，U2/U3/U4/U5/U6/U9 明确出界，未发现设计把非目标偷做进来 |
| 现状断言 | GRDB 版本/pin/平台/语言模式；GRDB 默认值（WAL、busyMode、外键、eraseOnSchemaChange、迁移台账）；pbxproj 4 处增量的现有锚点；ChatStore/Session/SendAttemptStore/ChatListView/ConversationView 的行号引用 | 全部 CONFIRMED（逐条见下），无反向证据；个别行号 ±1–2 行偏移（`ChatModels.swift:157` 实际 159、`Session.swift:11` 实际 12），不影响判断，不计 finding |
| 设计决定 | D1–D14 的决定、拒绝备选、演化口、降级路径 | D1/D3/D4/D5/D13 收口；D2 结论可用但理由三不成立（R1-R1）；D6 属可接受取舍（见 (b)）；D7/D8 有未闭合边（R1-W4）；D10/D11 有未定义窗口（R1-W1/W2）；D12 有两处 CRITICAL |
| 用户约束 | "一步到位/目标态"（spec.md:17-19）、issue #468 已定前提（GRDB、iOS 26、不存媒体字节、`/sync` 保持全量、不做第二次迁移） | 设计未违反任何一条；`read_state` 的"只写不读"是履行"不做第二次迁移"的合理代价 |
| delta-spec | canonical target `docs/specs/im/ios-client.md` 存在；MODIFIED 保留原有两个 Scenario：「恢复与切换」逐字未改，「断线及前后台切换」在原句基础上扩写并追加 AND，没有断言被删或放宽；conversations-messages "no spec delta" 与"不改 `/sync`、`/read`、未读计算"一致 | 锚定正确、无删除；但有两处可判定性问题（R1-W1、R1-W7）与一处措辞歧义（R1-R5） |
| milestone | M1/M2 骨架 `.gitkeep` 符合 `docs/changes/README.md:71-75`；两片串行无并行组；退出标准含 `[reviewer]`/`[worker]` 双轨 | 骨架合规；轨道可操作性有缺口（R1-W3） |
| 一次性部署 | design.md:394-396 判定"无" | 成立：无服务端数据/配置/部署迁移，旧 JSON 迁移发生在设备端，不需要 `deployment-prompt.md` |
| Agent Context | 按 `agent-context-review` Mode A 核对来源/选择阶段 | 主体结论（不组装 Prompt、不定义工具、不读写 Memory/History）成立；D14 漏了一条 `interaction_contexts` 链路（R1-W6） |

**现状断言核对证据（本机实测，非推断）**

- GRDB：本地 probe checkout `/private/tmp/grdb-probe/.build/checkouts/GRDB.swift` HEAD = `92a554cd0`（与 design.md:87 的 pin 一致），tag `v7.12.0` 提交日期 2026-11-01；`Package.swift:1` `swift-tools-version:6.1`、`:50-55` `platforms: [.iOS(.v13), …]`、`:119` `swiftLanguageModes: [.v6]`。
- GRDB 默认值：`Configuration.swift:28` `foreignKeysEnabled = true`；`:284-322` `journalMode` 默认 `.default`（属性在 `:322`），文档明确"Queue 不做设置、Pool 配置 WAL"；`:331` `busyMode = .immediateError`；`DatabasePool.swift:76-83` 在 `.default` 与 `.wal` 下都调 `setUpWALMode()`；`DatabaseQueue.swift:51-57` 在 `.default` 下 `break`（不设 journal_mode）；`Migration/DatabaseMigrator.swift:112` `eraseDatabaseOnSchemaChange = false`、`:616` 创建 `grdb_migrations`。
- 工程：`project.pbxproj:6` `objectVersion 77`、`:18/:28` `PBXFileSystemSynchronizedRootGroup`、`:58-59` `swift-markdown` 远程包、`:279-281` `packageProductDependencies`、`:327-329` `packageReferences`、`:134-156` 部署目标 26.0 + `SWIFT_STRICT_CONCURRENCY = complete`；`Package.resolved` 在 `NanoIM.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/`，当前只有 swift-cmark / swift-markdown 两个 pin。
- 代码基线：`ChatStore.swift:48/:50-62`（init 同步读 JSON）、`:100`（`accountEnabled`）、`:107`（cursor）、`:116-118`（membership 清空）、`:122-129`（401 返回 + 退避）、`:181-203`（快照差分）、`:383-403`（`lookup: true, resend: false`）、`:405/:479`（status 0 双重语义）逐条核对；`SendAttemptStore.swift:21-23` 默认目录、`:25-31` 精确目录查找、`:62-70` `(origin,userID)`/文件幂等口径；`Session.swift:82/:62/:101/:156` 四个清理挂点确实存在；`ConversationView.swift:98-99` 的"正在确认/已不可访问"现状。
- Runbook：`scripts/e2e-up.sh`、`scripts/e2e-down.sh` 存在；`apps/im-server/src/server.ts:285-286` 是 `/health`/`/healthz`。

**未验证（Gate 2 只审文档，不伪造运行结论）**：GRDB 的 xcodeproj 集成与 `xcodebuild` 未在本轮运行；`swift build --triple … 268.28s` 只能作为作者证据（probe checkout 的存在可佐证解析/编译发生过）；任何真机、模拟器、飞行模式行为均未观察。

### 作者请挑点判断 (a)–(e)

- **(a) M1/M2 不是按层横切，各自可独立验收，但有两处归属交叉。** M1 = 库/迁移/首绘/四态（"打开就看到上次内容"），M2 = 隔离/撤销/迟到拒绝（"换账号或被移出后旧内容不出现"），两条旅程的观察方式与证据形式不同，M1 的退出标准也不引用 M2 的行为。交叉点：① 凭据失效 purge 同时写在两片范围里（design.md:432 与 :433），归属需明确；② M1 的"不整屏闪回"在 `membership_changed` 场景仍会闪，因为 D11 排在 M2——M1 退出标准应写明该例外，否则 M1 会被这条判失败。见 R1-R3。
- **(b) 首绘先于凭据校验没有越出既有契约，但 delta 自身缺一句可判定条款。** 既有契约的时点是"服务端明确拒绝之后"（`spec.md:154-157` 的"才…失效后不再展示"），以及"退出或切服务后旧内容不进入**新会话**"（`ios-client.md:33-35`）——同账号、同服务、本人内容在服务端确认前短暂呈现，不属于"旧内容进入新会话"；媒体也只留元数据，`ServerOrigin.resource` 的授权约束不变。所以 D6/R9 的取舍我可以接受。问题在 delta：MODIFIED 保留了"资格失效时仅显示相应准入状态"（unit `ios-client.md:67`）却没有把"失效确认前可呈现、确认后立即停止"写成条款，Gate 3 的 verifier 会读到一条与实际行为相反的约束。见 R1-W7。
- **(c) `read_state` 只写不读应当保留，不该推迟到 U3。** 理由是已定前提"U1 一次交付完整 schema、不做第二次迁移"，且 D5 有守卫测试防止 U3 语义提前长进 U1。缺的只是写入触发点（`ChatStore.markRead` 收到 200 后写），补一句即可。见 R1-R4。
- **(d) 300 条这个常量本身不阻断，但缺上游依据且与分页尺寸耦合。** "60 × 5 页"是工程取值，不是需求推导；`ChatAPI.swift:4` 的分页尺寸一变就要重算，建议写成"≥5 个当前分页尺寸"的可配置常量。真正要补的是修剪与 boundary 的关系（见 R1-R2）以及修剪后 `isAtLocalStart`/`nextBefore` 必须与新窗口一致，否则"需要连接后才能读取"的提示会出现在错误的滚动位置。
- **(e) `membership_changed` 改定向核对没有越出 U1 范围。** spec 的"不整屏闪回"与"撤销后消失"要求它，且只用既有 `GET /conversations/{id}`，不新增协议；它已排在 M2，不算超范围。要补的是确认期间的呈现（R1-W2）与"兜底 `/sync` 的节奏"是否意味着改名仍触发一次全量（若是，收益只在"不清空时间线"，仍值得做，但应写明）。

### 补充问题判断 1–4

1. **DatabaseQueue 单写者：作者的事实断言正确，选择在 U2/U5 仍成立，不迫使返工。** 已核实 `DatabasePool` 在 `.default` 下强制 WAL、`DatabaseQueue` 默认不动 `journal_mode`（源码行号见上）。"仓储接口 + 单写者 + 事务边界"把并发面固定在 actor 里，U2 的用户意图事务与 U5 的快照事务都只是这条串行写队列上的短期任务；未来要并发读只需替换连接类型，接口/schema/事务边界不变——这条演化口是真实的。**但理由三站不住**：rollback journal 同样产生 `-journal` 文件，落在同一目录、同一 `.completeFileProtection` 下；"锁屏时有库但不可读"的成因是保护等级（D9 已正确归因），不是 WAL。用不成立的判据会带偏 U5 选型，见 R1-R1。另有一个真实代价被低估：默认 rollback journal 下每次 commit 都要 fsync，与"每键一次草稿事务"叠加（R1-W5）。
2. **离线态下的撤销：设计没有写"离线可读到什么程度"与"联网后多快收敛"，delta 的撤销 Scenario 在最不利读法下不可满足。** 撤销判定全部依赖网络（成功全量 `/sync`、详情 403/404、WS 事件），服务端在客户端离线期间撤销时客户端无法知道；M2 ④ 只覆盖"在线已得知撤销后断网"这一可行分支。spec.md 也有同样措辞（首文档已过 Gate 1，需要作者判断是收窄还是补边界）。见 R1-W1。
3. **迁移与回退：语义层（幂等身份、同事务标记、零网络、`recoverPending` 仍 lookup-only）成立，但三处不闭合。** ① `pending_sends` 的会话归属与"open 即迁移"时序冲突（R1-C1，会让"一条不丢"失效）；② 归档/删除与 R1 的回退承诺自相矛盾（R1-C2）；③ "pending 在首帧就在"在升级后首启不成立——那时 `conversations` 还没有任何行，首帧最多只能给出 pending 计数。
4. **可验证性：写了"哪些 CI 不能验"，但没写完"谁在哪一步验"。** Runbook 与"CI 无法证明"清单是够的，M1/M2 也确有 `[reviewer]` 轨道；缺口是 4 项里有 3 项（锁屏/文件保护、备份排除、签名续期连续性）没有落到任何 milestone 步骤，首绘时延给了 16ms 判据却没人测；M1 ⑤ 依赖"升级前留有未确认发送"，但没有可执行的构造步骤与无真机时的处理。见 R1-W3。所以不是"只靠自述"，但按现状会以自述或 CI 绿收尾。

### Issues

#### R1-C1（CRITICAL）— `pending_sends` 的会话归属与"打开分区即迁移"时序未闭合，可让"一条不丢"整体失效

- 位置：design.md:243（"外键开启（GRDB 默认）"）、:256（`pending_sends` 列定义未标注会话外键）、:196 与 :203（会话删除"级联消息/成员/草稿/pending/boundary/read_state"）、:220（迁移在 `ChatRepository.open` 内、`migrator` 之后、对外可用之前）。
- 证据：其余表都显式标了 `→ conversations (CASCADE)`，只有 `pending_sends` 没标；而 D10 两处都把 pending 算进"该会话全部行（级联）"。迁移发生在任何 `/sync` 之前，此时 `conversations` 表为空（升级后新建的库）。若实现者按 D10 的"级联"给 `conversation_id` 加外键，插入会因 FK 违约失败——`INSERT OR IGNORE` 只吸收 UNIQUE/NOT NULL/CHECK/PK 冲突，不吸收 FK 违约（GRDB 已开 `foreignKeysEnabled`，见 Configuration.swift:28），于是 D12 的失败路径会把每一条都记 `rejected`，整批迁移不可用。
- 后果：正是 spec.md:126-138 要保的行为在真实升级路径上失败；且 JSON 虽被保留，UI 里那条"未确认"消息已经消失，用户会以为它发出去了或没了。附带问题：design.md:220 的"对 UI 是同步可见的（pending 在首帧就在）"在该时序下也不成立——首帧没有任何会话行，`BootstrapSeed` 只能给 pending 计数。
- 需要作者回应：明确 `pending_sends.conversation_id` **不加**外键、改用显式删除（并写出 revoke/purge/snapshot 差分三处清理点），或明确迁移移到首次成功快照之后（并接受首帧看不到 pending 的代价）；同时修正"pending 在首帧就在"为"首帧可看到 pending 计数"或说明占位会话行的处理。

#### R1-C2（CRITICAL）— D12 的归档/删除时序与 R1 的回退路径自相矛盾，且改名后旧构建再也读不到旧 JSON

- 位置：design.md:224（"提交成功后才把旧目录改名为 `<digest>.migrated-<ts>`，下次成功打开时删除" + "保留一个发布周期的旧 JSON 是本次的回退路径"）、:384（R1 回退："新版本可退回旧构建，JSON 路径与语义原样可用，零数据丢失"）。
- 证据：旧构建按精确目录查找——`SendAttemptStore.swift:21-23` 默认目录 `ApplicationSupport/NanoIM/SendAttempts`、`:62-66` `ownerDirectory` 拼 `<digest>`、`:25-31` `load` 先 `fileExists(owner.path)` 再列目录。目录被改名为 `<digest>.migrated-<ts>` 后，旧构建返回空数组，`ChatStore.restoreAttempts()`（ChatStore.swift:50-62）恢复不到任何未确认发送。而"下次成功打开时删除"与"保留一个发布周期"直接冲突：下一次启动就会删掉。
- 后果：R1 是这条唯一数据风险的全部兜底；修复发布期内一旦发现迁移缺陷，回退会静默丢掉"可核对/可重试"的记录（不重发，也不会再提示用户），Gate 3 若按 D12 实施，回退能力会被写没。
- 需要作者回应：三选一并写清触发者与时点——(i) 不改名不删除，只写 `migration.send_attempts_v1` 标记（旧构建始终可读）；(ii) 改名但保留 N 个版本/天数，写明删除判据与谁执行；(iii) 复制而非改名，发布周期后删除，并写明删除失败的用户可见后果。R1 的回退描述必须与实现一致。

#### R1-W1（WARNING）— 离线期间的撤销与"联网后多快收敛"未写；delta 的撤销 Scenario 在最不利读法下不可满足

- 位置：delta `specs/im/ios-client.md:52-56`（"**AND** 处于离线状态或重启后同样不展示被撤销的内容"）、同文件 :36；design.md:196/:207/:209-216（撤销判定全部来自网络结果）、:433（M2 reviewer ④）。
- 证据：撤销只来自一次成功全量 `/sync`（design.md:107）、详情 403/404、或 WS 事件（D11），三者都需要网络。服务端在客户端离线期间撤销访问时，客户端无信息可用，本地内容会展示到下次联网。首文档 spec.md:102-106 有同样措辞（Gate 1 已过，需要作者判断是否收窄）。M2 ④"在线撤销后立刻断网冷启动"恰好只覆盖可行分支，没有"离线期间被撤销、恢复联网后收敛"的步骤；design.md:176 保留了 `pow(2, attempt)` 上限 30s 的重试，但没有把它写成收敛口径。
- 后果：Gate 3 verifier 按字面核对会发现不可满足；实现者为凑字面可能去造离线撤销检测。用户可见矛盾：离线查看一个已被撤销的群，界面显示正常可读。
- 需要作者回应：在 design 补"离线可读边界 + 收敛口径"（例如：撤销发生在离线期间时不承诺离线不展示，恢复联网后第一次成功 `/sync` 起不再展示），据此调整 delta 措辞（必要时提回首文档），并在 M2 增加一条可执行的"离线期间撤销 → 联网收敛"步骤。

#### R1-W2（WARNING）— D11 的 `accessUnconfirmed` 期间时间线呈现未定义，两条既存契约在此方向相反

- 位置：design.md:212-215（"标记 `accessUnconfirmed` → 定向 `GET /conversations/{id}`"），对照现状 `ChatStore.swift:135-144`（收到事件立刻 `timelines[chat] = nil` 并进 `checkingAccess`）与 `ConversationView.swift:98-99`（"正在确认聊天权限…" / "此聊天已不可访问"）。
- 证据：设计只说"标记"，没说这一屏显示什么。`ios-client.md:49-51`（权限撤销后不再显示或分享受保护缓存）要求先藏；`spec.md:52/:58`（不整屏闪回、不会在下一帧重新出现）要求不要藏了再恢复。约 1 个 RTT 内继续显示已被撤销的群历史是撤销后的可见泄漏；改名场景先隐藏再恢复就是本 unit 要消灭的闪回。
- 后果：实现者只能二选一，且两种选择都能被现有 Scenario 判失败。这是 U1 唯一直接决定"受保护内容"呈现的分支。
- 需要作者回应：在"状态呈现契约"表里明确三种事件的呈现：改名/加成员（就地更新、不隐藏）、撤销/删除（何时隐藏、是否保留列表行占位、期间文案）、核对失败（错误分类与重试）。

#### R1-W3（WARNING）— 四项"CI 无法验证"里有三项没有落到任何 milestone 步骤；迁移前置没有可执行构造步骤

- 位置：design.md:412（飞行模式替代验证）、:422-424（CI 无法证明清单）、:432-433（M1/M2 轨道）；相关判据 design.md:98（首绘读 >16ms）、:182（备份排除）。
- 证据：清单列 4 项：飞行模式、锁屏/`completeFileProtection`、签名续期连续性、首绘时延主观感受。只有飞行模式落到 M1 reviewer ②/③。锁屏与文件保护、备份排除是否生效、签名续期对本地库的连续性、首绘时延都没有对应的 `[reviewer]`/`[worker]` 步骤或证据要求；D2 给了"首绘读 > 16ms"这一具体判据却没人测量。另一方面 M1 reviewer ⑤（"升级前留有未确认发送的账号"）没有 runbook 步骤说明怎么造出这个前置（装旧构建 → 断网发送 → 覆盖安装），也没写无真机时该 milestone 是阻断还是接受替代证据。
- 后果：这三项会以作者自述或 CI 绿收尾——正是 Gate 2 要拦的缺口；reviewer 在另一台机器上无法复现 ⑤ 的前置，M1 的证据不可独立复核。
- 需要作者回应：把 4 项分别落进 M1/M2 的 `[reviewer]`/`[worker]` 步骤（写明证据形式与位置），给出"旧构建 → 未确认发送 → 覆盖升级"的命令序列与签名前提，并写明无真机时不得判该 milestone 通过。

#### R1-W4（WARNING）— `unauthorized`/`deactivated` 路径未闭合：状态机缺边、状态数与测试口径不一致、401 的 purge 归属未指明

- 位置：design.md:142-157（状态图无 `loaded → unauthorized`、无 `loaded → deactivated`）、:420 与 :432（"`ChatListPhase` 五态转换"）、:304-315（`ChatStorageController` 拥有 purge，ChatStore"不决定删除时机"）。
- 证据：D7 实际有 7 个状态（bootstrapping / loadingFirst / localOnly / loaded / empty / failed / offline）加 2 个终态，测试口径写"五态"；已 `loaded` 之后再遇到 401/停用没有出边，而 D10 要求在 401 后立即 purge 并离开内容。真正拿到 401 的位置在 `ChatStore.run()`（ChatStore.swift:122-129）与 `Session.refresh()`（Session.swift:143-152），但 ChatStore 被规定不决定删除，AppModel 侧只有 `observe()` 收到 nil 这一条隐含路径（NanoIMApp.swift:46-56），设计没有把这个连接写出来。
- 后果：401 后的 purge 可能没有归属点（本地内容留在盘上、下次启动仍可能先绘），或者由 ChatStore 直接调 purge 违反 D3/控制器职责；"已加载后凭据失效"会落到未定义行为。
- 需要作者回应：补齐状态边（至少 `loaded → unauthorized/deactivated`，以及重试类回边）、统一状态数与测试口径，并指定 401/停用的 purge 触发点（建议 AppModel 观察 `session.updates()` 的 nil 或显式回调 `ChatStorageController.purge`）。

#### R1-W5（WARNING）— 草稿逐键落库与 D2 的 rollback journal 叠加：写放大与顺序性未定义

- 位置：design.md:106（"一次用户意图（草稿写…）→ 各自一个事务"）、:303（写入必须经仓储）、:97（D2 默认 rollback journal）；`ConversationView.swift:36`（`Binding` 的 set 每次按键写 `store.drafts[conversationID]`）。
- 证据：草稿输入是逐字符 `Binding` set；改成仓储写后即每键一个事务。`DatabaseQueue` 默认不改 `journal_mode`（DatabaseQueue.swift:51-57），rollback journal 每个 commit 都要 fsync 日志，设备上是毫秒级。同时 `Binding.set` 是同步函数、无法 await，"fire-and-forget Task 写库"会出现乱序覆盖（后到的旧文本覆盖新文本）。
- 后果：长草稿输入可能卡顿与闪存写放大；重启后可能恢复出被乱序覆盖的草稿文本，落在"草稿可恢复、不自动发送"的既有契约上。
- 需要作者回应：给出草稿写入策略（节流/合并 + 单一串行写队列 + 失焦/退出/发送前 flush 的保证），或说明草稿留在内存、只在下述时机落库（失焦、切会话、后台、发送），并保证与 `textOnly`/`upsertPending` 的原子性一致。

#### R1-W6（WARNING, Context / PLAUSIBLE）— D14"无 Context 影响"的判断漏掉 `interaction_contexts` 这条模型可见的选择链

- 位置：design.md:233-237（"库里的消息不会再被投喂给任何 LLM…… 也没有把本地库内容回传服务端的路径"）。
- 证据（Surface：来源 → 选择 → 组装，消息/交互背景）：`ChatStore.backgroundContexts` 从 `timelines[id]` 选出最多 3 条交互选择，随发送作为 `interaction_contexts` 上送（ChatStore.swift:414-424、:325-326）；服务端把它放进 relay payload 交给目标 Agent（`apps/im-server/src/messaging.ts:519`、`:616-622`，`interactions.ts:59-61`）。U1 把 `timelines` 从会话内累积的内存数组换成"每会话最多 300 条"的库投影（D13），候选窗口因此变小。
- 影响（PLAUSIBLE，需 >300 条本地消息的会话才触发）：同一会话里更早的交互选择不再进入 Agent 的背景上下文——这是"选择"阶段的模型可见信息变化，与"无一受影响"不符。本 unit 确实不组装 Prompt、不定义工具、不读写 Memory/History，因此不需要完整 Context Review，但结论要留痕或加守卫（例如断言 300 条窗口不改变 `backgroundContexts` 的候选语义）。
- 需要作者回应：在 D14 增加一条边界说明（本地库不组装 Prompt；但 `interaction_contexts` 的候选来源是这份投影，窗口上限由 D13 决定），并说明该变化可接受或加守卫测试。

#### R1-W7（WARNING）— delta 没有把"本地优先先于凭据校验"写成可判定条款，与同一文件的 MODIFIED 措辞潜在冲突

- 位置：delta `specs/im/ios-client.md:7`（SHALL 先从本地渲染再校正）、`:63-77`（MODIFIED 保留"资格失效时仅显示相应准入状态"）。
- 证据：D6 的取舍（design.md:137、R9 :392）让本地内容在凭据重校验完成前出现；delta 里没有任何一句说明"失效确认之前可以呈现、确认后立即停止"。首文档 spec.md:154-157 的"才…失效后不再展示"支持这个读法，但那是首文档，不是这份 delta 的文本。
- 后果：Gate 3 逐条核对 delta 时会读到一条与实际行为相反的约束；M1/M2 的 reviewer 也会就"401 后先看到内容"判失败。
- 需要作者回应：在 ADDED 或 MODIFIED 里补一句时序（"本地内容可在凭据重新校验完成前呈现；服务端确认失效后立即停止展示并清理"），与 R9 的取舍对齐。

### Recommendations

- **R1-R1**：改写 D2 的理由三。已核实 `DatabasePool.swift:76-83` 在 `.default` 下也走 `setUpWALMode()`、`DatabaseQueue.swift:51-57` 在 `.default` 下不设 `journal_mode`、`Configuration.swift:284-322` 的属性与文档。但 rollback journal 同样产生 `-journal` 文件，落在同一目录、同一 `.completeFileProtection` 之下；"锁屏时有库但不可读"的成因是保护等级（D9 已正确归因），不是 WAL。建议理由改为"单写者 + 数据量小 + 读写都不需要连接级并发"，删掉理由三，避免 U5 选型被不成立的判据带偏。
- **R1-R2**：修剪与 boundary 的关系。D13 修剪更旧消息后，锚定在已删消息上的 `conversation_boundaries` 行会变成"未锚定"，`TimelineMerge` 把未锚定 boundary 排到全部消息之前（ChatModels.swift:159-172），离线时间线顶部会出现一条与当前窗口无关的"Agent 配置已更新"。建议 boundary 随锚定消息一起修剪，或在读投影里丢弃锚点缺失的 boundary，并补一条单测。
- **R1-R3**：M1/M2 归属。凭据失效 purge 同时写在 M1（:432）与 M2（:433）范围里。建议 M1 只交付 `purge()` 原语并验证"重开读不到行"，五个触发点的挂接全部归 M2；同时在 M1 退出标准写明"`membership_changed` 仍走旧清空路径，属 M2"，让 M1 的"不整屏闪回"可判定。
- **R1-R4**：`read_state` 的写入触发点在 D5/D10 没写（应为 `ChatStore.markRead` 收到 200 后写 `markReadBoundary`）。补一句，并保留"写 read_state 不改变任何列表投影"的守卫测试即可；"只写不读"的取舍本身成立。
- **R1-R5**：delta `:7` 的短语"本机保存已确认的会话、消息、草稿与未确认发送记录"修饰关系不清（"已确认"是否也约束草稿/未确认记录）。建议改为"已确认的会话与消息，以及本人的草稿与未确认发送记录"。
- **R1-R6**：D14 引用 `agent-context-engineering.md` 时写"八个阶段"，该文档 `:9-11` 是七段消费链路（来源→选择/检索→转换/组装→注入/加载→消费→更新/过期→压缩/恢复）与八种 Surface，两者不同；引用应准确（不影响结论）。

### Author Resolutions

> 待 author 逐条核实后追加（author 只在本节追加，不回写上面的结论与证据）。

- R1-C1：**采纳方案一（不加外键 + 显式删除），并修正首帧可见性。** ① `pending_sends.conversation_id` 明确**不建外键**（design「数据模型」表已标注「刻意不建外键」，含 `foreignKeysEnabled = true`、`INSERT OR IGNORE` 不吸收 FK 违约、迁移先于任何 `/sync` 的根因）；② 删除改为两个显式入口：`revoke()`（所有撤销来源汇聚于此，镜像 `ChatStore.swift:491-499`）与 `purge()`（D10 新增「`pending_sends` 的删除只有两个入口」段 + 守卫单测）；③ 「pending 在首帧就在」改为「首帧只给**计数** + 说明」：`BootstrapSeed.pendingCount`、D6 步骤 2、D12「迁移完成 ≠ 首帧可见」、状态呈现契约新增一行、M1 `[reviewer]` ⑤ 同步；④ 两个必答场景写明：**首启即崩溃**——插入与标记同事务，标记已持久化，下次跳过导入（源数据仍在，跳过安全）；**首启即断网**——迁移是纯本地 IO、零网络，正常完成，只有可见性推迟到首次成功 `/sync`。
- R1-C2：**采纳 (i)：不改名、不删除，只写库内标记。** D12 改写为「旧 JSON 原样保留，是否已迁移只由 `cache_meta["migration.send_attempts_v1"]` 判定」，并补「为什么用库内标记而不是探测目录」：库丢失即等同没迁移过，会从保留的 JSON 重新导入。删除判据明确写「U1 没有；退役留 U2 另立决策」。R1 的回退描述同步改为诚实口径：升级前的尝试回退后原样可读；升级后新产生的尝试只在库中，旧构建看不到——有界损失，**不承诺「零数据丢失」**。R1 风险行、D12「回退的真实覆盖」、「涉及范围」表中 `SendAttemptStore` 行均已改。
- R1-W1：**采纳「补边界 + 收敛口径」。** D10 新增「离线可读边界与撤销收敛口径」：撤销只能通过网络得知；承诺两段（已得知撤销 → 离线/重启/冷启动都不展示；离线期间发生 → 恢复联网后第一次成功 `/sync` 起不展示）；收敛上界 = 现有 `pow(2, attempt)` 上限 30s（`ChatStore.swift:122-129`）；明确不做猜测式隐藏。delta 的「会话访问被撤销」Scenario 已按「本机已得知撤销」改写并写清收敛。`spec.md:102-106` 按同一前提解释（D10 点名）。**后续（上级已批）**：首文档已按同一诚实口径修订——`spec.md`「会话访问被撤销」改为三条 AND 并附「口径修正（design 阶段确认）」；更强的「离线也能即时知道撤销」仍需服务端推送/访问租约（U4/U7），另立 unit。
- R1-W2：**按服务端事实设计，而不是按愿望设计。** 核对 `apps/im-server/src/messaging.ts:300-306`：`membership()` 只广播 `{conversation_id}`，改名（`:855-859`）、成员变更、删除（`:864-873`）共用同一帧，无 title/成员增量/event_id，客户端**无法**本地判别。D11 因此定为「收到即可能撤销」：列表行保留、该会话时间线先隐藏并显示既有占位（`ConversationView.swift:100-101`），三种情况分别定义——200 就地恢复（不重建整屏、不重排、不重拉消息）；403/404 或不在可见集合 → `revoke` + tombstone；传输失败/5xx → 不判撤销，随 `/sync` 收敛。状态呈现契约新增三行。明确接受代价：改名会看到 ≤1 RTT 占位。M2 `[reviewer]` ③/④ 分别验改名与被移出，`[worker]` ③ 补三条分支单测。
- R1-W3：**四项全部落到步骤，不再靠自述。** 测试策略新增「必须在 milestone 轨道留证据」表，Runbook 补执行细节：(a) 首绘读时延 → M1 `[worker]` 用 `os_signpost`/`Logger` 取 ≥20 次冷启动 p50/p95，落 `evidence/bootstrap-latency.md`，>16ms 触发 D2 演化口评估（替代「主观感受」）；(b) 锁屏/文件保护 → U1 只验**属性**（真机 Debug 打印 `URLResourceValues`：`.completeFileProtection`），**行为**（锁屏不可读）明确不在 U1 判据、属 U5 后台路径；(c) 备份排除 → 同法断言 `isExcludedFromBackup == true` 并用 `simctl get_app_container` 核对位置；(d) 签名续期连续性 → **不纳入任何 milestone**（需 ≥7 天等待，重签不换容器），理由写明。M1 ⑤ 的前置写成可执行 5 步（旧构建 → 断网发送 → `get_app_container` 核对 `NanoIM/SendAttempts/<digest>/*.json` → `simctl install` 覆盖安装 → 打开），并写明无真机不得判 pass 的项。
- R1-W4：**拆成正交两相位，补齐边并指定 purge 归属。** `ChatListPhase` = `.loadingFirst/.loaded/.empty/.failed`（内容呈现），`ConnectionState` = `.starting/.localOnly/.syncing/.online/.offline(attempt,nextRetryAt)/.unavailable(status)/.unauthorized/.deactivated`（连接），两幅状态图各自完整；补 `loaded → empty`、`empty → loaded`、`loaded → loadingFirst`（purge 重置）与 `localOnly/online → unauthorized/deactivated` 等边；不变量从 D8 收回 D7 单点维护，测试口径改为「四态 + 八态」。401/停用的 purge 归属：`Session` 在既有清理点维护 `termination: SessionTermination?`（`.signedOut/.credentials/.deactivated`），`AppModel.observe()`（已订阅 `session.updates()`，`NanoIMApp.swift:45-56`）收到 `nil` 后调 `ChatStorageController.purge(reason:)` + `resetProjection()`；`ChatStore` 不 purge。M2 `[worker]` ④ 加「401 后 purge 只被调用一次、ChatStore 不直接调」单测。
- R1-W5：**草稿不逐键落库。** D3 新增「草稿写入」：`Binding.set` 只改内存；flush 点 = 失焦 / 切会话 / `scenePhase != .active` / 发送前 / `openChat` 切走；flush 点之外 1s 节流合并；只保留最新快照由**单一串行写任务**提交（后写胜出，无乱序）；损失窗口 ≤1s 并写进 M1 证据；发送前 flush + `upsertPending` 同事务清 draft，保证与 `textOnly`/pending 的原子性。D2 把「提交成本」单列并注明它是写入策略、不是连接类型判据（rollback journal 每 commit fsync）。
- R1-W6：**采纳，结论从「无一受影响」改为「不组装输入，但候选窗口留痕」。** D14 标题改为「不组装任何模型输入……唯一要留痕的是 `interaction_contexts` 的候选窗口」，并补链路：`ChatStore.backgroundContexts`（`ChatStore.swift:414-424`，取最近 3 条）→ 随发送上送（`:325-326`）→ 服务端校验后放进 relay 载荷（`messaging.ts:512`、`:615`，`interactions.ts:59-61`）。D13 的窗口使「选择」阶段候选集变小，仅当会话本地消息超过窗口上限时触发；判断可接受（只取最近 3 条、按 `editedAt` 倒序），加守卫单测固定候选语义；若把窗口缩到 5 页以下，需回 Context Review。
- R1-W7：**采纳，补成可判定条款。** delta 的 ADDED 新增 Scenario「本地内容先于凭据校验呈现」：可以先呈现该账号本人的本地内容、不因此显示登录表单；服务端明确拒绝凭据或账号不可用时**立即停止展示并清理**。D6 的取舍描述改为指向该条款（与 R9 对齐），MODIFIED 段未删任何既有断言。
- R1-R1：**采纳。** 删除 D2 原「理由三」（WAL/`-wal`/`-shm` 与保护等级的说法不成立：rollback journal 同样产生 `-journal`，同目录同保护等级），结论不变；改为「理由三：本 unit 没有连接级并发的使用者」，并单列「提交成本约束（写入策略，不是选型判据）」。演化口（`DatabaseQueue → DatabasePool`）保持唯一。
- R1-R2：**采纳，并顺带处理 (d) 的常量问题。** D13 增：① 同事务删除锚点被修剪的 boundary；② 读投影丢弃锚点不在窗口内的 boundary（引用 `ChatModels.swift:166-169` 的未锚定排序）；③ `conversations` 增列 `trimmed_at TEXT NULL`，`nextBefore`/`isAtLocalStart` 与修剪后窗口一致（`trimmed_at` 非空时报「更早消息需要连接」而非「已到最早」）；④ 单测清单补齐。上限从「300」改为派生值 `max(300, 5 × 当前分页尺寸)`，避免与 `ChatAPI.swift:4` 的 60 耦合失配。
- R1-R3：**采纳。** Milestones 增「归属裁定」段：M1 只交付 `purge()` 原语并验「重开读不到行」，五个触发点全归 M2；M1 期间 `membership_changed` 仍走今天的「`clear()` + 全量重拉」，因此 M1 的「不整屏闪回」只覆盖 `/sync` 快照校正。M1 范围与 M2 范围已同步改写。
- R1-R4：**采纳。** D5 写明 `read_state` 的唯一写入触发点：`ChatStore.markRead` 收到 200 后 `markReadBoundary(会话, last_read_message_id)`（现状 `ChatStore.swift:254-260` 不记录已报边界），失败不写、下次可见消息重报；保留「写 read_state 不改变列表投影」守卫测试。
- R1-R5：**采纳。** delta 首句改为「已确认的会话与消息，以及本人的草稿与未确认发送记录」，修饰关系不再歧义。
- R1-R6：**采纳。** D14 改为「七段消费链路（`agent-context-engineering.md:11`）」+「八种 Surface 的取舍原则（`:13`，按原文引用）」，不再混称「八个阶段」。

## Round 2

- reviewer: 独立 `change-design-reviewer`（同一 reviewer，未参与 feat-714 设计与实施；本机）
- review_target: `docs/changes/feat-714-ios-local-chat-store/`（design.md、`specs/im/ios-client.md` delta、spec.md 两处「口径修正」、M1/M2 骨架）
- reviewed_head: `unit/feat-714` @ `a6ee1f364`，工作树 clean；轮次范围 `fe2c8fa60..a6ee1f364`（`b4c6ecac7` 是 Round 1 报告，`c19a18a23` + `a6ee1f364` 是作者修订）
- review_mode: closure（附首文档两处口径落地的 delta 核对）
- mode_reason: 需求、非目标、核心边界与 milestone 切分未变；改动集中在 Round 1 各条的收口文本、两处由上级决定的首文档口径，以及若干新增单测/证据步骤，按旧问题逐条闭环并只审新增句即可
- started_at: 2026-11-05T16:34:00+08:00
- completed_at: 2026-11-05T16:52:00+08:00
- duration: ≈18 min

### Verdict

**Issues Found（Changes requested）— 0 CRITICAL / 2 WARNING**，另 4 条 Recommendations。

Round 1 的 2 CRITICAL 与 7 WARNING、6 条 Recommendation **全部 CLOSED**，没有 PARTIAL / OPEN，也没有把结论改写成更模糊的措辞；两条 CRITICAL 的修法是结构性的（去外键 + 显式删除；不改名不删除 + 库内标记），不是解释对齐。本轮结论由两个**新出现的边**决定，二者都是一段话的补写，不涉及回退任何 Round 1 决定：① `pending_sends` 一旦没有对应会话行，`revoke` 永不触发；② 登录成功 / 分区变化后由谁打开分区没有定义，`ChatStorageController` 的「无仓储」被 D3 定义成「打不开」。

### Round 1 闭环核对

| R1 项 | 状态 | 证据（本轮重读文本 + 复核代码事实） |
|---|---|---|
| R1-C1 外键与时序 | CLOSED | design.md:329「**`conversation_id` 刻意不建外键**（D12）」并给出 `foreignKeysEnabled = true` / `INSERT OR IGNORE` 不吸收 FK 违约的根因（:286）；删除改为「只有**两个**显式入口」（:247-252，`revoke` + `purge`，快照差分不直接删 pending）；首帧改为「只给出 pending **计数**」（:145、:283、:374 `BootstrapSeed.pendingCount`，:446 呈现契约行、M1 `[reviewer]` ⑤）；单测补「**在 `conversations` 表为空时迁移成功**（无外键）」（:511）；「首启即崩溃」「首启即断网」两问写在 :290 与 :282。无残留「pending 在首帧就在」表述（grep「首帧」只剩计数口径） |
| R1-C2 改名/删除旧目录 | CLOSED | design.md:292「**U1 不改名、不删除**旧目录……U1 的删除判据是**没有**：退役旧目录留给 U2 另立 unit 决策」，并直接引用 `SendAttemptStore.swift:25-31`、`:62-67` 说明旧构建按精确目录查找；:293「不承诺「回退零损失」」；:465 R1 行同步为「不承诺「回退零数据丢失」」；:466 R2 依赖「U1 本来就不改名不删除」；:20 `SendAttemptStore` 行已改。grep 全文无 `migrated-<ts>`、无肯定式「零数据丢失」 |
| R1-W1 离线撤销 | CLOSED | design.md:258-265 两段承诺 + 明确不做猜测式隐藏 + 收敛上界=现有 `pow(2, attempt)` 上限 30s（`ChatStore.swift:122-129`，本轮复核成立）；spec.md:106-108 三条 AND 与 :110「口径修正（design 阶段确认）」；delta 同名 Scenario 已按「得知」改写；M2 `[reviewer]` ⑥ 是「离线期间撤销 → 恢复联网后 ≤30s 收敛」的可执行步骤（:535）。三处措辞互相一致，不是「靠解释对齐」 |
| R1-W2 `accessUnconfirmed` 呈现 | CLOSED | 本轮独立复核服务端事实：`apps/im-server/src/messaging.ts:301-307` 的 `membership()` 确实只广播 `{op:"event", event_type:"conversation.membership_changed", data:{conversation_id:id}}`，无 title、无成员增量、无 event_id；改名（PATCH，`:858-861` 调用同一方法）与删除（`:864-873`，`:872` 调用）共用。design.md:270-276 据此定义三分支（200 就地恢复 / 403·404 → `revoke` / 传输失败不判撤销）、:277 写明「改名不触发全量重拉、兜底 `/sync` 仍会跑」、:448-450 三行呈现契约、M2 `[reviewer]` ③④ 与 `[worker]` ③ 分别验三条分支与两条真实场景 |
| R1-W3 可验证性落点 | CLOSED | design.md:516-524 新增「必须在 milestone 轨道留证据」表，4 项逐项给落点与证据形式（飞行模式 → M1 ②③/M2 ④；首绘时延 → M1 `[worker]` + `evidence/bootstrap-latency.md`；文件保护/备份排除 → M1 `[worker]` 属性断言；签名续期 → 明写「无（不纳入任何 milestone）」并给理由）；:496-503 把 M1 ⑤ 前置写成 5 步可执行构造（旧构建 → 断网发送 → `get_app_container` 核对 `NanoIM/SendAttempts/<digest>/*.json` → `simctl install` 覆盖安装 → 打开）；:504 写明无真机不得判 pass 的项。M1 `[worker]` ⑧ 与表一致 |
| R1-W4 状态机与 purge 归属 | CLOSED | design.md:150 标题即「内容相位 `ChatListPhase`（四态）与连接相位 `ConnectionState`（八态）」，:154-170 四态图补 `loaded ⇄ empty`、`loaded/empty/failed → loadingFirst`，:180-200 八态图补 `localOnly/online → unauthorized/deactivated`，:202 取值列全 8 个，:204 三条不变量收在 D7 单点，:205 `Session.termination` → `AppModel.observe()` 收 `nil` → `ChatStorageController.purge(reason:)`，并明写「`ChatStore` 不 purge」；:512 测试口径「四态 + 八态」；M2 `[worker]` ④「`purge` 只被调用一次、`ChatStore` 不直接调」。全文已无「五态」 |
| R1-W5 草稿逐键落库 | CLOSED | design.md:115-120：`Binding.set` 只改内存、5 个 flush 点（失焦 / 切会话 / `scenePhase != .active` / 发送前 / `openChat` 切走）、flush 外 1s 节流、只保留最新快照由单一串行写任务提交、损失窗口 ≤1s 且明写「不伪装成零损失」、发送前 flush 与 `upsertPending` 同事务清 draft；:101 把「提交成本约束」单列为写入纪律而非选型判据。与 `ConversationView.swift:36` 的同步 `Binding.set` 事实一致 |
| R1-W6 `interaction_contexts` | CLOSED | design.md:305-309：结论从「无一受影响」改为「不组装任何模型输入……唯一要留痕的是候选窗口」，链路逐点复核成立（`ChatStore.swift:414-424` 取 3 条、`:325-326` 随发送上送、`messaging.ts:512`、`:615` 放进 relay 载荷、`interactions.ts:59-61` 服务端限 3 条）；:308 给出可接受判断与守卫单测要求 |
| R1-W7 先于凭据校验的条款 | CLOSED | delta 新增 ADDED Scenario「本地内容先于凭据校验呈现」（可先呈现本人的本地内容、不因此显示登录表单；服务端明确拒绝后「立即停止展示并清理」），MODIFIED 段同时保留「只有服务端明确拒绝……才显示需要重新登录」并加「**且此后**不再展示」，时序两侧都成立；design.md:147 的取舍与 :447 呈现契约行指向该条款。MODIFIED 未删任何既有断言（`fe2c8fa60..a6ee1f364` delta diff 逐行确认） |
| R1-R1 D2 理由三 | CLOSED | design.md:100 理由三已改为「本 unit 没有连接级并发的使用者」；原「rollback journal 保护等级不同」的判据在全文不存在（grep `-wal` / 保护等级只剩 :101/:116 的 fsync 论述，本身正确）；:101 提交成本单列。GRDB 事实本轮重跑见下 |
| R1-R2 修剪与 boundary | CLOSED | design.md:300 同事务删锚点被修剪的 boundary + 读投影兜底（引用 `ChatModels.swift:166-169`，本轮复核：`:168` 的 `unanchored` 排到全部消息之前）；:301 `trimmed_at` 与 `nextBefore`/`isAtLocalStart` 语义切换 + 单测项；:322 增列 `trimmed_at`、:333 索引；:534 `[worker]` ③ 覆盖四条 |
| R1-R3 M1/M2 归属 | CLOSED | design.md:530「归属裁定（R3）」：M1 只交付 `purge()` 原语，五个触发点全归 M2，M1 期间 `membership_changed` 仍走旧「clear + 全量重拉」且明写「M1 的『不整屏闪回』只针对 `/sync` 快照校正」；M1 范围行（:534）与 M1 `[reviewer]` ① 同步带该例外 |
| R1-R4 `read_state` 写入点 | CLOSED | design.md:138 唯一触发点 = `ChatStore.markRead` 收到 200 后 `markReadBoundary`（现状 `ChatStore.swift:254-260` 只更新会话行，本轮复核成立），失败不写、下次重报；:368 仓储接口有 `markReadBoundary` |
| R1-R5 delta 首句歧义 | CLOSED | delta 首句已改为「已确认的会话与消息，以及本人的草稿与未确认发送记录」 |
| R1-R6 引用准确性 | CLOSED | design.md:307 改为「**七段消费链路**（`agent-context-engineering.md:11`）」+「**八种 Surface 的取舍原则**（`:13`）」；本轮核对 `:11` 正是七段链路、`:13` 是「不要求每次遍历八种 Surface」，引用与原文一致 |

### 上级已决口径落地核对

| 决定 | 状态 | 证据 |
|---|---|---|
| 离线撤销口径诚实 | 已落地且一致 | spec.md:106-108 三条 AND（已得知 → 离线/重启都不展示；离线期间发生 → 第一次成功 `/sync` 后收敛、上界 ≤30s；不做猜测式隐藏）+ :110「口径修正（design 阶段确认）」；design.md:265 明确写「首文档与 delta 已按同一口径改写，不是『靠解释对齐』」；delta 同 Scenario 同口径 |
| 升级后有界让步（计数 + 说明） | 已落地且一致 | spec.md:139-145 新 Scenario「升级后首次启动的呈现」+ :145 口径修正（含「不以占位会话行呈现」「会话落库后进入时间线」）；design.md:283 与 :446、M1 `[reviewer]` ⑤ 同步。两份文档对「首次成功 `/sync` 前只给计数」描述一致 |

### 独立复核的现状断言（本轮重跑，非转述）

- **GRDB pin 与行为**：probe checkout `/private/tmp/grdb-probe/.build/checkouts/GRDB.swift` HEAD = `92a554cd0d5e8d67cb18993c6054e73fe42c066c`、tag `v7.12.0`、提交日期 2026-11-01，`git tag --sort=-v:refname` 首位即 `v7.12.0`。`Package.swift:1` `swift-tools-version:6.1`、`:50-55` `platforms: [.iOS(.v13), …]`（`.iOS(.v13)` 在 `:51`）、`:119` `swiftLanguageModes: [.v6]`；`README.md:20` 「Swift 6.1+ / Xcode 16.3+」。行为断言复核：`DatabaseQueue.swift:45-58` 在 `.default` 下 `break`（不改 `journal_mode`）、`Configuration.swift:28` `foreignKeysEnabled = true`、`:331` `busyMode = .immediateError`、`DatabaseMigrator.swift:112` `eraseDatabaseOnSchemaChange = false`；`GRDBSQLite` 确为 `.systemLibrary` + `.apt` provider（`Package.swift` targets），D1 对它的判断成立。**未由本轮重跑**：xcodeproj 集成后的 `xcodebuild`、作者的 `swift build --triple` 日志、任何真机/模拟器行为——与 Round 1 同一证据边界，文档也如实这么写（design.md:91）。
- **代码引用抽查**（全部逐行命中，仅个别 ±1 行偏移不计）：`ChatStore.swift:190`（撤销集含 `pending.keys`，见 R2-W1）、`:254-260`、`:325-326`、`:383-403`、`:405/:479`、`:414-424`、`:491-499`、`:84-89`、`:100`、`:107`、`:116-118`、`:119`、`:122-129`；`Session.swift:55-57/62/82/101/147/156`、`:189-201`；`SendAttemptStore.swift:25-31/35-37/41-47/62-67`；`ConversationView.swift:36/75/98-101`；`NanoIMApp.swift:11/15/45-56/74-77`；`ChatModels.swift:25-28/84-107/123/131-136/157-172`；`ChatAPI.swift:5`（文档写 :4，±1）；`ChatListView.swift:20/59`。
- **服务端事实**：`messaging.ts:301-307`（单字段载荷）、`:858-861` 与 `:864-873`（改名/删除共用）、`:512`、`:615`；`interactions.ts:59-61`（≤3 条）——全部与文档一致。

### 范围与非目标核对

- **零服务端 / 零 Web 仍在**：design.md:14「本 unit 只改原生 iOS 客户端，**零服务端、零 Web 改动**」、:27「不改 `apps/im-server/**`、`src/IM/frontend/**`、`/sync` 与 `/conversations` 的默认返回、`/read` 语义、事件类型枚举」、:459「其余包：no spec delta」；`/sync` 仍全量（:111、:321「不引入增量协议」）。
- **没有把推送/事件细分偷带进来**：更强撤销承诺与 `membership_changed` 细分都明确推给 U4/U7（:265「需服务端推送或访问租约，属 U4/U7，另立 unit；本 unit 不伪造该能力」、:278「这里只用现有接口，不新增协议」）；R10 的「若误伤不可接受」也停在 U4。
- **U3/U9 语义没有提前长进 U1**：`read_state` 只写不读并有守卫测试（:138）、`interaction_contexts` 只留痕（:308）、UI 信息架构与视觉属 U9（:310）。全程无 `TBD`/`待定`/`FIXME`（grep 为空）；三处显式延后（签名续期证据、旧 JSON 目录退役、更强撤销承诺）都写明了归属或「不做」的理由，不阻断实施。

### New findings

#### R2-W1（WARNING）— `pending_sends` 的会话从未落进权威集合时，没有任何收敛路径；计数与说明会永久残留

- 位置：design.md:283「这些记录在第一次成功 `/sync` **把会话写进库之后**，就按会话出现在时间线里」；:238/:245 删除范围以「会话」为起点（外键级联的表 + 显式删 `pending_sends`）；:247-252「pending 的删除只有**两个**显式入口」，其中 `revoke` 的触发被枚举为「快照缺项、详情 403/404、`membership_changed` 核对失败」。
- 证据：`revoke` 的「快照缺项」按 D3（:111）是对**库内已有会话行**做差分；迁移先于任何 `/sync`，所以这些 pending 行对应的会话在库里**没有行**（这正是 C1 去掉外键的原因）。今天的实现在这一点上反而是全的：`ChatStore.reconcile` 把 `pending.keys` 并入撤销集（`ChatStore.swift:190`：`Set(timelines.keys).union(uploadDrafts.keys).union(checkingAccess).union(pending.keys)…`），设计换成库层差分后没有继承这一条。也不在这两个入口内，所以除 `purge()` 外没有任何清理路径。
- 后果：升级前对某个此后被解散 / 已被移出的群留下的未确认发送，迁移后永远没有会话行；`bootstrapSeed.pendingCount` 每次启动都给「N 条未确认的发送，连接后可在对应会话中核对」，但第一次成功 `/sync` 之后也核对不到（没有入口），行永久留存。spec.md:145 的让步口径在这个分支上不可达，用户会面对一句永远兑现不了的说明。
- 需要作者回应：在 D3/D10 写明权威集合差分**同时覆盖 `pending_sends.conversation_id`**（镜像 `ChatStore.swift:190`），并定义这类记录的结论：判定为不可访问 → 删该会话 pending 行 + 写 `revocation`/`migration_report` 记录 + 计数递减；在 M1 `[worker]` ① 或 M2 `[worker]` ② 增一条「快照不含该会话时 pending 行被清理、计数归零、不产生占位会话行」的单测。

#### R2-W2（WARNING）— 登录成功 / 分区变化后由谁打开分区没有定义，「无仓储」把「尚未打开」和「打不开」混成同一状态

- 位置：design.md:385 `bootstrap() -> Bootstrap?` 只在 D6 的启动序列里被使用；:205 `AppModel.observe()` 只定义了「收到 `nil` 时 `purge` + `resetProjection()`」；:386「分区变化即换实例，旧实例关闭」没有说触发者；:390「`ChatStore` 只消费『有一个可用仓储或没有』」；:121 把「没有仓储」定义为降级：「仓储打不开（磁盘满、库损坏且重建也失败）时……退化为今天的纯网络模式」。
- 证据：`ChatStore` 今天的构造点是 `RootTabs` 的 `_chat = State(initialValue: ChatStore(client: client, user: user))`（`NanoIMApp.swift:115`），即**登录成功的那一刻**就会新建；D6 只覆盖「启动时已有 stored user」，`AppModel.authenticate()`（`NanoIMApp.swift:65-80`）之后没有任何 open 新分区的步骤，也没有区分「还没打开」与「打不开」。
- 后果：首次登录（全新安装）或 A 退出后登录 B 的同一次会话里，`ChatStore` 拿到的是「无仓储」，按 :121 的定义这**不是降级而是正常**，于是整段会话以纯网络模式运行、一个字节都不落库。用户在下一次冷启动（尤其断网）就没有本地内容，与 spec「断网冷启动」「打开就有上次内容」直接冲突；M1 ④ 只验首次安装、M2 ① 只验「B 看不到 A」，两条都不会暴露这个持久化缺口。
- 需要作者回应：在 D6 或「`ChatStorageController`」职责里补一句「登录成功或分区变化（含 nil → 新分区）→ `ChatStorageController.bootstrap(partition)` → 交出新仓储，`ChatStore` 重新绑定；『无仓储』只表示打开失败」，并在 M1（或 M2）加一条可执行步骤：「B 登录后在同一会话内收发，杀进程 + 断网重开仍能看到 B 的本地内容」。若 `Session.install`/`updateUser` 需要补 `publish(nil)` 才能让控制器察觉，也把顺序写明。

### Recommendations

- **R2-R1**：把三条「设计已承诺、milestone 未落」的证据补进轨道。D5 的守卫测试「写 `read_state` 不改变任何列表投影」（design.md:138）、D14 的守卫单测「窗口裁剪不改变 `backgroundContexts` 候选语义」（:308）、D3「≤1s 草稿损失窗口写进 M1 证据」（:119）在 M1 `[worker]` ①–⑧（:534）里都没有对应步骤；后两条直接关系「U3 语义不提前长进 U1」这条决定。
- **R2-R2**：M2 `[reviewer]` ⑦（:535）的构造手段要写成可执行命令。`apps/im-server/src/identity-routes.ts` 只有 register/login/refresh/logout/me/ws-ticket，**没有改密码路由**，全仓也无 `UPDATE … password_hash`；「改密码」不可执行。可行手段是直接在隔离服务 DB 上 `UPDATE auth_sessions SET revoked=1 WHERE session_id=…`（`identity.ts:466-468` 的同语义）或 bump `users.auth_epoch`（`:574-582`），写进 Runbook，否则 ⑦ 会以自述收尾。
- **R2-R3**：design.md:132「`ChatMessage` 有 16 个可空字段」与代码不符：`ChatModels.swift:84-107` 是 13 个可选字段（9 个非可选 + 13 个 Optional）。结论不受影响，改数字即可，避免 Gate 3 逐条核对时被当成未核实断言。
- **R2-R4**：`publish(nil)` 的加入点建议连顺序一起写。`Session.install(_:expected:)`（`Session.swift:154-159`）与 `updateUser`（`:101-103`）在 `clearSendAttempts()` 之后紧接着 `publish(user)`；若在这两处补 `publish(nil)`，`AppModel.observe()` 会先收到 nil、再收到新 user（账号停用时是 `accountEnabled == false` 的 user）。需要一句「nil 只触发 purge，停用走准入页而非登录页」，否则 M1 ④ / M2 ⑦ 的「不出现登录表单」「回到准入页」会被自己的信号顺序打破。

### 小结

Round 1 的两条 CRITICAL 与七条 WARNING 全部以结构性改动闭环，没有降级措辞、没有「以后处理」，GRDB pin 与所有被引用的服务端事实都经本轮独立复核成立，首文档两处上级口径也已如实落地并与 design/delta 一致。剩下的问题不是设计方向，而是两个**新增边界没写完**：迁移进来的 pending 一旦没有对应会话行就没有任何结论路径（R2-W1），以及登录后的分区打开被漏在生命周期之外、并被「无仓储=降级」的既有定义掩盖（R2-W2）。两者各需一段话与一条 milestone 步骤即可关闭，不触碰任何已定决定；修完后本 unit 的文档集即可在不再需要产品决策的前提下进入实施。

## Round 2 — Author Resolutions

> author 对 Round 2 的逐条回应（本章节只追加，不回写 Round 2 的结论与证据）。本轮无产品决策请求，两条 WARNING 按「补完边界」处理，不触碰任何已定决定与范围。文档改动只在 `design.md` 与 `spec.md`（首文档的呈现口径），commit `docs(feat-714): close Gate 2 round 2 findings`。

- **R2-W1（WARNING）→ 采纳 (a)+(b)+(c) 三件一起做：差分输入扩到会话身份全集、给孤儿 pending 一条显式结论路径、把说明文案改成可兑现的口径。**
  - (a) **差分输入**：D3（`design.md:113`）写明「差分的输入是**库内已存在的全部会话身份**，不是『会话行』：`conversations.id` ∪ `pending_sends.conversation_id` ∪ `revoked_conversations.conversation_id`」，并点名这是镜像今天 `ChatStore.reconcile` 把 `pending.keys` 并入撤销集的做法（`ChatStore.swift:190`）。顺带补上同一处第二个调用点：`can_write == false` / `dissolved_at != nil` 的会话丢弃其 pending（`design.md:114`，镜像 `ChatStore.swift:195-198`）——否则只读/已解散会话的未确认发送同样永远残留。
  - (b) **显式结论路径**：D10（`design.md:251-257`）把删除入口从「两个」改成「一条原语 `deletePending(conversationID:)` + 三个调用者」（`revoke` / 快照校正的「不可写」分支 / `purge`），并新增「孤儿 pending 的结论路径」：迁移进来但对应会话从未出现在权威集合里的记录，在**第一次成功 `/sync`** 时命中 `revoke` → 删行 + `revoked_conversations(reason='snapshot_absent')` + `migration_report(outcome='orphaned')`；`bootstrapSeed.pendingCount` 按行数计算，因此计数递减到 0，不会永久残留（`design.md:257`）。
  - (c) **文案可兑现**：说明改为「N 条未确认的发送；连接后会核对：仍在的会话可在其中查看，已无权访问的会被清除」，四处同步——D6 引导帧（`design.md:148`）、D12（`:290`）、状态呈现契约（`:457`）、M1 `[reviewer]` ⑤（`:556`）；首文档同句同步（`spec.md:142`），并新增一条可判定 AND：「该记录对应的会话在第一次成功 `/sync` 中已不可访问时，这条记录被清除、计数归零，不出现占位会话行，也不会无限期保留一条无法核对的说明」（`spec.md:144`）。
  - **为什么三件都要**：只做 (a) 会让「差集里的身份没有会话行」在 SQL 层仍无从下手（没有行可删）；只做 (b) 不给计数一个可证伪的口径，用户仍可能读到一句兑现不了的说明；只做 (c) 是措辞掩盖而不是收敛。(a) 的判据取自今天的实现（`:190` 已把 `pending.keys` 并入撤销集），所以升级前后语义一致，不是新发明的规则。
  - **证据位**：测试策略「单元（仓储 + 迁移）」行新增孤儿 pending 收敛（`design.md:533`）；M2 `[worker]` ② 增三条断言——只有 pending 行、无会话行的分区跑一次不含该会话的快照 → 删行 + `pendingCount` 归零 + tombstone 与 `migration_report` 双记录 + 不产生占位会话行；`can_write == false` / `dissolved_at != nil` 只丢 pending、不丢会话行（`design.md:557`）。D10 同时给两条守卫单测（`revoke` 一次提交后消息/草稿/pending 同时消失；孤儿 pending 首快照后清理）。
- **R2-W2（WARNING）→ 采纳：把「登录成功/换账号后谁打开分区」写进生命周期，并把「尚未打开」与「打不开」拆成两个状态。**
  - **状态三态**：D3（`design.md:124`）把「有/无仓储」改为 `ChatStorageState = .opening | .ready(ChatRepository) | .degraded(reason)`，明确 `.opening`（含登录成功后正在打开）**不是**降级、不显示「没有本地缓存」；只有 `.degraded` 显示提示并给重试入口。
  - **触发者与顺序**：D6 新增条目（`design.md:152`）说明本节只覆盖「启动时已有 stored user」，首次登录与换账号由 `ChatStorageController.activate(partition:)` 打开；控制器职责从四条扩到六条（`design.md:393-397`）：② `activate(partition:)`、③ `state` 与绑定、⑥ `retryOpen()`。调用点只有两个——`AppModel.authenticate()` 在 `session.login(...)` 返回且 Keychain 已保存之后立即调用（`NanoIMApp.swift:65-80`），并**在 `user =` 赋值之前完成状态登记**（置 `.opening`，打开完成后交 `.ready`），因为 `RootTabs` 构造会立刻 `ChatStore(...)`（`:115`）；第二个是 `AppModel.observe()` 发现 `user.id` 或 origin 与 `currentPartition` 不一致时。顺序固定「先拿到被接受的凭据 → 再算分区 → 再打开」，理由写在同处：分区身份来自已认证的 `user.id`，先建库会为未验证账号落盘。
  - **呈现契约**：新增两行——「分区尚未打开（启动引导中或登录成功瞬间）→ 正常聊天界面、不显示没有本地缓存」与「分区打不开 → 提示 + 重试入口」（`design.md:450-451`）；`.degraded` 的重试触发点 = 用户点重试 / 下一次进入前台 / 下一次 `run()` 之前，三者取先到，连续失败保持 `.degraded`，不静默降级成「永远纯网络」。
  - **证据位**：M1 `[worker]` ④ 的审计扩成「主线程 IO 与分区激活审计」（证明 `authenticate()` 后 `activate` 被调用、`.opening` 不被显示成没有本地缓存）、新增 ⑦「首次登录即落库」（全新安装登录 → 收发 → 杀进程 → 飞行模式冷启动仍能看到该账号内容）（`design.md:556`）；M2 `[reviewer]` ① 增「B 在这次会话里收发的消息已落库——杀进程 + 断网重开仍能看到 B 自己的内容」（`design.md:557`）。
  - **顺带修正编号卫生**：M1 `[worker]` 轨道因本轮新增两条而出现重复的 ⑥，已重排为连续的 ①–⑩（新增的首次登录落库为 ⑦，原 ⑦/⑧ 顺移为 ⑧/⑨，R2-R1 的三条证据为 ⑩）；`design.md:546` 的「真实 401 到达时机」引用不受影响。
- **R2-R1（Recommendation）→ 采纳。** 三条「设计已承诺、milestone 未落」的证据补进 M1 `[worker]` ⑩（`design.md:556`）：`read_state` 守卫单测（写 `read_state` 不改变任何列表投影）、`backgroundContexts` 守卫单测（300/派生窗口裁剪后候选仍是 3 条、按 `editedAt` 倒序、排除 superseded）、草稿损失窗口测量（输入中连杀 3 次，落 `evidence/draft-loss.md`，证明 ≤1s 且不出现旧文本覆盖新文本）；测试策略行同步点名 `read_state` 与 `backgroundContexts` 两条守卫（`:533`）。
- **R2-R2（Recommendation）→ 采纳，写成可执行命令。** Runbook 新增「凭据失效的构造（M2 `[reviewer]` ⑦）」（`design.md:515-524`）：DB 在 `<worktree>/data/im_service.sqlite3`（`scripts/e2e-up.sh` 的 `IM_DB_PATH`），手段 A `UPDATE auth_sessions SET revoked=1 WHERE user_id=...`（同 `identity.ts:582` 语义）、手段 B `UPDATE users SET auth_epoch=auth_epoch+1 WHERE id=...`（同 `:574` 语义），并写明构造后无需恢复（`e2e-up.sh:255` 会重建库）。M2 `[reviewer]` ⑦ 的正文改成同一命令，预期写成「401 → `termination = .credentials` → `purge()` → 登录页，且不出现准入页」（`design.md:557`）。
- **R2-R3（Recommendation）→ 采纳。** D5（`design.md:135`）改为「`ChatMessage` 有 13 个可空字段（9 个非可选 + 13 个 Optional，共 22 个，`ChatModels.swift:84-107`）」；结论（promoted 列 + 原始 DTO JSON 的混合形状）不变。
- **R2-R4（Recommendation）→ 采纳，且裁定为「不加 `publish(nil)`」。** D7 的 purge 归属（`design.md:209`）与控制器第 4 条（`:395`）统一为：`.signedOut`/`.credentials` 在 `stored` 被清空的路径上**先写 termination 再 `publish(nil)`**（签出 `Session.swift:82-85`、refresh 仍 401 `:147-148`）；`.deactivated` 由 `accountEnabled == false` 的**非 nil** user 表达（`updateUser` 判停用后仍 `publish(user)`，`:101-102`；`install` 同理 `:156-159`），**不额外发 nil**。理由：`AppModel.observe()` 若在停用路径上也收到 nil，会先回登录页、再收到携带 `accountEnabled == false` 的 user 回聊天页——停用态会闪一帧登录屏，而 M1 ④ / M2 ⑦ 的「不出现登录表单」「回准入页」正好被自己的信号顺序打破。因此只加顺序约束、不新增信号。
- **本轮改动面**：`design.md`（Changelog、D3、D5、D6、D7、D10、D12、仓储接口/控制器、呈现契约、Runbook、测试策略、M1/M2 轨道）、`spec.md`（`:142` 文案 + `:144` 新增 AND，无需求重新编号、未删任何既有断言）。Round 1/2 的结论、证据与被引用行号未回写。

## Round 3

- reviewer: 独立 `change-design-reviewer`（同一 reviewer；narrow：只核 Round 2 的两个 WARNING、两条已定口径的回归，以及本轮修订自身引入的缺陷）
- reviewed_head: `unit/feat-714` @ `611074df6`，工作树 clean；范围 `2b3437c18..611074df6`（design.md +60/−20、spec.md +3/−1、design-review.md +22 追加）
- review_mode: closure（narrow）
- mode_reason: 只审 R2-W1 / R2-W2 的闭合与修订引入的问题，未重审无关章节
- started_at: 2026-11-05T16:55:00+08:00
- completed_at: 2026-11-05T17:07:00+08:00
- duration: ≈12 min

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**，另 4 条非阻断建议（均在本轮改动面内）。

### 逐项核对

| 项 | 状态 | 依据 |
|---|---|---|
| R2-W1 孤儿 pending 收敛 | **CLOSED** | mechanism 而不是措辞：design.md:113「差分的输入是**库内已存在的全部会话身份**……`conversations.id` ∪ `pending_sends.conversation_id` ∪ `revoked_conversations.conversation_id`」，:114 另补第二个调用点「`can_write == false` 或 `dissolved_at != nil` 的会话 → 丢弃该会话的 pending 记录」；:251「收敛只有一条原语 `deletePending(conversationID:)`，三个调用者」；:257「在**第一次成功 `/sync`** 时命中第 1 条——`revoke` 删行并写 `revoked_conversations(reason='snapshot_absent')`，同时在 `migration_report` 记一行 `outcome='orphaned'`；`bootstrapSeed.pendingCount` 按行数计算，因此计数随删除递减到 0」。**收敛穷举**：迁移后 pending 无会话行 → 差集命中 → 删；会话在集合内但只读/已解散 → 第二分支删；无成功 `/sync` → 属已声明的离线边界（D10:265-272），不是隐藏分支；tombstone 不是删除对象、`purge()` 仍是分区级兜底。因此「首次登录 pending 的会话永不出现」会在第一次成功 `/sync` 清零，没有我上轮担心的第三个不可达分支。可执行证据：M2 `[worker]` ②（:557）与测试策略 :533。首文档现在可证伪：spec.md:142「连接后会核对：仍在的会话可在其中查看，已无权访问的会被清除」+ :144「该记录对应的会话在第一次成功 `/sync` 中已不可访问时，这条记录被清除、计数归零，不出现占位会话行」 |
| R2-W2 登录后分区打开 | **CLOSED** | design.md:124 `ChatStorageState = .opening \| .ready(ChatRepository) \| .degraded(reason)`，明写 `.opening`（含登录成功后正在打开）**不是**降级；:152 D6 增「首次登录与换账号由 `ChatStorageController.activate(partition:)` 在凭据被接受、Keychain 已保存之后打开分区……打开前是 `.opening`，不是降级」；:393「调用点只有两个——`AppModel.authenticate()` 在 `session.login(...)` 返回且 Keychain 已保存之后立即调用……并**在 `user =` 赋值之前完成状态登记**（置 `.opening`；打开完成后再交 `.ready`），因为 `RootTabs` 构造时会立刻 `ChatStore(...)`（`:115`），晚了就会先拿到一次「无仓储」」；:394 `.ready` 时交仓储 + 重读 `bootstrapSeed` 重投影。**窗口判断**：打开是异步 I/O，`ChatStore` 仍会在 `user =` 之后、open 完成之前被构造——但那一刻的状态是 `.opening`（正常界面、纯网络、不显示「没有本地缓存」），并在 `.ready` 时被重新绑定与重投影，所以「整段会话纯网络、一个字节不落库」的缺陷被消除，剩余窗口有界且被显式建模。**账号切换变体有场景**：M2 `[reviewer]` ①（:557）「**且 B 在这次会话里收发的消息已落库**——杀进程 + 断网重开仍能看到 B 自己的内容（分区 A 不得漏进 B……）」；:394 同时写了「分区变化时关闭旧实例再开新实例，旧实例关闭前先 `purge` 旧分区」。M1 `[worker]` ④/⑦（:556）给了对应审计与首次登录即落库的步骤 |
| 两条已定口径回归 | **未受影响** | spec.md:106-108「本机**已得知**这次撤销之后……离线期间不承诺不展示」与 :110 口径修正与 `a6ee1f364` 逐字一致（本轮 diff 未触及该段）；spec.md:139-146 的「计数 + 说明」让步仍在，只有文案与新增 AND 变化，让步语义（首次成功 `/sync` 前只给计数、不造占位会话行）不变；delta 本轮零改动 |
| 编号与引用卫生 | **通过** | M1 `[worker]` 现为 ①–⑩ 连续无重复（脚本提取：`①②③④⑤⑥⑦⑧⑨⑩`；M1 `[reviewer]` ①–⑤、M2 `[reviewer]` ①–⑦ / `[worker]` ①–⑤ 未变）。design.md 除 Milestones 两行外没有按序号引用 `[worker]` 项（:227/:527/:543/:544 均为不带序号的引用）；:507 引用 M1 `[reviewer]` ⑤、:546 引用 M2 `[reviewer]` ⑦ / `[worker]` ④，均未受重排影响；spec.md 只引用 `[reviewer]` ⑤。`docs/` 内未发现指向旧 ⑦/⑧ 的引用（`design-review.md` 的 Round 2 正文是历史记录，按约定不回写） |
| R2-R1 三条证据落位 | **已落** | M1 `[worker]` ⑩（:556）「`read_state` 守卫单测……`backgroundContexts` 守卫单测（300/派生窗口裁剪后候选仍是 3 条、按 `editedAt` 倒序、排除 superseded）；草稿损失窗口测量……落 `evidence/draft-loss.md`」；测试策略 :533 同步加了「`read_state` 与 `backgroundContexts` 守卫」 |
| R2-R2 凭据失效构造 | **已落** | Runbook :515-524「凭据失效的构造（M2 `[reviewer]` ⑦）」给出 `UPDATE auth_sessions SET revoked=1 WHERE user_id=…` 与 `UPDATE users SET auth_epoch=auth_epoch+1`，M2 ⑦（:557）指向该节；依赖事实复核成立：`identity-routes.ts` 无改密码路由、`scripts/e2e-up.sh:255` 确实 `rm -f "$WT_ROOT/data/im_service.sqlite3"`（`IM_DB_PATH` 在 :270/:304） |
| R2-R3 字段数 | **已落** | design.md:135「`ChatMessage` 有 13 个可空字段（9 个非可选 + 13 个 Optional，共 22 个，`ChatModels.swift:84-107`）」与代码一致 |
| R2-R4 `publish(nil)` 顺序 | **已落** | design.md:209「`.signedOut`/`.credentials` 在 `stored` 被清空的路径上**先写 termination 再 `publish(nil)`**……`.deactivated` 由 `accountEnabled == false` 的非 nil 信号表达……**不额外发 nil**」「`nil` → 按 termination `purge` + 回登录页；`user.accountEnabled == false` → `purge(.deactivated)` + 准入页」；:395 复述「**不新增 `publish(nil)`**」。与 `Session.swift:101-103`（判停用后仍 `publish(user)`）与 `:156-159`（`install` 同理）一致 |
| `docs_check` | **通过** | `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 219 maintained Markdown sources, 68 required routes` |

### Recommendations（非阻断，均在本轮改动面内）

- **R3-R1 反复 revoke 与记账重复**：差分输入含 `revoked_conversations.conversation_id`，而 tombstone 只在会话重新出现在快照时清除，所以每一次成功 `/sync` 都会对每个仍缺席的 tombstone 再调一次 `revoke`。若按 :257 字面「`revoke`……同时在 `migration_report` 记一行 `outcome='orphaned'`」，每轮快照都会追加一行，并把 `reason` 重写成 `snapshot_absent`、覆盖 `detail_forbidden` / `membership_denied` 的来源。建议补一句「仅当本次调用实际删除了 pending 行时才记 `migration_report`；已存在 tombstone 时 `revoke` 为幂等空操作，不重写 `reason`/`revoked_at`」，或把 tombstone id 从差分输入里去掉。无用户可见后果，不阻断。
- **R3-R2 Runbook SQL 的占位与 cwd**：:517 用 `username='alice'`，但隔离栈不预置账号（`scripts/e2e-up.sh` 只建库，账号由 reviewer 自己注册），照抄会得到空 `uid`，随后 `WHERE user_id=''` 静默不吊销，⑦ 会「看起来执行了但没生效」。建议改成 `'<A 的 username>'` 并加 `[ -n "$uid" ] || …` 保护，同时注明 SQL 在 worktree 根目录执行。
- **R3-R3 `.opening → .ready` 的重投影语义**：:394 只说「重读 `bootstrapSeed` 重投影」。首次登录时若打开分区慢于第一次 `/sync`，空 seed 会替换掉已渲染的网络结果。概率很低（本机 IO vs 至少一个网络往返），建议补半句「重投影是幂等合并，不用空 seed 覆盖已有投影」。
- **R3-R4 spec.md:144 的 AND 落在 Scenario 的 WHEN 之外**：该 Scenario 的 WHEN 是「第一次成功 `/sync` 尚未完成」，新增 AND 描述的是首次成功 `/sync` 之后。建议拆成独立 Scenario（如「升级后对应会话已不可访问」）或并入「升级后未确认消息仍在」，让 Gate 3 能按 WHEN 直接构造该证据。

### 结论

两条已定口径与范围没有被本轮改动触碰，Round 2 的两个 WARNING 都以可验证机制关闭：孤儿 pending 有确定的删除入口与归零计数，登录后的分区激活有触发者、顺序与三态语义，并在 M1/M2 轨道各有一条可执行步骤。编号连续、无悬挂引用，`docs_check` 通过。剩余四条都是加法级澄清，不涉及任何产品决策；**文档集现在可以在不再需要产品决策的前提下进入实施（M1）**。

## Round 4

- reviewer: 新任独立 `change-design-reviewer`，执行子 Agent `db5da8a2-a5d4-4902-9c59-bf34f66ce34e`；未参与受审设计或实现，不是 Round 1–3 reviewer，亦非作者换上下文自审。
- review_target: 冻结提交 `32c0421b825715fe90d800cf6c495ae317f19ec4`；增量 `1ee83e940..32c0421b8` 的 `design.md` D12 幂等/损坏修订、D12 补充与 `specs/im/ios-client.md` 新增迁移 Requirement，以及这些修改直接波及的 D3/D4/D10、回退与 M1/M2 边界。
- checkout: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-714`，branch `codex/feat-714`，HEAD 为上述冻结提交；审查开始及报告写入前，unit 文档相对冻结提交均无未提交修改。
- source_boundary: 源码已有并行的未提交独立缺陷修复；本轮只读必要调用链，用于核实落点与现有不变量，不把 dirty source 或测试文件的存在当作本次设计已实施、编译或通过测试的证据。
- review_mode: delta（narrow Gate 2）
- mode_reason: 外置 policy、跨两持久层清理及 handoff 是实质设计增量，不能作为 Round 3 closure 或 retained 直接放行；其影响可限定在迁移/清理/恢复、真实首绘 owner 及新增 delta。未重开首文档、未扩大为全 unit 重审。
- retained_from: Round 3。此前 GRDB 选型、schema/投影基本形状、离线撤销的已知边界、首启只给计数、不自动重发以及 M1/M2 的原有真实原生/真机证据要求仍保留；这是沿用历史审查范围，不声称本轮重跑此前 probe、docs_check 或产品验收。
- configuration: 使用当前可用的 DSH 独立子 Agent。工具不提供选择原流程指定模型/effort 的参数，当前会话也未暴露可核实的具体模型版本/effort 值，故不宣称复现原配置；用户已在本轮明确批准此配置差异。独立性、内容范围与门禁标准不降低。
- started_at: 2026-11-09T00:05:43+08:00（首个记录时间戳）
- completed_at: 2026-11-09T00:09:29+08:00（证据核对完成；随后追加本报告）
- duration: ≈4 min（证据核对，不含报告追加）

### Verdict

**Issues Found（Changes requested）— 0 CRITICAL / 3 WARNING。**

父级选定的 A（旧 `SendAttempts` JSON 原样只读保留 + 持久导入栅栏）方向可实现，不需要另立 unit、改变原验收或请求新的产品取舍。但本次新增方案尚有两条清理恢复边未闭合，并有一处损坏恢复指令冲突。Round 3 的 Approved 不覆盖这些新决定；本轮不批准该设计增量进入已批准状态。

### Coverage 与证据

| 本轮问题 | 核对与判断 |
|---|---|
| 新机制的职责与复用 | `LegacyAttemptImportPolicy` 只承载旧源资格/清理代际，放在 `Chat/<digest>/` 外是必要的存活边界；复用既有 partition digest、受保护原子 JSON 与 GRDB 事务，不另建聊天事实源。Session 发生命周期信号、controller 排序 opener/purge、repository 执行业务 SQL/应用回执的分工可成立；没有 DSH、服务端或 Web 依赖增量。 |
| 真实组装入口 | 只读 `NanoIMApp.swift:63-140,153-180,202-217`：`AppModel`/`bootstrapLocal`/`installChat` 与接收 `chat` 引用的 `RootTabs` 确是实际入口，不是仅测试手工装配。稳定 owner、metadata publish 复用、seed 为值、View 构造零 IO 的设计要求落点正确。源码为 dirty 状态，未据此宣称行为已经兑现。 |
| 旧源与 fallback | `Session.swift:64-79,82-107,169-189` 仍有 legacy 保存/删除及 `clearSendAttempts` 删除挂点；`ChatStore.swift` 的 persist/remove/discard fallback 仍调用这些接口；`SendAttemptStore.swift:25-30,47-81` 按精确旧目录读写。新设计要求必须贯穿这些挂点，不能只停一处 purge 删除。D12:321/323 已要求只读旧源、新请求去独立 handoff；不把这些待改代码另记为设计已实施的缺陷。 |
| policy/DB 事务与失败 | policy 先持久化、DB 只存应用回执，open 在导入/首绘前补未应用清理，可防止单靠 DB marker 丢失复活旧 JSON。不可读/未知版本 fail-closed、写失败不声称完成、drain detached opener、旧世代不能发布均有明确要求。清理动作粒度及 handoff 文件资格仍有 R4-W1/W2。D4 的 epoch/seq 拒绝仍须约束任何 policy 副作用，不能只在 policy 写成后的 DB 事务里才拒绝旧结果；本轮没有把旧有效性约束视为已取消。 |
| delta/current spec | canonical target 为 `docs/specs/im/ios-client.md`，新增迁移 Requirement 补足首文档已有需求；原 MODIFIED 两个 Scenario 未在本增量删除。迁移冻结身份、计数时序、零 POST 与已清理旧源不复活对齐首文档及 current 不确定发送/退出隔离。只读仍可见边与 R4-W1 冲突。 |
| 回退与范围 | D12:327 诚实区分「保留旧源字节」与「旧构建理解新 policy」；不承诺旧构建继承清理，升级后 DB/handoff 新请求旧构建不可见，原有有界回退损失未扩大为零损失承诺。不涉及服务器删除、自动重发、现有安装清理或部署。设备内自动适配不需要 `deployment-prompt.md`（本轮也未发现该文件），design:520-522 的判断保留。 |
| 验证与能力 | 加载 `codebase-design`、`frontend-experience-review`（设计模式）与 `performance-review`（设计模式）补核职责、首绘与证据方法。新增恢复/清理不要求为流程制造 HTML 原型；实际画面、真机文件保护/备份属性、飞行模式与原有 ≥20 次 p50/p95 仍是实施证据，不以本轮只读审查替代。D12:329-334 的独立 code review/原生旅程/体验/性能安排覆盖重要目标，新增 worker 验证仍归 M1；需补 findings 所列反例，而非另加 Gate。无新的模型输入/选择链改动，D14 原边界保留。 |

关键源码反证（均仅静态阅读）：`ChatRepository.swift:332-359` 将不可见差集撤销与可见但不可写的 pending 删除分开，`:394-400` 明确只读不写 tombstone，`:522-534` 是先 DB 清空再目录删除；`ChatStorage.swift:53-58,97-99` 只给 handoff 同目录位置和目录删除，没有跨文件/DB 原子提交能力；`ChatStorageController.swift:89-168` 是实际 opener/clear 编排落点。测试 `ChatRepositoryTests.swift:177-190` 已固定「只读只删 pending、保留会话且无 tombstone」，本轮未执行它。

### 历史问题与交接

- Round 1/2 的 CRITICAL/WARNING 按 Round 3 的已关闭记录保留，不回写旧结论。新增 policy 是对旧「旧源保留 + 仅 DB marker」方案必要但尚待审定的扩展，不能用旧 R1-C2 CLOSED 证明本增量已通过。
- Round 3 的 R3-R1 幂等口径在 D10:257 仍在；本轮新增「重复相同 tombstone/不可写快照不旋转代际」方向一致。R3-R2 Runbook、R3-R3 合并投影及 R3-R4 首文档 Scenario 的历史修订不是本轮新问题。
- 父级在收到 R4-W1 的提前通知后确认问题成立并表示将补 cleanup kind；冻结设计尚未修改。此意向不是闭环证据，本轮仍为 open，统一修订后再复审。

### Issues

#### R4-W1（WARNING）— 一个无类型会话代际同时表示不可访问与不可写，崩溃补清理把只读历史错删成撤权

- **位置**：`design.md:310`（不可访问或不可写都写 `revocations: [conversationID: UUID]`）、`:315-316`（未应用会话代际统一删 pending/内容并写 tombstone）；相冲突的既有决定是 `:114,254` 与 M2 `[worker]` ②（`:592`，不可写只丢 pending、不丢会话）。current `docs/specs/im/ios-client.md:74-80` 也要求只读聊天可查看。
- **触发/证据**：仍有读取权限的会话变为 `can_write == false`，库内有历史与 pending；客户端按新规则先持久化该会话 UUID，随后在 DB 清理事务前崩溃。下次 open 发现回执不匹配，按 :316 一律删除内容并写 tombstone。policy 只存 UUID，没有资料能辨别本次应执行「丢 pending」还是「撤销访问」。这不是权限可见性可由离线重新查询解决的问题。
- **根因与后果**：旧源永久排除资格与 DB cleanup kind 被合并成同一个无类型值；恢复过程因此放大原授权事件的删除范围。用户离线重开会丢掉仍有权阅读的会话/历史，且该 tombstone 会拒绝本应允许的消息投影。
- **闭合要求**：为持久清理意图保留可区分的动作（例如 `discardPending` 与 `revokeAccess`，或等价且可证明的结构），恢复按原范围补做；只丢 pending 时不删可读内容、不写撤权 tombstone，但旧源排除仍永久有效。加入「不可写 policy 提交后、DB 应用前崩溃 → 离线重开」断言：pending/旧源资格被清理，原会话与历史保留，真正访问撤销仍完整删除。无需产品改口径。

#### R4-W2（WARNING）— handoff 的文件清理与 DB 应用回执缺少提交顺序，回执已匹配时仍可重新导入退出前的残留文件

- **位置**：`design.md:315-317`（DB 清理事务同时写应用回执，允许 DB 已清理但文件尚在的崩溃点）、`:323`（新 handoff 放 `Chat/<digest>/*.json`、open/reloadPending 导入有效文件）；`:309-311` 的永久栅栏只定义旧 JSON 资格，没有 handoff 代际/旧文件资格规则。
- **反例**：降级期间新请求 H 已持久到 handoff，尚未交给 DB。purge 先写 policy，再清空 DB 并提交匹配回执；在删除目录/文件前崩溃，或文件删除失败。下次 open 按 :316 看到回执已匹配而不补清理，随后按 :323 把仍有冻结内容的 H 当有效 handoff 导入。分区 purge 后 DB 中没有撤权 tombstone/交接 marker 能排除 H，而 policy 禁的只是 legacy。H 在同账号重新登录后可能作为旧 pending 复活；零自动 POST 不能消除这项内容恢复错误。
- **根因**：同目录只是删除范围，不是 SQLite 与 JSON 的原子性；DB 应用回执当前证明的只是业务行已清空，没有证明待接管文件已失去资格。不能笼统用「清理同时覆盖 handoff」跳过这个已声明的崩溃窗口。
- **闭合要求**：定义可证明的 handoff 清理/资格与回执顺序：例如持久意图之后先完成目标 handoff 清理再确认应用完成，任何残留/删除失败不放行 ready/import；或让 handoff 带可校验的创建代际并由 policy 拒绝旧代际。还须覆盖新文件在扫描后落盘的 writer/drain 边界，不能为了禁旧文件误禁重新授权后的新请求。加入隔离测试「退出前 handoff 尚未交接 → policy/DB 已提交而文件仍在 → 重开/重新登录」及相应失败重试，断言旧 H 不进入投影、新请求仍可用、零自动发送。

#### R4-W3（WARNING）— D12 限定损坏错误后，风险 R2 仍命令对任意 open 失败侧移重建

- **位置**：新 `design.md:298`（只接受 `CORRUPT` / `NOTADB` 证明损坏）、`:332`（普通 schema/IO 错误不触发 quarantine），与仍保留的风险表 R2 `:510`（「库打开失败/损坏（磁盘满、异常中断）」→「`open` 失败时把 `chat.sqlite` 侧移……重建空库」）。
- **根因/后果**：同一恢复操作仍有两条相反触发指令。按 R2 实施/回退会把文件保护、磁盘满或 schema 问题误当损坏，侧移可恢复的库并在重建成功后丢失仅存在于库中的新 pending；旧 JSON 留存不能恢复这些升级后请求。当前 dirty `ChatRepository.open:94-104` 已体现窄分类，但不能用尚未审定/验证的实现消解冻结设计文本冲突。
- **闭合要求**：同步 R2 的触发条件、保留文件与降级结果，明确非损坏错误不侧移/不重建，真正损坏才按 policy/handoff 资格恢复；保留 :332 的分类测试要求即可，不新增部署或运行试验。

### Recommendations

无额外非阻断建议。上述三个问题修订后可按改动范围做 narrow closure，不要求重开既有首文档或全量 Gate 2。

### 未验证事实与执行边界

- 本轮只执行只读 Git/时间查询和文件阅读；没有运行构建、XCTest、模拟器/GUI、服务、HTTP 探针或脚本检查，也没有读取/操作用户现有安装数据。
- 所有崩溃序列是对冻结方案的静态反例，不是宣称已在运行中复现。现有 dirty tests 只用于辨明既有语义，未运行，不能据存在而称通过。
- 原生首帧、杀进程、离线/同 origin 不可达恢复、性能分位数、文件保护/备份属性与真实清理效果均未由本轮验证；原有实施验收要求不降低。
- 本 reviewer 的实际文件改动仅为向本 `design-review.md` 追加 Round 4，保留 Round 1–3 的报告与结论，不改源码、design、delta 或其他文档。

## Round 4 — Author Resolutions

以下为作者统一修订后的回应，不回写 reviewer 的 Issues Found 结论；三项是否闭合交回同一独立 reviewer 判定。未实施新增 policy/handoff 产品机制，也未把此前 dirty source 视为验证。

- **R4-W1 → 采纳**：D12 的会话 policy 改成带 `generation` 与 `kind` 的 `conversationCleanups`。`discardPending` 补清理只删 pending、保留可读会话/历史/草稿且不写 tombstone；`revokeAccess` 才删除全部并写 tombstone。两者永久排除旧 JSON。补充动作升级/重新授权后再次清理的代际规则、以及只读与真正撤权两个 policy 提交后崩溃测试。
- **R4-W2 → 采纳代际资格方案**：handoff 采用版本化 envelope，保留创建时分区/会话代际；每次导入无论 DB 回执是否匹配都核对两个值。清理先旋转 policy，旧遗留文件即使未删也不能导入；旧请求不得重贴新代际。repository/controller/fallback 共用分区串行协调，捕获/写文件与清理排序，生命周期 drain writer/opener。新增 policy/DB 已提交但文件仍在及删除失败重试、交错 writer 和重新登录后新请求可交接的反例测试。DB 回执只证明 DB 应用，不再被描述为文件删除证明。
- **R4-W3 → 采纳**：风险 R2 与 D12 同步为仅 `CORRUPT` / `NOTADB` 可 quarantine/rebuild，其他错误保留库并降级；写明仅库内升级后 pending 不能从 `/sync` 重建。相关风险 R3 同步去掉任意写错误可自动 purge 的绕过入口。D12 标题同步区分「库内导入幂等」与「库外主动清理资格」。原分类测试要求保留。
- 本次修订只改变设计文档及本回应；新增 delta 的可观察语义未变，首文档、视觉取舍、原验收与非目标不变。不请求产品重新决策，不新增部署/现有安装操作。

## Round 5

- reviewer: Round 4 同一独立 `change-design-reviewer`，执行子 Agent `db5da8a2-a5d4-4902-9c59-bf34f66ce34e`；未参与受审设计/实现，只提出审查发现，不代作者选择或修改方案。
- review_target: 冻结提交 `022e3c67465aeb6ae64e147d2c6e641ea7ce9ede`；closure 范围 `32c0421b825715fe90d800cf6c495ae317f19ec4..022e3c67465aeb6ae64e147d2c6e641ea7ce9ede` 中的 R4-W1/W2/W3 修订、Author Resolutions 及这些修订自身引入的边界。
- checkout: `/Users/czj/Repos/nano-multiagent/.worktrees/feat-714`，branch `codex/feat-714`，HEAD 为冻结提交；报告追加前 unit 文档相对该提交无未提交变化。源文件仍有并行未提交修复，不属于本次设计 closure 的实施证据。
- review_mode: closure（narrow）
- mode_reason: 三个 WARNING 的结构性收口及局部消歧；未改首文档、delta、核心产品范围、UI 决定或 milestone，闭环证据足以限定范围，不需要重新 full review。
- retained_from: Round 4 的未受影响 coverage/实际组装入口核对、范围及证据边界，并经 Round 4 沿用 Round 3 的既有结论；不是凭此前 Approved 自动放行本轮。
- configuration: 仍为用户已明确批准的当前可用 DSH 独立子 Agent；工具不能指定原流程要求的模型/effort，当前会话未暴露可核实的具体配置值，不宣称原配置已复现，内容与独立性标准不降低。
- started_at: 2026-11-09T00:16:40+08:00
- completed_at: 2026-11-09T00:17:28+08:00（证据核对完成；随后追加本报告）
- duration: ≈1 min（narrow closure 证据核对，不含报告追加）

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R4-W1、R4-W2、R4-W3 **全部 CLOSED**。冻结文本已给出可兑现的清理动作、文件资格和失败边界，未以降级需求或将验收推迟到上线来闭环。此批准针对设计增量，不是新增 policy/handoff 已实施、测试通过或 M1 产品验收通过的声明。

### 逐项闭环

| 原问题 | Author Resolution | 本轮独立证据与结论 |
|---|---|---|
| **R4-W1** 不可写被扩大成撤权 | `conversationCleanups` 携带 `generation + kind`；按原动作恢复，并补两个崩溃场景 | **CLOSED**。`design.md:310` 将 `discardPending` / `revokeAccess` 分开，`:316` 明确前者只删 pending，保留会话、历史、草稿且不写 tombstone；后者才整会话删除并写 tombstone。`:334` 给出 policy 已写/DB 未清理时两种动作的独立断言。因此离线 open 不再需要猜测权限来决定删除范围，与 D10:254、M2 不可写只丢 pending 以及 current iOS 只读可查看契约一致。`:310,319` 还明确动作升级、重新授权后再次清理必须产生新代际，不会因旧排除项存在而跳过新的撤权。 |
| **R4-W2** handoff 残留文件因回执匹配复活 | 版本化 envelope 固定创建时双代际；每次交接校验；同分区共享串行协调与 drain | **CLOSED**。`:323` 要求持久捕获 `purgeGeneration` 与会话 cleanup generation（包括 nil），旧请求不能重贴新代际；`:325` 要求 open/retry/每次 reload 都检查双代际，明确 DB 回执匹配不能跳过。故原反例「H 的创建代际 G0 → purge 持久旋转 G1 → DB 清理回执成功但 H 文件未删 → reopen」中 H 因 G0≠G1 被拒，删除失败只形成无资格残留，不会回投影。重新登录/授权后的真正新请求捕获 G1，仍允许交接，不将旧源永久排除错误扩到新请求。`:317` 不再把 DB 回执当文件删除证明；`:323,325` 的共享分区协调、owner 冻结/drain、扫描后新 writer 由 reload 接管，闭合捕获/清理交错与扫描窗口。`:334-335` 加入残留文件、删除失败重试、writer 交错与新请求继续可用的测试要求。 |
| **R4-W3** 损坏恢复触发指令相反 | 同步 R2，相关 R3 去掉任意失败自动 purge | **CLOSED**。`:512` 与 D12:298 均限定仅 `CORRUPT` / `NOTADB` 可 quarantine/rebuild，权限/保护/磁盘满/IO/schema 错误保留库、报错降级并重试；`:513` 取消任意写失败自动 purge 的旁路，且跨 policy/handoff 按分区串行。R2 不再宣称 `/sync` 能恢复仅库内未知冻结请求，也不要求无法打开的库必须成功记账。`:334` 仍保留非损坏错误不 quarantine 的测试约束。 |

### 修订自身与未受影响面

- **上下文资格先于持久副作用**：`:315` 新增 D4 epoch/seq 校验在 policy 更新之前，且校验→policy→DB 应用之间不允许同分区操作穿插。它保留原有迟到结果拒绝语义，不会出现 DB 最后拒绝了旧响应、policy 却已将其错误清理决定持久化的旁路。
- **两层状态的职责**：D12 标题 `:287` 区分库内幂等与库外源资格；`:315-317` 的 policy 是清理意图/源资格，cache_meta 是 DB 应用回执，handoff envelope 是创建身份与代际。三者不是互相覆盖的聊天事实源。实现可在原有 controller/repository 生命周期中共享小型分区协调器，文件 IO 保持非 MainActor；不需要新增服务或第二套数据库。
- **失败/崩溃组合**：policy 已持久但 DB 失败时，仍按 kind 补清理；DB 已应用但文件未删时，文件每次按双代际验证；有效 handoff 提交后删除失败时，以交接 marker 幂等；policy 无法解码/写入仍 fail-closed，不借损坏重建绕开。上述是设计上的恢复规则成立，不声称运行中已复现。
- **契约与范围 retained**：Git diff 只涉及 `design.md` 与同文件追加报告/Author Resolutions，首文档与 `specs/im/ios-client.md` 无变化。本轮重读 delta:70-85，冻结身份、首启计数、零自动 POST、已清理旧源不因重建复活仍被满足；`:329` 的旧构建回退限制没有被新规则掩盖。无新产品裁决、服务端删除、现有安装清理或部署；一次性迁移仍由设备内产品路径完成，不新增 deployment prompt。
- **真实入口与实施差距 retained**：Round 4 已核对 AppModel→controller→repository→RootTabs 的实际组装链，本轮没有把 dirty source 改成方案完成的证据。再次只读 `Session.swift:59-79`，legacy 写/删与 `clearSendAttempts` 仍存在，说明后续实施必须贯通改造这些实际挂点，不能把设计批准误写为运行清理已完成。
- **验证充分性**：新增反例验证明确仍归 M1，与原独立 code/原生旅程/体验/性能安排衔接；原真机、真实原生首绘、≥20 次 p50/p95、保护/备份属性等缺口与判据全部保留。修订没有新增布局或模型可见链路，沿用 Round 4 的专项设计判断，不因 closure 人为加原型/全量审查。

### Issues / Recommendations

无新增 CRITICAL、WARNING 或非阻断建议。没有仍为 partial/open 的 R4 问题；后续变更如影响上述冻结规则，应按真实增量判断复审范围。

### 证据与执行限制

- 本轮独立执行的是只读 Git diff/status、时间查询和文本阅读；未运行构建、XCTest、GUI/模拟器、服务、HTTP 或现有安装迁移，也未修改源码、design、delta 或其他文档。
- 作者提供的 `docs_check` 282/69 与 `git diff --check` 通过属作者证据，本 reviewer 没有重跑；并行本地 XCTest 无论结果如何，都不证明尚未实施的 policy/handoff 已兑现。
- 设计成立与实现正确分别验收；首绘/清理效果、崩溃恢复、并发交错和真机属性仍待后续实施证据，不降低原验收。
- 本轮实际改动仅为本 `design-review.md` 追加 Round 5；Round 4 的 Issues Found、全部历史 Round 与作者回应原样保留。
