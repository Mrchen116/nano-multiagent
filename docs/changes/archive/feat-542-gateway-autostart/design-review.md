# Design Review: feat-542

## Round 1

### Metadata

- reviewer: `/root/feat_542_design_reviewer`
- review_mode: `full`
- mode_reason: R1 恒为 full；本 unit 没有既有 review inventory 或历史问题可继承，因此重新枚举并核实全部五类承重原子，且执行全部四个架构进攻角度。
- started_at: `2026-09-03T15:53:58+08:00`
- completed_at: `2026-09-03T16:08:04+08:00`
- duration: `14m06s`

### Verdict

Issues Found — 3 CRITICAL / 4 WARNING

方案主干是成立的：让 `process_lifecycle` 保持唯一生命周期策略 owner、让一个具体的
`macos_launch_agent` 深模块收口 plist/launchctl、让 launchd 直接监督现有前台 Gateway，
并让 Gateway YAML 承载稳定运行环境，都比恢复 wrapper/tmux 或预造跨平台 ServiceManager
更直接。但当前文档仍缺三个会使 worker 猜测或使既有契约回归的设计闭环，不能进入
`change-orchestrator`。

### Coverage

- 首文档：`spec.md`；5 个 Requirement、11 个验收 Scenario、11 条澄清决定、5 段用户场景、4 条非目标。
- 设计：`design.md`；20 条现状/约束/grounding/复用/历史断言、7 个编号决策、配置/结果接口、start/restart/stop/失败/部署数据流、风险回退、reviewer runbook。
- delta-spec：`specs/gateway/service-lifecycle.md`；3 个 ADDED Requirement、1 个 MODIFIED Requirement（完整保留并更新 7 个既有 Scenario）、REMOVED=无；另核对其 canonical target 与 package index carrier。
- milestone：唯一 `feat-542-M1` 与 `M1-macos-gateway-autostart/.gitkeep` 骨架。
- 独立证据：从生产入口 `personal_assistant.main` 正向追到 `gateway.process_lifecycle.run_gateway` / `compose_gateway`，核对 config parse/save/writeback、PID/process-birth/lock/signal 路径、canonical gateway specs、current 运维文档、`refactor-461` / `refactor-470` 历史与本机 `launchd.plist(5)` / `launchctl(1)` 语义。

### 核实台账

#### 1. 现状断言

| ID | 承重原子 | 核实动作 | 结论与证据 |
|---|---|---|---|
| S1 | `main.py` 只解析并分派 start/stop/restart/foreground，现有结果只含 PID/IM/log | 从 `main()` 正向追全部分支与结果类型 | 成立。CLI 在 `src/personal_assistant/main.py:39-120` 分派到 lifecycle；结果类型当前只有 `pid/log_path/im_service_url`（`src/personal_assistant/gateway/process_lifecycle.py:74-86`）。 |
| S2 | `process_lifecycle.py` 是生产生命周期 owner | 从 CLI 入口追 background、restart、stop、lock、state、signal | 成立且不是测试死实现。默认 start、restart、stop 都进入该模块（`src/personal_assistant/main.py:94-113`）；真实算法在 `src/personal_assistant/gateway/process_lifecycle.py:172-387,442-455,627-703`。 |
| S3 | `local_store.py` 是 typed parse/save 与 runtime writeback owner，新字段必须走同一路径 | 核 dataclass、loader、serializer、`RuntimeConfigOwner` 与生产 persist 调用 | 成立。typed model/parse 在 `src/personal_assistant/config/local_store.py:293-305,600-645,1527-1556`，序列化在 `:910-1111`，串行持久化 owner 在 `:359-397`；token/config sync 的生产写回调用该 owner（`src/personal_assistant/auth/im_auth_client.py:172-218`; `src/personal_assistant/gateway/agent_config_sync.py:230,810,1452-1454`）。 |
| S4 | README、三份 operations 文档与 deploy skill 是需要同步的旧 detached 叙事 | 全仓排除 archive/change history 搜索 lifecycle 文案 | 部分成立但枚举不完整。列出的文件确实仍写旧路径（如 `docs/operations/gateway.md:50-100`; `.claude/skills/prod-fleet-deploy/SKILL.md:73-80,113-170`），但 current `docs/operations/local-stack.md:50` 与随包产品手册 `src/personal_assistant/builtin_skills/nanoassistant-docs/references/getting-started.md:56-72` 也明确写“后台 child”，未进入 M1，见 R1-W2。 |
| S5 | `service-lifecycle.md` 是唯一行为增量 area；其他包不改 | 对照 package entry、canonical area 与变更边界 | 行为归属成立：Gateway lifecycle 是语义最窄 area（`docs/specs/gateway/spec.md:19-27`; `docs/specs/gateway/service-lifecycle.md:8-12`），没有 kernel/IM/CLI 行为变化。但新增 3 个 Requirement 必须同时更新 package entry 的派生计数，当前缺 carrier，见 R1-C1。 |
| S6 | 变更闭合在 PA，保持 `personal_assistant -> agent.sdk` 与 IM 独立 | 查顶层架构与 PA imports | 成立。边界在 `SPEC.md:132-161`；当前 PA 对内核的 imports 均为 `agent.sdk`（如 `src/personal_assistant/product.py:26`; `src/personal_assistant/gateway/session_binder.py:27`），设计没有新增反向或跨产品依赖。 |
| S7 | `--foreground` 是 debug/E2E/外部 supervisor 入口，不应管理 LaunchAgent | 从 CLI 与 worktree 真入口追调用方式 | 成立。CLI 前台分支直达 `run_gateway`（`src/personal_assistant/main.py:104-108`）；worktree 契约固定 `--foreground --auto-bind` 且由外部 shell 管 PID（`docs/development/worktree-runtime.md:149-170`; `scripts/e2e-up.sh:322-335`）。 |
| S8 | 同一 resolved config 的 lifecycle 命令由一把 lock 串行并靠 state/process birth 保单实例 | 查 lock key、启动前检查、restart 原子序列与 signal 前复核 | 成立。lock 以 resolved config 派生（`src/personal_assistant/gateway/process_lifecycle.py:442-455`），start 拒绝 live state（`:214-243`），restart 同锁 stop+start（`:304-335`），signal 前后复核 birth（`:627-653`）。 |
| S9 | config/plist/log/state 是运行数据；production 换向需保护 dirty worktree | 对照仓库红线、worktree/生产规则 | 成立。`AGENTS.md` 工作红线与 `.claude/skills/prod-fleet-deploy/SKILL.md:37-45,119-158` 明确 dirty worktree 保护和新版本验证后清旧目录；新增 plist 也应保持本机运行数据。 |
| S10 | 范围只到当前用户 macOS GUI domain | 核 spec/non-goals 与系统 domain 语义 | 成立。首文档锁定登录后、无 root、无 Linux/Windows（`spec.md:29-35,138-146`）；`launchctl(1)` 将 `gui/<uid>` 定义为用户登录 domain，设计未越界到 system LaunchDaemon。 |
| S11 | current background 是 detached child；startup confirmation 不是 readiness | 对比 Popen、state write、waiter 与 canonical | 成立。child 用 `start_new_session=True`（`src/personal_assistant/gateway/process_lifecycle.py:722-731`），前台进程在 runtime 前写 state（`:120-169`），parent 只等 state/birth/liveness（`:734-761`）；canonical 同样只承诺 PID/process birth（`docs/specs/gateway/service-lifecycle.md:22-29`）。 |
| S12 | canonical/current 没有 login autostart 或 crash recovery | 搜索 canonical lifecycle 与 production code 的 launchd 实现 | 成立。canonical 现有 service lifecycle 没有登录加载/异常重拉 Requirement（`docs/specs/gateway/service-lifecycle.md:12-83`）；`src/personal_assistant` 无 `launchctl`/plist 实现。 |
| S13 | current duplicate start、atomic restart 与 fail-closed stop 仍成立 | 逐分支核生产代码 | 成立。重复启动在 `src/personal_assistant/gateway/process_lifecycle.py:219-243`，restart 在 `:327-335`，stop 对 mismatch/birth 变化 fail closed 并保留证据（`:338-387,576-624`）。 |
| S14 | `run_gateway()` 可改造为 launchd 直接监督的长期前台入口 | 追 state、signal、runtime ownership | 成立。它加载同一 config、安装 signal handler、原子写 state、调用 `runtime.run_forever()` 并按 expected state 清理（`src/personal_assistant/gateway/process_lifecycle.py:120-169,797-828`）。 |
| S15 | 现有 detached launcher 可保留为关闭/降级路径 | 查其与 runtime 的边界 | 成立。它只构造 `--foreground` argv、spawn、等待 state 后返回（`src/personal_assistant/gateway/process_lifecycle.py:204-280,706-761`），可以作为独立 fallback，而无需复制 runtime。 |
| S16 | lock/state/birth/signal cleanup 可共享，不需第二份 PID 真相 | 查数据读写与 expected-state cleanup | 成立。唯一 state path/原子写/conditional remove 在 `src/personal_assistant/gateway/process_lifecycle.py:656-703`；进程身份和 signal owner 已集中在 `:627-653`。 |
| S17 | 新建一个具体 `macos_launch_agent` 深模块、不建通用 port | 全仓搜索既有同类并做删除测试 | 成立。仓内无现成 launchd module 可复用；若删除该 module，plist XML、domain target、bootstrap/bootout/print、原子替换都会回流到 828 行 lifecycle owner。小 concrete interface 有真实 depth，不是未来多态占位。 |
| S18 | `refactor-461` 冻结 no-readiness 并保留 Gateway supervisor/process-group 边界 | 核 archived design review 与现行代码 | 成立。历史 reviewer 明确区分 PID confirmation 与 readiness，并保留 `start_new_session`/SIGTERM/SIGKILL 边界（`docs/changes/archive/refactor-461-dead-kernel-subprocess-seam/design-review.md:16-18`）；现行 S11/S15 仍验证同一事实。 |
| S19 | `refactor-470` 将 CLI/lifecycle/composition 分归现 owner | 核 archived progress 与现行 wiring | 成立。历史决策把生命周期整体迁入具名 owner、入口只做模块限定分派（`docs/changes/archive/refactor-470-managed-channel-composition/M3-entry-lifecycle-modules/progress.md:26-50`）；现行 `main.py:94-113` 仍一致。 |
| S20 | LLM proxy 历史证明 KeepAlive 不应监督 daemonizing/tmux launcher | 核本机参考项目的真实文档并对照 launchd man page | 成立。`/Users/czj/Repos/LLM_PROXY/docs/macos-autostart-zh.md:115-123` 明确记录该失败形态；本机 `launchd.plist(5)` 也说明 `KeepAlive=true` 持续保持 job 且隐含 RunAtLoad。直接监督长期前台 Python 是治本方向。 |

