# bugfix-495: 清理前端测试 console 噪声并建立失败门禁

## Relations

- Depends on: refactor-489
- Related: bugfix-493
- Related: feat-388
- Related: refactor-460
- Related: refactor-486
- Closes: #217

## 原始报告

GitHub issue：https://github.com/Mrchen116/nano-multiagent/issues/217

> ## 背景
>
> 一次 clean `npm ci` 后，前端 Vitest 的 68 个测试文件、653 条测试全部通过，但在本机 Node `v25.8.2` 环境中统计到大量 stderr：
>
> - 408 条 React `not wrapped in act(...)` warning；
> - 40 条 `user stream runtime error`；
> - 68 条 `--localstorage-file` warning。
>
> CI 当前使用 Node 20。现阶段只确认测试输出噪声，不把每条 stderr 都判定为产品 bug。
>
> ## 问题
>
> 大量预期错误和未隔离的后台错误会掩盖真实回归。当前“测试全绿”无法说明：
>
> - React 异步更新是否在断言和测试结束前完成；
> - user-stream 错误是测试主动制造并验证的，还是无关测试意外启动了真实 runtime；
> - localStorage warning 是 Node 25 环境差异，还是测试 setup 本身的问题。
>
> ## 处理方向
>
> ### 1. 在 CI Node 20 环境建立基线
>
> 使用 Node 20 clean install 重跑前端测试，按测试文件和 warning 类型统计 stderr，确认三类噪声在受支持环境中的真实数量。不要直接沿用 Node 25 的统计作为 CI 基线。
>
> ### 2. 修复 React 测试生命周期
>
> 优先处理产生 `act()` warning 最多的测试文件：
>
> - 用户操作使用 awaited `userEvent`；
> - 异步 UI 结果使用 `findBy*` / `waitFor`；
> - 直接触发订阅回调或推进 fake timer 时进入 `act()`；
> - 测试结束前取消订阅、停止后台任务并等待状态更新完成。
>
> 不得通过全局过滤隐藏 React warning。
>
> ### 3. 隔离 user-stream runtime
>
> - 与 user stream 无关的组件测试 mock `subscribeUserStream`，不启动真实 runtime；
> - 成功路径测试完整提供 sync、socket 和卸载流程；
> - 故意制造 404、无效游标等错误的测试，通过注入的 `reportError` 收集并断言错误，不把预期错误直接写到全局 stderr；
> - 将剩余未被断言的 `user stream runtime error` 视为测试失败或真实待修问题。
>
> ### 4. 单独处理 Node 25 localStorage warning
>
> - 如果 Node 20 下 warning 消失，明确并固定前端开发/CI 使用的 Node 版本；
> - 如果 Node 20 下仍出现，定位测试 setup 对 `globalThis.localStorage` 的访问；
> - 只有项目决定支持 Node 25 测试时，才修改 polyfill 检测以避免触发 Node 全局 getter warning。
>
> ### 5. 清理完成后建立回归门禁
>
> 未被具体测试声明并断言的 `console.error` / `console.warn` 应使测试失败。预期错误只能在对应测试中局部捕获，不建立 stderr 数量预算，也不使用全局字符串屏蔽。
>
> ## 验收标准
>
> - 在 CI Node 20 环境运行完整前端测试时，不再出现未解释的 React `act()` warning 或 `user stream runtime error`。
> - 故意验证错误路径的测试会显式断言对应错误。
> - 无关组件测试不会启动真实 user-stream runtime。
> - Node 25 的 localStorage warning 已被明确归类为“不支持的本地环境”或得到兼容修复。
> - 新增的 unexpected-console 门禁能够让后来引入的未断言 stderr 导致测试失败。
>
> 来源：文档体系重构漂移审查 D-013。

## 澄清记录

- Q1: Node 25 的 `--localstorage-file` warning 应如何收口？
  A(原话): 同意。本 unit 只以 CI 固定的 Node 20 作为受支持的前端测试环境，并在开发入口明确这个约束；Node 25 的 `--localstorage-file` warning 归类为未支持环境现象，不为它增加兼容代码或 warning 过滤。Node 20 下的 React `act()` warning、未被测试显式断言的 user-stream runtime error 和其他 unexpected console 必须清理，并由门禁阻止回归。将来若升级 CI Node 版本，再基于新支持面单独验证和处理。
  Agent 解读: 本 unit 的可执行基线和门禁都绑定 Node 20；Node 25 不进入兼容范围。门禁覆盖 Node 20 下所有未被具体测试声明并断言的 `console.error` / `console.warn`，不只处理 issue 最初列出的两类。

