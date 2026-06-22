# bugfix-424: 动态建 agent 的 workspace 落主目录而非隔离区

## Relations

- Related: feat-421
- Closes: #127
- Refs: #119

## 原始报告

由 feat-421 关键路径 e2e（#119）发现，issue #127（作者 @Mrchen116）：

> ## 背景
> feat-421 关键路径 e2e（#119）在 worktree 内经 `POST /im/v1/nodes/{node_id}/agents` 动态建 agent 时发现：新 agent 的 workspace_root 落在 **主目录 `~/nano-assistant/workspace/<agent_id>`**，而非 e2e 栈的隔离区 `<wt>/.gateway-workspace/`。
>
> ## 影响
> - 所有「经 IM 动态建 agent」的 e2e（建 agent / cron / heartbeat / 群聊自建 agent）会在主目录留下 workspace 残留，污染主仓环境。
> - e2e 隔离不彻底：worktree 副本 config 的 workspace_root 改写只对**预置** agent 生效，动态建的 agent 不继承该隔离。
>
> ## 现状缓解
> feat-421 的建 agent e2e 已在测试侧稳健清理它创建的主目录 workspace 残留（teardown）。但根因（动态建 agent 不走 worktree 隔离的 workspace 派生）在产品侧未修。
>
> ## 待办
> 让 `handle_agent_create` 派生 workspace_root 时遵循当前 gateway config 的 workspace 基目录（与预置 agent 同隔离规则），而非硬编码主目录默认。

用户确认修法 A（见根因段「修复方向」）。

## 现象 / 复现

Gateway 在某个隔离的 workspace 基目录下运行（如 e2e worktree 把 config 的 agent workspace 都指向 `<wt>/.gateway-workspace/`），此时：

1. 经 IM 配置中心动态新建一个 agent（`POST /im/v1/nodes/{node_id}/agents`，请求体不带 `workspace_root`）。
2. **预期**：新 agent 的 workspace 落在与预置 agent 同一隔离基目录下（`<wt>/.gateway-workspace/<agent_id>`）。
3. **实际**：新 agent 的 workspace 落在硬编码的主目录 `~/nano-assistant/workspace/<agent_id>`，无视 gateway 当前 config 的隔离基目录。

后果：动态建 agent 的 e2e 在用户主目录留下 workspace 残留、污染主仓；隔离不彻底（worktree config 的 workspace 改写对动态建 agent 无效）。

## 根因

**派生路径**（`src/personal_assistant/main.py`）：
- `handle_agent_create`（:436-445）：IM 未传 `workspace_root` 时 fallback 到 `self._workspace_root_factory(agent_id)`。
- `_IMConfigSyncClient` 构造处（:2252）**未传 `workspace_root_factory`** 参数（构造函数在 :277 预留了该参数，缺省走 `_default_workspace_root`）。
- `_default_workspace_root`（:758-760）**硬编码** `Path("~/nano-assistant/workspace").expanduser() / agent_id`，完全忽略 gateway 当前 config。

**为什么预置 agent 没这问题**：预置 agent 不走工厂——它的 workspace 来自 `config.agents[].workspace_root`（:335），所以 worktree 副本 config 对预置 agent 的 workspace 改写生效；唯独**动态建**的 agent 落到工厂默认，绕开了 config 隔离。

**为什么这种错能进来**：动态建 agent 的 workspace 派生从一开始就接了一个产品中立的硬编码默认工厂，没有从已加载的 gateway config 派生基目录的通路；构造处也没把 config 的隔离意图接进工厂。隔离机制（worktree config 改写）只覆盖了「预置 agent」这一条路径，「动态建 agent」这条路径在隔离设计里是盲区——直到 feat-421 在 worktree 内真动态建 agent 才暴露。

**修复方向（已与用户对齐，修法 A）**：让动态建 agent 的 workspace 基目录从 gateway config 派生，而非硬编码主目录——给 config 增一个 workspace 基目录字段，构造 `_IMConfigSyncClient` 时注入一个据此派生的 `workspace_root_factory`（`<base>/<agent_id>`）；`e2e-up.sh` 把该基目录写成 worktree 隔离区即自动隔离。

**修复必须保住的不变量**：
1. **向后兼容**：未配置该 workspace 基目录字段的现有部署，动态建 agent 行为**不变**——仍落 `~/nano-assistant/workspace/<agent_id>`（缺省回退现有默认工厂）。
2. **预置 agent 不受影响**：预置 agent 仍以 `config.agents[].workspace_root` 为准（`:335` 路径不动）。
3. **IM 显式传 workspace_root 时仍优先采用**（`:437-443` 分支不动）。
4. workspace 创建后不可变（bugfix-404-M2 既有约束）继续成立——本修只改「新建时基目录从哪派生」，不碰已存在 agent 的 workspace。

## 修复

<!-- worker 在 milestone 完成后回填：改了什么 + commits。 -->

## 验证

<!-- worker 回填：修前能复现（动态建 agent 落主目录）→ 修后落 config 基目录；预置 agent / 缺省回退 / 显式传 workspace_root 三条不变量回归正常。 -->
