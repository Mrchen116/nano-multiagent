# Design 评审：refactor-481-gateway-config-ownership

**结论**：Issues Found

旧报告的六项结论中，static/managed Feishu authority、runtime URL delta、
deep-freeze/path 单权威三项已经闭合；parent/foreground 唯一 writer、安全写盘矩阵、
durable→catalog→reporter/cron publication 三项仍未完全闭合。另发现 runtime credential
view 把 IM 服务端 token rotation 的 commit point 错当成本地磁盘 commit point。

## 核实台账

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状：`local_store.py` 同时拥有 schema、codec、durable write、runtime owner、workspace、model 与 static Feishu 行为 | 逐段枚举真实定义 | ✓ 成立。schema 在 `src/personal_assistant/config/local_store.py:27-323`，owner/runtime load 在 `:326-409`，static Feishu 在 `:412-546,644-708`，codec/writer 在 `:567-610,715-964`，workspace/model 在 `:100-138,619-641`。 |
| 现状：重构落点位于生产真实路径 | 从 CLI 入口正向追到 composition | ✓ 成立。`personal_assistant.main` 分派 foreground/background（`src/personal_assistant/main.py:93-113`）；foreground 经 `run_gateway` 加载并 build runtime（`gateway/process_lifecycle.py:119-168`）；production composition 创建 config owner、catalog、auth、sync 与 schedulers（`gateway/composition.py:168-233,333-383,501-591`）。 |
| 现状：background parent 在已有实例检查前执行带副作用 load，child 又执行一次 | 追 parent/child 两条入口 | ✓ 成立。parent 在检查 state 前调用 `load_gateway_runtime_config`（`gateway/process_lifecycle.py:203-231`），该函数会 probe/provision/write（`config/local_store.py:385-390`）；child 经 `run_gateway` 再走同一路径（`process_lifecycle.py:135-147`）。决策 2 已把 background parent 改为 read-only。 |
| 现状：显式 `--foreground` 是独立生产入口且不经过 lifecycle lock | 从 CLI 分支追 ownership acquisition | ✗ 成立但 design 未覆盖。`main` 直接调用 `run_gateway`（`src/personal_assistant/main.py:104-108`），只有 background/restart parent 才持 `_gateway_lifecycle_lock`（`gateway/process_lifecycle.py:193-200,326-334,441-453`）。见 Issue 1。 |
| 现状：当前进程内 owner 是 write-before-publish | 核 transform/save/publication 顺序 | ✓ 成立。`RuntimeConfigOwner.persist` 在锁内先 save，成功后才替换 snapshot（`config/local_store.py:351-364`）。 |
| 现状：当前 normal/sensitive writer 的 commit 语义不同 | 追两套 writer 完整路径 | ✓ 成立。normal path 做默认主配置 backup 后直接覆盖（`config/local_store.py:715-766,917-923`）；sensitive path 用 mode 0600 temp、file fsync、replace、directory fsync 且不备份（`:926-964`）。后者在 replace 后 dir-fsync 失败时会抛错而 owner 保持旧 snapshot，正是 v2 要修的 commit-point 分叉。 |
| 现状：active production writer 实际都选择 sensitive path | 扫描 `src/` 的 writer caller | ✓ 成立。Agent sync 将 production `save_local_config` alias 到 sensitive writer（`gateway/agent_config_sync.py:32-34,544-547`）；auth、static bot/owner/skill 也默认 sensitive writer（`auth/im_auth_client.py:163-173,217-218`；`config/local_store.py:420,504,662-665`）。普通 backup writer 除 sensitive temp 内部调用外没有 active `src/` consumer。 |
| 现状：current model snapshot 不保留任意 raw YAML | 追 decode/encode 投影 | ✓ 成立。decode 只取已知顶层字段（`config/local_store.py:588-610`），encode 也逐项重建已知字段（`:781-915`）；未知 raw mapping 不在 `LocalConfig` snapshot 中。该事实影响 v2 的“未来未识别 opaque mapping”自动分类，见 Issue 5。 |
| 现状：`--im-service-url` 当前会污染 durable YAML | 追 override 到后续写盘 | ✓ 成立。override 被 replace 进 `LocalConfig`（`config/local_store.py:391-409`），composition 又以该值建 owner（`gateway/composition.py:190-193`）；token/Agent 写回会全量 encode URL（`auth/im_auth_client.py:207-218`；`gateway/agent_config_sync.py:529-547`；`config/local_store.py:874-885`）。 |
| 现状：IM refresh 是先在服务端撤销旧 refresh token，再返回新 pair | 追 IM auth commit point 与 Gateway accept | ✓ 成立。IM 在锁内先把旧 jti 加入 revoked set，再 issue 新 pair（`src/IM/application/auth_service.py:145-159`），集成测试确认旧 token 随即 401（`tests/im_service/integration/test_auth_routes.py:126-148`）。当前 Gateway 则先把新 pair 放入进程内字段，再尝试持久化（`src/personal_assistant/auth/im_auth_client.py:180-220`）。见 Issue 2。 |
| 现状：token-only Gateway 配置是支持路径 | 核当前构造与测试 | ✓ 成立。`IMTokenProvider` 接受只有 token/refresh 的 `IMServiceConfig`（`auth/im_auth_client.py:154-173`），单测明确构造无 username/password 的 refresh 配置（`tests/unit/personal_assistant/test_gateway_build_runtime.py:255-296`）。 |
| 现状：workspace seeding 与 model precedence 是 Gateway policy | 追 startup/dynamic caller | ✓ 成立。parse 时 seeding 在 `config/local_store.py:1075-1088`，动态创建在 `gateway/agent_config_sync.py:156-175`；model precedence explicit→agent→product 在 `config/local_store.py:619-641`，生产调用点包括 `gateway/kernel_client.py:74-80,139-145,207-213` 与 `gateway/session_run_coordinator.py:1107-1111`。 |
| 现状：static Feishu 写 local YAML | 追 probe、owner bind、skill provision | ✓ 成立。bot identity、first-sender owner 与 skill 都经 local config writer（`config/local_store.py:412-461,496-546,644-708`），static adapter 从 composition 注入 binder（`gateway/composition.py:225-233,625-670`）。 |
| 现状：managed Feishu 使用 manifest + IM profile authority | 从 managed runtime 追 metadata/skill | ✓ 成立。metadata 带 generation guard 写 manifest（`gateway/channel_manager.py:555-608`；`gateway/channel_manifest_store.py:301-345`）；managed skill 经 `IMAgentConfigSync` patch IM profile（`gateway/managed_channel_control.py:143-155`）。canonical 明确 managed manifest 权威且 App Secret 不进 config（`docs/specs/gateway/external-channels.md:230-276`）。 |
| 现状：Agent config 当前 persist-first→catalog publish | 追 sync production chain | ✓ 成立。`_publish_agent_config` 先 `_persist_agent_config`，之后才 publish catalog（`gateway/agent_config_sync.py:529-563`）；当前 create path 再单独更新 reporter/cron（`:236-247`）。 |
| 现状：cron registration 自身以 registry presence 幂等 | 追 `on_agent_created` 到 registry | ✓ 成立。`register_agent` 以 `registry.resolve` no-op（`scheduler/cron_gateway_runtime.py:68-77`），`on_agent_created` 只是该 ensure 行为的事件名包装（`:117-123`）。因此重连时按 registry 缺失重试是可复用能力，不需要“只在 config 首次出现”限制。 |
| 现状：reconnect 会全量 reconcile Agent，但当前不会单独补 cron follower | 追 connection-ready path | ✓ 成立。每次 register-ready 调 `reconcile_all_agents`（`gateway/connection_ready.py:99-109`）；sync 的 `_publish_agent_config` 只做 durable/catalog（`gateway/agent_config_sync.py:549-563`），cron callback 仅 create handler 调用（`:236-247`）。 |
| 现状：canonical 约束 single-instance、自动 reconnect 与动态 cron | 逐项读取 gateway area | ✓ 成立。single-instance 在 `docs/specs/gateway/service-lifecycle.md:14-33`，reconnect 在 `:122-149`；动态新 Agent 的 cron 正确路由在 `docs/specs/gateway/heartbeat-cron.md:29-34`，配置重连收敛在 `:100-108`。 |
| 现状：CC 对照的“大 settings 不等于应机械拆分” | 直接读本机文件并核 git identity | ✓ 方向成立但锚点表述不准确。commit `0991eac5` 的 `src/utils/settings/settings.ts` 确实集中 source/path/read/write/cache；当前 working tree 的 provider loader 也独立在 `src/services/providerRegistry/loader.ts:1-8,68-159,186-245`。但该 loader 在本机 git 状态是 staged `A`，`git cat-file -e 0991eac5:src/services/providerRegistry/loader.ts` 不存在，不能称为“快照 0991eac5”的文件；见 Recommendations。 |
| 决策 1：deep-freeze model，path 只归 document/store | 核嵌套不可变与 path authority | ✓ 已拍死。所有 opaque JSON 经 freeze、store 对 transform 结果再 normalize（`design.md:96-102`）；`LocalConfig` 删除 `source_path`，document/store 各自明确 path context，runtime path helper 显式接收（`:103-107`）。旧 WARNING 已修复。 |
| 决策 2：background read-only，foreground 唯一 writer | 核所有 CLI 入口与 ownership protocol | ✗ background parent 的旧缺口已修，但 direct foreground/foreground+background 并发没有 ownership acquisition 协议；“架构上不允许第二 writer”不是 enforcement（`design.md:109-121`）。见 Issue 1。 |
| 决策 3：store 自动分类并拥有安全 transaction | 核矩阵穷尽性、删除测试、raw/durable base | ✗ backup/commit rows已补齐，但 classifier 只写 snapshot 规则，无法兑现“未来未识别 raw mapping”；`model 与 serialized bytes 均 no-op` 也会让 model no-op、原文件非 canonical bytes 的调用落入写盘分支（`design.md:140-162`）。见 Issue 5。 |
| 决策 3：replace 后 dir-fsync failure 视为 committed | 核磁盘可见态与 in-memory publish | ✓ commit point 本身正确。replace 成功后不能假装目标仍旧；publish 新 snapshot + durability warning 比当前“disk 新 / owner 旧”更一致（`design.md:156-162`）。warning 的消费出口仍未闭合，见 Issue 6。 |
| 决策 4：每次从最新 durable snapshot 重算 runtime view | 核 durable/runtime 数据流及失败态 | ✗ URL B 不污染 A 的主路径闭合，但“token/refresh 始终来自最新 durable snapshot”忽略了 IM 服务端已先旋转并撤销旧 token 的外部 commit point（`design.md:164-172`）。见 Issue 2。 |
| 决策 5：static/managed Feishu 共享纯逻辑、不共享 owner | 核双 authority 与 import 方向 | ✓ 已拍死。static 只写 Store；managed metadata 只写 generation-scoped manifest，skill profile-first→local mirror；禁止共享 save callback/generation guard/skill authority（`design.md:174-187`）。旧 CRITICAL 已修复。 |
| 决策 6：durable→catalog→reporter/cron publication | 核顺序、失败、no-op 与 retry | ✗ durable→catalog→reporter 顺序闭合，但 step 5 的“仅当 agent 从不存在变为存在时调用 cron”与后文“失败由 reconnect reconciliation 重试、缺失 follower 可补齐”不能同时成立（`design.md:189-204`）。见 Issue 3。 |
| 决策 7：全部 caller 直连并原子删除 façade | 做删除测试与边界检查 | ✓ 成立。schema/codec/store 与 workspace/model/channel policy 分别有独立变化轴；一次性迁移并删除旧 surface 避免双入口/双 writer（`design.md:206-213`）。 |
| 澄清 Q1：中途无需逐项问用户 | 核有无待用户拍板的核心分叉 | ✓ 七项方向均有结论；本报告要求作者修技术矛盾，不要求用户重新逐项选方案（`motivation.md:19-27`）。 |
| 澄清 Q2：不按 LOC 机械拆分 | 核新模块变化轴与 CC 对照 | ✓ schema/codec/store、workspace/model、static/managed channel 各自依赖目的不同（`motivation.md:23-24`；`design.md:43-50,61-69`）。 |
| 澄清 Q3：runtime URL 不再污染 YAML | 核 design + delta | ✓ 决策 4 与 gateway delta 两个 Scenario完整覆盖（`motivation.md:25-27`；`design.md:164-172,248-253`；`specs/gateway/service-lifecycle.md:1-25`）。旧 CRITICAL 已修复。 |
| 目标：schema/codec、deep-frozen store、path 单权威 | 核决策与接口 | ✓ 决策 1、3 及接口列表覆盖（`motivation.md:42-47`；`design.md:96-107,217-224`），除 Issue 5 的 raw-byte/classification 边界。 |
| 目标：launcher read-only、foreground unique writer | 核 background 与 direct foreground | ✗ background 场景覆盖，整个 CLI surface 的唯一 writer 不成立。见 Issue 1。 |
| 目标：workspace/model 各归产品策略 | 核 startup/dynamic/run caller | ✓ 决策落点明确，M1 范围同时覆盖 startup 与动态 caller（`design.md:47,80-81,292-298`）。 |
| 目标：static/managed Feishu 保持各自权威 | 核总图、决策、测试退出 | ✓ 总图显式分叉，决策 5 与 M1 双路径保真要求一致（`design.md:82-87,174-187,263-264,298`）。 |
| Scenario：既有 YAML 启动并重启保持 | 核 schema/default/path/write/runbook | △ schema semantic round-trip、path 与真栈均覆盖（`design.md:257-260,271-286,298`）；model no-op/bytes drift 的写盘行为尚不明确，见 Issue 5。 |
| Scenario：IM 修改 Agent 后 runtime/YAML 一致 | 核 durable/live/follower chain | ✗ durable/catalog 主链覆盖，但 cron follower fault 后的重连补齐矛盾会让 YAML/catalog 已新、cron service 仍缺。见 Issue 3。 |
| Scenario：已运行时重复 background start 零写/零 probe | 核 design 路径与 canonical delta | △ 决策 2 的 background path、风险测试和 M1 exit已覆盖（`design.md:111-138,261-262,298`）；但该对外保证未投影到 delta，见 Issue 4。 |
| Scenario：runtime URL override A→B→A | 核 dynamic consumer、disk baseline、delta | ✓ durable update 永远基于 A，overlay无 encoder，风险回归与 delta 两个 Scenario齐全（`design.md:164-172,267`；`specs/gateway/service-lifecycle.md:7-25`）。token rotation 的本地写失败语义另见 Issue 2。 |
| Scenario：模型选择/workspace 初始化保持 | 核 policy 落点与退出标准 | ✓ 决策 1/7、M1 scope 和 reviewer/worker exit覆盖（`design.md:96-107,206-213,296-298`）。 |
| Scenario：Feishu 首次接入保持 | 核 static probe/owner/skill 与验收前置 | ✓ static bootstrap owner、真实 app 前置和 journey 写清（`design.md:174-187,279-286`）。 |
| Scenario：static/managed Feishu 不互相覆盖 | 核 authority 与 canonical | ✓ 决策 5 忠实保留 canonical manifest/profile authority（`design.md:174-187`；`docs/specs/gateway/external-channels.md:230-276`）。 |
| 非目标：不改变 YAML schema、默认路径、CLI 参数形态 | 核 model/document/CLI | ✓ schema fields 与参数形态不变；删除 `source_path` 只移除内部 metadata，default path 仍由 document/store入口拥有（`motivation.md:94-101`；`design.md:96-107`）。 |
| 迁移/回滚：测试先行、单 snapshot、无双写、整体回滚 | 核风险与 M1 | ✓ 单 M1 原子 cutover、semantic fixture、fault injection、旧 façade 删除与无数据 migration均有落点（`motivation.md:103-108`；`design.md:255-269,292-298`）。 |
| delta-spec：kernel no delta | 核是否改 `agent.sdk` 行为 | ✓ 只重排 PA 产品层 owner，不改 `agent.sdk` 消费合同（`SPEC.md:120-133`；`design.md:250`）。 |
| delta-spec：im no delta | 核是否要求 IM 新行为 | ✓ IM auth rotation/current profile/manifest 现有行为不变（`design.md:251`）。 |
| delta-spec：gateway URL override ADDED | 核 target、用法与 THEN 可观察性 | ✓ target 是最窄的 `service-lifecycle.md`；canonical 无既有 override Requirement，ADDED 用法正确；两个 THEN 都是运维者可观察结果（`specs/gateway/service-lifecycle.md:1-25`）。 |
| delta-spec：重复 start 零副作用 | 对照 motivation Scenario 与 canonical 同名 Scenario | ✗ 缺失。它强化 canonical 已有“重复启动被单实例锁拦下”，应以 MODIFIED 完整条目保留原 Scenario 并追加零 config write/Feishu probe 保证；当前 delta 只含 URL override。见 Issue 4。 |
| delta-spec：cli no delta | 核 coding_cli 范围 | ✓ 不涉及 coding_cli（`design.md:253`）。 |
| M1：Gateway config owners 原子切换 | 核垂直性、拆分举证与范围交集 | ✓ 单 M1 同时交付完整可观察配置链；按 schema/codec/store 横切会制造双入口/双 writer，拆分反门槛举证成立（`design.md:288-298`）。 |
| M1：退出标准两轨 | 核 reviewer/worker 标记与可验性 | △ 两轨齐且覆盖旧六项；需按 Issues 1-6 补 foreground 并发、refresh→disk failure、cron follower retry、raw/no-op matrix、warning sink 与 delta 对账。 |
| 与 refactor-478/480 并行关系 | 核范围交集与集成顺序 | ✓ 逻辑 owner不同，但三者都可能改 composition；design 明示并行开发、478→480→481 串行集成且逐次跑 Gateway contract/e2e，没有错误承诺同文件可并行 merge（`design.md:292-294`）。 |
| 常驻服务 Runbook 与验收前置 | 核 AGENTS 规范、健康检查与真实 Feishu 资源 | ✓ 使用 worktree `e2e-up/down`、独立 config、IM health check；Feishu app/用户缺失明确阻断最终验收（`design.md:271-286`；`AGENTS.md:181-317`）。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | background launcher、spawned child、direct foreground 的唯一 writer ownership | ✗ owner 应归“成功取得同 config runtime lease 的进程”，不是所有进入 `run_gateway` 的 foreground 进程。当前设计只剥离 parent 写权限，却没有定义 direct foreground 如何取得/拒绝 lease；长期会让 debug 模式重新成为 stale overwrite 的第二入口。见 Issue 1。 |
| 归属 | IM auth server commit 与 local config commit | ✗ 新 refresh pair 的第一事实 owner 是已完成 rotation 的 IM 服务端；本地 store 只能持久镜像，不能用磁盘失败否定已发生的远端 commit。把 dynamic credential 完全派生自 durable snapshot 会在 token-only 部署上失去唯一有效 pair。见 Issue 2。 |
| 归属 | static/managed Feishu | ✓ 走完无存活发现。代码归 channel domain，但 durable authority继续分属 Store 与 Manifest/IM profile，依赖方向自然。 |
| 该不该存在 | 自动 sensitivity classifier + non-secret backup branch | ✗ 删除测试未通过：当前所有 active mutation caller 都已选择 sensitive atomic writer，普通 backup writer没有 production consumer；新增分类器目前只为一个无用户 Scenario 的未来分支服务。长期每加一个可承载凭据的 scalar/mapping 都要同步分类器与 fault matrix，漏一次就复制 secret。若必须保留 backup，应先给出真实 consumer与 raw-byte安全 contract；否则统一 secure atomic policy 更深。见 Issue 5。 |
| 该不该存在 | model/codec/document/store、workspace/model/static Feishu 模块 | ✓ 删除任一边界都会把 I/O、产品 policy 或 provider dependency搬回无关模块；不是为未来多态预造的 façade。 |
| 深还是浅 | `GatewayRuntimeConfigView` | ✗ 对 URL overlay 是必要边界，但“全量最新 durable config view”把本来独立的 endpoint overlay 与 externally-committed credential rotation揉成一个接口，隐藏不了后者的失败状态机。应把 topology snapshot、process endpoint overlay、volatile rotating credentials 三种生命周期分开。见 Issue 2。 |
| 深还是浅 | `ConfigCommitResult.durability_warning` | ✗ store 把 post-commit failure降成字段，却没有定义哪个 owner必须 log/report/health-publish；调用方可合法忽略，接口没有真正隐藏 transaction复杂度。长期会出现磁盘 durability 已降级但用户仍看到无条件 success。见 Issue 6。 |
| 治本还是补丁 | deep-freeze/path 与删除 façade | ✓ 治本。model 内不再夹 I/O metadata，store normalize 所有 transform结果，旧聚合 surface 原子删除。 |
| 治本还是补丁 | durable→catalog→reporter/cron publication | ✗ durable/catalog 顺序治本，但 cron仍建模为一次性 create event而非 desired-state reconciliation；一次 follower failure后重连无法按字面补齐，留下“YAML/catalog正确但 cron缺席”的隐性分叉。见 Issue 3。 |

