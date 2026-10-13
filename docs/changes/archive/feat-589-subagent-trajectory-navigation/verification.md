# Verification Report: feat-589-subagent-trajectory-navigation

> Current result: **Round 7 W3 closure PASS at bdeb9741b — final-sync applicable evidence retained; corrected-delta aligned.**

> Validation snapshot: `82b4c1320 → 3f316d482a83f33d62e7a40342b6245c72cc96ef`

## Round 1 — full + corrected-delta (historical)

## Metadata

- unit_id: `feat-589-subagent-trajectory-navigation`
- reviewer: `/root/feat589_static_review`，未参与受审实现
- review_round: 1
- verification_mode: `full + corrected-delta`
- branch: `codex/feat589-subagent-trajectory-navigation`
- executed_base: `82b4c1320`
- validated_at: `3f316d482a83f33d62e7a40342b6245c72cc96ef`
- implementation commits: `31ee7379d`, `3f316d482`
- completed_at: `2026-10-13T14:01:51+08:00`
- requires_full_verification: `false`（本轮已经 full；修复可就 W1 定向闭环）
- verdict: **FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**
- corrected-delta outcome: **implementation-mismatch**
- 现场：caller 冻结的 worktree；开始时 HEAD 相符且工作区干净。本 reviewer 只新增这两份报告，不启动服务、不修改实现、不提交。其余 Agent 的后续实现、产品证据和 canonical 归并不属于本固定版本。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 的运行事实、只读接口、导航及 frame 栈已实现；W1 影响恢复读取。R1–R4 产品退出标准仍由独立 reviewer 作最终判定。 |
| Correctness | R1、R2、R3.1–3、R4、R5、R7 有实现与适用回归；R3.4 的窗口恢复存在直接复现缺陷。 |
| Coherence | 公开 DSH 生命周期 / storageDomain、新 View + 官方完整 View、宿主 frame 栈均符合 design；历史覆盖恢复存在 W1。 |

## Evidence and limits

完整读取 unit spec、Gate 2 Approved design/design-review、全部 IM delta、current Work spec、仓库架构与 testing 规则；审完 `82b4c1320..3f316d482` 的 29 个文件，包括两笔实施提交及新增测试。`git diff --check 82b4c1320 3f316d482` 独立通过。

复用 [run-facts.md](M1-navigation/run-facts.md) 的真实锁定 DSH + 受控模型证据和 [implementation.md](M1-navigation/implementation.md) 的版本、命令、运行事实与构建记录：6 files / 14 tests；完整 workspace 61 files / 175 tests；frontend 88 files / 828 tests；build/typecheck；依赖契约 11 passed。没有重复这些有效全量测试。实际检查测试断言与实现接线，未把测试数量当作覆盖依据。

独立查看已存的 1280 图（本地截图） 和 820 图（本地截图），核实来源、范围条、三轨概览、记录与检查区域确有实现投影。作者记录已有真实模型并行普通/fork、嵌套与逐级返回，第一轮 fork 无非空继承前缀的限制也如实说明。390 图、非空继承浏览器旅程及独立产品验收在 caller 处理中；本报告不把 fixture、截图阅读或静态检查替代这些产品结论。

对 W1 额外执行受审真实 React 组件的内存 JSDOM probe，并核对安装锁定版公开 client 实现。该 probe 使用受控 projection/snapshot 变化验证组件恢复逻辑；它不是完整浏览器或真实 DSH 端到端产品验收。

## Completeness

| Milestone 退出标准 | 实现 / 直接证据 | 状态 |
|---|---|---|
| M1-R1 主动普通/fork、memory/skills 发起入口；并行重复不串线 | `trajectory-runs.ts:68–99`；`knowledge/runtime.ts:203`；`navigation-model.ts:96`；真实 DSH 并发 rendezvous、重复 epoch、knowledge 两类来源断言；作者实际并行普通/fork UI 记录 | 静态与运行事实 covered；最终产品 review 独立 |
| M1-R2 本次范围、继承历史和真实状态；完整过程 | DTO 包含式上下界；真实 DSH 非空 fork / completed / error / aborted / crash unknown；导航 `scopedRows`；`RecordDetail` 保留官方投影；官方 View 保持挂载 | **WARNING W1：恢复窗口后旧范围可能空白**；其他产品场景待独立 review |
| M1-R3 嵌套逐级返回及阅读状态 | `agent-trajectory.tsx:20–32` 保持祖先 iframe；宿主回归证明 push/pop 释放；作者真实 2.0×、选择恢复与嵌套记录 | covered；最终产品 review 独立 |
| M1-R4 1280/820/390、完整原生检查、非管理者/身份清除 | 两张实现图；responsive CSS；保留官方 bundle/View；IM 非管理者真实 WebSocket 路径回归；宿主 logout/1008 清栈回归 | 结构与权限 covered；390 与完整旅程待独立 review |
| M1-W1 真实 DSH 捕获顺序与持久回看；scope/mutation 拒绝 | `trajectory-runs.test.ts` 三个真实锁定 DSH 场景、`knowledge.test.ts`、`trajectory.test.ts` 和 IM carrier 测试 | covered |
| M1-W2 窄测试、构建、依赖、docs/local CI；bundle 不改 | 复用冻结实施记录的有效 tests/build/typecheck/11 dependency checks；本 diff 不改 bundle；独立 diff-check pass。docs-check 最终交付门禁仍由 caller 记录 | 已有有效证据；不宣称最终 CI/PR 已完成 |
| M1-W3 浏览器及原型对照、独立门禁 | 当前有作者交互和 1280/820 durable 图，产品 reviewer 独立进行中；本报告与 code-review 给出 W1 | **尚不能收口 unit** |

## Correctness