#### 2. 编号决策

| ID | 决策 | 四问结论 | 证据/状态 |
|---|---|---|---|
| D1 | YAML 拥有 autostart + environment，配置值覆盖同名启动环境 | 已拍死、spec 驱动、与 typed config owner 自洽；不需要为 SearXNG 造特例 | `spec.md:43-45,97-103`；`design.md:96-108,189-195`。注意 CLI transient controls 不能因此丢失，见 R1-C2。 |
| D2 | launchd 直接监督前台 Gateway，KeepAlive=true | 已拍死且机制正确；拒绝 daemonizing wrapper/tmux 与 LaunchDaemon 有事实依据 | `design.md:110-121`；`run_gateway` 的长期前台路径见 `src/personal_assistant/gateway/process_lifecycle.py:120-169`；`launchd.plist(5)` KeepAlive 段支持 crash relaunch。 |
| D3 | lifecycle 保持策略 owner，macOS module 只收口机制 | 边界清楚、没有通用 port、与 refactor-470 owner 对齐 | `design.md:123-134,201-204`；历史 owner 证据见 S19。 |
| D4 | running start 拒绝，restart 才替换并应用 | 已拍死且保住当前破坏性边界 | `spec.md:47-49,91-95`; `design.md:136-146,243-245,258`; current error path `src/personal_assistant/gateway/process_lifecycle.py:219-243`。 |
| D5 | stop 只 bootout current domain、保留 plist；false 时永久移除 | 正常路径方向成立，但 bootout/remove 的 idempotency、失败终态与 launchd kill timeout 未拍死 | `design.md:148-158,258-261,286`。这些不是 worker 实现细节，而决定 explicit disable/stop 是否会虚假成功或破坏 shutdown grace，见 R1-C3。 |
| D6 | label/plist 由 resolved config 稳定派生，定义原子换向 | config-scoped identity 与 production worktree 换向成立；但 service definition 对 transient CLI controls 的语义不闭合 | `design.md:160-171,263-272`。遗漏 `--auto-bind` 见 R1-C2；把 `--im-service-url` 写成长存 plist 见 R1-W1。 |
| D7 | enable apply 失败先撤销 managed job，再 detached fallback，结果非零 | 对 enable/write/bootstrap/start-confirmation failure 已拍死，并明确无法证明单实例时 fail closed | `spec.md:37-41,129-136`; `design.md:173-183,249-255`。它没有覆盖 disable/remove/stop failure，不能替代 D5 的缺口（R1-C3）。 |

决策间没有发现额外互相矛盾：D2 的 supervisor owner、D3 的产品策略 owner和 D5 的
人工暂停是三个不同层次；D4 保证配置变更不会借 start 隐式替换实例；D7 的 fallback 也以
单实例证明为前置。

#### 3. spec 约束

##### 澄清决定

| ID | spec 原子 | 设计落点 | 结论 |
|---|---|---|---|
| Q1 | 只管理 Gateway，不管理 IM/LLM proxy | 架构图、边界、M1 reviewer 轨（`design.md:75-92,276-279,314`） | 覆盖且未越界。 |
| Q2 | 缺省即开启 | D1、typed field、delta（`design.md:96-99,189-195`; delta `:5-19`） | 覆盖。 |
| Q3 | 停止态 start 或 restart 才应用 | D4 与流程（`design.md:136-146,217-232,243-258`） | 覆盖。 |
| Q4 | 登录拉起 + 意外退出恢复 | D2 KeepAlive、M1 reviewer 轨（`design.md:110-121,299-303,314`） | 覆盖。 |
| Q5 | stop 仅本登录暂停，下一登录恢复 | D5、delta（`design.md:148-158`; delta `:49-53`） | 正常路径覆盖；错误语义缺口见 R1-C3。 |
| Q6 | 仅 macOS | constraints/risk/M1（`design.md:39-40,290,314`） | 覆盖。 |
| Q7 | user login 后，不要求 pre-login/root | D2 GUI domain 与 LaunchAgent（`design.md:110-119`） | 覆盖。 |
| Q8 | enable 失败时 detached 可用并明确降级 | D7 与 failure flow（`design.md:173-183,249-255`） | 覆盖。 |
| Q9 | 稳定环境进入 YAML，不复制整份 shell | D1、plist data flow（`design.md:96-108,235-237`） | 覆盖。 |
| Q10 | running bare start 保留 already-running | D4（`design.md:136-146`） | 覆盖。 |
| Q11 | fallback 已运行但 CLI 非零 | D7 + result interface（`design.md:173-180,196-199`） | 覆盖。 |

##### 用户场景与验收 Scenario

| ID | 场景/Requirement 原子 | 对应设计与核实 | 结论 |
|---|---|---|---|
| U1 | config 单一入口、缺省 true、start/restart 应用 | D1+D4，`design.md:96-108,136-146,206-233` | 覆盖。 |
| U2 | 两种后台模式共享 YAML environment，plist 不复制 | D1 + `run_gateway` 应用点，`design.md:189-195,235-237` | 覆盖。 |
| U3 | login/crash 恢复、stop 暂停、false 长期关闭 | D2+D5，`design.md:110-121,148-158,258-261` | 正常路径覆盖；bootout/remove failure 未闭合（R1-C3）。 |
| U4 | enable failure 保当前可用、明确降级、exit nonzero | D7/result，`design.md:173-183,196-199,249-255` | 覆盖。 |
| U5 | IM/LLM 等各自独立 | 图、delta inventory、M1（`design.md:75-92,274-279,314`） | 覆盖。 |
| R1 | 用户通过本地配置选择 Gateway 是否登录自启 | D1+D4+D5 与 start/restart 流程（`design.md:96-108,136-158,206-261`） | Requirement 整体覆盖；disable failure 缺口见 R1-C3。 |
| R1-S1 | 缺省配置默认开启 | `design.md:98-99,220-226`；delta `:11-14` | 覆盖。 |
| R1-S2 | 显式开启 | 同一 true 分支；delta `:16-19` | 覆盖。 |
| R1-S3 | 显式关闭后 detached 且下次不自启 | `design.md:148-156,227-231`；delta `:21-25` | happy path 覆盖；失败终态缺失（R1-C3）。 |
| R1-S4 | 只编辑不改变已应用模式 | D4 拒绝 running start，应用仅 start/restart（`design.md:136-146,243-245`） | 覆盖。 |
| R1-S5 | running bare start 不替换并指引 restart | D4；current production path `src/personal_assistant/gateway/process_lifecycle.py:219-243` | 覆盖。 |
| R2 | Gateway 稳定运行环境由本地配置拥有 | D1 + config/result interface（`design.md:96-108,185-204,235-237`） | Requirement 整体覆盖。 |
| R2-S1 | ordinary/launchd 使用同一 environment、config 优先、值不外泄 | D1 + plist boundary + risk（`design.md:189-195,235-237,289`） | 覆盖。 |
| R3 | 开启后 Gateway 由系统持续保持在线 | D2 + state cleanup（`design.md:110-121,258-261`） | Requirement 整体覆盖。 |
| R3-S1 | 下一 login 自动上线 | LaunchAgent location + KeepAlive/implicit RunAtLoad（`design.md:110-121,160-164`） | 覆盖；真栈 runbook 用 re-bootstrap 模拟 login load，合理。 |
| R3-S2 | crash 后自动恢复 | KeepAlive 直接持有前台 process、state expected cleanup（`design.md:110-121,258-261`） | 覆盖。 |
| R4 | 人工停止与长期自启意图互不混淆 | D5（`design.md:148-158,258-261`） | 正常路径覆盖；错误终态未闭合（R1-C3）。 |
| R4-S1 | stop 后本 login 不立即重拉 | 先 bootout 再 stop（`design.md:148-156,258-260`） | 正常路径覆盖；bootout 失败的用户终态未定义（R1-C3）。 |
| R4-S2 | plist 保留使下次 login 恢复 | D5（`design.md:150-156`） | 覆盖。 |
| R5 | 自启应用失败时保持当前可用并如实反馈 | D7 + result/failure flow（`design.md:173-183,196-199,249-255`） | Requirement 整体覆盖。 |
| R5-S1 | enable apply fail -> one detached Gateway + clear error + nonzero | D7 + result + fail-closed safe check（`design.md:173-183,196-199,249-255`） | 覆盖。 |