## Issues

- [CRITICAL] [决策 2 / foreground ownership] v2 只封住了 background parent，仍没有为所有
  foreground 入口定义“取得唯一 runtime writer lease”的机制。显式 `--foreground` 直接进
  `run_gateway`（`src/personal_assistant/main.py:104-108`），不经过 background parent 的
  config-scoped lifecycle lock；design 又明确拒绝跨进程 writer lock，仅说“架构上不允许第二
  writer”（`design.md:109-121`）。不改时，两个 direct foreground，或 direct foreground 与
  background child，可各自 `LocalConfigStore.open` 并从不同 snapshot 写同一 YAML，旧 CRITICAL
  的 stale overwrite 仍存在。修订要求：拍死覆盖 background child 和 direct foreground 的 runtime
  ownership protocol，例如 parent 持 lifecycle lock完成 reservation/spawn，child持可验证 launch
  lease，而 direct foreground必须在同一 lock/state 协议下拒绝已有实例；或者由 runtime 持有同
  config 的 lifetime writer lock。M1 增加 foreground↔foreground、foreground↔background、
  background↔background 三组并发验收，且 loser 零 probe/零 store open。

- [CRITICAL] [决策 4 / commit point / dynamic runtime view] “token/refresh 始终来自最新
  durable snapshot”把本地 `os.replace` 误当成 credential rotation 的总 commit point。IM
  refresh 在返回新 pair 前已经撤销旧 refresh jti（`src/IM/application/auth_service.py:145-159`；
  `tests/im_service/integration/test_auth_routes.py:126-148`）。若服务端成功后
  `LocalConfigStore.update` 因 backup/temp/replace 等 pre-commit error失败，durable snapshot仍
  是已撤销的旧 token；按 design，view又不能发布刚拿到的新 pair。token-only 配置是现有支持路径
  （`tests/unit/personal_assistant/test_gateway_build_runtime.py:255-296`），因此下一次 reconnect
  可能永久 401，违反 `service-lifecycle.md:122-139`。修订要求：把 process endpoint overlay 与
  volatile rotating credential owner分开；服务端 rotation成功即必须把新 pair留在进程内并驱动当前
  reconnect，本地持久化失败要明确报警/重试，不能让旧 durable值覆盖新远端事实；同时拍死 restart 前
  尚未持久化时的可恢复/失败语义，并增加“refresh成功 + local pre-commit failure + reconnect”测试。