| Requirement / Scenario | 实现位置 | 测试 / 证据 | 状态 |
|---|---|---|---|
| R1.1 / R1.2 主动与后台真实发起 | `trajectory-runs.ts:68–99`、`knowledge/runtime.ts:203`、`navigation-model.ts:96`、`execution-view.jsx:150–151` | 真实 DSH 普通/fork/并发；knowledge memory/skills 真实来源；作者 UI 发起行进入 | covered |
| R2.1 / R2.2 / R2.3 单次完整区间、fork、重复 | `trajectory-runs.ts:51–66,80–110`、`navigation-model.ts:33–35`、`execution-view.jsx:60–65,78–101` | 真 DSH 创建下界、继承前缀、末事件、两次 residency；projection 测试排除继承和 later epoch | 正常读取 covered；恢复受 W1 影响 |
| R3.1 启动返回不结算、运行尾延伸 | `trajectory-runs.ts:101–110`、`execution-view.jsx:80–109,125–142` | residency held 子任务在工具返回后仍 running，驻留收信不增 run | covered |
| R3.2 / R3.3 真实终态与未知 | `trajectory-runs.ts:108–110,128–136`、`execution-view.jsx:92–94,119–126` | 真 DSH error/aborted；SIGKILL 重启 running→unknown；verifiedRun 固定 parent/session | covered |
| R3.4 中断及恢复原执行 | `execution-view.jsx:48–65,123–126,145`、官方 Session window replace | W1 probe；现有测试没有覆盖窗口替换后的旧 epoch 补页 | **偏离 / WARNING** |
| R4.1 并行父子对应 | AsyncLocalStorage 真实 exec context；`carrierKeyOf(this)`；固定 observer 再验 run | 真 DSH 并发 rendezvous；nested 父链；`verifiedRun` 拒绝错 parent/session/run | covered |
| R4.2 / R4.3 上下文及逐级返回 | `agent-trajectory.tsx:20–32`、`boot.jsx:123–127` | 保留祖先 frame、pop 子 socket、嵌套；真实浏览器作者恢复记录 | covered |
| R5.1 持久发起关系 | `trajectory-runs.ts:114–136`、`trajectory.ts:79–80` | clean restart 后原 run DTO 完全一致；子/孙 observer 冷读 | covered |
| R6.1 两类屏幕与完整检查 | `execution-view.css`；`execution-view.jsx:160–178`；`boot.jsx:116–128` | 图1280/820；projection 含 prompt/tools/usage/raw data；官方原件与公开 callId focus | 静态 covered；390 与体验结论待独立 review |
| R7.1 只读、附件、撤权 | `trajectory.ts:57–71,79–80,148–152`；`transport.ts` allowlist；`agent-trajectory.tsx:12–17,27,105–114` | 非管理者 IM path；scope/mutation 拒绝；原附件规则保留；logout/1008 整栈释放 | covered |

## Coherence

| design 决策 | 遵守？ | 代码与证据 |
|---|---|---|
| 真实生命周期 runId / residency epoch，不用 sessionId 或工具结束代替 | 是 | start/end 同 runId；创建时 next offset；提前 tail 观察，end 不依赖仍活着的 child；真实 DSH 覆盖 |
| 并发上下文独立、knowledge 显式来源 | 是 | AsyncLocalStorage + 父 carrier 校验；`withKnowledgeRun` 不解析 UUID/标签；真实并发与 memory/skills 回归 |
| storageDomain 元数据、串行写与读屏障、重启 unknown | 是 | `trajectory-runs.ts:114–136`；读等待屏障稳定，失败拒绝；已结束事实独立 runId；冷读与 crash 测试 |
| 固定 observer，只读 carrier | 是 | 新方法仍调用 `arguments` 身份检查及 prepare 的 binding/父链检查；只新增 read allowlist |
| 公开 slot 新 View + 原件明细；官方投影不改写 | 是 | `boot.jsx:123–134`，`navigation-model.ts:52–98`；不导入 private UI；原 bundle 无变化；source/data 检查完整投影 |
| 本次/完整会话范围不混淆 | 是 | nativeMode 来源摘要；隐藏导航控件/计数；完整会话说明；导航状态仍挂载 |
| 自动加载起点且确保覆盖，恢复仍检查同一次 | **否，W1** | `execution-view.jsx:60–65` 只按固定身份补页，未观察被替换的历史窗口 |
| 宿主保留父 frame / identity 清栈 | 是 | 稳定 target、只 push active 顶层、pop 清理子 frame；账号/revision/Agent/root/session key；1008 清整栈 |

`SPEC.md` 的 viewer 呈现例外与 current Work spec 的 canonical 归并按 design/caller 安排在门禁通过后执行；当前尚处 active unit，不能把尚未归并判成实现漏项。依赖白名单只增加 viewer→product-contracts；PA/Channels/IM 未获得 DSH import 或执行能力。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 真实发起入口、用途/fork/主动后台/状态 | M1-R1/W3 | marker + runTitle + metadata badges | implementation.md 与1280/820图 | covered；产品 reviewer 继续核实后台旅程 |
| 来源/本次范围/概览/起止；继承区别 | M1-R2/W3 | scopedRows、range/axis/tracks 同时间与 seq；真实 fork 下界 | DSH fixture 与作者范围记录 | **W1；正常显示有证据，恢复不成立** |
| 父阅读状态与嵌套 | M1-R3/W3 | retained iframe 栈 | 宿主回归与作者真实 2.0×/选择恢复 | covered；独立体验 review 另行结论 |
| 完整检查与原生明细同页、返回不丢范围 | M1-R4/W3 | official slot 保持挂载；投影原文/request/schema/image | 作者 callId focus；1280/820图 | covered；390 与完整产品 review 待完成 |
| 中断/失败/取消/未知不冒充成功/实时 | M1-R2/W3 | metadataError、状态映射、开放尾端 | 真 DSH终态及中断机制；无对应完整产品验收冒充 | 静态 covered；恢复 W1 |

## Issues

### CRITICAL

无。

### WARNING

#### W1 — 历史窗口重建后所选旧 epoch 不再补页（CONFIRMED / P2）

- 契约：spec R2.1、R3.4；design“展示时间概览前确保本次已知起止覆盖所需记录”“恢复读取继续查看原执行”；delta `specs/im/agent-work.md:22–30`。
- 位置：`packages/dsh-trajectory-viewer/src/execution-view.jsx:60–65`（主要），`:145`（隐藏历史补读入口）。
- 触发：同一 child session 的旧 epoch 已进入并补读；该 Session 的官方 follow/resync 将历史窗口替换成后续 epoch 的近期窗口，起点已不在窗口。不是要求改调度或人为构造非法 DTO：锁定官方 client 支持窗口 replace、soft-failed/superseded loadThrough，正是已有 generation 恢复链路所用机制。
- 直接源码：安装锁定 `dsh-api-session-controller/lib/client.js` 的 `acceptEventChange` replace→`installWindow`（2691–2715），`resync`（2554–2565）及 loadThrough（2508–2549）；renderer `cachedSessionInject`（487–499）保持同一 binding 的函数 identity。
- 独立复现：直接 bundle 受审 `ExecutionView` 到内存，初始已知 run #3–20，projection含#3；随后保持同一run/回调，将公开 snapshot 替换为#700，并模拟 session cold→open。输出：

```json
{"phase":"initial","loadThroughCalls":1,"oldInputShown":true}
{"phase":"same-session-resync","loadThroughCalls":1,"emptyScope":true,"loadOlderAvailable":false}
```