##### 非目标

| ID | 非目标 | 核实 | 结论 |
|---|---|---|---|
| N1 | 无 pre-login/root LaunchDaemon | D2 只用 user GUI domain（`design.md:110-119`） | 未越界。 |
| N2 | 不管理 IM/LLM/SearXNG 生命周期 | topology 与 M1 reviewer 轨（`design.md:75-92,314`） | 未越界。 |
| N3 | 不做 systemd/Windows/cross-platform service abstraction | D3/risk/M1（`design.md:123-134,290,314`） | 未越界。 |
| N4 | 不做 Web IM 设置页 | source/M1 范围无 IM/frontend（`design.md:10-26,310-314`） | 未越界。 |

#### 4. delta-spec

| ID | delta 原子 | 锚定/可观察性核实 | 结论 |
|---|---|---|---|
| Δ1 | ADDED：本地 config 拥有 macOS autostart + stable environment | canonical 尚无同名或等价 Requirement；target 是最窄 lifecycle area；5 个 Scenario 均由运维者观察运行方式/配置生效/值不外泄（delta `:5-35`） | ADDED 用法正确。 |
| Δ2 | ADDED：启用后系统保持运行 | canonical 尚无 login/crash/temporary-stop contract；3 个 Scenario 是节点/消息入口与重拉的外部结果（delta `:37-53`） | ADDED 用法正确。 |
| Δ3 | ADDED：apply failure 降级并如实失败 | canonical 尚无这一 failure contract；THEN 暴露单实例、运行方式、错误与 exit status（delta `:55-62`） | ADDED 用法正确。 |
| Δ4 | MODIFIED：运维者用启停命令管理 Gateway | 精确锚定 canonical 同名 Requirement（canonical `docs/specs/gateway/service-lifecycle.md:22-58`）；完整保留 7 个 Scenario 并只扩展 mode/stop/restart/status，未静默删场景（delta `:66-111`） | MODIFIED 用法正确。 |
| Δ5 | REMOVED=无 | 与范围一致（delta `:113-115`） | 正确。 |
| Δ6 | package entry carrier | 合并后 lifecycle area 将由 7 个 Requirement 增至 10 个，而 package entry 仍声明 7（`docs/specs/gateway/spec.md:19-23`）；docs-check 会逐项比较声明数与实际标题（`scripts/docs_check.py:477-484,653-663`） | 不完整，见 R1-C1。 |

#### 5. milestone

| ID | 核实项 | 结论与证据 |
|---|---|---|
| feat-542-M1 | 单 M、垂直性、范围交集、两轨退出 | 单 M 合理，无横切或并行碰撞；reviewer 轨覆盖用户旅程，worker 轨覆盖 config/plist/launchctl/lifecycle/CLI/regression/quality（`design.md:310-314`）。但 scope 漏 package entry carrier 与两处 current 产品文档（R1-C1/R1-W2）；runbook 的 interpreter path 与 repo worktree 约定冲突（R1-W4）。 |

### 整体判断

- **给人的上层**：架构图和 7 条一句话决策能直接看懂“CLI 不变、lifecycle 选模式、mac module 管 launchd、两条后台路径共用前台 runtime”，没有被 grounding 细节淹没。
- **接口与数据流**：config -> lifecycle -> launchd/detached -> foreground -> SDK/IM 主流闭合；managed startup failure -> bootout/prove -> detached -> nonzero 也闭合。断口在 transient CLI controls（R1-C2/R1-W1）与 bootout/remove failure（R1-C3）。
- **完整性/自洽**：标题、对齐、unit branch、空 Changelog、delta inventory、风险表、M1 骨架齐全，无模板注释/TBD；图与正文命名一致。
- **常驻服务 runbook**：有 stop/start/health 与真栈前置、隔离和 cleanup，满足常驻服务必须给 reviewer 命令的要求；但 `<unit-worktree>/.venv` 并非本仓保证，见 R1-W4。

### 四角度架构进攻

| 角度 | 主动攻击 | 发现与长远代价 |
|---|---|---|
| 1. 归属 | 分别尝试把策略放 CLI、把 launchctl 放 lifecycle、把 config 放 plist、让 IM 管 Gateway | design 当前主归属正确：CLI 只呈现、`process_lifecycle` 持跨模式不变量、concrete mac module 持 OS 机制、YAML 持稳定意图，依赖仍是 PA -> SDK。但把一次性 `--im-service-url` 固化进 plist 会让 OS 定义成为第二份长期 runtime config（R1-W1）；遗漏 `--auto-bind` 则让 CLI owner 的既有控制无法到达真实 child（R1-C2）。 |
| 2. 该不该存在 | 删除 `macos_launch_agent`、删除 renamed result、改用通用 ServiceManager | mac module 不能删：删除后 plist/domain/launchctl transaction 会污染 lifecycle；一个具体实现足够，通用 port/noop adapter 是 YAGNI。结果对象增加 effective mode/error 也有真实 CLI consumer，不是空包装。无新增 Issue。 |
| 3. 深还是浅 | 对比 module interface 与隐藏复杂度；搜索仓内已有 launchd/helper | 三个 lifecycle 动作能隐藏 label/plist/XML/domain/命令/原子文件更新，接口明显小于实现；仓内无同类轮子。问题在于“从当前会话停止/永久移除”的行为契约还不够深：not-loaded、bootout error、delete error、kill timeout 被留给调用方猜，复杂度会重新泄漏回 lifecycle（R1-C3）。 |
| 4. 治本还是补丁 | 比较 direct foreground vs wrapper/tmux；检查是否新增 shadow state/临时特例 | direct foreground + KeepAlive 与 YAML environment 是治本；它去掉了 shell snapshot 和 daemonizing launcher。把 optional IM override 留在长期 plist 是 shadow-config 补丁，会造成跨登录陈旧目标与排障双真相（R1-W1）；漏 current shipped docs 会让修复后的产品继续自述旧拓扑（R1-W2）。 |

### Issues

- [R1-C1][CRITICAL] [delta-spec / Milestone feat-542-M1] **新增 3 个 lifecycle Requirement，却没有 `docs/specs/gateway/spec.md` 的 delta carrier，也没有把 package entry 纳入 M1。** 当前 Gateway entry 声明 Service Lifecycle 有 7 个 Requirements（`docs/specs/gateway/spec.md:19-23`）；本 delta 是 3 ADDED + 1 MODIFIED，所以归并后实际数应为 10。`scripts/docs_check.py:653-663` 会把声明数与 area 标题数机械比较。**不改的坏事**：worker 按冻结范围只归并 lifecycle area 后，canonical index 立即 drift 且 docs-check 必失败；若 worker 越过 M1 临时补 entry，又违反设计冻结并使 orchestrator 无法按 delta 对账。请增加 `specs/gateway/spec.md` 的最小 MODIFIED carrier（或在本仓既定规则允许的等价载体）并把 canonical package entry 纳入 M1。