## 现象与复现

### 当前 main 的受支持环境基线

2026-08-04 在 `main@a8886b2f4` 上，将 `src/IM/frontend` 的 Git 快照导出到仓外临时目录，使用 Node `20.20.2` / npm `10.8.2` 执行 clean `npm ci`，再按 CI 入口执行：

```bash
CI=1 NO_COLOR=1 npm run test
```

完整套件为 71 个测试文件、730 条测试，三次均全部通过；stderr 观测如下。计数只用于证明问题规模和分类，不是允许后续保留的预算。

| 运行 | React `act()` | `user stream runtime error` | 路由未匹配 | React Query `undefined` | `--localstorage-file` |
|---|---:|---:|---:|---:|---:|
| clean install 后首次 | 410 | 41 | 2 | 4 | 0 |
| 同依赖树第 2 次 | 406 | 40 | 2 | 5 | 0 |
| 同依赖树第 3 次 | 409 | 40 | 2 | 4 | 0 |

首轮 `act()` warning 的主要来源为：

| 测试文件 | warning 次数 |
|---|---:|
| `agent-detail-page.test.tsx` | 148 |
| `account-page.test.tsx` | 63 |
| `chat-workspace.integration.test.tsx` | 59 |
| `agent-channels-panel.test.tsx` | 39 |
| `tool-calls-panel.test.tsx` | 22 |

首轮 41 条 user-stream error 分为：25 条 `/im/v1/sync` 404、8 条相对 URL 无法解析、8 条 `max_event_id` 无效。它们出现在 Account、Agents、Nodes、Policies 和 route 等与 user-stream 错误路径无关的测试中。两个代表性聚焦集合连续运行两次，分别稳定得到 148 条 `act()` warning，以及 63 条 `act()` warning + 12 条 user-stream error，证明核心噪声不是只在全量并发时偶发。

其余 stderr 也不是可忽略的背景文本：两条 `No routes matched location "/settings/agents/a-planner"` 说明测试路由环境不完整；4–5 条 `Query data cannot be undefined` 说明 query mock 返回了 React Query 不接受的值。它们同样在测试 exit 0 时被保留。

### Node 25 与 Node 20 的边界

Node 20 的三次完整运行均没有 `--localstorage-file` warning。Node 25 的 warning 来自测试 setup 为判断是否需要 polyfill 而读取 `globalThis.localStorage`；Node 25 暴露的全局 getter 在没有 storage file 参数时会自行告警。按 Q1，本 unit 不把这项未支持环境差异改造成兼容需求，也不以过滤器隐藏它；当前开发入口需明确前端测试使用 Node 20。

### 在途 refactor-489 不能替代本 unit

开放 PR #227（`refactor-489`）会删除或合并大量低价值前端测试，并修复 user-stream fake-timer 的 CI 时序，但它没有声明关闭 #217，也没有 unexpected-console 门禁。在其 head `4f0499e7d` 上用同一 Node 20 / npm 10 clean 依赖树运行，59 个文件、555 条测试仍全部通过，同时仍有 203 条 `act()` warning、14 条 user-stream runtime error 和 2 条路由未匹配；localStorage warning 为 0。

因此 #217 是 refactor-489 之后仍成立的独立测试基础设施缺陷。实现必须基于 refactor-489 的最终测试树，避免同时改写同一批测试文件，所以本 unit 声明 `Depends on: refactor-489`。bugfix-493 会更新同一前端依赖树，但不负责 console 生命周期或门禁，故只列为 Related。

## 用户场景 / 目标状态

这里的用户是运行、维护和审查本仓前端测试的开发者与 coding agent。当前他们看到 71 个文件、730 条测试全绿，却仍需从数千行 stderr 中人工猜测哪些是测试故意制造的错误、哪些是尚未结束的 React 更新、哪些是无关测试误启了真实实时连接。真实新回归可以混在相同文本里继续得到绿色 CI。

修复后，维护者在受支持的 Node 20 环境运行完整前端套件时，绿色结果同时表示：测试断言覆盖的异步 UI 更新已经稳定收口；与 user stream 无关的测试没有悄悄启动真实 runtime；故意制造的错误由所属测试局部捕获并逐项断言。任何后来新增、但没有被当前测试明确声明的 `console.error` / `console.warn` 都直接让对应测试失败，并给出可定位的测试上下文。