- 后果：范围仍称本次 #3–20 / 已完成，但本次过程空白；用户无法在默认范围内补读。运行事实本身没有错，恢复展示违反契约。
- 建议：按公开 Session/window 状态检查起点覆盖，window replacement / 恢复后按需重新 loadThrough；完成软返回后再次确认覆盖，仍不足时保持明确读取状态或可操作补读。保留用户已有缩放/选择/滚动，不重启执行。新增最低合适层回归保护“旧 epoch →同身份历史窗口被替换→重新覆盖该范围”，不另造一套私有窗口/DSH Loop。

### SUGGESTION

无。

## Round 1 Delta Snapshot (historical)

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 从真实发起位置进入：主动与后台 | 显式 knowledge provenance、真实调用 carrier、flow badges/marker | 并发/knowledge 真实DSH +投影scope | aligned |
| 从真实发起位置进入：并行/重复/嵌套与刷新 | runId 独立、residency 语义、durable domain与frame栈 | 真实DSH两次epoch/冷读/nested；宿主回归 | aligned |
| 本次范围：默认聚焦/fork历史 | 包含式bounds、scopedRows、loadThrough初次加载 | 真实fork继承前缀与projection回归 | aligned（正常读取）；恢复受下一行影响 |
| 本次范围：运行与异常 / 恢复 | 正确终态与unknown；但旧范围窗口被替换后不补页 | 真实终态保护通过；独立probe证实W1 | **implementation-mismatch** |
| 本次范围：全部原生明细 / full session 独立范围 | 官方slot保留、source摘要、控件隐藏与full计数 | 作者实际callId检查与固定代码；完整体验review独立 | aligned |
| 父子导航：返回恢复 | retained ancestors +pop | 宿主frame identity/清理回归与作者交互 | aligned |
| 父子导航：跨屏 / identity /只读 | CSS responsive、fixed observer、全栈销毁 | 1280/820图、IM非管理者/附件、logout/1008 | aligned（390最终产品证据待独立review） |

### Uncovered Observable Behavior

未发现需要另补 delta 的对外行为。用途、foreground/background/unknown、residency epoch、全会话与本次范围区别、导航返回和身份释放均已被 delta 覆盖。W1 是实现未兑现既定恢复要求，不应修改 delta 去适配缺陷。

Outcome: **implementation-mismatch**。

## W1 probe reproduction

在 unit worktree 根目录执行下列内存 probe；只读取实现及安装依赖，不落测试文件，不启动服务。React18 的 act 弃用提示不影响结果。将 projection/window 变化换成真实 session hook 的窗口 replace 可作为后续回归 seam；本脚本本身只是一轮诊断证据，不进入长期测试套件。

```sh
node --input-type=module <<'JS'
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const req = createRequire(process.cwd() + '/packages/dsh-trajectory-viewer/package.json');
const { build } = req('esbuild');
const React = req('react');
const { JSDOM } = createRequire(process.cwd() + '/src/IM/frontend/package.json')('jsdom');
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost' });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, requestAnimationFrame: fn => fn() });
const { createRoot } = req('react-dom/client');
const { act } = req('react-dom/test-utils');
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const path = process.cwd() + '/packages/dsh-trajectory-viewer/src/execution-view.jsx';
const result = await build({ stdin: { contents: readFileSync(path, 'utf8') + '\nexport { ExecutionView };', resolveDir: process.cwd() + '/packages/dsh-trajectory-viewer/src', loader: 'jsx' }, bundle: true, write: false, format: 'cjs', platform: 'node', external: ['react'], loader: { '.css': 'empty' } });
const mod = { exports: {} }; new Function('require', 'module', 'exports', result.outputFiles[0].text)(req, mod, mod.exports);
const run = { runId: 'old-epoch', parentSessionId: 'parent', sessionId: 'child', provider: 'spawn', kind: 'tool', delegation: 'foreground', startSeq: 3, endSeq: 20, startedAt: 1000, endedAt: 2000, state: 'completed' };
const mk = (seq, text) => ({ eventNodes: [{ kind: 'user', seq, time: seq * 100, content: [{ type: 'text', text }] }], requests: [], runningCalls: [], partial: null, eventLocations: new Map(), callSchemas: new Map() });
let snapshot = mk(3, 'old epoch input'), session = { hasMore: true, loadingOlder: false, openState: 'open' }, calls = 0;
const props = { useTrajectory: fn => fn(snapshot), useSession: fn => fn(session), sessionId: 'child', initialRunId: run.runId, parentSessionId: 'parent', readRuns: async () => [run], loadThrough: async () => { calls++; }, loadOlder: async () => {}, firstSeq: () => snapshot.eventNodes[0].seq, loadImage: async () => '', navigate() {}, isActive: () => true, nativeMode: false, openNative() {}, publishPosition() {} };
const root = createRoot(document.getElementById('root'));
await act(async () => root.render(React.createElement(mod.exports.ExecutionView, props)));
console.log(JSON.stringify({ phase: 'initial', loadThroughCalls: calls, oldInputShown: document.body.textContent.includes('old epoch input') }));
await act(async () => { session = { ...session, openState: 'cold' }; snapshot = mk(700, 'latest epoch input'); root.render(React.createElement(mod.exports.ExecutionView, props)); });
await act(async () => { session = { ...session, openState: 'open' }; root.render(React.createElement(mod.exports.ExecutionView, props)); });
console.log(JSON.stringify({ phase: 'same-session-resync', loadThroughCalls: calls, emptyScope: document.body.textContent.includes('当前范围暂无已加载记录'), loadOlderAvailable: document.body.textContent.includes('读取更早历史') }));
await act(async () => root.unmount());
dom.window.close();
JS
```

最小回归断言应从可见 seam 观察恢复后本次输入重新出现、范围仍是原 epoch，并确认恢复补页不会重跑任务；固定版本相反地保持 calls=1/空范围。不要只断言 effect 次数来代替可见结果。

## Round 2 — Targeted Closure

### Metadata

- unit_id: `feat-589-subagent-trajectory-navigation`
- reviewer: `/root/feat589_static_review`，未参与受审实现
- review_round: 2
- verification_mode: `targeted-closure + corrected-delta`
- prior_verification_path: `verification.md`（上方 Round 1 原结论和复现保留）
- branch/worktree: 与 Round 1 相同
- executed_base: `82b4c13201dccd12ac72bb2a79c4dd99aa233c49`
- validated_at: `293a8a367ffa8516480f65b3c92a9c389b072691`
- finding_origin_head: `3f316d482a83f33d62e7a40342b6245c72cc96ef`
- fix_delta_range: `3f316d482..293a8a367`
- focus_issues: `W1`
- completed_at: `2026-10-13T14:18:36+08:00`
- requires_full_verification: `false`
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**
- validated_issues: `W1 closed`
- corrected-delta outcome: **aligned**