- [R1-C2][CRITICAL] [决策 1/2/6 / service argv] **launchd 路径没有保住既有 `--auto-bind` / `NANO_MULTIAGENT_AUTO_BIND=1` 行为。** 当前 CLI 在 default start 接到 `--auto-bind` 后只把它写入 parent environment（`src/personal_assistant/main.py:58-64,91-92`），当前 detached `Popen` 会继承该 environment（`src/personal_assistant/gateway/process_lifecycle.py:722-731`）；binding consumer 只读该 env（`src/personal_assistant/gateway/im_bootstrap.py:153-179`）。canonical 仍要求 env 或 flag 能自动确认节点（`docs/specs/gateway/service-lifecycle.md:178-185`）。设计已经正确指出 LaunchAgent 不继承启动 shell，但 plist 只允许派生 `PYTHONPATH`，service definition 的显式输入只列 config 与 optional IM override（`design.md:160-164,235-237`）。**不改的坏事**：macOS 缺省 autostart=true 后，`... main --auto-bind` 会启动一个不带 auto-bind 的真实 Gateway，首次节点反而打开浏览器/等待人工确认；现有 contract 与自动化入口静默回归，且当前测试只覆盖 consumer env，容易全绿漏过。请拍死 transient control 的传播方式及其 crash/login 生命周期，并把回归纳入 M1；不能靠复制整份 shell environment。

- [R1-C3][CRITICAL] [决策 5/7 / stop-disable flow] **`bootout` / permanent remove 的失败与时限语义未设计，导致 explicit disable 和人工 stop 的关键终态要由 worker 猜。** D5 只写“bootout 后 stop、false 时 bootout+删 plist”，flow 只有成功边；D7 只覆盖 enable 的 write/bootstrap/start-confirmation failure（`design.md:148-183,239-261`）。但首次/重复 remove 必须区分 not-loaded（应幂等）与真实权限/command failure；bootout 失败时若继续 signal/detached，会被 KeepAlive 重拉或产生双实例；bootout 成功但 plist 删除失败时，下次 login 仍会自启却可能被报告 disabled。另 `launchd.plist(5)` 的 `ExitTimeOut` 决定 job stop 时 SIGTERM 到 SIGKILL 的等待，而现有 `gateway.shutdown_grace_seconds` 是 canonical lifecycle timing（`docs/specs/gateway/service-lifecycle.md:75-83`; code default/consumer `src/personal_assistant/config/local_store.py:293-305`; `src/personal_assistant/gateway/process_lifecycle.py:390-398`），当前 service definition 未说明是否映射。**不改的坏事**：两个 worker 会分别选择“失败仍 detached”“直接报错”“保留/删除 plist”等不兼容架构；其中一些选择会虚假满足关闭、立即重拉、留下下次登录自启或提前 SIGKILL 活动运行。请给 stop-current-session 与 permanent-remove 各自拍死 success/idempotent/failure postcondition、单实例 gate、CLI 结果，并说明 launchd stop timeout 如何遵守现有 config。

- [R1-W1][WARNING] [决策 1/6 / 架构进攻-归属与治本] **`--im-service-url` 被固化进 plist，悄悄把一次性 override 变成跨 crash/登录的第二份长期配置。** current docs 明确它“只覆盖本次启动连接的 IM 地址”（`docs/operations/gateway.md:70-78`; bundled docs `src/personal_assistant/builtin_skills/nanoassistant-docs/references/getting-started.md:62-72`），但 D6 让 persistent service definition 保存 optional IM override（`design.md:160-169`）。**不改的坏事/长远代价**：用户曾临时指向测试 IM 后，下一次登录仍可能从 plist 连接旧地址，而 YAML 显示另一个地址；排障必须检查 YAML + plist 两份 runtime truth，并且这是 spec 未批准的行为变化。请明确其生命周期：要么保留 current one-launch 语义并设计 crash recovery 后的来源，要么把持久化语义回到 spec 与用户确认，不能静默改文档掩盖。

- [R1-W2][WARNING] [现状分析 / Milestone feat-542-M1] **current 文档更新面漏了两个真实消费者。** `docs/operations/local-stack.md:50` 仍把默认启动写成 detached child；随包 `nanoassistant-docs` 是产品问题的默认说明书（`src/personal_assistant/builtin_skills/nanoassistant-docs/SKILL.md:1-16`），其 getting-started 仍写后台 child 与旧反馈（`references/getting-started.md:56-72`）。二者都不在 `design.md:22-24,314` 的范围。**不改的坏事**：实现和 canonical 归并后，用户及 Agent 仍会从 current 权威入口得到旧进程模型/反馈，造成启动与排障误判。请补进现状清单和 M1；其余全仓搜索命中可按是否真的陈述 default lifecycle 再裁剪。

- [R1-W3][WARNING] [结果 interface / 非 macOS边界] **`autostart_status = enabled | disabled | failed` 无法无歧义表达“非 macOS 不适用且保持旧后台行为”。** design 同时要求 autostart default=true、其他平台沿用 detached、且本期不宣称跨平台服务（`design.md:189-199,290`）。**不改的坏事**：worker 只能猜 Linux 应返回 `disabled`、`failed`、省略输出还是让 CLI 自查平台；前两者会把 true 配置说成关闭或让正常启动非零，后者又把平台策略漏回 CLI。请在 result contract/CLI observable output 中拍死 non-mac 状态（可用明确的 not-applicable 语义，或说明为何不需新状态）并纳入 worker test。

- [R1-W4][WARNING] [Runbook for Reviewer] **启动命令假定 `<unit-worktree>/.venv/bin/python` 存在，与仓库 worktree 契约和 production 路径不一致。** `design.md:295-308` 给出的唯一真栈启动命令使用 unit worktree 内 `.venv`；本仓只保证当前环境已安装依赖，worktree 无独立 `.venv` 时复用主 checkout（`docs/development/worktree-runtime.md:23-28`），production skill 更明确要求 worktree 使用主仓绝对 interpreter（`.claude/skills/prod-fleet-deploy/SKILL.md:42-45`）。**不改的坏事**：reviewer 按 runbook 在常见 unit worktree 会在进入 launchd 验收前就 `No such file`，Gate 2 虽有 runbook 却不可直接执行。请把解释器参数改成派发时真实可用的绝对 project interpreter，并保留 worktree `PYTHONPATH`/cwd 的绝对指向。

### Recommendations

- [R1-R1] 在修订 service definition 时把 `Program`/`ProgramArguments`、`WorkingDirectory`、`EnvironmentVariables`、stdout/stderr、`KeepAlive`、stop timeout 的来源列成一张小表；这会让 worker 与 reviewer 对 transient/persistent inputs 一次对清，但不要求写 plist 代码。
- [R1-R2] 真 LaunchAgent evidence 只记录 label、路径、PID/birth、exit status 与清理结果；继续禁止把 `gateway.environment` 的值或 secret-bearing config 内容写进报告。

### Author Resolutions

| 项目 | Resolution | 判真证据与修订位置 |
|---|---|---|
| R1-C1 | accepted | canonical `docs/specs/gateway/spec.md` 的 Service Lifecycle 计数确为 7，而 area 将净增 3。新增 `specs/gateway/spec.md` index delta（目标 10），并把 index delta/canonical entry 加入 `design.md` 的涉及范围、delta 清单和 M1 范围。 |
| R1-C2 | accepted | current `--auto-bind` 只经 parent env 到 detached child，LaunchAgent 不会继承。`design.md` 的决策 1/6、配置与结果 interface、LaunchAgent 定义和 M1 现显式传 `auto_bind`，并用当前登录临时 bootstrap plist 传播，稳定 plist 不持久化该控制。 |
| R1-C3 | accepted | stop/disable 的错误会决定是否重拉或产生双实例，属于设计契约。`design.md` 决策 5、macOS module interface、流程图和风险表现区分 idempotent absence 与真实错误，失败不 signal/不 replacement/不虚报；`ExitTimeOut` 映射现有 shutdown grace。首文档与 service-lifecycle delta 增加 stop/disable 失败场景。 |
| R1-W1 | accepted | current docs 将 IM override 定义为本次启动。`design.md` 决策 6 改为稳定 plist 只读 YAML；本次 override 仅进入当前 GUI-domain 临时 bootstrap definition，临时文件立即删除，bootout/重新登录后回到稳定 config。 |
| R1-W2 | accepted | 两份命中文档确属 current 运维/随包产品说明。已将 `docs/operations/local-stack.md` 与 bundled getting-started 加入现状范围和 M1。 |
| R1-W3 | accepted | 三态结果不能表达非 macOS 兼容路径。`GatewayLaunchResult` 设计增加 `not_applicable`；非 macOS 不调用 macOS module、不增加自启输出并保持既有 detached 行为，M1 增加回归要求。 |
| R1-W4 | accepted | unit worktree 不保证自有 `.venv`。Runbook 已改用当前可用的绝对 project interpreter `/Users/czj/Repos/nano-multiagent/.venv/bin/python`，仅以 unit worktree 提供 cwd/PYTHONPATH。 |
| R1-R1 | accepted | `design.md` 新增 LaunchAgent 定义表，逐项列明 Program/argv、WorkingDirectory、PYTHONPATH、stdout/stderr、KeepAlive、ExitTimeOut 及稳定/临时来源。 |
| R1-R2 | accepted | Runbook 与 M1 明确真栈证据只保留 label/path/PID/birth/status/cleanup，继续禁止记录 config environment 值或 secret。 |