- [CRITICAL] [决策 6 / cron follower convergence] step 5 规定“仅当 agent 从不存在变为存在”
  才调 `on_agent_created`，后文却规定 cron failure由 startup/reconnect reconciliation重试且缺失
  follower可补齐（`design.md:194-204`）。第一次 cron registration若在 durable/catalog commit后失败，
  下次 reconcile 中 agent已存在，按 step 5 不再调用；YAML、catalog、reporter均显示成功，但 cron
  registry永久缺 service直到进程重启。当前 `GatewayCronRuntime.register_agent` 已以 registry
  presence幂等（`scheduler/cron_gateway_runtime.py:68-77,117-123`），应将契约改成每次
  create/edit/reconnect都以 committed agent snapshot调用 `ensure_agent_registered`，由 registry
  自身 no-op；“首次创建”只能控制确实非幂等的副作用。补 follower-first-failure 后同连接重试与 reconnect
  两条测试。

- [CRITICAL] [delta-spec / repeated start] motivation新增了“已有 foreground 时再次 background
  start 不写配置、不做 Feishu probe/provision”的用户 Scenario（`motivation.md:69-72`），它强化
  canonical 已有 `Scenario: 重复启动被单实例锁拦下`（`docs/specs/gateway/service-lifecycle.md:29-33`），
  但 unit delta 只写 runtime URL（`specs/gateway/service-lifecycle.md:1-25`）。不改，收尾按 delta
  机械归并后，最关键的第二-writer回归保证不会进入 canonical，后续 lifecycle重构可再次把副作用移回
  reject 前而不违反契约。修订要求：在同一 delta 增加 `MODIFIED Requirements`，完整保留
  “运维者用启停命令把 Gateway 当后台服务管理”及其全部既有 Scenarios，并把重复启动的零 config
  write/零 Feishu probe/provision作为对应 Scenario 的可观察 AND；不能另写一个与既有
  requirement重叠的 ADDED 条目。

