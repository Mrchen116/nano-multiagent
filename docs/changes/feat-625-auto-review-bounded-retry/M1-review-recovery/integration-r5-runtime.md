# R5-W1 集成运行证据调查（工程输入，未关闭门禁）

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
