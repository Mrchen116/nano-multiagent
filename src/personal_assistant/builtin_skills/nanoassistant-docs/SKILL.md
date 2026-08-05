---
name: nanoassistant-docs
description: Nano Personal Assistant（PA）产品说明书。用户询问 PA/Nano Assistant 能做什么、Web IM、Gateway、节点与 Agent 配置、模型、skills、tools、memory、heartbeat、cron、飞书渠道、启动、状态判断或故障排查时使用；也用于区分本机已安装版本、远端最新版和现场运行状态。不用于回答 Coding CLI、Agent Kernel 内部架构或仓库开发流程。
---

# Nano Personal Assistant 产品手册

## 回答规则

1. 默认依据本手册回答用户正在使用的已安装 PA 版本。基础产品问答不要联网。
2. 用户询问“我的 Agent 当前选了什么”“节点现在是否在线”等现场状态时，先用当前已启用的工具或产品状态核实；把“产品规则”和“现场观察”分开写。无法读取现场时明确说明，禁止用默认值代替事实。
3. 只有用户明确询问最新版、升级变化或远端当前行为时，才使用已启用的 `web_search` / `web_fetch` 查询项目官方仓库 `https://github.com/Mrchen116/nano-multiagent`，并分别标明“本机已安装版本”和“远端版本”。远端不可用时只回答本手册事实并说明无法确认最新版。
4. 手册没有覆盖、现场也无法核实时，直接说明资料边界或不确定性。不要编造页面、配置项、能力或修复命令。
5. coding CLI、Agent Kernel 内部架构和仓库开发流程不属于本手册。遇到这些问题时说明边界；存在其他已启用的专门 skill 或来源时再引导用户使用。

## 产品定位

Nano Personal Assistant 是一套在用户自己的节点上运行、配置和协作多个长期 Agent 的个人助手产品。

- Web IM 是默认入口：负责账号、会话、消息、Agent/节点配置和状态展示。
- Gateway 运行在用户节点上：主动连接 IM，接收消息，在本机执行 Agent，再把回复送回原入口。
- Agent 是可长期识别和配置的主体：拥有稳定身份、独立工作区、会话历史、skills、tools 和 memory。
- 飞书等外部渠道扩展触达范围，但不是使用 PA 的前置条件。
- heartbeat 与 cron 让 Agent 主动工作；权限、运行状态、历史和中断能力让行动保持可见、可控。

PA 不等同于终端 Coding CLI。本手册只覆盖个人助手所需的 Web IM、Gateway、Agent 和外部渠道产品表面。

## 核心概念

| 概念 | 含义 |
|---|---|
| IM / Web IM | 中心账号与消息服务及其浏览器界面。保存会话、消息和期望配置，不执行 Agent。 |
| Node | 用户拥有的一台运行节点，在 Web IM 中完成绑定并上报在线状态。 |
| Gateway | Node 上的常驻个人助手进程。主动连接 IM，托管本机 Agents、调度器和外部渠道。 |
| Agent | 长期助手主体。配置模型、提示词、skills、tools、features 和工作区。 |
| Workspace | Agent 在 Node 上的本地目录，保存会话、memory、任务和 Agent 自有资源。 |
| Conversation | 用户、Agent 或群组之间的连续聊天。历史与实时事件最终汇成同一条时间线。 |
| Channel | Web IM 或飞书等消息入口。回复通常回到触发它的原通道和原目标。 |
| Skill | 按需加载的专业说明或工作流；模型先看到名称与描述，命中后用 `skill_view` 读取正文。 |
| Tool | Agent 可实际调用的操作能力。每个 Agent 的 tool allowlist 决定本轮能执行哪些工具。 |
| Memory | 跨会话保留的稳定用户偏好和环境事实，不等同于当前任务进度或聊天历史。 |

## 最短启动路径

按“先 IM，后 Gateway，再绑定并聊天”的顺序启动。

### 1. 准备环境和 Gateway 配置

项目要求 Python 3.11+。默认 Gateway 配置位于 `~/.nano-assistant/config.yaml`。最小结构如下：

```yaml
node:
  node_id: my-macbook

agents:
  - agent_id: assistant
    title: My Assistant

channels:
  - name: web_relay
    enabled: true

im_service:
  url: http://127.0.0.1:8011

llm:
  default_model: <model-id>
  providers:
    - name: anthropic
      base_url: <anthropic-compatible-base-url>
      models:
        - name: <model-id>
```