- [WARNING] [决策 3 / 自动敏感分类与 no-op] 新 classifier/backup branch 没有清晰的 raw-byte
  authority。design说对 current/new snapshot分类并覆盖“未来未识别 opaque mapping”，但当前 decode
  丢弃未知 raw字段、encode只重建已知字段（`config/local_store.py:588-610,781-915`）；仅看
  `LocalConfig` 无法判断实际将被 copy 为 backup 的旧文件是否含未知敏感值。矩阵又只在“model 与
  serialized bytes 均 no-op”时短路（`design.md:147-158`），所以 transform语义 no-op但用户原 YAML
  含注释/非 canonical格式时，worker可按字面重写文件；当前 owner则在 model equality处直接返回
  （`config/local_store.py:359-364`）。长期代价是分类规则随 schema漂移，以及本应 no-op 的 owner调用
  擦除用户格式。修订要求：先决定是否真的需要当前没有 production caller 的 non-secret backup分支；
  若保留，store须拥有实际 preimage bytes/hash，model equality优先 no-op，写前检测 external divergence，
  并对实际旧 bytes与新 bytes做可执行的分类；否则统一 secure atomic no-backup policy，删除 classifier。

- [WARNING] [决策 3 / post-commit warning 出口] replace成功、directory fsync失败后继续 publish
  是正确的，但 `ConfigCommitResult.durability_warning` 没有消费 owner。接口列表只把结果返回 caller
  （`design.md:158-162,217-224`），Agent sync、auth和static bootstrap谁必须记录日志、上报 degraded
  health或把 warning带回请求都未拍死。不改时 worker可以完全忽略该字段，运维者收到 success却不知道
  本次 config未获得 crash-durability保证。修订要求：至少由 store无条件结构化 log post-commit
  warning；再明确各 orchestration caller是否向 IM/health surface传播，M1 fault injection断言 warning
  有可观察出口而非只存在返回对象里。

## Recommendations

- 修正 CC 对照的来源锚点：本机 HEAD 是 `0991eac5`，但
  `src/services/providerRegistry/loader.ts` 是当前 working tree 的 staged新增，不存在于该 commit。
  应写成“本机 working tree 对照”，或选择一个真正包含该文件的 commit后再引用。
- 将 `GatewayRuntimeConfigView` 收窄为明确的 IM runtime connection view，列出动态字段；LLM、
  channels、node、gateway timing等 startup topology不应因名字宽泛而被 future caller误认为热更新。
- 补一条 background launcher result测试：带 URL B 启动时 parent仍只读 A，但命令行展示的
  `IM service` 应是本次 effective B，避免 read-only parent迁移后回报错误 endpoint。
