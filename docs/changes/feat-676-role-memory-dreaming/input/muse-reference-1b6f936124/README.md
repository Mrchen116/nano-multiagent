# Muse 原始说明参考

来源为第三方公开收集仓库 `asgeirtj/system_prompts_leaks`，固定 commit `1b6f936124b4eceb6e697a69da07519bea67feab`，2026-10-29 重新读取。下列正文按 GitHub blob 逐字节校验，文件名加 original 防止当作 Nano 指令。它们不是 Nano 的运行提示，不因保存于仓库获得执行权。

这是 Muse 公开流出说明，不是官方开源实现；没有拿到完整后台 Dreaming system prompt、调度/分页/提交源码。只能据原文确认其描述的职责，不能把运行周期和产物描述当成已实测行为。收集仓库标注 [CC0](https://github.com/asgeirtj/system_prompts_leaks/blob/1b6f936124b4eceb6e697a69da07519bea67feab/LICENSE)，保留来源身份，不将该标注当作 Muse 官方发布声明。

| 本地原文 | 上游路径 | Git blob SHA-1 | SHA-256 |
| --- | --- | --- | --- |
| [memory.original.md](memory.original.md) | `Meta/muse-agent/docs/memory.md` | `3521939c3165822c37908f996e832754905d4ca0` | `f41267adf57ae73a443ea219a2427ea89d513787f87b1345ced5288870e63816` |
| [self_improvement.original.md](self_improvement.original.md) | `Meta/muse-agent/docs/self_improvement.md` | `5dcc9e2d0f2603d1b65295ac28f2cfa098c9bcaf` | `aaf856069ffc853c259ae82660b084e257560bb4ae634731a57bdebf13df93e9` |
| [operating-notes.original.md](operating-notes.original.md) | `Meta/muse-agent/AGENTS.md` | `0d1c88c421a1b1f8a2df3975b5779a467dc6119a` | `50c6238dee6f5df15da6f683d6e6f9ec54d74b8784b82de1c6cd6a5de36f1958` |
| [proactive-preferences.original.md](proactive-preferences.original.md) | `Meta/muse-agent/PROACTIVE_PREFERENCES.md` | `c1ce772adc61e180397ff0bcfa1612a42f644391` | `fc16d125c2cece493aabfedc16f2949fc0726659e1be3c2e6c0161c6d68168a1` |

固定目录：[Muse 文件树](https://github.com/asgeirtj/system_prompts_leaks/tree/1b6f936124b4eceb6e697a69da07519bea67feab/Meta/muse-agent)。本轮检查该目录树，没有发现独立夜间 Dreaming 提示或关系维护实现；Goals 下的 relationships 文件属于目标辅导，不能拿来冒充关系记忆作业。

`self_improvement` 是后台记忆、关系维护与互动反思的主要依据；`memory` 说明前台记住/修改/忘记及后台关系；`proactive-preferences` 给出用户希望听到什么、不希望听到什么、时机及表达的维度；`operating-notes` 区分工作经验与用户事实。阅读过的 USER/SOUL 只帮助判断职责边界，不复制其中个人实例或自我人格设定。

本轮不新建 Muse 的目录、日夜多个调度器、Goals/Ideas 卡片或 Skill 自动复盘。原文如何进入 Nano 的角色文档、Global 整理关注和提示词，见 [design 的内容映射与适配](../../design.md#global-的-muse-参考与-nano-内容落点)。先读这些原文再改提示，不能只依据本页摘要实施。
