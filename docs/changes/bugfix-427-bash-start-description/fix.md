# bugfix-427: bash 折叠行开始调用时显示原始 command 而非 description

## Relations

- Related: feat-409（IM 工具调用展示重做，决策 4 引入 bash 折叠态人话 summary）
- Related: feat-425（工具自带展示 / presenter 随工具走，未触及本缺口）

## 原始报告

> 你看看worktree unit-feat-425 我发现bash工具的description似乎只有在工具执行完才出现，开始调用的时候没出现。你看看代码。当初做这个tool调用展示重做的时候，需求是这样吗，当初文档怎么写的，我实际上是希望bash工具从开始调用，就展示description了 。另外，Agent工具呢

澄清记录：

- Q1: 本 unit 只对齐 bash 一个工具，还是顺带把"折叠行 summary 在开始态/完成态必须一致"立成覆盖所有工具的不变量？
  A(原话): 对
  Agent 解读: 范围限定为只修 bash。已逐个核过其余工具的 `format_start`/`format_end` summary 来源：write/edit/read 用 `path`、web_fetch 用 `url`、web_search 用 `query`、memory/skill 用 `action target`、Agent 用 `description` —— 开始态与完成态用的是同一个主参数，本就一致。唯独 bash 的开始态取 `command`、完成态取 `description`，是独有缺口。

## 现象 / 复现

IM 聊天面板里，agent 调用 bash 工具时，折叠行文案在两个阶段不一致：

1. 工具**开始调用**（进行中）阶段：折叠行显示原始 `command`（截断 80 字符）。
2. 工具**执行完**阶段：折叠行才切换成 `description`（agent 写给人看的人话），空时降级命令首段。

用户期望：从开始调用就显示 `description`（人话），而不是先看到原始命令、完成后才变人话。

对照：Agent 工具的折叠行从开始调用即显示 `description`（`_AgentPresenter.format_start` 已用 `args.description`），符合预期，不受本 bug 影响。

## 根因

展示链路（`src/agent/platform/hooks/builtins/realtime_stream.py`）：`tool_start` 事件调 `presenter.format_start(args)`，`tool_end` 事件调 `presenter.format_end(args, result)`；折叠行文案取 presentation 的 `summary` 字段。

`_BashPresenter`（`src/agent/platform/tools/builtins/bash.py:96`）两个方法的 summary 来源不同：

- `format_start`：`summary=_truncate(str(args.get("command", "")), 80)` —— 直接用原始 command。
- `format_end`：`summary=_summarize_bash(args, command)` —— 优先 `args.description`，空才降级命令首段（`presentation.py:121`）。

**设计意图追溯**：本缺口源于 feat-409 决策 4。该决策原文：

> 要让 bash 折叠态显示 description，改的是 **bash presenter 的 `summary`**（format_end 由 `exit=N elapsed=Xms` 改为 `args.description`，空则降命令首段）

决策只点了 `format_end`，从未提 `format_start`。因此这不是回归（`format_start` 自始即显示 command），而是 feat-409 实现时只盯"完成态 summary 由裸状态串改人话"、漏覆盖"开始态"的缺口。`description` 在工具调用时即随 args 由模型一次性给齐，`format_start` 拿得到，无需等执行。

**修复必须保住的不变量**：
- `format_end` 的现有人话 summary 行为（`_summarize_bash`：优先 description、空降命令首段）不变。
- 修复只让 `format_start` 同样走 `_summarize_bash`，使开始态与完成态来源一致——不改其余工具、不改前端、不改 detail 结构。

## 修复

<!-- 改了什么 + commits。worker 回填。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。worker 回填。 -->
