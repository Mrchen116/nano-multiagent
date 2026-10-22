# R5-W1 集成运行证据调查（工程输入，未关闭门禁）

> 更新索引：下列初始调查与03:07阻塞按当时事实保留。2026-10-22 09:14公开零Agent初始化恢复、09:21–09:28七文件串行37pass见文末“资源恢复与原期限串行补证”；它们是作者工程输入，尚未改写原独立R5-W1 NOT PASS或Q R3 FAIL。

## 固定版本与结论

- 受试产品、测试、fixture、锁文件仍为 `22114489ba131fbf847b60e0a4ca730d61471796`；本轮 executed_base 为 `18e1af8b1cd0834ae3f22f5780f2d50b740f5171`。原 executed_base 与 R1–R4 记录不改。
- 原 R5 报告 `db7c875efe3677e024bfcfe37df10d6b7cf57a12` 原样 cherry-pick 为 `22a5cbf25`，两份报告与原 commit 的逐字 diff exit0。[verification R5](../verification.md#round-5--final-integration-patch--corrected-delta) 的 **NOT PASS / 0C-1W-0S**、[code-review R5](../code-review-r5.md) 的 `[]` 和 corrected-delta 18/18 aligned 均保留。
- **尚未建立稳定集成运行通过，R5-W1 未关闭。** 当前已把最窄失败定位到公开 `initialize` 尚未返回；不能把六 Agent 测试的失败归结为 opt-out/restart，也不能声称其后的 HTTP 恢复、CC 超窗终态、history/model-policy/capabilities 已验证。
- 本轮无已确认产品源码缺陷、无修复提交、无 timeout/预算/fixture/assertion 放宽。未代 Q 给 PASS，未 canonical/archive/Ready PR、merge/deploy。后续 gate/effective_through 由原独立 reviewer 核收，本文不是 closure verdict。

## 有界探针与真实结果

全部在 unit 专属 worktree 运行，Node25.8.2 / pnpm11.7.0 / locked DSH0.2.1-alpha.1，单个 native 测试、一个 worker、禁止文件并行；`caffeinate -i` 只覆盖命令生命周期。未改永久电源设置或重启共享服务。

本地 gitignored `.e2e-feat625-r5-diagnostics/` 保存 `setup.ts`、`vitest.config.ts`、逐 RPC JSONL、native stderr 和 Vitest 原始结果。观察配置沿用仓库的 include/testTimeout，另设 maxWorkers=1/fileParallelism=false；setup 只包装 Nano 导出的 RuntimeClient/prepareProfile，转发原参数、原 onLog 和返回/错误，记录 pid、公开方法名、action、session/Agent 标识及起止时间，不导出 prompt/config。各测试自带 30s/25s 期限不变。

```bash
PROBE_RUN=context-alone caffeinate -i pnpm exec vitest run \
  --config .e2e-feat625-r5-diagnostics/vitest.config.ts \
  packages/dsh-integration/tests/agent-context-default.test.ts \
  -t 'defaults new and existing Agents'
```

- **exit1，1 failed /4 skipped，35.09s**；该测试原 30000ms 到期。
- prepareProfile113ms、spawn43ms，随后唯一公开 RPC 是 `initialize(agents=6)`；没有 `rpc-end`，没有进入 session.ensure、capabilities、插件开关或 restart。Vitest 到期不取消正在等待的 RPC，测试 finally 未完成，临时 home 仍在。

第二探针同测试/原30s期限，在已知初始化边界仅给 **Nano 自有 integration JS** 的 await 前后增加进程本地时间点（Node 公共 registerHooks）；不变更任何磁盘源码或 DSH package，不当成候选 PASS。命令与首探针相同，另加：

```bash
PROBE_RUN=context-boundary \
NODE_OPTIONS="--import=$PWD/.e2e-feat625-r5-diagnostics/trace-own-integration.mjs" \
caffeinate -i pnpm exec vitest run \
  --config .e2e-feat625-r5-diagnostics/vitest.config.ts \
  packages/dsh-integration/tests/agent-context-default.test.ts \
  -t 'defaults new and existing Agents'
```

- **exit1，1 failed /4 skipped，37.77s**；原测试仍30s超时，不延长等待换绿。
- 从 native spawn 到 initialize handler 首个时间点 **28719ms**；controller/fiber/knowledge/loader await 在其后40ms内返回。六个 preset register 的最后时间点是 spawn 后29584ms，不能把该时间当成完整初始化完成。
- worker 结束后 native 仍继续做真实 workspace mount；保留的最后 mount-refresh 时间点为 spawn 后48928ms。故“test timeout”不是“该进程已经关闭”，也没有证据在插件切换/重启阶段死锁。该诊断并未观察到 initialize 返回，不伪称其最终成功。

最窄 HTTP 对照（无 initial503，避免长退避与多次请求）使用首个观察配置：

```bash
PROBE_RUN=http-one caffeinate -i pnpm exec vitest run \
  --config .e2e-feat625-r5-diagnostics/vitest.config.ts \
  packages/dsh-integration/tests/approval-retry-native.test.ts \
  -t 'nano executes once.*initial503=false'
```

- **exit1，1 failed /14 skipped，33.22s**；原25000ms到期。
- 同样仅 `initialize(agents=1)` 未返回，prepareProfile190ms、spawn129ms；尚未 session.ensure/submit，不能归因为 reviewer HTTP/retry。没有将未执行的14个场景算失败或通过。

再做不加载任何测试或业务 fixture 的公开 API 对照：`prepareProfile → RuntimeClient → initialize({agents:[],bindings:[]})`，独立 **30s诊断 cutoff**，不是修改原测试期限，也不作为任何产品场景通过。`PROBE_RUN=boot-plain caffeinate -i node .e2e-feat625-r5-diagnostics/boot-profile.mjs` **exit1**，prepared92ms、spawn53ms，30s仍无 initialize 返回；随后本脚本 TERM、等待实际 exit、校验 mkdtemp 绝对路径后删除自建 home。实际 TERM 后约7.22s退出（code0/signal null），spawn前起计37.38s观察到exit、38.23s完成home删除；诊断命令因30s cutoff仍exit1，不把进程exit0冒充初始化成功。原始回执见 `boot-plain.log` / `boot-plain.events.json`。这排除了“仅六 Agent 配置/该测试观察 shim 才触发”这一必要条件，但没有证明每个 R5 历史失败都来自同一原因。

## 环境事实、推论边界与停止条件

- 本轮起点 load18.24/30.48/104.23，8 logical CPU；单探针期间仍约14–24的一分钟 load，并非已恢复为低压力的空闲宿主。原 reviewer 的694 load是历史关联，未拿来替代本轮测量。
- 02:55只读采样：swap已用 **9489MiB/10240MiB**；iostat相邻1s采样 disk0约 **1912tps/32.02MiB/s**、CPU约32%user/34%system/34%idle；pmset未记录thermal/performance warning。多组件启动显著拖长与资源压力一致，但**未证明资源压力是全部失败唯一根因**，也不以swap数字诊断某个产品泄漏。
- 一个额外零 Agent CPU-profile诊断有观察设施问题：将 `Debugger ending on` 误识别为 listening，反复重连；其30s到期后的退出受到该诊断干扰，最终只对已核对 cwd/命令的本探针 pid28562 KILL、脚本完成 home 删除。已修正 ignored 脚本的匹配条件，并用上列 **无 debugger 的 boot-plain** 对照取代。该 CPU-profile 跑次**不用于 root-cause/PASS/正常关闭结论**，没有把设施失败归到产品。
- 因隔离六 Agent、单 Agent HTTP及零 Agent对照都卡在初始化之前，且宿主压力未恢复，不继续反复跑其余重型 native/history/model-policy/capabilities 批次制造冗余 timeout。尚欠的具体场景不删减；下一次先在实际稳定资源条件下跑同树同期限单测，再按公开 RPC 后移的首个失败边界选择邻域。若启动恢复而后续某阶段仍失败，再按该阶段判真，不能自动全归环境。

## 已完成的实际补证与清理

- `.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q`：**13 passed/7.65s/exit0**。补上 R5 reviewer 因 Python 缺 pytest 未执行成功的真实 contract；不是新栈 native 通过，也不是全部28个 contract 的本轮重跑。
- 三个超时测试遗留 pid27008/27748/28202，分别核对 **exact unit DSH命令 + lsof cwd = 本次 mkdtemp home** 后 TERM。最终三者与额外诊断28562、boot-plain28945均不在进程表；按 exact unit path 核对活动 native/Vitest进程0。未杀 Q/其他 worktree/生产/共享代理进程。
- 三个超时测试的自建临时 home 保留为恢复现场，未猜路径删除；本文只提交脱敏边界和本地 locator，不提交 raw stderr、配置、prompt、PID文件、CPU profile或数据目录。
- 后续恢复条件：资源实际可用且同期限六 Agent 初始化/opt-out/restart通过，再补 CC超窗终态、15项真实 HTTP matrix、model-policy/history/capabilities等原 R5 缺口；由父E继续原 reviewer/R5-W1 closure。原 Q 新栈验收单独等待其真实结果。

## Q R3报告整合与只读readiness（2026-10-22 03:07 +0800）

父E本轮仅要求整合Q报告和有界只读准备，不继续运行重型测试、initialize或新诊断器。本节没有启动任何native/IM/fixture、没有删除数据或回收文件、没有kill旧PID，没有改期限或预算。

- Q原报告 `252c43528e05331abd5c5244e5ae1083c58031eb` 原样cherry-pick为 `03327b4b2`，完整读取[acceptance R3](../acceptance.md#round-r3--main-同链路语义集成后的定向续验)的367–467行，逐字diff exit0；前R1/R2历史保留。
- Q R3实际受审仍为18e1→22114489：**FAIL /11pass6inconclusive**，新增 `Q625-R3-01 major/unclear` 运行阻塞，不是已确认审核算法/授权漏洞。S9/11/13/14/15/17及required/source/stop/fallback/native owner/双vendor新profile旅程仍欠闭环。
- 保留两个真实新树C3成功：`context→503→allow` 后续delta、总3效果；`context→503→context` 封顶→真实WS deny→后续新full、总2效果。它们是Q实际新观察，不因本轮整体FAIL抹除，也不外推required/source等邻域通过。具体call/review与locator保持原报告415–422行。
- Q初批ENOSPC/load611、I3串行仍5timeout、P3单Agent Gateway启动失败，以及Q的12IM/10fixture端口实际释放，均按原报告保留。本执行者没有再次操作其现场或旧PID。

### 当前资源事实与就绪判断

只读命令为`df -k`、`sysctl`、`vm_stat`、`memory_pressure -Q`、`uptime`、两次相隔1s的`iostat`和精确unit路径`ps`筛选；一次有限采样，不轮询，不附带启动探针。

| 03:07:11 +0800采样 | 实际结果 / 边界 |
|---|---|
| 本worktree与本机temp所处Data卷 | 同一`/dev/disk3s5`，Available **1566940KiB（约1.49GiB）**，df显示100%；不是已发生新的ENOSPC，也不是已获得足够headroom |
| CPU / load | 8 logical CPU；load **14.98/16.20/32.10**；相邻1s实际CPU **49%user/48%system/3%idle** |
| I/O | 相邻1s disk0约2548tps/14.08MiB/s；未用自启动负载做压力测试 |
| RAM / swap | 物理24GiB；swap总10240MiB、用 **9456.94MiB**、余783.06MiB；memory_pressure查询报system-wide free52%，这是其查询口径，不等于physical free52% |
| 自己活动进程 | exact unit路径匹配的Node/Python/Vitest runtime/test进程 **0**；本轮未启动它们，不用已清理旧PID推导新进程身份 |

**未测得足以建议立即复跑的实质资源恢复。** 相对于上轮02:55采样（03:00交付），swap只少约32MiB，盘仍只有约1.5GiB可用，当前CPU接近满载。load比上轮高峰低，不等于启动条件已恢复；现有低层free52%也不能单独推翻CPU/I/O和近满盘事实。没有把这些观测当成全部产品失败唯一根因。

建议父E下一次续跑前采用保守的**工程readiness闸，而非产品契约或已验证充分条件**：先恢复可供swap/本轮证据增长使用的磁盘headroom（建议至少10GiB）；只读采样显示CPU有明显idle、load接近或低于8逻辑CPU且swap没有继续快速增长；自己仍无遗留runtime。满足后先由父E明确续跑一个原期限零Agent/六Agent公开初始化探针，再按实际阶段恢复原测试计划，不并行起多栈。当前条件未满足，本轮不自行启动。

### 可核实拥有的产物体积与保留建议（本轮均未删除）

只对八个已由本执行者创建、绝对路径与realpath一致的既知目录做`du -sk`，每个5s cutoff；未递归扫描Q、共享或生产目录。以下本worktree相对路径和三个mkdtemp目录沿本节前文已有来源：

| 自建目录 | KiB |
|---|---:|
| `.e2e-feat625-r5-diagnostics` | 688 |
| `nano-context-default-uLBEMe` / `nano-context-default-QOzeU6` / `nano-review-recovery-IgkyqO` | 56 /64 /24 |
| `.e2e-feat625-native-r2` | 660 |
| `.e2e-feat625-context-final` | 26416 |
| `.e2e-feat625-source-final` | 109784 |
| `.e2e-feat625-stop-final` | 53764 |
| 合计 | **191456KiB，约187MiB** |

这八项即使全回收也不能提供建议headroom，且包含版本相关历史证据，不建议为腾约187MiB直接丢弃。最小应保留受试SHA/命令/退出码/时序manifest、RPC/native失败日志、approval/request/context/source/stop导出及实际effect事实；原配置/DB/prompt只能本地安全保留，不提交或公开。若后续确需回收，只能在父E另行确认具体归属与范围后，先核实所需证据完整，再考虑已重建且非唯一的重复运行产物；本轮不推导删除授权，不建议删Q/共享/生产数据。

## 资源恢复与原期限串行补证（2026-10-22 09:14–09:28 +0800）

### 版本、恢复准入与零Agent对照

父E根据新的资源事实先续同一执行者做一次有界只读核对、至多一个原30s cutoff公开零Agent探针；探针结果回包并由父E核实后，才另行续原最窄→邻域串行计划。本轮没有fetch/merge新main。全部新执行的`validated_at=3e5fff368d0d536ec471b0a6e7dc88e78d6e51fc`、`executed_base=18e1af8b1cd0834ae3f22f5780f2d50b740f5171`；该HEAD含报告整合，产品/测试/fixture/脚本/锁树与`22114489ba131fbf847b60e0a4ca730d61471796`逐path实际diff为0。

09:14:32–33 +0800一次只读采样：Data卷Available **11810232KiB≈11.26GiB**（df98%），8 logical CPU的load **6.16/14.64/19.30**，相邻1s CPU **30%user/5%system/65%idle**、disk0约223tps/2.02MiB/s；swap用 **2948.44MiB/4096MiB**，memory_pressure查询free65%（不是物理free百分比）。自己exact unit runtime/test为0，当前构建/测试候选为0；另一个生产native未触碰。相对03:07磁盘、swap、CPU/I/O均有实质改善，只支持一个最窄恢复探针，不是已证全部失败仅由资源引起。

```bash
env -u NANO_PROBE_INSPECT -u NODE_OPTIONS \
  PROBE_RUN=boot-recovery-20261022-0914 \
  caffeinate -i node .e2e-feat625-r5-diagnostics/boot-profile.mjs
```

**exit0**：prepared6ms、spawn10ms、initialize返回1431ms（公开RPC约1421ms）；同刻开始shutdown，1461ms实际exit code0/signal null，1463ms删除自建home。仍为原30_000ms诊断cutoff，无debugger/观察hook/业务fixture。日志为`boot-recovery-20261022-0914.log`与`.events.json`；PID40748与自建home后续实际不存在，不需fallback kill。此结果仅证明本次公开bootstrap恢复，不替代六Agent或HTTP/Q旅程。

### 七文件串行矩阵与命令

父E续跑后先完整核原[verification R5](../verification.md#独立命令与失败证据)的455–492行。原报告记录10个失败文件/25fail，但未逐名列全10个；以下覆盖父E与R5直接指向的七个文件，不猜测其余文件、不无差别重跑30文件。`realtime-window`已有独立窄复跑3pass，按原版本保留，未重复；其他未知失败文件若还需覆盖，由原reviewer补精确清单后定向核收。

每行是一个独立命令，前一job实际结束/收取后才启动下一行；每次仅一个native批次，maxWorkers1、fileParallelism=false。使用前文已有ignored观察配置，仓库原testTimeout15000、每test自带期限、生产恢复预算、fixture和业务断言均不变；没有打开NANO_PROBE_INSPECT或NODE_OPTIONS。命令模板如下（`FILE`与`PROBE_RUN`按表逐项替换，非同时执行的shell变量清单）；第一行另加`-t 'defaults new and existing Agents'`，其余跑整文件：

```bash
set -o pipefail
env -u NANO_PROBE_INSPECT -u NODE_OPTIONS PROBE_RUN="$RUN" \
  caffeinate -i pnpm exec vitest run \
  --config .e2e-feat625-r5-diagnostics/vitest.config.ts \
  "packages/dsh-integration/tests/$FILE.test.ts" \
  2>&1 | tee ".e2e-feat625-r5-diagnostics/$RUN.vitest.log"
result=${PIPESTATUS[0]}; exit "$result"
```

| 实际开始 +0800 / job | FILE / PROBE_RUN | 保留原期限 | 真实结果（命令exit0） | 新执行的范围 |
|---|---|---|---|---|
| 09:21:11 / bash-76 | `agent-context-default` / `context-recovery-0918` | 30s | **1pass/4skip，6.17s**；test5992ms | 六Agent新旧profile默认context、disable/enable、重启和managed removal；不是把4skip算pass |
| 09:22:14 / bash-77 | `approval` / `approval-recovery-0922` | native各30s；低层默认15s | **6pass，11.92s** | reviewer阶段/escalation/终态及来源上下文；CC超窗终态原poll、仅normal effect、overflow no_verdict/context断言通过 |
| 09:23:03 / bash-78 | `approval-retry-native` / `http-matrix-recovery-0923` | 每项25s | **15pass，26.51s** | nano/codex/dsh × 无503/503整数/日期/非法Retry-After/transport真实HTTP矩阵，原效果与审计断言 |
| 09:24:11 / bash-79 | `history` / `history-recovery-0924` | 25s | **1pass，3.10s** | 原生fork的配置/已compact前缀独立性及重启 |
| 09:26:27 / bash-81 | `capabilities` / `capabilities-recovery-0932` | 20s/25s/30s | **3pass，13.33s** | 空tools/skills、busy配置切换、extension实际dispatch/PTC及重启、复制skill实时发现/禁用保留；run标签0932不是实际开始时刻 |
| 09:27:04 / bash-82 | `model-policy` / `model-policy-recovery-0927` | 四native各20s；低层默认15s | **5pass，19.98s** | context windows开关×Skill可调用2×2、effort、manual compact命令幂等、重启和配置更新；另1低层preset路由 |
| 09:27:50 / bash-83 | `personal-security` / `personal-security-recovery-0929` | 两native各20s、Global30s；低层默认15s | **6pass，9.50s** | nano/codex有效历史授权、普通Global/PA capability与owner extension/source controls；另3低层effort组合 |

合计是**七个串行命令、37pass/4skip**，不是一次30文件全批通过，也不宣称原25个独立失败逐一映射完毕。没有新confirmed产品缺陷或修复必要性；本轮未改产品源码、测试、fixture、期限、策略或预算。

### 公开阶段、终态与实际清理

以下从对应`$RUN.jsonl`的原始时间点计算，单位ms；native onLog仍按需写`$RUN.native.log`，没有 stderr 输出的跑次不补造日志文件。prepareProfile为实际原调用，不计入initialize；shutdown列是调用shutdown至其finally返回，另核实际exit事件，不仅看Vitest绿灯。

| PROBE_RUN缩写 | prepareProfile | 每次initialize | 代表后续公开RPC | 每次shutdown总耗时 |
|---|---|---|---|---|
| context | 2 | 1440 /2363 | set_bundle17/26、remove_bundle18；12次session.ensure均返回 | 62 /74 |
| approval | 各1 | 1385 /807 /758 /719 /690 | submit24次返回5–19；configuration.apply110；原exact-input lookup终态断言全过 | 96 /73 /39 /197 /58 |
| HTTP matrix | 各1–2 | 671–1125（15次） | 15次ensure28–43、submit8–12；原每input终态/效果/审计断言全过 | 31–59（15次） |
| history | 2 | 1177 /920 | compact23、fork74/0/0（含幂等）、configuration.apply23/26 | 46 /67 |
| capabilities | 3 /2 /4 | 2204 /1565 /1895 /1799 /1813 | configuration.apply49/44/54；submit9次11–24；原PTC结果与终态poll通过 | 162 /141 /109 /67 /98 |
| model-policy | 3 /1 /1 /1 | 1248–2453（8次） | 首次compact20–25、重复0–1；effort16–26；配置更新17–20 | 48–64（8次） |
| personal-security | 4 /1 /1 /1 | 1546 /1036 /1079 /1403 | 8次submit10–15；两个Global configuration.apply28/11；原效果/source断言通过 | 50 /46 /62 /67 |

记录器的notification只保留事件type和时间，不导出正文，不能凭任意一个`turn/end`判断某input完成；终态归属仍由原测试以**sessionId+inputId的公开session.lookup**断言证明。这里的submit数字只是公开RPC返回时间，不冒充审核总延迟。完整配置、review prompt与临时数据库不提交。

七份JSONL聚合实际**41个spawn=41个exit**（全部code0/signal null），37个test-end全部pass；所有rpc-start都有对应rpc-end或rpc-error（含原测试预期拒绝），无未结RPC。32个唯一自建home在最后afterEach及后续实际文件存在检查均不存在，41个spawn PID后续均不在进程表，exact unit路径runtime/test进程0。没有手工kill、额外删除、共享服务重启或其他Q/生产现场操作；旧失败三home继续保留。七个job全部收取exit0，零Agentjob也已收取。

### 中性结论与独立核收边界

- 相同产品/测试树、相同期限，在多维资源实质改善后，原先未进入的六Agent插件开关/重启、CC超窗终态、HTTP15矩阵与指定配置邻域已实际执行通过。该事实支持恢复原reviewer/R5-W1定向核收，**不证明此前每个失败唯一根因都是资源，也不把单次串行通过外推为长期稳定性或整套CI通过**。
- 先前实际`.venv` runtime dependency contract **13pass/7.65s/exit0**保留；本轮无产品/测试变更，未为重复绿灯再跑contract/build/全30文件。本文件只是工程证据，不修改verification/code-review/acceptance的独立结论。原R5 `[]`/18aligned及NOT PASS、Q R3 FAIL/11pass6inconclusive和两个真实C3成功均各按原版本保留。
- 原Q缺口S9/11/13/14/15/17、真实host source/context/stop/required/fallback/native owner与双vendor新profile，仍由父E协调原Q续验。本轮没有启动真IM、双vendor、90s×3 owner/quarantine或Q批次；ordinary RuntimeClient/native fixture即使含Global product.call stub，也不标成真实PA/IM验收。
- 交父E的下一步为：读取本次原始结果和同树diff后，沿原独立reviewer核收R5-W1，明确七文件与未枚举的其余失败范围；再按资源协调原Q定向续验。整体effective_through仍未建立，未canonical/archive/PR/merge/deploy。