### Scope and retained conclusions

审阅指定完整 fix delta，确认生产代码变化仅为 `210e100dd` 的 viewer 历史覆盖恢复；根 `package.json`/lock 新增 jsdom devDependency 支持真实组件回归；`ad15fdf1b` 仅修正既有 auth-tenancy 文档相对链接；`293a8a367` 收录 R1 两份报告。运行事实、carrier、DTO、权限栈、官方投影解码和官方 bundle 均未变化，因此保留 Round 1 对这些部分的 full 结论。

未提交的 `acceptance.md` 属于独立产品 reviewer，未修改、未纳入本轮静态复验结论。此处 PASS 表示 W1 静态与组件行为门禁已关闭，不代表全部产品退出标准、canonical 归并或 PR 已完成。

### W1 closure — closed

| 原问题条件 | 修复与实际证据 | 结果 |
|---|---|---|
| 同 runId/startSeq 的窗口替换后，不重新补读 | `execution-view.jsx:61–73` 从公开 firstSeq 判断 missingStart，并观察 session openState；覆盖丢失或恢复 open 后补读原 startSeq。独立运行新组件回归，原输入在窗口 replacement 后重新出现。 | closed |
| loadThrough soft resolve 被误当作已覆盖 | 同一 effect 完成后核对 firstSeq，未覆盖显示明确提示；`execution-view.jsx:134` 提供范围重试；`:127` 禁用不完整范围的起止定位。独立 probe 在软失败后直接断言可见 alert、retryAvailable=true 和两个 locator disabled。 | closed |
| 恢复必须仍属于原执行，不重跑或切到后续 epoch | 修复仅调用现有只读 loadThrough；不改 runId、边界、调度或执行接口。独立 probe 在 cold→open 和 retry 后均恢复原输入与 #3→#20；无执行 mutation 新路径。 | closed |

新增永久测试位于 viewer 行为 owner 的 `tests/execution-view.test.ts`，通过公开 slot 注册取得真实 React 组件，使用 jsdom 验证窗口 replacement 与 soft failure/retry 后可见原输入，不复制生产范围判断逻辑。loadThrough 次数断言辅助证明没有忽略恢复或无界重试，主要结果断言为原输入重新可见，符合 testing 规则。

### Independent verification

2026-10-13 14:18:36，冻结 head 与指定版本相符：

```sh
pnpm exec vitest run packages/dsh-trajectory-viewer/tests/execution-view.test.ts
```

**1 file / 2 tests passed**（453 ms）。`git diff --check 3f316d482 293a8a367` 也通过。

另外独立以内存 esbuild bundle 执行受审真实 ExecutionView，使用同一 session/run/稳定 props，模拟公开 projection 窗口和 openState 的变化；不落源文件、不启动服务。该 probe 扩展了 R1 的复现，验证源码补页 effect 确实在 cold→open 时恢复，且 soft failure 后两个定位均禁用、重试恢复原范围：

```json
{
  "recovered": {
    "coldCalls": 0,
    "afterOpenCalls": 1,
    "inputRestored": true,
    "originalRange": true
  },
  "failure": {
    "alert": "历史读取中断：已加载历史尚未覆盖本次起点，请重试读取。重新读取本次范围",
    "locatorsDisabled": true,
    "retryAvailable": true
  },
  "retry": {
    "inputRestored": true,
    "originalRange": true,
    "retryCleared": true
  }
}
```

此 probe 初始窗口已覆盖，因此未多余调用 loader；换为后续窗口并置 cold 时仍保持 0 次，恢复 open 后恰好补页一次并恢复原输入。随后故意 soft resolve 未覆盖，再点击重试恢复。全部布尔断言通过。它证明组件行为，不能替代真实浏览器/DSH 的产品验收。

复用 caller 已提供、且本轮读取确认的 `/tmp/feat589-final-runtime-tests.log`：同一修复版本 `pnpm test` 在 14:15:44 运行，**62 files / 177 tests passed**。该日志为本机临时定位，关键命令、时间与结果在本 durable 报告保存。viewer typecheck 与此前不受影响的 frontend/build/依赖证据复用，不重复全量运行。

### Issues

无 CRITICAL / WARNING / SUGGESTION；W1 已关闭。未发现修复影响共享边界或要求重新 full verification 的条件。

## Round 2 Delta Snapshot (historical)

| Delta item | Final implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 从真实发起位置进入：主动/后台、并行/重复/嵌套、持久回看 | 与 R1 full 固定实现相同；修复未改变运行事实或入口身份 | 复用真实 DSH/knowledge/冷读/宿主回归，以及修复后 62/177 全量通过 | aligned |
| 本次范围：默认聚焦、fork 历史、真实终态 | scopedRows 与真实包含式 bounds 不变；新增公开覆盖校验避免恢复后漏记录 | 复用 fork/terminal 回归；新真实组件窗口替换回归 | aligned |
| 本次范围：运行与异常 / 恢复 | `execution-view.jsx:61–73,127,134` 窗口恢复重读、soft resolve 校验、禁用定位和显式重试 | 独立 2 个组件测试与 cold→open/soft failure/retry probe 全通过；W1 closed | aligned |
| 全部原生明细与独立全会话范围 | R1 已核对的两个 slot 与 nativeMode 范围说明未变 | R1 有效代码/投影/作者明细证据继续适用，独立产品 review 另行判定 | aligned |
| 返回恢复与只读/身份释放、跨屏 | retained frame 栈、授权/清除与 CSS 不变 | R1 宿主/非管理者/附件有效回归保留；不把本轮静态结论当作产品体验验收 | aligned |

### Uncovered Observable Behavior

None。修复增加的加载不足提示、定位禁用与范围重试是既定“忠于已加载事实、恢复读取原执行”的具体实现，delta 的默认范围与中断/恢复 Scenario 已覆盖，不产生新执行能力或权限，也不需改变 spec 适配错误实现。

Outcome: **aligned**。


## Round 3 — Full static verification, native UI fork

### Metadata

- unit_id: `feat-589-subagent-trajectory-navigation`
- reviewer: `/root/feat589_native_static`，未参与受审实现
- review_round: 3
- verification_mode: `full + corrected-delta`
- branch: `codex/feat589-subagent-trajectory-navigation`
- worktree: `/Users/czj/.codex/worktrees/unit-feat589/nano-multiagent`
- executed_base: `b75ae90fa`
- validated_at: `22aaefa094f088e2a73b9500dfdf8a1d86eeff6e`
- requires_full_verification: `false`（本轮已覆盖完整适用静态范围；W2 可定向关闭）
- verdict: **FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**
- validated_issues: `W1 closed, W2 confirmed`
- corrected-delta outcome: **implementation-mismatch**