关键约束：

- `llm` 必填，`llm.default_model` 必须登记在某个 `llm.providers[].models[]` 中。
- provider 使用 `anthropic` 或 `openai_compat`，并与上游协议匹配。
- 配置 `im_service` 时启用内置 `web_relay`。
- 省略 `agents[].workspace_root` 时，默认使用 `~/nano-assistant/workspace/<agent_id>/` 并自动创建。
- 配置、密钥、状态文件和日志属于本机运行数据，不应作为普通项目文件分享。

### 2. 启动 IM

在项目 checkout 中运行：

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011
```

访问：

- `http://127.0.0.1:8011/`
- `http://127.0.0.1:8011/chat`

先用 `http://127.0.0.1:8011/openapi.json` 判断 HTTP 是否可达。若 OpenAPI 可达但页面不存在，检查当前安装或 checkout 是否包含已经构建的 Web IM 静态资源。

### 3. 启动 Gateway

```bash
PYTHONPATH=src python -m personal_assistant.main
```

常用生命周期命令：

```bash
PYTHONPATH=src python -m personal_assistant.main stop
PYTHONPATH=src python -m personal_assistant.main restart
PYTHONPATH=src python -m personal_assistant.main --foreground
```

使用非默认配置时，start、stop、restart 都传同一 `--config /absolute/path/to/config.yaml`。`--im-service-url` 只覆盖本次连接的 IM 地址；`--auto-bind` 用于自动化，日常使用通过浏览器确认绑定。

`Gateway started (pid=...)` 只证明后台 child 已创建有效运行态且当时存活，不证明 IM、Agent 或渠道已经就绪。继续检查 `gateway.log` 和 Web IM 节点状态。

### 4. 绑定并聊天

- 首次连接未绑定节点时，按 `gateway.log` 中的 `ACTION` / `NEXT` 打开绑定页并确认。
- 节点已绑定且 online 后，打开 `/chat` 发送消息。
- 输入区显示 `Chat unavailable` 时，按卡片提示先完成绑定或恢复 Gateway online。
- 发送瞬间节点失效时，Web IM 保留草稿并显示失败，不要求重新输入。

## Web IM

Web IM 是默认的聊天和配置入口。

### 账号与数据边界

- 用户注册或登录后取得自己的会话、Agent、节点和配置视图。
- 不同 owner 的资源相互隔离；看不到其他租户的节点、会话和 Agent。
- 长时间登录和短暂断线会自动刷新身份、恢复用户事件流；切换账号后只接收新账号事件。

### 会话与消息

- direct 会话用于用户与 Agent 的一对一连续聊天。
- group 会话用于用户和多个 Agent 的协作；回复策略决定是否必须 @Agent。
- 飞书会话在 Web IM 中显示为独立 shadow conversation，便于从内部查看外部消息和回复。
- 刷新、分页和重连应保持历史与实时事件连续；会话历史持久化并可在 Gateway 重启后继续。
- Web IM 支持附件；桌面端可把剪贴板图片直接加入待发区。上传失败的图片不会破坏已经成功加入的附件。

### 工具过程与权限

- Agent 调用工具时，聊天气泡中的“过程”区域展示运行中、完成、超时、中断或拒绝状态。
- 展开工具行可查看命令、参数、结果或结构化详情；长输出会受控展开，不应撑乱聊天流。
- 需要用户批准的工具会显示权限卡。用户可以允许、仅本会话允许、拒绝或总是允许；拒绝理由可选填并会传给当前运行。
- `/stop` 用于中断正在进行的 Agent run；中断后工具和回复应进入明确终态。

## Agent 与节点配置

### 创建 Agent

- 只能在当前 owner 已绑定且 online 的节点下创建 Agent。
- Node 分配并返回 `workspace_root`；Agent 创建后，该路径不能通过普通配置更新修改。
- `agent_id` 是稳定身份；显示名称、描述、头像等展示字段可以独立修改。
- 创建页的 runtime 候选项来自目标在线 Gateway 当前上报的 models、skills、tools 和 features，IM 不从自己的文件系统猜测节点能力。

