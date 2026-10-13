# Code Review: feat-589-subagent-trajectory-navigation

Current result: **Round 7 W3 closure passed — no surviving findings at bdeb9741b.**

## Round 1 — full (historical)

```json
[
  {
    "file": "packages/dsh-trajectory-viewer/src/execution-view.jsx",
    "line": 65,
    "summary": "[P2] 历史窗口重建后重新补齐所选执行的起点",
    "failure_scenario": "用户正在查看同一子会话的较早 epoch，已加载窗口覆盖 startSeq；官方 Session follow 恢复或 resync 替换为近期窗口后，该 epoch 的 runId/startSeq 和缓存的 loadThrough 函数都不变，60–65 行的 effect 不会重跑。若新窗口首条记录晚于该 epoch.endSeq，导航仍显示准确范围和已完成状态，却变成‘当前范围暂无已加载记录’，145 行又因存在已知 run 隐藏‘读取更早历史’。锁定官方 Session.installWindow 接受 replace 并更新 baseSeq，renderer.cachedSessionInject 缓存同一 binding 的回调；独立内存 React/JSDOM probe 直接执行受审组件，初始 loadThroughCalls=1、oldInputShown=true，替换窗口并恢复 open 后 calls 仍为1、emptyScope=true、loadOlderAvailable=false。需在公开窗口/连接状态变化后检查所选 startSeq 的覆盖并重新补页，未覆盖时不能把 soft-resolved loadThrough 当作完整读取；加入长历史旧 epoch 恢复回归。完整 probe 和证据边界见 verification.md 的 W1。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "executed_base": "82b4c1320",
    "validated_at": "3f316d482a83f33d62e7a40342b6245c72cc96ef"
  }
]
```

## Round 2 — closure

- review_mode: `closure`
- finding_origin_head: `3f316d482a83f33d62e7a40342b6245c72cc96ef`
- diff_range: `3f316d482..293a8a367`
- executed_base: `82b4c13201dccd12ac72bb2a79c4dd99aa233c49`
- validated_at: `293a8a367ffa8516480f65b3c92a9c389b072691`
- completed_at: `2026-10-13T14:18:36+08:00`
- focus_findings: `W1`

Surviving findings:

```json
[]
```

| Focus finding | Outcome | Direct evidence |
|---|---|---|
| W1 / P2 历史窗口重建后重新补齐所选执行起点 | **closed** | `execution-view.jsx:61–73` 观察公开 firstSeq 的覆盖与 session openState；恢复后补页并核验 soft return 的覆盖；未覆盖禁用定位并提供明确重试。独立运行新组件回归 1 file / 2 tests pass；独立 React/JSDOM probe 验证 cold→open 恢复原输入及 #3–20 范围、软失败禁用两个定位、手动重试恢复相同范围。详见 verification.md Round 2。 |

完整审阅指定 fix delta：生产代码仅修复上述 viewer 读取恢复；新增测试与根 devDependency jsdom/lock 一致；另含既有文档路径修复和 R1 报告归档，不扩大功能或 DSH 接口。本轮无新存活问题，未重开不受影响的 full 范围，也不承担独立产品 UI 验收。


## Round 3 — full, native UI fork

- reviewer: `/root/feat589_native_static`，未参与受审实现
- review_mode: `full`
- executed_base: `b75ae90fa` (`origin/main` at dispatch)
- validated_at: `22aaefa094f088e2a73b9500dfdf8a1d86eeff6e`
- scope: 完整 unit diff；重点为 `a8844b60e..22aaefa09` 原样复制后新增的 UI / viewer / 宿主接线。
- 审查期间 HEAD 到 `3b1963001`，只增加 probe、截图及实施证据，以上受审产品源码没有变化；不将报告基线改成该提交。

`upstream.json` 的 39 个 SHA256 与 `a8844b60e` 全部相符。原版组件按其实际调用边界审查，新 fork 差分单独核对；没有把原样引入的上游代码视作本轮新增行为无限扫描。后端生命周期、固定 observer、只读 carrier、身份释放与附件权限按未改变的范围保留 R1/R2 的直接证据；旧双视图的 UI 验收不保留。