### Summary and retained evidence

| 维度 | 结果 |
|---|---|
| Completeness | R1–R7 均有实现；独立产品验收由本轮产品 reviewer 判定，不复用旧双视图验收 |
| Correctness | W2：历史尾窗把旧发起行提前显示；其余适用检查通过 |
| Coherence | 单个原生派生插件及公开 navigation face 符合设计；当前显示窗口约束有一处偏离 |

本轮检查 spec、最终 design、corrected delta、current Work spec、SPEC 架构边界、testing 规则及全分支适用 diff。`upstream.json` 的 39 个源文件摘要独立对比 `a8844b60e` 全匹配；重点检查其后本仓差分。审查期间 HEAD 到 `3b1963001`，只有 probe/证据改动，产品源码与固定受审版本相同。

复用 `M1-navigation/native-implementation.md` 的最终 workspace build/typecheck、65 files / 206 tests、frontend 90 files / 840 tests、56 Python tests、Ruff 和 docs 成功证据。复用 `M1-navigation/run-facts.md` 及 R1/R2 对未改变的生命周期、durable epoch、权限和宿主栈证据；旧 UI、旧 renderer 和旧双视图截图不据此获得新路线验收结论。独立重跑新 UI 2 files / 8 tests 全通过，并为 W2 执行模型和真实注册组件 probe；没有重复全量测试或启动生产服务。

### Correctness

| Requirement / Scenario | 实现证据 | 测试 / 核验 | 状态 |
|---|---|---|---|
| R1.1 主动、R1.2 后台真实发起点 | `navigation-model.ts:68–89`；`TrajectoryView.tsx:341–342,598–605`；真实 provenance 来自 integration | 真 DSH/knowledge 证据保留；新增模型覆盖；独立 probe 证实旧发起点提前进入尾窗 | **WARNING W2** |
| R2.1 已结束范围、R2.2 fork 历史、R2.3 重复唤起 | `scopeSnapshot` 按包含式 seq 隔离；`executionFocus` 精确成员；同一原生组件切历史 | 新投影 tests 覆盖继承、后续 epoch、partial/runningCalls 和四种时间模式；真实 DSH 下界/epoch 证据保留 | covered |
| R3.1 运行、R3.2 终态、R3.3 未知、R3.4 中断恢复 | `trajectory-runs.ts:47–136`；`use-run-navigation.ts:26–52`；范围条未知终点及错误状态 | 真实终态/crash/驻留测试证据保留；独立 8 tests 包括窗口重建及软失败重试 | covered；W1 closed |
| R4.1 并行、R4.2 返回、R4.3 嵌套 | 独立 runId/parent；`agent-trajectory.tsx:12–38` 保留父 frame/pop；`:55` run bookmark key | 新模型身份验证；宿主 existing regression 的父 iframe identity、pop 清理及外源/父身份拒绝 | covered |
| R5 刷新回看 | durable runs；child 固定 observer 重读真实 run/session/parent | 冷读及运行事实回归保留；新 `verifiedRun` 不信任父 payload | covered |
| R6 跨屏与原生检查 | 原生组件/样式与公开图片 slot保留；新增范围/行按钮换行；旧 execution renderer 已删除 | 包构建/公开导出与来源核验；新真实浏览器 must-match 由产品 reviewer 独立判断 | 静态 covered；无旧 UI 验收继承 |
| R7 只读与身份变化 | 原方法 allowlist 只增 runs；固定 observer；identity key / 1008 整栈销毁；附件原链路 | 后端 scope/mutation/非管理者/附件证据及宿主清栈测试保留 | covered |

### Coherence and reference contract

| 设计决定 / must-match | 实现及 evidence | 结论 |
|---|---|---|
| 单原生派生界面，保留时间线/搜索/折叠/检查器 | `@nano/trajectory-ui` 来源39文件；viewer只装配该插件；截图/产品审查另行归属 | 静态 aligned |
| 发起行真实位置、后台用途与状态 | producer-owned run facts 和原工具行 actions；独立历史窗口 probe | **W2** |
| 本次范围/历史同组件，seq成员与模式对应；未知结束不造终点 | `scopeSnapshot`、`coordinateLayout`、`executionFocus`；range/history与autoFocus独立状态 | aligned |
| 逐级返回保留父级阅读状态 | retained iframe；弹出卸载子 frame；runId位置键 | aligned |
| 完整原生明细、窄屏只读与身份/附件边界 | public imports + 原检查器/图片 slot + 原固定 carrier；新截图已独立归属产品门禁 | 静态 aligned |
| 官方执行运行时/安装包不改，只有UI包fork例外 | SPEC:48–50 与依赖契约例外对齐；运行事实仍只在 integration | aligned |

### Issues

CRITICAL：无。

WARNING **W2 — 当前尾窗提前显示旧发起点（CONFIRMED / P2）**。

- 契约：spec R1.1/R1.2 的“真实发起位置”；design“历史窗口之前的已知发起点不会提前混入当前尾页”；delta“从真实发起位置进入子 Agent 的本次执行 / 主动委派和后台维护”。
- 位置：`packages/trajectory-ui/src/client/TrajectoryView.tsx:342`；关联 `:173–201` 和 `navigation-model.ts:78–86`。
- 条件/后果：完整 Session window #1–100，原生局部末50显示 #51–100；旧 launchSeq #10 被按完整 source firstSeq=1 放行，在当前首组、#51前生成独立发起入口。工具行仅被本地裁窗隐藏时也会转成该独立行。用户看到的发起位置属于错误阅读上下文，早期 launch 还能污染当前时间概览与搜索窗口。
- 直接证据：新8测试全通过，但模型调用输出 seq `[10,51,52]`；实际注册 bundle 的真实组件输出首行 `run%3Aold-memory`，随后 `user%00seq%0051`，`oldInputDisplayed=false`、`oldLaunchDisplayed=true`。复现方法与JSON保存在本轮 `code-review.md`，临时 probe `/tmp/feat589-static-native.cjs` 只读取冻结产品；自建诊断进程已清理，保留测试服务未动。
- 可执行建议：无对应可见工具行的已知发起事实须按当前显示投影的历史下界过滤；读取更早历史后再在正确上下文出现，当前可见工具行仍直接装饰。增加最低层行为回归区分“完整 Session 已加载范围”和“原生内部末50窗口”，不改 delta 来适配错误位置。

SUGGESTION：无。

## Round 3 Delta Snapshot (historical)

