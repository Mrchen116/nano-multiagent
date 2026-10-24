# Skills、Tools 与 Memory

## Skills

Skill 是按需加载的专业知识或工作流，不会因为处于启用状态就自动在每个普通任务中加载全文。

- 运行时在提示中提供可见 skill 的名称与描述；相关问题命中后，Agent 用 `skill` 工具 读取 `SKILL.md`，再用 `read` 读取入口指定的 reference。
- `skill` 是普通可选工具。关闭它后，Agent 仍可能看到 skill 候选，但产品不承诺能够读取正文。
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
- `skill`、`memory`、`read`、`write`、`edit`、`bash`、`web_fetch`、`web_search`、`skill_manage`、`subagent`、`subagent_fork`、`workflow`、`job_output`、`job_kill` 等是否可用，以目标节点当前 capabilities 和 Agent 保存的选择为准。
- 启用 cron feature 需要选择 `schedule_create`；查询、修改、删除、立即运行和历史分别选择 `schedule_list`、`schedule_update`、`schedule_delete`、`schedule_run`、`schedule_history`。Gateway 不在会话里偷偷扩宽白名单。
- 权限批准解决的是“这次允许不允许执行”；tool allowlist 解决的是“这个 Agent 是否拥有该工具”。未进入 allowlist 的工具不能靠权限卡临时获得。

### Web 搜索

- 未配置其他默认 provider 时，`web_search` 使用 DuckDuckGo。
- `BRAVE_API_KEY` 配合 `DSH_WEB_SEARCH_PROVIDER=brave` 选择 Brave。
- 设置 `SEARXNG_URL` 后默认使用 SearXNG；`DSH_WEB_SEARCH_PROVIDER` 可指定 `duckduckgo`、`brave` 或 `searxng`。原生 `web_search` 接收 `queries` 数组，结果数由节点配置决定。
- provider 不可用时明确报错，不静默切换。`web_search` 返回结果列表；需要读取网页正文时再用 `web_fetch`。

## Memory 与会话连续性

区分三类持续信息：

1. **聊天历史**：属于具体 conversation，支持同一会话继续、Gateway 重启恢复和配置变更后延续。
2. **Memory**：保存跨会话仍有价值的稳定事实。`user` 目标记录用户身份、偏好和沟通习惯；`memory` 目标记录环境事实、约定、工具特点和长期经验。
3. **工作文件**：位于 `<workspace>/.nanoassistant/`，例如 `HEARTBEAT.md`，定时记录由运行时 Schedule 持有，不等同于聊天或 memory。

历史查询和分支基于原生 DSH 会话及受控消息锚点；蒸馏按需请求完整原始历史快照。workspace 不再自动生成可读聊天副本，已有副本保留但不再更新，也不作为会话恢复来源。

使用 memory 时：

- 保存用户明确偏好、稳定环境事实、反复出现的约定或纠正。
- 不保存一次性任务进度、临时状态、容易重新发现的琐碎信息或敏感秘密。
- Memory 在未来轮次注入；若用户问“你记住了什么”，应依据当前可见 memory，而不是凭空复述。

## 自建插件与工具

Agent 启用 `plugin_manager` 后，可以创建、安装、更新和停用当前 workspace 的标准 DSH 插件。插件可提供工具、提示词、私有服务、受支持局部监听和高级压缩引擎；新增独立工具名自动可用，原有工具禁用、显式空集合及子任务限制保持。

创建、配置或排障时，加载可用的 `nano-plugin-development` Skill；完整开发说明、当前 API 查询与模板集中在该 Skill，本手册只说明产品用法。用户明确禁用该 Skill 时尊重选择，不强制加载。开发入口见 [插件开发 Skill](../../nano-plugin-development/SKILL.md)。

用户可在 Agent 设置的“插件”页查看已安装、关闭或失败的插件。关闭会撤销整个包及其受管资源，保留源码和安装；卸载是单独的移除操作。两者影响共享此 workspace 的所有 Agent。网页忙碌时等待空闲边界，不需额外保存或重启会话。同名停用插件更新保持停用，重新开启是明确操作。网页管理权限与 Agent 能否调用管理工具分开。

本地插件安装及选择在重启后保留；更新自己的源码后可由 Agent 重装，不直接编辑安装产物。配置路径由管理入口提供，不修改节点公共 profile。必须区分安装成功、业务效果与持续生效；失败按真实诊断处理，要求重启的更新不能报告已经在线生效。构建脚本仍需用户明确授权。

插件压缩引擎作用于当前 workspace，接管自动与人工压缩，关闭后恢复默认方式；无需停用宿主引擎。定时任务与消息交付仍使用已有 Nano 产品入口。

这些插件是可信本地代码，workspace 归属不是操作系统沙箱。身份、权限、凭据、Inbox 路由、交付、节点生命周期和其他 workspace 由宿主管理。DSH Web UI 插件不会自动扩展 Web IM、原生 iOS 或飞书界面；MCP 尚未纳入当前开发入口的支持承诺。
