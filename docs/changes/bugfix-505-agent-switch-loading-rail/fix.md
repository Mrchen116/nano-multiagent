# bugfix-505: Agent 切换加载与导航栏

## Relations

- Related: bugfix-500, refactor-483

## 原始报告

> 切换的时候，卡住的页面为啥没了左边，而且这个加载页面很丑，不符合商业的IM的设计

> 另一个问题，左边的agent名字和背景，对比度不够，很难看得清，很丑。

截图：

- `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-b65bf1cb-8acf-4394-ac04-7115171c9de4.png`
- `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-5bda6115-41fe-4a6e-9b81-51c354bcd1cb.png`

## 澄清记录

- Q1: 是否将修复范围收口为桌面端 Agent 配置切换的连续导航和左侧 Agent 列表可读性，保留移动端单栏与现有配置表单？
  A(原话): 独立完成这两个问题的修复。并提一个pr，中途spec，design，不需要我人工review。我做最后的pr review
  Agent 解读: 用户授权自行完成截图中两项桌面端体验问题及必要的 spec/design 流程，并以 PR 供最终审阅；不扩大为重做配置表单或其他 IM 页面。

## 现象 / 复现

在桌面端的 Agent 配置页中，从一个 Agent 切换到另一个 Agent 时，新的配置请求尚未返回会显示一整页孤立的“加载 Agent 配置中…”文本。Agent 左侧导航栏同时消失，用户不能继续识别当前产品位置或改选其他 Agent。请求失败时也会出现相同的壳层缺失。

已加载页面的 Agent 左栏中，未选中 Agent 的名称采用了比深色背景更暗的文字色。多个 Agent 同时出现时，名称和 agent id 难以辨认，无法承担持续导航的职责。

复现：在至少有两个 Agent 的桌面 Web IM 中，打开 `/settings/agents/<agent-id>` 后通过左栏切换到另一 Agent，并让后一个详情请求处于 pending；或观察未选中的 Agent 行。

## 根因

`AgentDetailPage` 在 desktop layout wrapper 之前对 loading、initial error 和未完成 detail state 直接 return。因此正常状态才渲染的 `AgentsRailDesktop` 在切换的异步窗口被卸载。该 early-return 在 `038d615a7f` 中引入；`5febbd3c3` 为 Agent 详情/创建页提取连续 desktop rail 时只把 rail 放在正常渲染分支，未覆盖这些早退状态。

`bugfix-500` 的原始设计意图是桌面 Agent 页面保持连续导航、移动端保持单栏。修复必须保持这一不变量：桌面端切换、加载或请求失败时仍可见同一套 Agent 左栏；移动端不出现桌面侧栏。

同一提交新增的 `AgentsRailDesktop` 将未选中名称设为 `oklch(0.18 0.01 240)`，而 rail 背景为 `oklch(0.24 0.012 240)`。深色文字叠在深色底上造成低对比度，且现有测试只断言侧栏存在和可点击，未断言 loading 状态保留侧栏或视觉 token 的可读关系。

## 修复

## 验证