```json
[
  {
    "file": "packages/trajectory-ui/src/client/TrajectoryView.tsx",
    "line": 342,
    "summary": "[P2] 按当前显示窗口过滤独立发起行",
    "failure_scenario": "父 Session 已加载超过 50 个投影事件时，TrajectoryView 的本地历史窗口先裁到最后 50 条，但 withLaunches 接收的是完整 Session eventSource 的 firstSeq。已加载 #1–100、当前显示 #51–100 时，launchSeq=#10 的旧后台 run 通过该下界检查并被插入当前首组，在 #51 前显示可点击的发起入口；#10 的原上下文仍隐藏。旧工具行仅被本地窗口裁掉时也会被误作独立发起行。独立运行当前注册 bundle 的真实原生组件已复现首行 run%3Aold-memory，后接 user #51/#52，Input 10 不显示而记忆整理入口显示。应使用当前显示投影的实际历史下界限制无对应工具行的发起事实，读取更早历史后再在真实位置显示；保留当前窗口内真实工具行装饰。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

### Direct verification and limits

- `pnpm exec vitest run packages/trajectory-ui/tests/navigation.test.ts packages/trajectory-ui/tests/run-navigation.test.ts`：**2 files / 8 tests passed**。旧 W1 的窗口 replacement 与 soft-failure retry 保护已迁移到新 hook，仍有效。
- `withLaunches` 独立直接调用：当前原生 cells 为 #51–100、Session firstSeq=1、后台 launchSeq=10；输出前三行 seq 为 `[10,51,52]`，首行身份 `run:old-memory`。
- 实际插件注册 bundle + React/JSDOM：以公开 SlotRegistry 取真实 `TrajectoryView`，喂给相同 100 条输入及运行事实；仅设置 JSDOM viewport/RAF，不改组件、bundle 或实现。输出如下。临时 probe 位于 `/tmp/feat589-static-native.cjs`，自建诊断进程已全部清理；保留的测试服务未操作。此证据证明接线后的显示行为，不代替真实浏览器产品验收。

```json
{"rowCount":32,"firstRows":[{"key":"run%3Aold-memory","text":"Turn {turn}#1发起记忆整理fork · 后台维护 · 已完成查看本次执行 ↗"},{"key":"user%00seq%0051","text":"USERInput 51"},{"key":"user%00seq%0052","text":"USERInput 52"}],"oldInputDisplayed":false,"oldLaunchDisplayed":true,"loadEarlierAvailable":true}
```

定位：本地裁窗在 `TrajectoryView.tsx:173–201`；错误参数在 `:342`；`navigation-model.ts:78–86` 用完整 source 下界放行并插入首个可见组。该问题是现有历史分页路径的实际条件，不要求构造非法 DTO。其余全分支适用范围无存活 finding；不作风格或假想边界建议。

### Author Resolution — W2

`TrajectoryView` now supplies the rendered event-node window lower bound to `withLaunches`; native tool rows retain their direct decoration. Added a regression through the actual local registration bundle: 100 loaded records initially show only #51–100 with no #10 launch; loading earlier history and scrolling to its original context restores that launch. The check failed on the old bundle, then passed after the one-line correction. Navigation tests (8), local bundle build and typecheck passed. Live viewer assets remain frozen until the ongoing product walkthrough ends.


## Round 4 — closure, W2 and final main sync

- reviewer: `/root/feat589_native_static`，未参与受审实现或修复
- review_mode: `closure`
- finding_origin_head: `22aaefa094f088e2a73b9500dfdf8a1d86eeff6e`
- fix_commit: `684ac43a0`
- diff_range: `22aaefa09..fb3ec48d3`
- executed_base: `36f2cad9e`（最终同步的 origin/main）
- validated_at: `fb3ec48d3fc5b1ae1e33e6da52b4b991dfbcef01`
- focus_findings: `W2`

Surviving findings:

```json
[]
```

| Focus finding | Outcome | Direct evidence |
|---|---|---|
| W2 / P2 当前尾窗提前显示旧发起点 | **closed** | `TrajectoryView.tsx:342` 将 `navigation.firstSeq()` 改为当前 `nodes[0]?.seq`；`withLaunches` 原工具行优先匹配和装饰未改。独立运行当前 local 注册 bundle 的组件回归：已加载 #1–100 时默认显示 Input 51，#10 维护入口不可见；点击读取更早历史并回到顶部后入口和 Input 10 同时可见。 |

独立执行：

```sh
NANO_TRAJECTORY_FORK=1 pnpm exec vitest run --config packages/dsh-trajectory-viewer/probes/vitest.config.mjs
```

**1 file / 1 test passed**，17:05:54 开始、3.52s；日志 `/tmp/feat589-static-closure-probe.log`。新增回归在 `probes/native-extension.probe.ts:108–125`，真实注册 bundle / 原生内部50窗口 / 更早历史加载均在同一测试中观察，不复制范围过滤算法。锁定官方包缺少 sourcemap 的既有提示不影响断言。另复用作者修复后8导航tests、build/typecheck证据（`/tmp/feat589-window-{green,tests,types}.log`）。

最终 merge `fb3ec48d3` 的另一父提交 `36f2cad9e` 只带 bugfix-590：`prepareProfile` 更新持久profile的过期依赖symlink，并补测试与部署规范。它没有改变运行事实、只读observer、UI组件、数据契约或附件权限；已有适用结论保留。首次同步测试因 `lib/client.js` 尚未重建而运行旧实现；只读核验确认 src/lib差异。作者重建integration后同4文件 **15 tests passed**（17:07:20，18.64s），日志 `/tmp/feat589-final-sync-tests.log`；最终lib已含readlink/unlink，源码无额外改动。该失败属于构建前提，不能当作最终源码缺陷或忽略失败直接报绿。

`git diff --check 22aaefa09 fb3ec48d3` 通过。本轮无新存活 finding，不重开不受影响的全分支审查，不代替最终真实浏览器产品复验；保留live服务未操作。


## Round 5 — patch, complete-session native selection

- reviewer: `/root/feat589_native_static`，未参与实现
- review_mode: `patch`
- executed_base / diff_range: `d737d1dca` / `d737d1dca..9f6a47f13`
- validated_at: `9f6a47f13ca82185a19ced563d25f84608d2eab3`
- scope: 用户反馈修正；完整会话含继承前缀及其他epoch，原生自动选区、顶部执行与导航栈同步、显式选择重置。保留此前未失效证据，不重审完整分支。

Surviving findings:

```json
[]
```

核对结果：

- `TrajectoryView.tsx:164–180` 直接消费完整原生snapshot，进入run不使用内部50节点裁窗；旧scopeSnapshot与本次/历史开关已删除。运行中工具及partial保持原会话数据，通过原请求坐标参与执行选区，不将后续epoch高亮为旧执行。
- `use-run-navigation.ts:40–52` 通过公开hasMore/loadThrough(0)读取完整历史；窗口重建时重新核对，软失败显式重试，未完整加载时不冒充完整会话。viewer公开navigation face提供真实Session.hasMore，所有产品调用方已接线。
- `TrajectoryView.tsx:411–435` 保留原生精确成员、自动范围与手动选区分离；用户清除/拖选或点击范围外记录后不被轮询接管。完整轨迹不被选区过滤。
- `agent-trajectory.tsx:20–23` 当前frame通知宿主；`agent-work-panel.tsx:93–105,158–161` 使用active会话显示选择器，并通过显式选择version重新打开所选会话，避免显示层状态反过来销毁保留的父栈。
- 后端生命周期/DTO/observer/附件权限未变化；原39文件fork来源及W2父会话尾窗保护保持有效。旧“过滤本次投影”的通过依据被最新用户契约取代，不作为本轮正确性证据。

独立执行：`pnpm exec vitest run packages/trajectory-ui/tests/navigation.test.ts packages/trajectory-ui/tests/run-navigation.test.ts`，**2 files / 6 tests passed**（18:01:52，556ms）；`NANO_TRAJECTORY_FORK=1 pnpm exec vitest run --config packages/dsh-trajectory-viewer/probes/vitest.config.mjs`，**1 file / 1 test passed**（18:01:52，2.50s；`/tmp/feat589-static-full-focus-probe.log`）。实际local注册bundle断言完整fork轨迹中的Input 1保持显示且为outside、原生选区存在、无历史切换，同时保留父会话W2分页保护。新hook回归覆盖loadThrough(0)、窗口重建和软失败恢复。

复用同实现的 `/tmp/feat589-selector-green.log` 宿主 **2 files / 19 tests passed**、作者typecheck/build与真实63084走查证据；独立查看 `evidence/native-full-session-focus.png`，可核对全背景时间轴、#447–470选区、范围外淡化和顶部技能复盘选择。静态审查不据此扩称为本轮重新完成全部跨屏产品验收。`git diff --check d737d1dca 9f6a47f13`通过；未修改实现、未启动进程、未操作保留服务。


## Round 6 — final-sync patch, resource-space permission combination

- reviewer: `/root/feat589_native_static`，未参与实现
- review_mode: `patch`
- executed_base / diff_range: `1caed76ae` / `1caed76ae..96f5ac497`
- validated_at: `96f5ac497dbe5d330cf8ac5467dc367186c6a4f3`
- origin/main: `74bfff7f7`
- scope: main同步对Work空间资格、原生observer和runs只读载体的影响；不重审主干新功能或不变的UI。

```json
[
  {
    "file": "apps/im-server/src/trajectory.ts",
    "line": 107,
    "summary": "[P1] 公司 Agent 失效时撤销其原生观察连接",
    "failure_scenario": "owner同时有私人空间且被公司suspend后，Gateway.valid为其私人资源保留节点连接；company Agent的agentAvailable已为false，Work.append也丢弃其新内容，但trajectory.valid只核对reader空间与owner恒等，仍允许另一个合法company reader通过既有observer请求session/page并接收该company运行时的新数据。初始browser prepare的33行也只核对reader，可重新建立相同观察。真实identity.transition/Work/Gateway/TrajectoryObservers及隔离SQLite复现确认节点仍合法、company新Work事件0条、native请求仍转发且新结果返回。应在初始prepare和持续valid两处叠加agentAvailable约束，保留private Agent和原Work历史的合法读取，不关闭整个混合节点。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]
```

直接复现：`pnpm exec tsx /tmp/feat589-space-sync.ts`（本worktree），临时SQLite自动清理；真实server/identity.transition/Work/Gateway/TrajectoryObservers，仅socket输送使用EventEmitter，不连接live或执行LLM。停用后再从合法reader发真实只读`session/page`请求并回送匹配requestId，输出：

```json
{"ownerPersonal":true,"ownerMembership":"suspended","companyAgentAvailable":false,"nodeStillValid":true,"companyWorkAfterRevocationRows":{"n":0},"appendAcknowledged":2,"nativeReadForwardedAfterRevocation":true,"nativeBrowserState":1,"nativeBrowserLastFrame":{"type":"result","requestId":"new-company-data","value":{"ok":true,"value":{"text":"AFTER_COMPANY_REVOCATION"}}}}
```

契约为 `docs/specs/im/auth-tenancy.md`“停用立即覆盖真人与机器”：公司Agent不因owner仍有私人空间继续公司接入，历史共享Work仍可给合法成员查看。风险由Gateway节点级资格放宽与原生通道缺少Agent级资格组合产生，不是要求撤销合法company reader或断开private服务。

未失效证据retained：trajectory-ui/viewer/宿主选择器源码在sync中完全不变，R5完整会话/选区证据有效；普通active公司reader的runs只读透传、mutation拒绝、原附件规则由现3个相关IM测试 **12 tests passed**保护（`/tmp/feat589-main-sync-tests.log`）。这些测试没有覆盖上述mixed-owner停用条件。作者已复验63084正常reader进入完整fork与选区；不因此覆盖W3。其余指定同步范围无新finding，`git diff --check 1caed76ae 96f5ac497`通过。报告外用户dirty实施记录未改。


## Round 7 — closure, W3 and final-sync validity

- reviewer: `/root/feat589_native_static`，未参与修复
- review_mode: `closure`
- finding_origin_head / executed_base: `96f5ac497`
- diff_range: `96f5ac497..bdeb9741b`
- validated_at: `bdeb9741bdf5577fb354a1e233f0e33a9af69383`
- focus_findings: `W3`

Surviving findings:

```json
[]
```

| Finding | Outcome | Direct evidence |
|---|---|---|
| W3 停用company owner但保留私人节点后原生company读取继续 | **closed** | `trajectory.ts:33,107`均复用`agentAvailable(db,profile)`，叠加既有reader空间资格、owner恒等和节点/浏览器检查。新tenancy回归验证company观察两端关闭、新prepare拒绝、同节点仍valid、fresh owner的private session/page继续可读。 |

独立执行`pnpm exec vitest run apps/im-server/tests/tenancy.test.ts -t 'closes revoked company trajectory reads'`，**1 test passed / 6 unselected**（18:34:28、1.09s）。独立重跑原失败probe `pnpm exec tsx /tmp/feat589-space-sync.ts`，结果由转发新company读取变为：

```json
{"companyAgentAvailable":false,"nodeStillValid":true,"companyWorkAfterRevocationRows":{"n":0},"nativeReadForwardedAfterRevocation":false,"nativeBrowserState":3,"nativeBrowserLastFrame":{"closed":1008}}
```

复用`/tmp/feat589-space-fix-green.log` **3 files / 13 tests passed**（18:33:12、5.46s）和IM build/tsc通过证据；先红日志`/tmp/feat589-space-fix-red.log`对应真实失败条件。原Work共享历史HTTP读取没有改成要求owner可用，修复只阻止已失效company运行时原生接入，不关闭private节点或扩大管理权限。

完整final-sync有效性：Round6中除W3外的权限组合核验保留，W3现在关闭；Round5完整会话/选区/顶部选择器源码仍未变，其组件与宿主证据retained。作者已在96f5同步产物IM上复验普通reader完整fork+#447–470选区及选择器；本修复不改该active正向条件，且相关IM套件通过。未额外重开UI或主干功能验收。`git diff --check 96f5ac497 bdeb9741b`通过。未改实现、未提交、未操作live；临时probe的隔离库已清理。