| Delta item | Final implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 真实发起位置：主动与后台用途/状态 | `withLaunches` +原生行actions；局部窗口下界传错 | 新模型回归和实际注册组件 probe 证实 W2 | **implementation-mismatch** |
| 并行/重复/嵌套与刷新持久关系 | durable runId/parent facts；固定 observer 重读身份；frame stack | 真实DSH/冷读/宿主证据保留；verifiedRun新测试 | aligned |
| 默认本次范围与fork继承历史 | seq本地投影+原生时间概览+history同组件 | 新scope/epoch/partial/工具坐标/四模式测试通过 | aligned |
| 运行/终态/未知/连接中断和恢复 | 生命周期事实不变；coverage hook检查实际起点并允许重试 | 真实终态证据；独立新hook replacement/soft-failure测试通过 | aligned |
| 全部原生明细，自动与手动范围区分 | 官方派生检查器原样保留；autoFocus与manual state分离 | 来源hash/构建证据；最终产品走查独立，不复用旧双视图验收 | 静态 aligned |
| 返回上下文 | retained parent frame；run bookmark key | 原宿主回归与静态核验 | aligned |
| 跨屏/身份变化/只读附件 | 原生样式+新增响应式行；原授权/清栈/附件 | frontend、依赖契约与backend证据；实际跨屏验收独立归属 | 静态 aligned |

### Uncovered Observable Behavior

None。独立 UI fork、单视图、本次/会话历史、自动与手动范围、新行及中断/重试均已被 corrected delta 表达。W2 属实现没有兑现真实发起位置，应修实现，不应静默修改 spec。delta 相对冻结 base `origin/main=b75ae90fa` 为 ADDED 合理。

Outcome: **implementation-mismatch**。0 CRITICAL / 1 WARNING；修复 W2 后可定向静态复验，不需重跑未受影响的后端或全量产品门禁。


## Round 4 — Targeted Closure, W2 and final main sync

### Metadata

- unit_id: `feat-589-subagent-trajectory-navigation`
- reviewer: `/root/feat589_native_static`，未参与受审实现或修复
- review_round: 4
- verification_mode: `targeted-closure + corrected-delta`
- branch/worktree: 与 Round 3 相同
- executed_base: `36f2cad9e`（最终 origin/main）
- validated_at: `fb3ec48d3fc5b1ae1e33e6da52b4b991dfbcef01`
- finding_origin_head: `22aaefa094f088e2a73b9500dfdf8a1d86eeff6e`
- fix_delta_range: `22aaefa09..fb3ec48d3`；W2修复提交 `684ac43a0`
- focus_issues: `W2`
- requires_full_verification: `false`
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**
- validated_issues: `W1 closed, W2 closed`
- corrected-delta outcome: **aligned**

### Closure and independent evidence

| 原问题 / 约束 | 最终实现及直接证据 | 结论 |
|---|---|---|
| 原生内部末50窗口误插完整Session较早launch | `TrajectoryView.tsx:342` 以当前 `nodes[0]?.seq` 传入 `withLaunches`；已知launch下界检查与显示窗口一致。独立实际注册bundle回归确认 #51–100窗口不显示旧#10launch。 | W2 closed |
| 读取更早历史后应在原上下文出现 | 同一回归点击真实Load earlier，回到顶部，确认run入口与Input 10均出现；不是永久丢弃早期事实。 | covered |
| 当前可见工具行仍就地装饰 | 修复只改下界参数；`navigation-model.ts:73–77` 的真实工具行匹配优先于独立行下界过滤，代码未变。既有导航投影tests通过。 | retained |
| 补页恢复、软失败重试及原执行身份 | `use-run-navigation.ts` 本轮未改；原8tests与R3独立证据继续有效。 | W1 remains closed |
| main同步后是否影响既有门禁 | merge另一侧仅bugfix-590的profile symlink维护与部署规范；run事实、observer、DTO、UI和附件链路未改。重建integration后受影响profile+run+UI四文件15tests全部通过。 | retained |

独立命令：`NANO_TRAJECTORY_FORK=1 pnpm exec vitest run --config packages/dsh-trajectory-viewer/probes/vitest.config.mjs`，**1 file / 1 test passed**，17:05:54、3.52s，日志 `/tmp/feat589-static-closure-probe.log`。该实际组件回归保护可见的旧launch与原上下文关系；不是仅测试过滤helper。作者修复后8tests、build/typecheck可信记录复用。

同步首次测试失败已明确源于未重建的旧 `lib/client.js`，没有将其当作绿色证据；只读检查确认新src含readlink/unlink而旧lib不含。作者随后执行 `pnpm --filter @nano/dsh-integration build` 再跑同四文件，**4 files / 15 tests passed**，17:07:20、18.64s，日志 `/tmp/feat589-final-sync-tests.log`；最终lib与源码对应。最终sync既没有新增feat-589行为，也没有使既有有效后端证据失效。

### Scope and limits

Round 3 全范围静态结论除已关闭W2外保留；运行事实、只读/身份/附件与39源文件fork来源不重验全量。`git diff --check 22aaefa09 fb3ec48d3` 通过。此轮PASS是静态与组件行为门禁：保留live仍是22aa版本，本 reviewer 没有重启服务；主任务须按既定安排重建最终服务并完成局部产品复验，不能将旧live验收直接称为fb3ec48d3部署验收。

### Issues

无 CRITICAL / WARNING / SUGGESTION。W2定向关闭；没有要求重新full verification的共享边界变化。

## Round 4 Delta Snapshot (historical)

| Delta item | Final implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 真实发起位置：主动/后台用途及状态 | 本地显示窗口下界正确，工具行优先装饰保持；加载更早历史后旧launch回到原上下文 | 独立实际local注册bundle回归通过；W2 closed | aligned |
| 并行/重复/嵌套与持久关系 | runId/parent、durable存储、固定observer和frame stack均未变 | R3有效证据保留；sync后真实run测试通过 | aligned |
| 默认本次范围/fork历史/自动与手动选区 | 原生本地投影、精确seq成员、autoFocus状态未变 | 修复后8导航tests，R3相关核验保留 | aligned |
| 运行/终态/未知/中断及恢复 | 原生命周期与coverage/retry未变 | R3终态证据保留；sync窄测试及既有窗口恢复保护 | aligned |
| 原生完整明细、上下文返回、跨屏只读/身份/附件 | 只有显示窗口下界变化；原组件、retained父frame与权限链保持 | 来源/静态/宿主证据保留；最终服务产品复验另行完成 | aligned（静态） |

### Uncovered Observable Behavior