## Round 2

### Metadata

- reviewer: `/root/feat_542_design_reviewer`
- review_mode: `full`
- mode_reason: R1 后不仅补了证据或措辞，还新增了首文档的 disable/stop failure Scenario，修改了 shared service-lifecycle contract、CLI control 传播、macOS module postcondition、结果 interface、plist data flow 与 M1 范围；这些变化触及需求、共享契约和跨模块数据流，按规则从可考虑的 delta 升级为 full，重新核全部五类承重原子与四个架构进攻角度。
- started_at: `2026-09-03T16:21:14+08:00`
- completed_at: `2026-09-03T16:28:11+08:00`
- duration: `6m57s`

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

R1 的 index carrier、stop/remove 失败、临时 override、文档范围、非 macOS 结果、runbook
解释器和 evidence 约束均已实质落位；主架构仍然正确。剩余一处是新 `gateway.environment`
与显式 `--auto-bind` 的优先级/应用顺序没有闭合，worker 仍会在一个受支持的配置冲突上猜。
按本仓 Gate 2 必须 `0 CRITICAL / 0 WARNING` 的规则，本轮尚不能进入 `change-orchestrator`。

### Coverage

- 首文档：`spec.md`；5 个 Requirement、13 个验收 Scenario、11 条澄清决定、5 段用户场景、4 条非目标。
- 设计：`design.md`；20 条现状/约束/grounding/复用/历史断言、7 个编号决策、配置/结果/module/plist interface、start/restart/stop/失败/部署数据流、9 条风险、reviewer runbook。
- delta-spec：`specs/gateway/spec.md` 的 1 个 package-index MODIFIED carrier；`specs/gateway/service-lifecycle.md` 的 3 个 ADDED Requirement（10 个 Scenario）、1 个 MODIFIED Requirement（完整保留并扩为 8 个 Scenario）、REMOVED=无。
- milestone：唯一 `feat-542-M1` 与根目录下 `M1-macos-gateway-autostart/.gitkeep` 骨架。
- 独立证据：重新从 `personal_assistant.main` 正向追 default/foreground/stop/restart 到 `gateway.process_lifecycle.run_gateway`、detached launcher 与 `compose_gateway`；复核 typed config parse/save/writeback、auto-bind consumer、PID/process-birth/lock/signal、canonical gateway area/index、current 运维与随包文档、历史 owner 边界、本机 `launchd.plist(5)` / `launchctl(1)`。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 新增 gateway index delta，目标计数 10，并纳入 M1 | carrier 已存在且只改 Service Lifecycle 行（`specs/gateway/spec.md:1-7`）；current area 7 个 Requirement，本 delta 净增 3，10 与 `scripts/docs_check.py:653-663` 的派生口径一致；design inventory/M1 均纳入两份 canonical（`design.md:27-29,328-333,370`） | closed |
| R1-C2 | transient `--auto-bind` 进入普通 child argv/临时 bootstrap definition，稳定 plist 不持久化 | 原先“managed child 完全收不到 flag”的缺口已补（`design.md:174-186,216-220,242-250,370`），但 `gateway.environment` 与显式 flag 的同名优先级仍冲突，见 R2-W1 | partially closed → R2-W1 |
| R1-C3 | 区分 idempotent absence、真实 bootout/delete failure；fail closed；映射 `ExitTimeOut` | D5、module interface、流程/风险和两份行为文档一致规定：not-loaded/missing 成功，真实错误非零且不 signal/replacement/虚报；`ExitTimeOut=max(1, ceil(shutdown_grace_seconds))`（`design.md:152-170,229-250,289-315,337-346`; `spec.md:87-90,129-132`; delta `:27-31,100-104`） | closed |
| R1-W1 | IM URL override 只进入当前 login 的临时 bootstrap definition | stable plist 无 override，temporary 文件调用后删除；当前 job crash 重拉沿用，bootout/新 login 回到 YAML（`design.md:172-191,242-250,284-287`），与 current “for this launch” 来源一致（`src/personal_assistant/main.py:49-52`） | closed |
| R1-W2 | 纳入 local-stack 与 bundled getting-started | 两者进入现状清单和唯一 M1；定向搜索到的 current detached 叙事均已落在 M1 的 README/gateway/local-stack/bundled/deploy-skill 范围（`design.md:22-29,370`） | closed |
| R1-W3 | 结果增加 `not_applicable`，非 macOS 保留旧输出 | result contract 明确四态，非 macOS 不调用 mac module、不打印 autostart 三态且走 detached；M1 有对应 worker 退出项（`design.md:222-227,346,370`） | closed |
| R1-W4 | runbook 使用主仓绝对 interpreter | stop/start 都使用 `/Users/czj/Repos/nano-multiagent/.venv/bin/python`，cwd/PYTHONPATH 仍指向 unit worktree（`design.md:349-354`），符合 worktree 可复用主仓环境的约束（`docs/development/worktree-runtime.md:23-28`） | closed |
| R1-R1 | 增加稳定/临时 plist source table | 表已覆盖 Label、Program/argv、cwd、environment、stdio、KeepAlive、ExitTimeOut（`design.md:240-250`） | adopted |
| R1-R2 | evidence 禁止 environment/secret | M1 明确 evidence 不含 config secret，runbook 前置禁止读写生产 config，并限定检查 label/path/PID/birth/status/cleanup（`design.md:319-326,361-364,370`） | adopted |

### 核实台账

#### 1. 现状断言