Web IM 终端用户的 Chat、Settings、通知和共享 user-stream 行为不变。本 unit 改善的是测试信号，不通过关闭生产错误报告、删除真实行为保护或过滤字符串换取“安静”。

## 验收标准 / 目标状态

### Requirement: Node 20 下的绿色前端测试没有未解释 console 噪声

#### Scenario: 维护者运行完整前端测试
- **GIVEN** 贡献者使用仓库声明支持的 Node 20，并按 lockfile clean 安装前端依赖
- **WHEN** 执行完整 `npm run test`
- **THEN** 全部既有测试通过，且没有未被测试声明的 `console.error` 或 `console.warn`
- **AND** 输出中没有 React `act()` warning、意外的 user-stream runtime error、路由未匹配或 query-data 错误

### Requirement: 异步 UI 测试在可观察结果稳定后才结束

#### Scenario: 用户操作或后台结果触发 React 更新
- **WHEN** 测试驱动用户交互、订阅回调、timer 或异步数据返回
- **THEN** 维护者看到该场景的最终 UI 结果被断言，测试稳定通过
- **AND** 测试输出不伴随“更新未包在 act 中”的警告

#### Scenario: 测试卸载带后台工作的页面
- **WHEN** 维护者连续运行该页面测试和后续测试
- **THEN** 后续测试不会出现来自上一场景的状态更新、错误输出或间歇性失败

### Requirement: user-stream 错误只出现在明确验证它的测试中

#### Scenario: 与 user stream 无关的页面或组件测试
- **WHEN** 测试渲染 Chat 之外或不验证实时恢复的页面
- **THEN** 维护者不会看到该测试尝试真实 sync/socket 流程，也不会看到 user-stream runtime error

#### Scenario: 测试故意制造 user-stream 失败
- **GIVEN** 测试要验证 404、无效游标、socket failure 或恢复失败
- **WHEN** 该错误发生
- **THEN** 所属测试局部收集并断言错误及相应可观察结果
- **AND** 预期错误不写到全局 stderr，也不影响无关测试

### Requirement: 未声明 console 输出会阻止交付

#### Scenario: 新改动引入未断言的 warn 或 error
- **WHEN** 任一前端测试执行期间产生未被该测试明确声明的 `console.warn` 或 `console.error`
- **THEN** 该测试与 Frontend CI job 失败，并把输出归因到对应测试

#### Scenario: 测试需要验证预期错误
- **WHEN** 某个错误场景确实要求 console 输出
- **THEN** 只有该测试可以局部捕获、逐项断言并在结束时恢复 console
- **AND** 不使用全局字符串过滤、永久白名单或 stderr 数量预算放行

### Requirement: 前端测试支持版本边界清楚

#### Scenario: 贡献者准备运行前端测试
- **WHEN** 查阅本地开发或前端测试入口
- **THEN** 能明确看到当前支持版本是 Node 20，并与 CI 保持一致

#### Scenario: 使用尚未支持的 Node 版本
- **WHEN** 贡献者使用 Node 25 并遇到 `--localstorage-file` warning
- **THEN** 该现象被明确识别为未支持环境，不形成兼容承诺或 warning 过滤
- **AND** 将来升级 CI Node 版本时再按新的支持面独立验证

### Requirement: 清噪不改变 Web IM 产品行为

#### Scenario: 用户继续使用现有 Web IM 能力
- **WHEN** 用户使用 Chat、Settings、通知或依赖 user stream 的状态更新
- **THEN** 其可见结果、错误反馈和实时恢复语义与修复前保持一致

## 影响范围

受影响对象是所有依赖 Frontend CI 判断 Web IM 回归的维护者和 coding agent。严重度为中高：没有证据表明当前 410 条 `act()` warning 或 41 条 runtime error 对应已发生的终端用户产品故障，也没有用户数据损坏；但绿色 CI 已不能区分“断言完成”与“后台仍在更新”，真实错误可以被同类噪声掩盖。

范围横跨三类独立回归簇：React 测试生命周期、共享 user-stream 的测试隔离、全局 unexpected-console 失败门与 Node 支持文档。它们涉及 Chat、Settings、App/router、realtime 测试和公共测试 setup，需要独立回归矩阵与多个实施切片，因此采用 Full bugfix，而不是压成单 milestone lite。

