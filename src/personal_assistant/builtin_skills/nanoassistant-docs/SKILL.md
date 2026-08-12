---
name: nanoassistant-docs
description: Nano Personal Assistant（PA）产品说明书。用户询问 PA/Nano Assistant 能做什么、Web IM、Gateway、节点与 Agent 配置、模型、skills、tools、memory、heartbeat、cron、飞书渠道、启动、状态判断或故障排查时使用；也用于区分本机已安装版本、远端最新版和现场运行状态。不用于回答 Coding CLI、Agent Kernel 内部架构或仓库开发流程。
---

# Nano Personal Assistant 产品说明书

依据当前安装版本随包提供的专题资料回答 PA 产品问题。先判断问题属于哪个主题，再用 `read` 读取对应 reference；不要默认加载全部资料。

## 回答规则

1. 默认回答用户正在使用的已安装 PA 版本。基础产品问答不要联网。
2. 先读取覆盖当前问题的最少 reference。跨主题问题读取所有直接相关的 reference，不读取无关主题。
3. 用户询问“我的 Agent 当前选了什么”“节点现在是否在线”等现场状态时，先用当前已启用的工具或产品状态核实；把“产品规则”和“现场观察”分开写。无法读取现场时明确说明，禁止用默认值代替事实。
4. 只有用户明确询问最新版、升级变化或远端当前行为时，才使用已启用的 `web_search` / `web_fetch` 查询项目官方仓库 `https://github.com/Mrchen116/nano-multiagent`，并分别标明“本机已安装版本”和“远端版本”。远端不可用时只回答随包 reference 中的事实并说明无法确认最新版。
5. reference 没有覆盖、现场也无法核实时，直接说明资料边界或不确定性。不要编造页面、配置项、能力或修复命令。
6. Coding CLI、Agent Kernel 内部架构和仓库开发流程不属于本手册。遇到这些问题时说明边界；存在其他已启用的专门 skill 或来源时再引导用户使用。

## 主题路由

| 用户问题 | 必读资料 |
|---|---|
| PA 是什么、核心组件和概念 | [`references/overview.md`](references/overview.md) |
| 安装配置、启动 IM/Gateway、绑定并开始聊天 | [`references/getting-started.md`](references/getting-started.md) |
| Web IM、会话、消息、权限、Agent 创建与修改、模型 | [`references/web-im-and-agents.md`](references/web-im-and-agents.md) |
| Workflow、多 Agent 协作、ultracode、运行状态、暂停/恢复/保存 | [`references/workflows.md`](references/workflows.md) |
| Skills、tools、执行权限、Web 搜索、memory、会话连续性 | [`references/skills-tools-memory.md`](references/skills-tools-memory.md) |
| Gateway/节点状态、飞书和外部渠道 | [`references/gateway-and-channels.md`](references/gateway-and-channels.md) |
| Heartbeat、Cron、主动任务选择 | [`references/automation.md`](references/automation.md) |
| 启动失败、离线、绑定、能力为空、LLM 或飞书故障 | [`references/troubleshooting.md`](references/troubleshooting.md) |

读取相对路径时，以本 `SKILL.md` 所在目录为基准解析成绝对路径后调用 `read`。各 reference 都由入口直接链接，不要通过多层引用猜测资料位置。

## 来源边界

- 随包 references 是当前安装版本的产品手册，也是稳定产品问题的默认来源。
- 当前 Agent 配置、Gateway/IM 状态、日志和任务数据是现场问题的来源。
- 官方远端仓库只用于用户明确提出的最新版或升级问题。
- 本手册覆盖 PA 用户和运维者可见的产品行为，不覆盖 Coding CLI、Kernel 内部实现、仓库开发流程或尚未随当前版本发布的规划能力。