| ID | 承重原子 | 本轮核实动作与证据 | 结论 |
|---|---|---|---|
| S1 | `main.py` 只解析/分派 lifecycle，现有结果仅 PID/IM/log | 从 `main()` 的四个分支正向追到 lifecycle（`src/personal_assistant/main.py:39-120`），结果 dataclass 仅三字段（`gateway/process_lifecycle.py:74-86`） | 成立 |
| S2 | `process_lifecycle.py` 是生产唯一 lifecycle owner | default/restart/stop/foreground 均从 `main.py:94-113` 进入该模块；lock、start、stop、restart 与 foreground runtime 在 `process_lifecycle.py:120-398,442-455` | 成立，不是测试死实现 |
| S3 | `local_store.py` 是 typed parse/save/writeback owner | dataclass/parser/serializer 在 `config/local_store.py:293-356,910-1111,1527-1556`；`RuntimeConfigOwner.persist` 在 `:359-397`，生产 token/config sync 使用同 owner 与 sensitive writer（`auth/im_auth_client.py:163-218`; `gateway/agent_config_sync.py:780-810,1437-1455`） | 成立；新字段必须全链路 round-trip |
| S4 | current docs/skill 仍讲 detached/manual lifecycle | 对 README、operations、bundled docs、deploy skill 定向搜索；旧叙事实存于 `README.md:75-118`、`docs/operations/gateway.md:50-100`、`local-stack.md:46-55`、bundled getting-started `:56-72` 与 deploy skill `:73-80,113-170` | 成立；修订后的范围已完整承载命中项 |
| S5 | 唯一行为增量是 gateway service-lifecycle，index 需 7→10 | current index 指向 7（`docs/specs/gateway/spec.md:19-23`）；current area 实数 7；delta 是 3 ADDED + 1 MODIFIED（delta `:3-128`） | 成立；新增 index carrier 正确 |
| S6 | 变更闭合在 PA，保持 PA→`agent.sdk` 与 IM 独立 | 依赖红线见 `SPEC.md:132-160`；生产 composition 仍由 PA 经 SDK，定向 import 搜索无 PA→agent internals/IM 产品包 | 成立 |
| S7 | `--foreground` 是 debug/E2E/外部 supervisor 入口且不能管理 LaunchAgent | foreground 直达 `run_gateway`（`main.py:104-108`）；worktree 真入口固定外部管理 `--foreground --auto-bind`（`scripts/e2e-up.sh:322-336`） | 成立；D1/D2 均保留不安装服务 |
| S8 | 同 config 生命周期由 lock 串行，state/birth 保单实例 | lock 由 resolved config 派生（`process_lifecycle.py:442-455`）；start 查 live state（`:214-243`），restart 同锁 stop+start（`:304-335`），signal 前复核 birth（`:627-653`） | 成立 |
| S9 | config/plist/log/state 属运行数据；production 换向须保护 dirty worktree | 仓库红线与 deploy skill 的 dirty/new-worktree 验证边界一致；设计只把 plist 放用户 LaunchAgents、把 log/state 放 config 目录（`design.md:39-41,242-250,317-326`） | 成立 |
| S10 | 只支持当前登录用户 GUI domain | spec 锁定 login-after/no-root/no-cross-platform（`spec.md:29-35,148-156`）；本机 `launchctl(1)` 定义 `gui/<uid>` 为 GUI login domain | 成立 |
| S11 | current background 是 detached child，startup confirmation 非 readiness | child 为 `Popen(... start_new_session=True)`（`process_lifecycle.py:722-731`）；foreground 在 runtime 前写 state（`:120-169`），parent 只等 state/birth/live（`:734-761`）；canonical `:22-29` 同口径 | 成立 |
| S12 | current 无 login autostart/crash recovery | canonical lifecycle 的 7 个 Requirement 无登录/异常重拉；`src/personal_assistant` 无 launchctl/plist 实现 | 成立，无 drift |
| S13 | duplicate start、atomic restart、fail-closed stop 仍是 current contract | 分支在 `process_lifecycle.py:219-243,327-387,576-653`；modified delta 完整保留这些 Scenario（delta `:89-124`） | 成立 |
| S14 | `run_gateway()` 是 launchd 可直接监督的长期前台入口 | 同一入口加载 config、写 PID/birth state、安装 signal handler、`run_forever` 并 expected-state cleanup（`process_lifecycle.py:120-169,797-828`） | 成立，落点在生产路径 |
| S15 | detached launcher 可保留为 false/fallback 路径 | 它只构造 foreground argv、spawn、等 state 后返回（`process_lifecycle.py:204-280,706-761`） | 成立，无需复制 runtime |
| S16 | lock/state/birth/signal cleanup 可共享，无第二份 PID truth | state 唯一路径、原子写与 expected remove 在 `process_lifecycle.py:656-703`；identity/signal 在 `:627-653` | 成立 |
| S17 | 一个 concrete `macos_launch_agent` 深 module 合理 | 全仓无既有 launchd helper；删除该 module 会让 label/plist/XML/domain/bootstrap/bootout/atomic-write 全回流到 lifecycle，设计只暴露三个机制动作（`design.md:63-66,229-238`） | 成立，不需通用 port |
| S18 | refactor-461 冻结 no-readiness 并保留 Gateway process ownership | archive reviewer 从生产入口确认 PID confirmation 与 readiness 分离、保留真实 background/process-group 边界（`archive/refactor-461-dead-kernel-subprocess-seam/design-review.md:11-18`）；现行 S11/S14 仍一致 | 成立 |
| S19 | refactor-470 已分离 CLI/lifecycle/composition owner | archived M3 progress 记录入口只分派、生命周期迁入具名 owner；现行 `main.py:94-113` 与 `process_lifecycle.py:824-828` 仍按该结构 | 成立 |
| S20 | KeepAlive 不应监督会 daemonize 的 launcher | 本机 LLM proxy 历史记录该失败形态（`/Users/czj/Repos/LLM_PROXY/docs/macos-autostart-zh.md:115-123`）；`launchd.plist(5)` 明确 KeepAlive 持续保持 job | 成立；直管 foreground 是正确根治 |

#### 2. 编号决策

| ID | 决策 | 四问结论与证据 |
|---|---|---|
| D1 | YAML 拥有 autostart + stable environment，config 值覆盖同名 process env | ownership/spec 驱动成立，typed owner 与不复制 shell/plist 也自洽（`spec.md:43-45,102-108`; `design.md:99-112,209-220`）；但与显式 auto-bind 的优先级未拍死，见 R2-W1 |
| D2 | launchd 直接监督 foreground Gateway，KeepAlive=true | 已拍死；`run_gateway` 是真实长期入口，本机 man page 支持 KeepAlive/ExitTimeOut/默认 process-group cleanup；拒绝 detached wrapper/tmux 与 LaunchDaemon 有事实依据（`design.md:114-125`） |
| D3 | lifecycle 持策略，macOS module 持机制 | owner、三个动作与 internal command seam 清楚；没有跨平台 ServiceManager，和现有分层一致（`design.md:127-138,229-238`） |
| D4 | running bare start 拒绝，restart 才替换 | 与 spec Q10/current error path一致，应用边界为 stopped start/restart（`spec.md:47-49,92-100`; `design.md:140-150,252-315`） |
| D5 | stop 暂停当前 login；false 才永久 remove | success/idempotent/error postcondition、CLI nonzero、replacement gate 与 timeout 已拍死且互不矛盾（`design.md:152-170,229-250,289-315`） |
| D6 | resolved config 派生稳定 label/plist；transient controls 用临时 definition | identity、stable/temp source、cleanup、crash vs bootout/login 生命周期已明确（`design.md:172-191,240-250`）；IM override shadow-config 已消除，auto-bind precedence 见 R2-W1 |
| D7 | enable apply 失败安全撤销后 detached fallback + nonzero | rollback/prove-no-managed/single-instance gate、原错误与 CLI status 完整；不能证明安全时 fail closed（`design.md:193-203,289-308`） |

D2-D7 之间未发现新增结构冲突：restart 先完成 D5 stop，再走 D6 apply；D7 fallback 只有在
managed owner 已撤销后才进入 D3 保留的 detached 路径。唯一未闭合的是 D1 与 D6 对同名
auto-bind 来源的优先关系。

#### 3. spec 约束

##### 澄清决定

| ID | spec 原子 | 本轮覆盖核实 |
|---|---|---|
| Q1 | 只管理 Gateway | topology、delta inventory、M1 均不接管 IM/LLM（`design.md:78-95,328-333,370`），覆盖 |
| Q2 | 缺省 autostart=true | D1/config interface/delta `:5-19` 均明确，覆盖 |
| Q3 | stopped start 或 restart 应用 | D4 和两张 flow 明确，覆盖 |
| Q4 | login 启动 + crash 恢复 | D2 KeepAlive、delta `:43-59`、M1 reviewer 轨，覆盖 |
| Q5 | stop 仅当前 login；下次恢复 | D5 保留 stable plist、delta `:55-59`，含失败边界，覆盖 |
| Q6 | 仅 macOS | constraints、not_applicable 与 M1 非 macOS regression，覆盖 |
| Q7 | login 后 user agent，无 root/pre-login | D2 GUI domain/LaunchAgent，覆盖 |
| Q8 | enable 失败 detached 可用且明示降级 | D7/result/failure flow，覆盖；unsafe rollback 明确 fail closed |
| Q9 | stable environment 入 YAML，不复制 shell | D1、plist source table与 secret risk，覆盖 |
| Q10 | running bare start 保留 already-running | D4/current single-instance path，覆盖 |
| Q11 | degraded running 仍 exit nonzero | D7/result contract/delta `:61-68`，覆盖 |

##### 用户场景

| ID | 场景 | 设计落点与结论 |
|---|---|---|
| U1 | config 单入口、默认开、stopped start/restart 应用 | D1+D4+start flow（`design.md:99-112,140-150,252-282`），覆盖 |
| U2 | 两后台模式共享 stable environment，plist 不复制 shell | D1+run_gateway apply+definition table（`design.md:209-220,240-250,284-287`），主路径覆盖；同名 auto-bind 例外未闭合（R2-W1） |
| U3 | login/crash 恢复、stop 暂停、false 长期关闭 | D2+D5+failure flow（`design.md:114-125,152-170,289-315`），覆盖 |
| U4 | enable failure 保持可用、clear error、nonzero | D7/result/fallback（`design.md:193-203,222-227,300-307`），覆盖 |
| U5 | 外部基础设施独立生命周期 | architecture/non-goals/M1 reviewer 轨，覆盖且未越界 |

##### Requirement 与 Scenario