### 修改 Agent

可配置的运行能力包括模型、system/custom prompt、skills、tools 和 features（如 heartbeat、cron）。

- 保存成功表示期望配置已持久化并可同步，不表示每个休眠会话已经立即重建。
- 同一聊天的下一轮新回复采用最新完整配置，并保留此前聊天历史。
- 已经开始的回复不会中途切换模型、prompt、skills 或 tools。
- 连续保存多次时，真正开始下一轮时使用最终配置，不依次重演中间版本。
- 配置冲突或同步失败时，不应以“新模型 + 旧 tools”之类混合配置继续运行。

## 模型

- Agent 的 `default_model` 决定每次新回复使用的模型；未选择时回退 Gateway 产品默认模型。
- 修改模型后，同一历史会话继续使用新模型，旧历史不会因此丢失。
- 当前回复在开始时固定模型；运行中修改只影响下一轮。
- `llm.providers[].models[]` 可以声明可选 `context_window`。未声明或值非法时使用内核默认上限，不阻断聊天。
- 判断“我的 Agent 当前使用哪个模型”时，读取 Agent 当前配置或 live snapshot；不要仅引用配置示例中的占位值。

## Skills

Skill 是按需加载的专业知识或工作流，不会因为处于启用状态就自动在每个普通任务中加载全文。

- Kernel 在提示中提供可见 skill 的名称与描述；相关问题命中后，Agent 用 `skill_view(name=...)` 读取 `SKILL.md`。
- `skill_view` 是普通可选工具。关闭它后，Agent 仍可能看到 skill 候选，但产品不承诺能够读取正文。
- PA 全局 skills 位于 `~/.nanoassistant/skills`，对同一 Gateway 上的 Agents 可见；Agent workspace 也可以有自己的 skills。
- 随 PA 包发布的内置 skills 是产品托管内容。Gateway 启动时以当前安装包完整刷新这些保留名称，清除旧版本残留文件。
- 非内置名称的用户自建 skills 不会被这次刷新修改。需要定制内置 skill 时，复制为新的 skill 名称再修改。
- 新建 Agent 默认选择 Gateway 标为 default-on 的全局 skills，包括本产品手册。用户可在 IM 中取消或重新选中。
- 升级不会静默改写已有 Agent 的非空显式 skill 选择；新手册会显示为未选中，用户可手动开启。
- 当前产品手册的 skill 名为 `nanoassistant-docs`。关闭它后，Agent 不再调用本手册。

## Tools 与执行权限

每个 Agent 的 `tool_allowlist` 是实际执行白名单。

- 非空时，只提供名单中的工具；默认工具也可以被用户关闭。
- 显式空名单表示该 Agent 没有任何工具；模型尝试调用名单外工具时执行层拒绝，且不产生副作用。
- `skill_view`、`memory`、`read`、`write`、`edit`、`bash`、`web_fetch`、`web_search`、`skill_manage`、`agent`、`task_stop` 等是否可用，以目标节点当前 capabilities 和 Agent 保存的选择为准。
- 启用 cron feature 时，配置侧会把所需 `cron` 工具联动进 allowlist；Gateway 不在会话里偷偷扩宽白名单。
- 权限批准解决的是“这次允许不允许执行”；tool allowlist 解决的是“这个 Agent 是否拥有该工具”。未进入 allowlist 的工具不能靠权限卡临时获得。

### Web 搜索

- 未配置其他默认 provider 时，`web_search` 使用 DuckDuckGo。
- `BRAVE_API_KEY` 允许显式选择 Brave。
- 设置 `SEARXNG_URL` 后，SearXNG 成为未显式选择 provider 时的默认项。
- provider 不可用时明确报错，不静默切换。`web_search` 返回结果列表；需要读取网页正文时再用 `web_fetch`。

## Memory 与会话连续性

区分三类持续信息：

1. **聊天历史**：属于具体 conversation，支持同一会话继续、Gateway 重启恢复和配置变更后延续。
2. **Memory**：保存跨会话仍有价值的稳定事实。`user` 目标记录用户身份、偏好和沟通习惯；`memory` 目标记录环境事实、约定、工具特点和长期经验。
3. **工作文件**：位于 Agent workspace，例如 `HEARTBEAT.md` 和 cron job 数据，不等同于聊天或 memory。

