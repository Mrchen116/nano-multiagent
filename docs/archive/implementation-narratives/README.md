# 已退役实现叙事

本目录保存曾用于指导实现、后来已被代码和 current specs 取代的长篇实现说明。它们可用于理解历史语境，不能用来判断系统当前接口、目录结构或运行行为。

## Kernel design details

[`kernel-design-details/`](kernel-design-details/) 的四篇文档来自 2026 年 2–3 月的早期内核设计：

| 历史文档 | 退役原因 | 当前入口 |
|---|---|---|
| [`Hook体系设计细化.md`](kernel-design-details/Hook体系设计细化.md) | 混合目标、内部模块路径和建议接口；目录拓扑已变化 | [`Gateway contracts`](../../specs/gateway/spec.md) |
| [`Skill体系设计细化.md`](kernel-design-details/Skill体系设计细化.md) | `read(location)`、`task.load_skills` 等接口已被取代 | [`Gateway contracts`](../../specs/gateway/spec.md) |
| [`工具设计细化.md`](kernel-design-details/工具设计细化.md) | 外部实现摘录和具体返回文案容易与代码分叉，旧 `task` 接口已退役 | [`Gateway contracts`](../../specs/gateway/spec.md) |
| [`系统提示词.md`](kernel-design-details/系统提示词.md) | 单体模板已被 prompt skeleton、sections 和 `PromptSlots` 取代 | [`Gateway contracts`](../../specs/gateway/spec.md) |

仍需长期保证的消费者行为已经写入 current specs；准确的类名、参数、模板文本和内部数据流由代码、类型和测试表达。历史文档保留原文，只新增退役说明和 current 入口。

## CLI call sequence

[`CLI到工具调用时序图.md`](CLI到工具调用时序图.md) 记录早期 HTTP ServerClient/API 架构下的 CLI 调用链。旧 Coding CLI 已退役；当前个人助手行为入口见 [`Gateway contracts`](../../specs/gateway/spec.md)。