| ID | 原子 | 设计核实与结论 |
|---|---|---|
| P1 | 配置选择 Gateway login autostart | D1/D4/D5 与双 flow 覆盖整个 Requirement |
| P1-S1 | 缺省开启 | `autostart=true` + managed true branch + enabled result（`design.md:101,213,266-275`），覆盖 |
| P1-S2 | 显式开启 | 同 true branch，覆盖 |
| P1-S3 | 显式关闭→detached、下次不自启 | permanent remove 成功后才 detached/disabled（`design.md:154-165,276-280`），覆盖 |
| P1-S4 | disable 无法完整应用不虚报/不竞争 | remove false branch直接 nonzero/no replacement（`design.md:296-299,342`），覆盖 |
| P1-S5 | 只编辑不改变 applied mode | D4 仅 stopped start/restart apply，覆盖 |
| P1-S6 | running bare start 不替换并引导 restart | D4 + flow Live→Reject（`design.md:140-150,293-295`），覆盖 |
| P2 | stable runtime environment 归 config | D1/config interface，覆盖 |
| P2-S1 | detached/managed 同环境、config 优先、值不外泄 | run_gateway 统一 apply 与 stable plist boundary覆盖；但 CLI auto-bind 同名冲突见 R2-W1 |
| P3 | 开启后由系统持续在线 | D2 KeepAlive 与 foreground owner，覆盖 |
| P3-S1 | 新 login 自动上线 | user LaunchAgent + KeepAlive implicit load，reviewer 真栈重新 bootstrap retained definition，覆盖 |
| P3-S2 | crash 自动恢复 | KeepAlive 直接监督长期 foreground + expected-state cleanup（`design.md:114-125,310-315`），覆盖 |
| P4 | manual stop 与长期意图分离 | D5，覆盖 |
| P4-S1 | stop 当前 login 不重拉 | 先 print/bootout，失败不越过（`design.md:310-315`），覆盖 |
| P4-S2 | stop bootout 失败 nonzero/no false stop/replacement | module postcondition + D5 failure语义（`design.md:161-168,231-235`），覆盖 |
| P4-S3 | 保留 plist 使下次 login 恢复 | D5 stable definition retained，覆盖 |
| P5 | enable apply failure 可用且如实失败 | D7，覆盖 |
| P5-S1 | safe rollback→one detached + error + nonzero | failure flow 与 result contract完整（`design.md:193-203,222-227,300-307`），覆盖 |

##### 非目标

| ID | 非目标 | 核实 |
|---|---|---|
| N1 | 无 pre-login/root LaunchDaemon | 只用 user GUI domain（`design.md:42-43,114-123`），未越界 |
| N2 | 不管理 IM/LLM/SearXNG 生命周期 | 图与 M1 只改 Gateway；environment 仅提供地址/运行条件，未接管服务，未越界 |
| N3 | 无 systemd/Windows/cross-platform abstraction | D3 明拒通用 port，非 macOS detached + not_applicable，未越界 |
| N4 | 无 Web IM setting page | M1 无 IM/frontend，config file 是唯一入口，未越界 |

#### 4. delta-spec

| ID | delta 原子 | 锚定、用法与可观察性核实 |
|---|---|---|
| ΔI1 | package index MODIFIED Service Lifecycle row | 只更新 covers 与 7→10，链接命中同目录 area；格式与既有 index delta 惯例一致（`specs/gateway/spec.md:1-7`），正确 |
| ΔA1 | ADDED：login autostart + stable environment | canonical 无等价 Requirement，service-lifecycle 是最窄 target；ADDED 正确（delta `:5-9`） |
| ΔA1-S1 | default true | THEN 是 managed mode/status，消费者可观察，覆盖 |
| ΔA1-S2 | explicit true | 同上，覆盖 |
| ΔA1-S3 | explicit false | THEN detached/status/next-login，覆盖 |
| ΔA1-S4 | disable apply failure | THEN nonzero/no false disabled/no competing process，外部可观察且与 D5一致 |
| ΔA1-S5 | edit-only no apply | applied mode/status 可观察，覆盖 |
| ΔA1-S6 | two modes share config environment | runtime/child behavior与不外泄可观察；一般优先级有 D1落点，但 auto-bind 同名交集见 R2-W1 |
| ΔA2 | ADDED：enabled Gateway system-kept | canonical 无 login/crash/temporary-stop contract，ADDED 正确（delta `:43-59`） |
| ΔA2-S1 | next login auto-run | node/message entry observable，覆盖 |
| ΔA2-S2 | crash relaunch | new PID/process恢复入口 observable，覆盖 |
| ΔA2-S3 | stop only current login | no immediate relaunch + next login observable，覆盖 |
| ΔA3 | ADDED：apply failure degraded/nonzero | canonical 无等价 failure contract，ADDED 正确（delta `:61-68`） |
| ΔA3-S1 | safe rollback then detached + original error + nonzero | 结果全部是 operator-observable，没有函数/类/日志串断言，覆盖 |
| ΔM1 | MODIFIED exact canonical title：运维者用启停命令管理 Gateway | 精确锚 `docs/specs/gateway/service-lifecycle.md:22`；原 7 个 Scenario 全保留并新增 stop failure，MODIFIED 用法正确（delta `:70-124`） |
| ΔM1-S1 | default background/status/readiness boundary | 泛化 detached/managed且保留 PID+birthday/no-readiness，忠实 |
| ΔM1-S2 | duplicate start | 保留原错误/不替换，忠实 |
| ΔM1-S3 | stop graceful→SIGKILL/state cleanup | 保留原 Scenario并加 managed auto-relaunch stop，忠实 |
| ΔM1-S4 | stop service failure fail-closed | 新增外部 failure result，与首文档一致 |
| ΔM1-S5 | lifecycle commands serialized | 原样保留并扩成 apply target mode，忠实 |
| ΔM1-S6 | signal only proven process | 原三条 THEN 全保留，忠实 |
| ΔM1-S7 | active work drains before exit | 原样保留，忠实 |
| ΔM1-S8 | earliest real failure retained | 原样保留，忠实 |
| ΔR | REMOVED=无 | 与目标只新增/泛化行为一致，正确 |

所有 delta Scenario 的 THEN 都以运维者、IM 节点/消息入口或进程结果为观察面；未出现内部
symbol/call assertion。除 R2-W1 的跨契约优先级外，没有 ADDED/MODIFIED 误用或 silent
Scenario deletion。

#### 5. milestone

| ID | 核实项 | 结论与证据 |
|---|---|---|
| feat-542-M1 | 垂直性、范围、两轨退出、骨架 | 单 M 无横切/并行碰撞；source/config/lifecycle/mac mechanism/tests/docs/delta/canonical 在一个端到端切片。reviewer 轨覆盖 13 个 spec 场景、transient controls、失败与 production 换向；worker 轨覆盖 config/plist/launchctl/lifecycle/output/regression/quality（`design.md:366-370`）。`M1-macos-gateway-autostart/.gitkeep` 存在且为空，符合设计阶段骨架。仅缺 auto-bind 与 environment 同名冲突的明确退出用例（R2-W1）。 |

### 整体判断

- **给人的上层**：架构图和 7 条粗体结论可直接读出“CLI→唯一 lifecycle policy→launchd/detached→同一 foreground runtime”；source table把 stable/temp definition 区别讲清，没有被实现步骤淹没。
- **接口与数据流**：config→lifecycle→mac/detached→foreground→SDK/IM、disable fail-closed、enable rollback/fallback、stop/restart 和 production 换向均闭合。唯一断口是 config environment 与 CLI auto-bind 在进入 `run_gateway` 时的 precedence（R2-W1）。
- **完整性/自洽**：标题、对齐、unit branch、空 Changelog、delta inventory、风险/回退、runbook、单 M 骨架齐；无模板注释/TBD，图/正文/module 命名一致。
- **常驻服务 runbook**：绝对 project interpreter + unit cwd/PYTHONPATH 可直接照搬；有真实 stop/start/health、隔离前置和 cleanup，且不读生产 config、不记录 environment 值。

### 四角度架构进攻

| 角度 | 主动攻击 | 发现与长远代价 |
|---|---|---|
| 1. 归属 | 尝试把 policy 放 CLI、OS command 放 lifecycle、stable config 放 plist、让 IM 管 Gateway；再叠加 transient control | 当前归属最自然：CLI 只呈现，lifecycle 持跨模式不变量，concrete mac module 持 OS transaction，YAML 持稳定意图，PA 仍只依赖 SDK。唯一泄漏是 auto-bind 先被 CLI 降成 env、再遇到 YAML env owner，优先级无人拥有；长期会让启动结果依赖实现顺序（R2-W1）。 |
| 2. 该不该存在 | 删除 `macos_launch_agent`、temporary plist、renamed launch result；改用 ServiceManager | mac module 删除后复杂度回流 lifecycle；launchctl bootstrap 需要 definition path，temporary plist 是承载本 login override 的最小机制且调用后删除；四态 result 有 CLI consumer。通用 ServiceManager/noop adapter 仍是 YAGNI。无新 Issue。 |
| 3. 深还是浅 | 比较三个 module 动作与隐藏细节；全仓搜索既有 launchd helper | interface 隐藏 label/path/XML/domain、atomic file、print/bootstrap/bootout/idempotency/stderr/cleanup，明显小于实现；仓内无可复用同类。stop/permanent remove 的错误 postcondition 已收入 module，不再泄漏给 lifecycle。无新 Issue。 |
| 4. 治本还是补丁 | 比较 direct foreground 与 wrapper/tmux；检查 shadow config、特殊状态和 evidence 泄密 | direct supervision + YAML environment 正面解决 daemonization 与 shell snapshot；临时 definition 消除了 IM override 的长期 shadow truth，`not_applicable` 消除了非 macOS 假状态。若不拍死 auto-bind precedence，R1 的修复只在“无同名 YAML key”时成立，是条件性补丁（R2-W1）。 |

