# Research

本目录保存外部项目比较、阶段性审查、脑暴和其他带时间/基线的研究快照。它们提供调查证据和历史语境；
当前产品、架构、行为和开发流程仍从 [`../README.md`](../README.md) 路由到各自的 current owner。

## 研究入口

| 入口 | 内容 | 使用方式 |
|---|---|---|
| [`upstreams.md`](upstreams.md) | 本地参考仓、主要参考面和基线记录规则 | 开始外部实现调研时先读 |
| [`comparisons/`](comparisons/README.md) | Claude Code tools/kernel 等外部实现比较 | 读取页首基线，再回当前实现核实 |
| [`brainstorms/`](brainstorms/README.md) | 尚未成为 current 的方案探索 | 核对 adopted/superseded/review pending 状态 |
| [`architecture-reviews/`](architecture-reviews/README.md) | 针对特定代码基线生成的架构审查快照 | 查候选来源；再回 current 架构和代码验证 |

Agent-Native 文档体系研究会在完成来源对账后接入本索引。

## 快照最小信息

纳入本目录的研究至少写清：

- 状态：research snapshot、review pending、adopted、partially adopted 或 superseded；
- 记录日期与 nano commit 基线；
- 外部项目 commit/版本；当时没有记录时明确写“未记录”，不使用今天的 checkout 反向代填；
- 哪些结论已经进入 current code/spec/workflow，哪些仍待裁决；
- 对应 current owner 或 active issue/change。

研究正文记录当时的观察。后续代码前进时更新页首状态和索引，不把历史正文改写成今天的结论。

## 消费规则

1. 先读页面状态、日期和基线。
2. 把研究结论当作调查线索，回到当前代码、[`../../SPEC.md`](../../SPEC.md)、
   [`../specs/`](../specs/README.md) 或 [`../development/`](../development/README.md) 核实。
3. 仍值得实施的缺口进入 issue/change；已经验证的稳定结论归并到唯一 current owner。
4. 本机生成但未纳入索引的报告仍是 local snapshot，不因文件位于 `docs/` 就获得仓库权威。
