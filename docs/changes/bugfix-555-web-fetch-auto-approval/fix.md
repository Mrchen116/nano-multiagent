# bugfix-555: 普通网页抓取进入 Auto 审批

## Relations

- Related: bugfix-355, feat-552

## 原始报告

> [http://100.88.34.122:8011/settings/agents/tes?view=work](http://100.88.34.122:8011/settings/agents/tes?view=work) 为啥正常web\_Fetch也被拒绝啊，CC不太可能也直接拒绝这些吧

> 修正

用户已在根因说明后要求修正，并明确“别用 change-orchestrator，自己简化流程。在 worktree 内高质量完整就行”。修复范围是普通网页抓取的 Auto 审批分流，保留显式禁止、显式人工确认与 URL 安全检查；不改变默认提示词，不通过域名白名单或跳过权限规避问题。本次在独立 worktree 完成实现与验证。

## 现象 / 复现

2026-09-12，生产版本 `879760c5ffa2e5f10240ad74562c4dd27ecfc064` 的 Global Agent `tes` 接到上网调研小红书游戏工具的请求。工作记录中，主会话 `sess_e135993c2831dde4` 的轮次 `turn_391c05f0eaf0160a` 在 14:20:13 UTC 抓取 `https://open.xiaohongshu.com/document/developer/file/4`，立即收到 `permission not granted yet for open.xiaohongshu.com`。随后腾讯新闻、知乎及子 Agent 抓取 GitHub 也遭遇同类拒绝。

使用该提交的真实 `WebFetchTool` 与 Auto Gate、本地隔离的 hook context 复现：小红书与 GitHub URL 的工具决定是 `ask` / `fallback`，Gate 返回 `block=true` / `manual_required`，审批模型调用为零；预批准的 `https://docs.python.org/3/` 正常通过。生产全局 Auto 配置没有自定义覆盖，tes 工作区没有 Auto 配置文件。

### Requirement: 普通网页抓取可以由 Auto 审批

#### Scenario: 用户要求上网调研
- **WHEN** Auto 模式中的 Agent 或其普通子 Agent 抓取任务相关的公开网页，域名没有显式允许、拒绝或人工确认规则
- **THEN** 该动作接受自动审批；自动审批允许后实际抓取，不因域名首次出现就直接拒绝或等待人工确认。

#### Scenario: 自动审批没有允许
- **WHEN** 普通抓取被自动审批拒绝，或审批服务无法给出有效结果
- **THEN** 不执行抓取，继续遵循该运行入口已有的拒绝、人工处理或无人值守策略。

### Requirement: 必须保留的限制继续生效

#### Scenario: 明确限制或不合法 URL
- **WHEN** 请求匹配显式拒绝、显式人工确认，或 URL 本身不合法
- **THEN** 继续按原有保护处理，不因普通域名修复而自动放行。

#### Scenario: Auto 关闭或目标已预批准
- **WHEN** 用户关闭 Auto，或请求命中已有预批准／允许规则
- **THEN** 分别保留人工审批或既有允许行为，不增加无关自动审批。

## 根因

`WebFetchTool.check_permissions` 的默认分支把“域名尚未授权”表示为 `ask`，带 `decision_reason.type=fallback`。Auto Gate 对工具返回的所有 `ask` 一律执行 `escalate(..., manual_required)`，没有区分默认未决与显式人工约束。Global 的 `return_to_agent` 路由随后直接返回阻断，因此请求无法到达分类器。这个组合来自旧权限接线，本次 feat-552 迁移沿用后，在全局模式表现为即时拒绝。

原始意图见 bugfix-355 的工具权限决策链与 feat-552 的共享 Auto / 全局拒绝分流：工具规则与安全限制仍有效，普通未决操作应按当前权限模式处理。普通 `fallback ask` 不等于显式 `ask` 规则。固定官方 CC 2.1.267 包（SHA-256 `a681f3008f0050029aeebcab3af51bb6a55ddeb625a3af3141a4416d43cd2558`）中，WebFetch 默认返回 `ask`；权限入口 `TOo` 对 Auto 下该结果继续判定，仅将显式 ask、安全／交互约束保留为人工路径。对应字节位置：WebFetch 检查 `166673780`，Auto 分流 `165617957`，人工例外约 `165618450`，分类调用约 `165624015`。这属于静态实现观察，不冒充真实 CC 模型实验。

已有 Gate 分流测试用 mock 工具返回 `passthrough` 验证分类路径，未验证真实 WebFetch 默认返回的 `ask/fallback`，因此不能拦住这条产品接线错误。修复必须用真实工具保护这一边界，并保留明确权限限制与 Auto 关闭的原行为。

## 修复

Auto Gate 仅在 Auto 已启用、工具返回 `ask` 且原因为 `fallback` 时继续分类；其他 `ask` 仍走原有人工处理分流。工具的 URL 校验、预批准、显式规则和分类器拒绝／故障处理保持各自职责。

真实 SDK 回归同时暴露配置接线遗漏：`WebFetchTool` 原先只读没有运行时装配方写入的 `_auto_mode_config`，导致工作区域名规则未被消费。修复为从会话配置 loader 读取规则，普通子 Agent 优先使用继承的父策略快照；不向共享工具对象写入会话配置。只改 Gate 的中间版本有 6 项显式域名规则回归失败，补齐此接线后通过。

消费者行为已同步到 [kernel tools-hooks](../../specs/kernel/tools-hooks.md)。

## 验证

- 新增 `tests/integration/test_web_fetch_auto_approval.py`：真实 SDK、内置 WebFetch 和内置 agent 派生子会话；仅模型回复及 HTTP 传输使用可控替身。主／子会话各覆盖允许、两阶段拒绝、审批不可用、无有效结果、显式 ask/deny/allow、预批准、Auto 关闭、非法 URL，共 20 项；同时断言审批次数、实际 HTTP 调用次数及抓取正文进入后续模型请求。未修复版本 10 失败／10 通过，修复后全部通过。
- Auto Gate、交互分流、WebFetch 权限／结果／配置、审批上下文与 SDK 行为契约，共 **218 passed**。Ruff 检查、格式检查、`scripts/docs-check` 与 `git diff --check` 通过。
- 真实隔离 IM → Gateway → Global Inbox → 工具 → 聊天回复：DeepSeek `deepseek-v4-flash` 主模型、`gpt-5.6-luna` 审批模型，未替换模型或 HTTP 响应。节点 `wt-unit-bugfix-555-39462`、IM `127.0.0.1:61974`、Agent `webfetch555`；消息 `aef80b06618a4823a8297e69dd3c7408`，聊天 `c_ym8qc8ik`。主会话 `sess_60bc4a0c20b75392` 抓取 `https://example.org/`，子会话 `sess_76ca6a6065943b7b` 抓取 `https://raw.githubusercontent.com/python/cpython/main/README.rst`。两者均经真实 Luna S1 `<block>no</block>` 后执行，HTTP 200，公开工作记录显示 completed 和正文，最终聊天分别收到标题。
- 上述实际审批请求定位于 LLM_PROXY `logs/session/2026-09-12_22-41-35_353_sess_60bc4a0c20b75392/2026-09-12_22-41-38_858-req-anthropic_messages.json` 与 `logs/session/2026-09-12_22-41-43_572_sess_76ca6a6065943b7b/2026-09-12_22-41-43_572-req-anthropic_messages.json`，配对响应各明确允许。这里只记录可复核定位，不提交原始日志或数据库。

本次交付不包含合并或生产部署。
