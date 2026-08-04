# bugfix-500: agent create rail

## Relations

- Related: feat-340-agent-native-im

## 原始报告

> http://100.88.34.122:8011/settings/agents/new 为啥不带左边的agent列表，不像我已有agent的情况，导致很丑
>
> 见 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-14e6da9b-75b0-4972-9b30-a06dc9e632f6.png`
>
> 我记得之前改过这个问题呀
>
> 新建unit，修复这个问题

## 澄清记录

- Q1: 桌面端新建页是否应与已有 Agent 详情页完全一致地显示左侧 Agent 列表，而移动端继续不显示？
  A(原话): 好
  Agent 解读: 桌面端新建页复用现有 Agent rail；移动端保留单栏创建流程。
- Q2: 从节点页进入的 `/settings/nodes/:nodeId/agents/new` 也要显示同一左侧 Agent 列表吗？
  A(原话): 对
  Agent 解读: 两个新建 Agent 路由都显示同一桌面 Agent rail。
- Q3: 用户已在新建表单填写内容后，点击左侧已有 Agent 时该如何处理？
  A(原话): 如果用户已经填了东西，，不小心按错了切换，会很苦恼
  Agent 解读: 未提交的新建内容不能因误点既有 Agent 而无提示丢失。
- Q4: 新建表单有未提交内容时，点击左侧已有 Agent 是否应先弹出确认框，提供“继续编辑”和“放弃并切换”？空白表单则直接切换。
  A(原话): 应该提醒类似：未保存，是否确认退出。
  Agent 解读: 离开含未保存内容的新建页前，须以“未保存，是否确认退出”提醒用户；用户确认后才离开。
- Q5: 这个“未保存，是否确认退出”提醒，是否应覆盖新建页的所有站内离开操作——侧栏切换、取消按钮、移动端返回——而不是只覆盖侧栏？
  A(原话): 好
  Agent 解读: 所有站内离开新建页的操作都遵循同一确认；浏览器关闭与刷新不在本次范围。

## 现象 / 复现

在桌面端，用户从 `/settings/agents/new` 或 `/settings/nodes/:nodeId/agents/new` 进入新建 Agent 页面时，页面没有已有 Agent 详情页同样的左侧 Agent 列表，导致两个相邻入口的工作区布局断裂。

如果用户已经填写新建表单，当前页面的取消、返回与未来新增的侧栏切换都可能让用户离开页面。用户必须在未保存时先看到“未保存，是否确认退出”的提醒；取消退出应留在原表单并保留已填内容，确认退出后才进入所选目标。空白表单离开时不需要确认。桌面端以外保持现有单栏创建体验；浏览器关闭和刷新不在本次范围。

## 根因

左侧 rail 最初由 `feat-340-agent-native-im` 的 M20 R12-bis-1 引入，其退出标准明确限定为“Agents detail 1440 viewport”。对应提交 `5c9e896a4` 只修改 `AgentDetailPage`、其测试和 edit 测试；历史中没有把 rail 加到 `AgentCreatePage` 的提交。因此这是该视觉修复的范围遗漏，而不是后来回归。

当前两个新建路由都直接渲染 `AgentCreatePage`，而 rail 定义并仅挂载在 `AgentDetailPage`。新建页也没有未保存草稿的离开保护：取消和移动端返回直接导航。既有测试只验证详情页有 rail、创建页的 Cancel 指向列表，未覆盖桌面新建页的 rail，也未覆盖填写后离开，因此遗漏没有被捕获。

修复必须保留已有详情页的桌面 rail、移动端新建页的单栏布局，以及成功创建 Agent 后直接进入新建 Agent 详情页的流程。

## 修复

- 把桌面 Agent rail 提取为 `AgentsRailDesktop`，由详情页和两个新建路由共用；新建状态的 `+ New` 显示为当前、不可重新触发，避免它重置进行中的表单。
- 桌面新建页使用与详情页相同的 240px rail 和内容滚动容器；移动端仍只显示原有单栏创建页。
- 任何用户编辑都会标记草稿为未保存，并由路由 blocker 覆盖所有站内导航（包括侧栏、取消、移动端返回、顶部/底部导航、用户菜单和浏览器后退）。用户菜单退出登录也先发起到登录页的路由导航，再清理会话，避免先卸载 blocker。未编辑时仍直接离开；编辑后统一先显示“未保存，是否确认退出？”。选择“继续编辑”保留所有字段，选择“确认退出”才导航到原目标。
- 成功创建后的既有直接进入新 Agent 详情页行为不变；未扩大到浏览器关闭或刷新保护。

## 验证

- TDD：先为桌面 rail、空表单直接切换、填写后侧栏切换确认与填写后取消确认补上失败用例，再实现修复。
- `cd src/IM/frontend && npm run test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/app/shell/app-shell.test.tsx`：29 passed。
- `cd src/IM/frontend && npm run build`：`tsc -b && vite build` 通过。
- 隔离真实栈：以 `scripts/e2e-up.sh --wt <unit worktree>` 启动 IM/Gateway，并以该 IM 作为 Vite 代理目标。Playwright 登录测试用户后，在 `1280px` 宽的新建页确认 rail、已有 Agent 行和与详情页一致的桌面分栏均实际渲染；移动宽度下 rail 继续由 `lg` 断点隐藏。浏览器截图仅作本地运行证据，未纳入提交。