使用 memory 时：

- 保存用户明确偏好、稳定环境事实、反复出现的约定或纠正。
- 不保存一次性任务进度、临时状态、容易重新发现的琐碎信息或敏感秘密。
- Memory 在未来轮次注入；若用户问“你记住了什么”，应依据当前可见 memory，而不是凭空复述。

## Gateway 与节点状态

Gateway 是本地常驻进程，同一 config 同一时刻只允许一个实例。start、stop、restart 由 config-scoped lock 串行化。

- 后台状态写入 config 同目录的 `.gateway-state.json`，日志写入 `gateway.log`。
- `STOPPED` 表示目标实例已关闭；`NOT RUNNING` 表示没有可管理实例；`STALE` 表示旧进程身份失效且状态已清理。
- Gateway 主动连接 IM；IM 暂时不可达时会指数退避重连。
- IM 离线期间，已经接入的外部渠道尽可能保持本地自治；Web IM 要等连接和节点 online 恢复。
- 判断 Gateway 可用性时，同时核对存活进程、process birth、当前日志、节点 online 和一次真实消息往返。旧 PID、历史日志或“start 没报错”都不能单独证明可用。
- 节点首次绑定到 owner 后，其他 owner 不能直接改绑；需要迁移时不要假设重新点确认会转移所有权。

## 飞书渠道

飞书是当前主要外部渠道，由 Web IM 的 Agent 通道页托管。

### 配置

1. 先让目标 Gateway 至少上线一次、完成节点绑定并登记凭据公钥。
2. 在 `/settings/agents/<agent_id>` 的“通道”页添加飞书。
3. 填写飞书 App ID 和 App Secret；飞书应用启用 Bot、长连接和消息收发权限。
4. 需要把群内未 @Bot 的普通消息作为后续上下文时，额外授予 `im:message.group_msg`。

同一 Agent 最多配置一个飞书实例。App Secret 经加密 envelope 交给目标节点，不写入普通 `config.yaml`、日志或 HTTP 响应。

### 运行行为

- 保存成功只表示 desired state 已提交；以通道页 runtime 状态和 diagnostics 判断是否真正连接。
- Gateway online 时，新增、编辑、停用、重连和删除会热调和，不要求改本地 YAML 或重启 Gateway。
- 已应用的飞书配置以节点密文 cache 支持 Gateway 重启和 IM 暂时离线；IM 恢复后再收敛到最新 desired state。
- 私聊消息触发绑定 Agent 回复；群聊通常要求 @Bot、回复 Bot 或发送明确控制命令。
- 飞书用户消息和 Agent 回复会镜像为 Web IM 中独立 shadow conversation。IM 离线时本次镜像可以暂缺，但飞书主路径不应因此阻塞。
- 多个 Agent/Bot 在同一节点或同一外部群中保持独立 runtime、影子会话和上下文。
- 普通 Gateway 飞书对话由 Gateway 拥有；用户明确要求的独立 Lark event 监听不接管普通入站和回复链路。
- 内置完整 Lark skill bundle 让飞书绑定 Agent 能操作文档、云盘、表格、日程、任务、审批、邮件、知识库和会议等资源；具体操作仍受 Lark 登录身份、权限和对应 skill 规则约束。

## Heartbeat 与 Cron

Heartbeat 和 Cron 是两套独立、都由 Gateway 本地调度的主动机制。

| 对比 | Heartbeat | Cron |
|---|---|---|
| 适合 | 周期性检查“现在有什么值得主动推进或提醒” | 在明确时间执行一条确定任务 |
| 上下文 | 携带 Agent 与 owner 的 canonical 直聊上下文 | 在隔离 session 中运行，不带普通聊天上下文 |
| 配置 | per-agent 开关、`heartbeat.every`、activeHours；任务内容在 `HEARTBEAT.md` | per-agent 开关；Agent 通过 `cron` 工具创建、查看、立即运行或删除 jobs |
| 结果 | 有可冒泡内容时发到 canonical 直聊；无内容时 `HEARTBEAT_OK` 静默 | 结果发回 canonical 直聊并记录运行历史，用户可继续追问 |
| 错过周期 | 恢复时只推进最近边界，不逐个补跑 | 同样不补跑；已经过期的一次性任务也不补跑 |

