---
name: nano-plugin-development
description: "为当前 Nano Agent 创建、安装、更新、配置或排障 workspace 插件时使用；包括自定义工具、报告格式/上下文贡献、私有服务、局部监听与压缩引擎。普通一次性任务无需插件；Nano 客户端或宿主源码开发不属于此入口。"
---

# Workspace 插件开发

把用户目标做成能实际工作的 workspace 能力。插件是可信本地代码；workspace 归属与服务作用域不是操作系统沙箱。同 workspace 的所有 Agent 共享安装状态，每个 Agent preset 会挂载自己的实例。

## 先决定是否需要插件

- 现有工具能完成的一次性任务：直接完成。
- 可复用操作知识：使用 Skill；多步编排和定时任务使用现有 Workflow/Cron。
- 需要新增可调用工具、提示词贡献、私有服务、局部监听或压缩策略：使用标准 DSH bundle。不要用独立后台 Agent Loop 重做产品能力。
- Nano 身份、权限、凭据、Inbox 路由、消息交付、节点生命周期和其他 workspace 属于宿主。DSH Web UI 插槽不会变成 Web IM、iOS 或飞书界面。用户需要可视化时，说明实际交付位置，例如文件、报告或独立应用；不要声称修改了客户端。
- MCP 接入尚未纳入本开发入口的支持承诺，不照搬 DSH MCP/UI 模板来声称可用。

## 开发流程

1. 读取 `references/bundle.md` 和下表中与任务相关的资料。按用户目标选最小扩展，不加载所有资料。
2. 调用 `plugin_manager`，`action: describe_api`，选择对应 `topic`。用 `read` 读取返回的 README/公开 types 中相关部分，确认当前版本的方法、参数和返回值。公开声明里也有宿主 API；只能使用该 topic 和本 Skill 支持的扩展点。不要猜源码路径、方法或 schema。
3. 在当前 workspace 创建独立源码目录。读取模板文件，把内容复制到源码目录并按用户任务改写；为包、行、工具和提示词取有意义且不冲突的名字。不要直接安装或修改 Skill 模板目录。
4. 检查文件语法与 manifest，调用 `plugin_manager install_bundle`，`target` 为源码目录的绝对路径。只在用户明确批准构建脚本后传 `approvedBuilds`。
5. 检查安装结果及诊断，实际调用/体验新增能力。按 `references/verification.md` 验证业务结果；有失败就在原源码修正并重装，不让用户代查 API 或代改白名单。
6. 返回插件名称、源码位置、共享影响范围、实际验证结果与未验证部分。安装成功、工具可见、业务成功、重启持久和客户端显示是不同事实，只声明已证明的结果。

开发指导被明确禁用时尊重选择，不从隐藏路径补读；若缺所需开发知识或 API，说明具体限制，不杜撰。修复观察到的问题后收尾，不做推测性扩展。

## 按需读取

以下路径均相对于本 Skill 的 base directory；以 `skill` 返回的位置为准，用文件读取工具读取，不猜用户 home 或仓库路径。

| 任务 | topic | 资料与模板 |
|---|---|---|
| 所有 bundle 的创建、安装、更新与配置 | 按实际能力选择 | `references/bundle.md` |
| 自定义工具、调用脚本或业务 API | `tool` | `references/tools.md`；`templates/tool/package.json`、`templates/tool/cordis.patch.yml`、`templates/tool/tool.mjs` |
| 报告格式、领域提示、动态上下文 | `prompt` | `references/prompt.md`；`templates/prompt/package.json`、`templates/prompt/cordis.patch.yml`、`templates/prompt/prompt.mjs` |
| 私有服务、索引、缓存、资源生命周期 | `service` | `references/services-events.md`；`templates/service/package.json`、`templates/service/cordis.patch.yml`、`templates/service/provider.mjs`、`templates/service/consumer.mjs` |
| 插件自己的调用观察或文件监听 | `events` | `references/services-events.md`；service 模板含被动 `tools/result` 观察 |
| 压缩策略或高级摘要定制 | `compaction` | `references/compaction.md` |
| 实际使用、停用、恢复和交付 | 按实际能力选择 | `references/verification.md` |