### Issues

- [R2-W1][WARNING] [决策 1/6 / 配置与结果 interface] **`gateway.environment` 与显式 `--auto-bind` 的同名优先级和实际应用顺序仍未拍死，R1-C2 只闭合了传输、没有闭合消费。** D1 与新 spec 要求 config 值覆盖同名启动环境（`design.md:99-102`; `spec.md:102-108`; delta `:37-41`）；同时 interface 规定 foreground/managed child 收到 `--auto-bind` 后仍由 CLI 设置 `NANO_MULTIAGENT_AUTO_BIND=1` 再进入 `run_gateway()`（`design.md:216-220`）。current 生产路径确实先在 `main.py:91-92` 设置 env、后在 `:104-108` 调 `run_gateway`，而设计新增的 `gateway.environment` 要在该函数 composition 前覆盖 process env（`design.md:213-214`）；唯一 consumer 又只读这个 env（`gateway/im_bootstrap.py:153-179`）。因此合法配置若含 `gateway.environment.NANO_MULTIAGENT_AUTO_BIND`，worker 无法判断应让显式 flag 覆盖稳定 config，还是让 config 覆盖 flag；照当前文字顺序实现时，显式 `--auto-bind` 可被 YAML 值静默抹掉，违反 canonical 的 flag 行为（`docs/specs/gateway/service-lifecycle.md:178-185`）。**不改的坏事**：两个 worker 会实现不同 precedence；其中一条会让自动化明确传 `--auto-bind` 却仍打开浏览器/等待人工绑定，且 M1 现有“transient controls”测试不一定覆盖同名碰撞。请明确 precedence 与单一应用点（例如区分 inherited env 与 explicit CLI control，并说明是否允许该 reserved key 出现在 `gateway.environment`），同时把碰撞用例纳入 M1；无需扩大成通用配置优先级框架。

### Recommendations

无新增建议。R1-R1/R1-R2 已落实；本轮唯一事项应作为契约歧义修正，而不是非阻断建议。

### Author Resolutions

| 项目 | Resolution | 判真证据与修订位置 |
|---|---|---|
| R2-W1 | accepted | current `--auto-bind` 是显式 CLI control，不能被稍后加载的 YAML 静默取消。`spec.md` 与 service-lifecycle delta 现明确“显式 CLI control > Gateway 配置环境 > inherited environment”；`design.md` 决策 1 和 interface 把 effective environment 收口为 `run_gateway()` 单一应用点，foreground 不再预先写环境；M1 增加同名碰撞的 reviewer 与 worker 用例。 |

## Round 3

### Metadata

- reviewer: `/root/feat_542_design_reviewer`
- review_mode: `delta`
- mode_reason: 修订虽只针对 R2-W1，但新增了首文档/delta 的消费者可观察 precedence，并调整 `main → lifecycle → run_gateway` 的 control data flow，不是纯证据或措辞 closure；影响严格限于一个 Requirement Scenario、D1、environment interface 与 M1 对应用例，未改变需求范围、核心模块边界或 milestone 拆分，因此选择 delta。`retained_from: Round 2 — 除上述 precedence 链外，Round 2 的完整 inventory、D2-D7、其余 spec/delta 原子、module/plist/stop/fallback 架构进攻均未失效。`
- started_at: `2026-09-03T16:33:08+08:00`
- completed_at: `2026-09-03T16:34:05+08:00`
- duration: `57s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R2-W1 已实质关闭：显式 CLI control、稳定 YAML environment 与 inherited environment 的
优先级在行为契约、design interface、三种启动路径和两轨退出标准中一致，worker 不再需要
猜应用顺序。Gate 2 当前满足 `0 CRITICAL / 0 WARNING`，可进入 `change-orchestrator`。

### Coverage

- 重查 changed atoms：`spec.md` 的 stable environment Scenario、gateway service-lifecycle delta 的对应 Scenario、D1 precedence、`run_gateway()` effective-environment interface、reviewer runbook 与唯一 M1 的碰撞用例。
- 重查上下游：CLI parse → lifecycle launch/restart → detached argv 或临时 LaunchAgent argv → foreground `run_gateway(auto_bind=...)` → YAML environment 合成 → `im_bootstrap` env consumer。
- 重跑受影响的架构进攻角度：归属、治本性。其他角度与完整 inventory 继承 Round 2，未发现影响扩大，未升级为 full。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 显式 CLI > YAML > inherited；`run_gateway()` 单点合成；spec/delta/runbook/M1 同步 | 首文档明确显式 `--auto-bind` 不能被同名配置取消（`spec.md:102-109`），delta 用同一消费者可观察结果（`specs/gateway/service-lifecycle.md:37-42`）；D1 给出完整 precedence 和冲突示例（`design.md:99-115`）；interface 让 `main`/launcher 只传 `auto_bind`，由三种模式共同进入的 `run_gateway()` 先保留 inherited、再覆 YAML、最后显式 flag 强制为 `1`（`design.md:212-228`）。这与 current 唯一 consumer 只读 `NANO_MULTIAGENT_AUTO_BIND`（`src/personal_assistant/gateway/im_bootstrap.py:153-179`）相接，且不再沿用 current `main.py:91-92` 的提前写 env。runbook 与 M1 同时要求 YAML 同名冲突下的真栈与聚焦测试（`design.md:357-379`） | closed |

### Changed atoms 与波及链

| 原子 | 本轮核实动作 | 结论 |
|---|---|---|
| spec P2-S1 | 对照 R2-W1 的反例，逐条读 config>inherited、CLI>config 与不外泄三项 THEN（`spec.md:104-109`） | 三层优先级可观察且不互相矛盾；覆盖原 issue |
| delta ΔA1-S6 | 对照首文档和 canonical auto-bind Requirement（canonical `docs/specs/gateway/service-lifecycle.md:178-185`; delta `:37-42`） | 忠实承载新增 precedence，没有实现 symbol/call 断言 |
| D1 | 核是否只有结论、是否处理同名键、是否预造通用 framework（`design.md:101-115`） | 明确 `explicit CLI > YAML > inherited`，并以 `NANO_MULTIAGENT_AUTO_BIND` 反例拍死；显式拒绝扩大为通用参数框架 |
| environment interface | 从 current `main` 和唯一 consumer 正向追 proposed data flow（current `main.py:84-113`; `im_bootstrap.py:153-179`; design `:219-228`） | `auto_bind: bool` 保持为 typed control，只有最深公共入口 `run_gateway()` materialize env；default detached、managed temp definition 与 direct foreground 得到同一结果 |
| runbook / feat-542-M1 | 核 reviewer/worker 两轨是否都能防回归（`design.md:363-379`） | 真栈要求冲突配置下不打开浏览器/不等待人工绑定；worker 明列 precedence 聚焦测试，退出标准可验 |

完整波及链现为：用户显式 flag → `main` 解析 bool → lifecycle 明确传递 control → detached
argv / temporary plist 均带 `--auto-bind` → foreground 将 bool 交给 `run_gateway()` → inherited
environment 上覆盖 YAML → `auto_bind=True` 最后写 `NANO_MULTIAGENT_AUTO_BIND=1` → 既有
`im_bootstrap` consumer 自动确认。未带 flag 时最后一步不发生，YAML 仍能按新 spec 覆盖 inherited
environment；bootout/重新登录从不自动持久化本次 flag，R1-W1/C2 的生命周期结论保持有效。

### 受影响的架构进攻

| 角度 | 主动攻击 | 结论 |
|---|---|---|
| 归属 | 尝试把 precedence 留给 `main`、macOS module 或每个 launcher 各自实现 | `run_gateway()` 是三种模式在 consumer 前唯一共享的生产入口（current `process_lifecycle.py:120-148`），在此合成 effective environment 可避免三份分支逻辑；CLI/lifecycle 只传 typed intent，macOS module 不学习业务 env，归属正确 |
| 治本还是补丁 | 检查是否仅禁止一个 key、或在 managed path 特判 | 修订按统一三层 precedence 处理所有显式 CLI control 与 stable/inherited env 的关系，同时只把现有 `auto_bind` materialize 为其既有 env contract；没有增加 reserved-key registry、通用 override framework 或 macOS 特判，是对顺序根因的最小修复 |

### Validation notes

- unit 相关文件的 `git diff --check` / no-index whitespace check 无输出。
- `./scripts/docs-check` 仍只报 `docs/research/studies/README.md:9` 指向两个未跟踪 research 目录的既有 broken links；无 `feat-542-gateway-autostart` 路径问题，不计入本轮 finding。

### Issues

无。

### Recommendations

无。