None。W2修复兑现既有真实发起位置与历史范围契约，没有增加新用户行为。最终origin/main=`36f2cad9e`的bugfix-590不属于unit增量，相关Gateway行为规范已在main维护；feat-589 corrected delta的ADDED性质及范围仍正确。

Outcome: **aligned**。静态可继续交付；最终服务重建与局部产品复验仍由主任务收口。


## Round 5 — Feedback Delta, complete-session selection

### Metadata

- unit_id: `feat-589-subagent-trajectory-navigation`
- reviewer: `/root/feat589_native_static`，未参与实现
- review_round: 5
- verification_mode: `delta + corrected-delta`
- branch/worktree: 与此前相同；unit现位于archive
- executed_base: `d737d1dca`
- validated_at: `9f6a47f13ca82185a19ced563d25f84608d2eab3`
- fix_delta_range: `d737d1dca..9f6a47f13`
- requires_full_verification: `false`
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**
- corrected-delta outcome: **aligned**

### Scope and revised contract

用户最新要求是“整个轨迹加载”“切换过去了，然后再选中对应段”。本轮依据归档spec澄清、design的完整轨迹/历史/选区决定、已同步canonical与delta核对限定修正范围。此前“仅显示本次投影”“切换会话历史”的结论明确失效；后台运行事实、固定observer、父frame保留、只读/身份/附件边界及W2父会话分页证据没有因本修正失效。没有重审无关main或重跑全量套件。

### Correctness and coherence

| 修正契约 | 实现证据 | 测试/证据 | 结论 |
|---|---|---|---|
| 完整子会话含fork前缀及其他epoch，不过滤记录 | `TrajectoryView.tsx:164–180` completeInspection=rawInspection；initialRunId时historyStartIndex=0；scopeSnapshot与历史开关删除 | 实际local注册bundle保留Input 1并标outside；原生选区存在；未显示历史切换 | aligned |
| 关系核对后补齐全部历史，恢复及软失败仍可读原会话 | `use-run-navigation.ts:40–52` hasMore判断、loadThrough(0)、完成后覆盖确认、retry；`boot.jsx:127`真实Session.hasMore | 独立hook回归确认读取0、同会话窗口重建再读、软失败告警与重试恢复 | aligned；原W1恢复约束继续成立 |
| 原生自动选区，区间外淡化，可手动调整/清除 | `TrajectoryView.tsx:411–435`和原onClearSelection；`executionFocus`仍按真实seq成员在当前时间模式推导 | 独立精确成员/四时间模式及实际原生selection probe；author真实图显示完整背景与#447–470选区 | aligned |
| 顶部当前执行随push/pop同步，显式下拉打开所选会话 | `agent-trajectory.tsx:20–23` activeTarget callback；`agent-work-panel.tsx:93–105,158–161` shownNative与显式选择version | 宿主19 tests证据含push/pop回调；作者实际fork/返回选择器走查；独立核对接线与截图 | aligned |
| 不丢原生明细、返回上下文或只读边界 | 完整snapshot保留request/partial/runningCalls；原父frame保留和身份释放路径未变；未新增执行方法 | 原有效详情/权限/宿主证据保留；新测试仍校验身份与坐标；W2父尾窗bundle回归继续通过 | retained |

### Direct evidence and reference contract

独立运行UI **2 files / 6 tests passed**，18:01:52、556ms；独立运行实际local注册bundle **1 file / 1 test passed**，18:01:52、2.50s，日志`/tmp/feat589-static-full-focus-probe.log`。后者通过公开注册取得原生组件，确认继承Input 1仍存在且淡化、自动原生selection存在、无本次/历史开关，实际经过新呈现路径。新hook测试同时验证完整历史恢复；未沿用已删除的过滤测试冒充完整会话保护。

复用 `/tmp/feat589-selector-green.log`：宿主2 files /19 tests passed（17:50:09、1.35s），以及`/tmp/feat589-focus-types.log`和作者记录中的build成功证据。独立检查`evidence/native-full-session-focus.png`：完整背景时间轴可见，末端#447–470高亮，继承记录淡化，顶部当前执行为技能复盘，与design显式must-match及作者63084真实旅程记录相符。该图为真实服务durable evidence，静态verifier不据此给新增全跨屏体验评分。

### Issues and limits

无CRITICAL/WARNING/SUGGESTION。指定差分足以核对本轮变化，无共享运行时边界影响，`requires_full_verification=false`。`git diff --check d737d1dca 9f6a47f13`通过。未修改实现、未提交报告、未触碰保留服务；旧产品验收只在未受影响范围retained，过滤行为相关结论已被本轮新契约/证据替换。

## Round 5 Delta Snapshot (historical)

| Delta item | Final implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 默认聚焦一次执行：完整轨迹包含继承前缀与其他执行，不过滤 | rawInspection完整保留、进入run取消50节点截断、loadThrough(0)/hasMore确认；原生executionFocus选区 | 独立6tests及实际bundle Input1/outside/native selection/no switch回归 | aligned |
| 检查全部原生明细：同组件、直接改/清选区、顶部当前执行同步 | 原完整snapshot与native handlers；activeTarget callback、shownNative与显式选择version | 宿主19tests/作者实际返回及选择器记录、独立静态接线和截图 | aligned |
| 运行/终态/未知/中断恢复 | 后端不变；完整历史重建与soft failure retry取代仅补startSeq | 独立hook重建/失败恢复；此前真实DSH终态证据保留 | aligned |
| 真实发起位置、并行/重复/嵌套与持久关系 | producer run facts、真实seq成员、durable身份与frame栈未改 | 原适用run/冷读/权限证据保留；新bundle保留W2父窗口保护 | aligned |
| 返回上下文、跨屏身份与只读边界 | 保留祖先frame、释放子frame与身份key；无新执行/附件权限 | 原适用宿主/权限/跨屏证据retained；本轮受影响真实fork/返回记录 | aligned |

### Uncovered Observable Behavior

None。完整会话加载、继承/其他epoch保留、自动选区与手动修改、取消历史开关、顶部选择器同步均由校正delta明确覆盖；spec/design/canonical与实现一致。没有通过静默修改契约适配旧过滤行为。

Outcome: **aligned**。


## Round 6 — Final Sync Impact Verification

- reviewer: `/root/feat589_native_static`，未参与实现
- verification_mode: `delta + corrected-delta`
- executed_base / fix_delta_range: `1caed76ae` / `1caed76ae..96f5ac497`
- validated_at: `96f5ac497dbe5d330cf8ac5467dc367186c6a4f3`
- origin/main: `74bfff7f7`
- requires_full_verification: `false`（具体空间资格交叉可定向关闭；无需重新验全部UI/主干功能）
- verdict: **FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**
- corrected-delta outcome: **implementation-mismatch**（最终既有资格边界；R5完整轨迹契约仍aligned）

