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
4. **可读历史导出**：读取、分支与蒸馏均基于当前 DSH 会话及受控消息锚点。旧内核聊天文件保留为历史资产，不作为新会话上下文。

使用 memory 时：

- 保存用户明确偏好、稳定环境事实、反复出现的约定或纠正。
- 不保存一次性任务进度、临时状态、容易重新发现的琐碎信息或敏感秘密。
- Memory 在未来轮次注入；若用户问“你记住了什么”，应依据当前可见 memory，而不是凭空复述。

## 自建插件与工具

使用标准 DSH plugin/bundle。个人共享层为 `~/.nanoassistant/plugins.json`，workspace 层为 `<workspace>/.nanoassistant/plugins.json`；局部同名工具优先。安装不自动取消 Agent 的工具选择限制。Python 程序可以由原生工具通过明确参数调用，旧 `agent.sdk` Tool 适配器需要转换，不能继续动态加载。

Agent 启用 `plugin_manager` 后，可以自己创建并安装 workspace 标准插件（工具、提示词、scope 内监听器和隔离服务），无需逐个添加工具白名单或重启。管理入口只管理当前配置 workspace；不会改其他 workspace 或节点公共 profile。动作使用 `list_bundles`、`install_bundle`、`set_bundle`、`remove_bundle`。安装得到的新独立工具名自动可用，原有静态工具的禁用选择保持；关闭管理能力或显式空工具集不自动获得这些工具。自建能力按 bundle 停用或移除。

创建本地工具时，在当前 workspace 建一个独立 bundle 目录：`package.json` 声明 `name`、`version`、`type: module` 和 `dsh.bundle.patch: ./cordis.patch.yml`；patch 插入 `name: ./tool.mjs` 的插件；JS 插件导出 `inject = ['tools']` 与 `apply(ctx)`，通过 `ctx.tools.register` 声明名称、描述、参数、`output {schema, render}` 和执行函数。Python 可以作为 bundle 中的脚本由该执行函数调用。把 bundle 的目录传给 `plugin_manager install_bundle`，然后实际调用新工具验证。

本地安装在 `<workspace>/.nanoassistant/dsh-plugins/` 保存标准 DSH profile 和独立版本产物；重启不会重写这些状态。修改源目录后再次安装会生成新版本，所以首次源码加载失败后也可修正并重试。不要修改已安装版本产物。`list_bundles` 返回 `profileDir`；需要配置第三方插件时，修改该目录下的 `cordis.patch.yml` 原生 user overlay，系统会热应用。只覆盖该 bundle 已声明的行（例如行级 `isolate`、`config`），这样停用 bundle 时对应贡献也会撤销；不要独立插入一份不随 bundle 开关的副本。不要改 `runtime.json` 或宿主 profile。宿主 DSH peer 依赖由原生解析器复用，无需在 workspace 再装一份运行时。只有结果 `application: applied` 且真实工具调用成功，才能声称已可用；`failed` 要按诊断修正。普通 registry/git 包的替换可能返回 `restart-required`，不能声称已经在线生效。构建脚本授权仍需用户明确同意，不从一般工具安装请求推断。

插件不必提供工具。例如 `style.mjs` 可以写：

```js
export const inject = ['systemPrompt'];
export function apply(ctx) {
  ctx.systemPrompt.section({name: 'expense-report-style', order: 850, text: '报销报告先给总额，再用分类表格列明细。'});
  // 自建资源通过 ctx.effect(() => () => cleanup()) 管理，停用时由原生生命周期释放。
}
```

标准 patch 插入 `{id: 'expense-report-style', name: './style.mjs'}`，安装后通过真实回复核实效果。普通服务不会因 workspace scope 自动隔离：provider 和 consumer 放入同一个 `{id:'report-group', name:'cordis:group', group:true, isolate:{reportService:true}, config:[provider,consumer]}`；根服务泄漏会被拒绝并返回诊断。局部源入口必须留在 bundle 内。支持当前 preset 可用的原生能力，不替换节点宿主 runtime。

用户可在 Agent 设置的“插件”页查看所有已安装包，包括没有工具、已关闭或加载失败的插件。关闭通过原生选择停用整个包并回收受管资源，保留安装包和源码；卸载是单独确认的移除操作。两者影响共享此 workspace 的所有 Agent，网页在空闲安全边界应用并显示等待状态，不需要额外保存或重启 session。同名停用插件更新默认保持停用，可显式 enabled:true 重新启用。网页管理权限与 Agent 能否调用 plugin_manager 分开。

压缩引擎插件：当前 workspace 插件树属于 Agent preset。通过原生 user overlay 给已安装 bundle 的现有条目配置 `isolate: {compaction: true}`（相关 provider/consumer 需共享隔离 group），该引擎由 preset 发现；Nano 默认自动压缩会让出处理权，人工 `/compact` 也路由到它。无需停用宿主默认 provider，也无需为首次激活重启会话。若插件自身有 model surface 或存储路径配置，按其文档在 workspace overlay 中设置；工具实际可见、调用成功和 compaction 事务完成仍需分别验证。