补充规则：

- Heartbeat 顶层节律来自 Agent 配置，默认 `30m`；不要把 `HEARTBEAT.md` 顶层文本当成调度器主频率。
- `HEARTBEAT.md` 可以包含 freeform 任务清单和可选的 per-task 独立频率。
- activeHours 窗口外不唤醒，避免打扰用户。
- Cron 的手动立即运行和定时触发使用同一执行、投递和历史语义；手动调用只改变触发时机。
- 两种机制都关闭时不创建主动运行。Cron 未启用时，相关 job 不应获得可运行能力。

选择建议：

- “每 30 分钟看看有没有要跟进的事”使用 Heartbeat。
- “每天 9:00 发日报”或“明天 14:00 提醒我”使用 Cron。
- 需要引用近期直聊上下文的周期判断优先 Heartbeat；需要隔离、可列举的固定任务优先 Cron。

## 故障排查

先保留首个错误、当前 config 绝对路径和运行身份，再执行恢复。不要一遇到问题就重启全部服务，否则会丢失最有价值的因果证据。

按以下顺序排查：

1. 确认当前命令属于哪个安装或 checkout，Gateway 使用哪份 config，浏览器访问哪个 IM 地址。
2. 用 OpenAPI 检查 IM HTTP；再确认 Web IM 静态页面是否存在。
3. 交叉核对 `.gateway-state.json`、live process 和 `gateway.log` 是否属于同一 config 与同一次启动。
4. 查看节点是否已绑定、是否 online，以及日志中的 `ACTION`、`NEXT` 或第一个启动错误。
5. 最后走一次真实路径：登录、打开会话、发送消息、收到回复。

| 症状 | 优先检查与处理 |
|---|---|
| `/` 或 `/chat` 打不开 | 检查 IM 进程、8011 监听和 `/openapi.json`；端口占用时先确认占用者。 |
| OpenAPI 可达但页面不存在 | 检查 Web IM 静态构建是否随当前安装提供。 |
| Gateway 启动后立刻退出 | 阅读 `gateway.log` 第一个错误；检查必填 `llm`、provider 协议、web_relay 和 IM 地址。 |
| `gateway already running` | 使用同一 config 的 `restart`，不要再启动第二实例。 |
| `NOT RUNNING` / `STALE` | 确认 stop 使用与 start 相同的 `--config`；保留旧日志后重新启动。 |
| 浏览器要求绑定 | 按 `gateway.log` 的 `NEXT Open ...`，用当前登录 owner 完成确认。 |
| Web IM 显示 Gateway offline | 检查 Gateway 进程、IM WebSocket、节点页 `last_error`；恢复后验证消息往返。 |
| Agent 能力为空或接口 503 | 检查是否有旧 Gateway、重复 node_id 或目标 Gateway 尚未完成注册。 |
| `workspace_root does not exist` | 创建 config 中的准确目录，或移除显式路径使用默认 workspace。 |
| Agent 不回复或 LLM 报错 | 核对实际 `default_model`、provider 协议、上游健康和本次 LLM 日志。 |
| 飞书保存后未连接 | 查看通道 runtime diagnostics、节点 online、App 凭据、Bot/长连接设置和权限；修正后重连。 |
| 飞书群普通消息没进入上下文 | 检查 `im:message.group_msg` 是否已授权。 |
| 产品回答与现场不一致 | 明确记录差异，以已核实的现场事实描述本机；不要静默把手册或猜测当作运行事实。 |

恢复时只对目标 config 执行 stop/restart。状态文件中的 PID 未通过 live process birth 校验时，不要向该 PID 手工发信号。整套服务关闭时先停 Gateway，再停 IM；恢复后重新验证节点 online 和一次真实消息往返。

## 范围边界

本手册覆盖 PA 用户和运维者可见的产品行为。以下内容不在范围内：

- Coding CLI 的 REPL、命令和终端工作流。
- Agent Kernel 的内部类、模块、事件实现或 SDK 设计。
- 仓库开发流程、change unit、测试规范和贡献指南。
- 尚未出现在当前安装版本中的规划能力。

用户明确询问范围外内容时，先说明本手册无法作为权威来源；不要把 PA 的相似概念推断成这些系统的真实行为。