## 根因分析（RCA）

### 直接根因

1. **React 测试没有等到自己启动的全部更新收口。** 多个页面在一次 render 后并行启动 React Query、effect、订阅或 timer；测试往往只等待第一个 heading/控件出现，随后立即做同步断言或结束。其余 query/child state 随后完成时，React 19 把这些更新报告为未进入测试 lifecycle。`agent-detail-page.test.tsx` 一次文件运行稳定产生 148 条，涉及 `AgentsRailDesktop`、`AgentDetailPage`、Heartbeat/Cron/Behavior/Skills 等多个子视图；这不是单个组件的一行错误。
2. **通用 route harness 在已登录状态下装载了真实 user-stream adapter。** `renderRouter()` 默认写入 authenticated session；受保护路由随后渲染 `App → useGlobalMessageToast → subscribeUserStream()`。除少数真正验证实时行为的测试外，大部分 page/route suites 没有隔离该依赖，于是模块级 runtime 发起真实 `/im/v1/sync` 与 WebSocket 流程。各测试自己的 fetch mock 对 sync 返回 404、无效对象或让相对 URL 落入 Node fetch，最终由生产 adapter 的 `reportError` 写出 `user stream runtime error`。
3. **测试环境本身允许不完整 fixture 继续通过。** 个别 route harness 没有声明导航目标，React Router 打印 `No routes matched`；部分 React Query mock 未提供值，query function 返回 `undefined`。测试只断言局部页面元素，故这些框架诊断不影响 exit code。
4. **Vitest 与 CI 只把断言失败当作失败。** `src/test/setup.ts` 只安装 DOM/storage/request polyfill，`vite.config.ts` 没有 unexpected-console policy；`.github/workflows/ci.yml` 只执行 `npm run test` 并信任 Vitest exit code。因此 React、runtime、router 和 query 的 console 错误都能与“全部通过”并存。
5. **Node 25 localStorage warning 是另一条环境支线。** setup 为判断是否需要 storage polyfill 会读取 `globalThis.localStorage`；Node 25 的实验性全局 getter 在没有 storage file 参数时告警，Node 20 不存在该输出。按 Q1，它不属于受支持环境内的代码修复面。

### 为什么这种错能进入并长期存活

- **初始 CI 契约只定义“零测试失败”。** `feat-388` 在 commit `3dbd86d77` 建立 Node 20 → `npm ci` → `npm run test` 的 Frontend job，原始目标是让 Vitest 红灯阻止合并；其验收记录 54 files / 345 tests 全绿，但没有把 console 诊断纳入退出状态。此后测试数量增长，噪声始终被解释为“全绿时的附属输出”。
- **共享 runtime 的生产意图正确，但测试消费边界漏接。** `refactor-460` 在 commit `e5c108068` 建立单标签页唯一 user-stream 生命周期，必须保住 Chat、通知和状态共享同一连接的产品不变量；后续 commit `90bb0a27d` 还让 route fixture 使用有效登录 token。user-stream 自身测试通过依赖注入收集 `reportError`，但通用 page/route tests 没有同步获得“无关测试隔离真实 runtime”的约束。
- **异步页面与测试逐步叠加，没有反向门禁。** 前端 shell/setup 可追溯到 `822915e83` / `b12a534e5`，之后 Settings、Chat、通知和 realtime 单元不断增加异步 query、effect 和子视图。Testing Library 会打印 lifecycle 警告，但仓库没有规则让新增 warning 当场失败，也没有要求每个测试结束前证明后台工作已收口。
- **Node 25 workaround 混进了公共 setup，但未形成版本权威。** `c2455fbf9` 为 Node 25/jsdom 现象加入 storage polyfill，CI 与 `feat-388` design 实际一直只支持 Node 20；本地开发文档却没有写出该边界，导致环境差异与真实 Node 20 噪声被混为一谈。
- **发现后仍只留在输出和历史证据中。** 多个旧 unit 的 progress/verification 已记录既有 `act()` 与 localStorage warning；`refactor-486` 最终在 validation 中把它转入 Issue #217，但当前门禁没有变化。开放 PR #227 的 refactor-489 会降低数量，却仍留下 203 条 `act()`、14 条 runtime error 和 2 条 route warning，说明“删改低价值测试”不能替代本 issue 的生命周期和失败门。

