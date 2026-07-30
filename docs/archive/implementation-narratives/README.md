# 已退役实现叙事

本目录保存曾用于指导实现、后来已被代码和 current specs 取代的长篇实现说明。它们可用于理解历史语境，
不能用来判断系统当前接口、目录结构或运行行为。

## Kernel design details

[`kernel-design-details/`](kernel-design-details/) 的四篇文档来自 2026 年 2–3 月的早期内核设计：

| 历史文档 | 退役原因 | 当前入口 |
|---|---|---|
| [`Hook体系设计细化.md`](kernel-design-details/Hook体系设计细化.md) | 混合目标、内部模块路径和建议接口；目录拓扑已变化 | [`docs/specs/kernel/tools-hooks.md`](../../specs/kernel/tools-hooks.md) + `src/agent/{core,platform}/hooks/` |
| [`Skill体系设计细化.md`](kernel-design-details/Skill体系设计细化.md) | `read(location)`、`task.load_skills` 等接口已被取代 | [`docs/specs/kernel/skills.md`](../../specs/kernel/skills.md) + `src/agent/core/skills/` |
| [`工具设计细化.md`](kernel-design-details/工具设计细化.md) | 外部实现摘录和具体返回文案容易与代码分叉，旧 `task` 接口已退役 | [`docs/specs/kernel/tools-hooks.md`](../../specs/kernel/tools-hooks.md) + `src/agent/platform/tools/` |
| [`系统提示词.md`](kernel-design-details/系统提示词.md) | 单体模板已被 prompt skeleton、sections 和 `PromptSlots` 取代 | [`docs/specs/kernel/prompts.md`](../../specs/kernel/prompts.md) + `src/agent/core/agent/prompt_sections/` |

仍需长期保证的消费者行为已经写入 current specs；准确的类名、参数、模板文本和内部数据流由代码、类型和
测试表达。历史文档保留原文，只新增退役说明和 current 入口。