同步范围核对：Work HTTP入口用requireSpace，updated广播用canAccessSpace；原生browser/valid新增reader空间和owner恒等检查，runs仍走既有固定observer及只读allowlist，原附件对象权限保留。UI/viewer/宿主选择器与run事实源码未变，因此Round5完整会话/原生选区/下拉同步及Round4未失效静态证据retained。main新功能本身不扩为本轮验收任务。

### WARNING W3 — mixed-owner停用后company原生读取继续（CONFIRMED）

- 契约：`docs/specs/im/auth-tenancy.md`“停用立即覆盖真人与机器”，原company Agent不因owner仍有私人空间继续公司接入；授权成员可读保留的共享历史不等于继续接入已失效company运行时。
- 位置：`apps/im-server/src/trajectory.ts:33,105–109`；组合条件为 `identity.ts:49–59` 的Agent空间资格和 `gateway.ts:62–73` 的节点级accountEnabled。
- 直接证据：最小真实类/隔离SQLite probe `/tmp/feat589-space-sync.ts`；执行`pnpm exec tsx /tmp/feat589-space-sync.ts`。owner个人空间保持true，真实transition停用company资格后agentAvailable=false，节点仍valid，Work.append已ack但新company事件0条；合法company reader经既有observer的session/page仍被转给node并收到新结果，browserState仍1。结果JSON保存在本轮code-review；不依赖真实外部执行，也不改live或源码。
- 建议：初始browser prepare及持续valid均核对agentAvailable，并保留reader canAccessSpace、固定owner与原附件规则；补同条件company观察撤销/新连接拒绝以及private继续可用的最低层回归。已交caller修复，不修改spec去放行失效company数据面。

适用证据：作者build/typecheck/frontend build通过；`/tmp/feat589-main-sync-tests.log` **3 files / 12 tests passed**（18:26:12、5.84s）覆盖普通space隔离、runs只读、mutation与附件；没有覆盖W3，不能据此判最终权限组合pass。作者63084更新后正常reader进入完整fork、#447–470选区和下拉技能复盘成功，docs-check230 sources/64 routes通过；这些事实与W3不冲突。`git diff --check 1caed76ae 96f5ac497`通过。

## Round 6 Delta Snapshot (historical)

| Item | Evidence | Outcome |
|---|---|---|
| 完整会话+原生选区、手动选区、选择器与返回 | 相关产品源码sync无变化；R5证据和作者最终正常路径有效 | aligned / retained |
| 真实run关系、epoch、状态与只读方法 | run事实及固定observer/allowlist未变；runs e2e在同步测试中通过 | aligned / retained |
| 继承既有Work资格、身份释放和附件边界 | reader空间规则正确，但失效company Agent仍经保留private节点接入原生数据面；直接probe确认W3 | **implementation-mismatch** |

### Uncovered Observable Behavior

没有新增feat-589 UI行为需要补delta。main引入的私人/公司空间规则已由current auth-tenancy和Work specs维护；W3是与既有资格契约组合后的实现缺口，应定向修复。Outcome: **implementation-mismatch**。


## Round 7 — W3 Targeted Closure and Final-Sync Validity

- reviewer: `/root/feat589_native_static`，未参与修复
- verification_mode: `targeted-closure + corrected-delta`
- executed_base / fix_delta_range: `96f5ac497` / `96f5ac497..bdeb9741b`
- validated_at: `bdeb9741bdf5577fb354a1e233f0e33a9af69383`
- focus_issues: `W3`
- requires_full_verification: `false`
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**
- validated_issues: `W3 closed; prior W1/W2 applicable protections retained`
- corrected-delta outcome: **aligned**

| Closure condition | Implementation / direct evidence | Outcome |
|---|---|---|
| 已失效company Agent不得通过保留private节点继续原生读取 | `trajectory.ts:107`加入真实agentAvailable，双向每帧、node配对和check共用该valid；独立原probe不再转发停用后session/page，browser以1008关闭 | W3 closed |
| 不能重新prepare相同company观察 | `trajectory.ts:33`初始资格同样叠加agentAvailable；新真实类tenancy回归确认failed与closed | covered |
| 共享节点/private功能不被连带关闭 | Gateway节点资格未改；回归确认node valid=true，owner重新登录后private观察可配对且session/page转发成功 | covered |
| 授权成员仍可检查保存的共享Work历史，原只读/附件边界不扩大 | Work HTTP路由及只读allowlist/原附件检查未改；只限制不可用Agent的运行时观察通道 | retained |

独立复跑新tenancy回归 **1 passed /6 unselected**（18:34:28、1.09s），并重跑R6原probe：`companyAgentAvailable=false`、`nodeStillValid=true`、company新Work事件0条、`nativeReadForwardedAfterRevocation=false`、`nativeBrowserState=3`、关闭码1008。原错误条件已直接消失，不以普通active路径替代停用场景。probe隔离库自动清理。

复用作者修复后 **3 files /13 tests passed**（18:33:12、5.46s；`/tmp/feat589-space-fix-green.log`）、IM build/tsc证据。修复使用同一空间资格owner判断，未新增权限抽象、fallback或节点级停用逻辑。`git diff --check 96f5ac497 bdeb9741b`通过。

最终sync判定：R6空间入口、广播、固定observer和只读/附件组合的无问题部分retained；唯一W3已关闭。R5完整轨迹/自动与手动选区/下拉/返回实现和测试未变化，R4/R5其余未失效证据retained。作者96f5同步后63084普通reader完整child正向走查与docs-check仍适用；本轮不改UI或该active资格路径，无需重新执行完整产品旅程或主干feat587/588功能验收。报告不代称bdeb为已发布/部署；live更新由主任务负责。

## Corrected Delta Reconciliation

| Item | Evidence | Outcome |
|---|---|---|
| 完整会话与原生选区、顶部选择器、父子返回 | UI/宿主源码不变，Round5独立组件及宿主证据和最终正常reader走查保留 | aligned / retained |
| run关系、epoch、状态和只读传输 | 原运行事实、固定scope和allowlist不变；修复后相关IM套件通过 | aligned / retained |
| 既有Work空间资格、身份失效、原附件边界 | prepare与valid均叠加agentAvailable，company失效关闭且private继续可读；独立失败probe转为拒绝 | aligned；W3 closed |

### Uncovered Observable Behavior

None。W3修复兑现current auth-tenancy既有company停用/私人节点边界，未增加feat-589 UI行为或放宽delta；无需补主干功能验收或修改spec适配错误实现。Outcome: **aligned**。