### 原始设计意图与必须保住的不变量

- `feat-388` 的原始意图是：前端真实回归与 Python 回归一样阻止合并。修复必须让绿色 Frontend CI 成为更强、更可信的信号，不能通过 `continue-on-error`、字符串过滤或 warning budget 弱化它。
- `refactor-460` 的原始意图是：生产 Web IM 在一个标签页内只有一个权威 user-stream 生命周期，Chat、通知与 Node/Agent 状态共享恢复语义。测试隔离不得关闭或分叉生产 runtime，也不得删除真实 realtime 行为覆盖。
- `refactor-489` 的原始意图是：永久测试只保留独立回归风险并收敛到最低 seam。#217 的实现应在其最终测试树上修生命周期与门禁，不能恢复已删除的低价值测试或用重复用例补数量。
- `refactor-486` 的原始意图是把 drift 转成独立可追踪工作，而不是在文档迁移中顺手修。Issue #217 与本 incident 正是该交接的后续 owner。

### 回归 / 引入点定位

这不是单一提交把已安静的套件回归成有噪声，而是门禁缺失与多个测试/runtime 能力叠加形成的系统性缺陷：

- `822915e83` / `b12a534e5` 建立 Vitest setup、前端 shell 与通用 route 测试基础；
- `3dbd86d77` 建立只看 Vitest exit code 的 Node 20 Frontend CI；
- `719455816` 让通用 route harness 默认使用 authenticated session；
- `e5c108068` 建立生产单例 user-stream adapter，通用 route tests 此后可经 App 间接启动它；
- `90bb0a27d` 为实时迁移把 fixture token 固定为长期有效，进一步稳定触发已登录 runtime；
- `c2455fbf9` 把 Node 25 storage workaround放入公共 setup，但没有定义 Node 支持政策。

上述提交各自服务真实功能；本 unit 不回退它们。要修的是测试生命周期、隔离边界和失败政策没有随能力一起建立的缺口。

## 修复方向

本节只锁定消费者可观察结果和高层约束；具体 harness 形态、文件切片与实现顺序留给 design。

1. 基于 refactor-489 的最终前端测试树，在 Node 20 clean dependency tree 上重新分类全部 `console.error` / `console.warn`，逐项让异步 UI、订阅、timer 和 query 生命周期在测试结束前收口。
2. 与 user stream 无关的测试不启动真实 runtime；真正验证 realtime 的测试继续从可控边界注入 sync/socket/error，并对成功、失败、恢复和卸载结果显式断言。
3. 清理路由未匹配、query-data undefined 等剩余 console 输出。预期错误只能由所属测试局部捕获、逐项断言并恢复，不允许全局字符串过滤、永久 allowlist 或数量预算。
4. 在清洁基线之上建立 unexpected-console 失败门，使未声明的 `console.error` / `console.warn` 同时让本地 Vitest 和 Frontend CI 失败，并能定位到产生它的测试。
5. 在开发入口明确 Node 20 是当前受支持的前端测试版本。Node 25 不做 storage 兼容、不加 warning 过滤；未来升级 CI Node 版本时另行验证。
6. 保持 Web IM 产品源码、用户可见 Chat/Settings/通知行为和生产 user-stream 错误报告语义不变；若清噪过程中发现真实产品缺陷，暂停并按 change workflow 独立裁决，不把它伪装成测试修复。

## 范围与非目标

范围内：

- Node 20 下当前前端 Vitest 全套的 React lifecycle、user-stream、router、React Query 与其他 `console.error` / `console.warn` 清理；
- App/router、Chat、Settings、realtime 相关测试及公共 test setup/harness；
- unexpected-console 本地/CI 失败门；
- 前端测试 Node 20 支持边界的开发文档。

非目标：

- 不改变 Web IM 终端用户功能、IM 后端协议或生产 user-stream 生命周期；
- 不通过删除真实行为断言、关闭生产错误报告、全局字符串过滤、永久白名单或 stderr 数量预算制造安静输出；
- 不在本 unit 更新 npm 依赖或处理 audit advisory，该工作属于 bugfix-493；
- 不支持 Node 25，不修改 storage polyfill 以兼容其全局 getter；
- 不把 `console.log` / `console.info` 的风格治理扩入本次 `console.error` / `console.warn` 正确性门；
- 不因为发现某条产品错误就顺手修改产品代码；真实产品缺陷需独立判断与立项。
