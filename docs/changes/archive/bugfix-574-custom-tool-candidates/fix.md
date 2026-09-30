# bugfix-574: Agent 配置页展示已注册用户工具

## Relations

- Closes: #315
- Related: feat-379, refactor-406

## 原始报告

用户在工具配置页询问：“为啥我在这没看到你的这些工具？”、“为啥会漏”、“我们产品设定原本应该怎么样的”，随后要求“这个问题，提一个issue”。

实施授权（2026-10-01）：“好，你做一个新的unit解决这个问题吧”。

原截图引用：`codex-clipboard-35a82924-b20d-427d-a925-5d87dfb112d5.png`（用户此前提供的 Agent 工具选择页截图）。完整问题、证据链接和验收范围见 [#315](https://github.com/Mrchen116/nano-multiagent/issues/315)。

Agent 解读：在新 unit 中补齐用户工具从运行目录到配置候选的闭环，不继续未定稿的 feat-531 插件产品方案，不部署生产舰队。

## 现象 / 复现

在 Gateway 的用户工具目录安装符合契约的工具并重启后，加载器能够成功注册工具，但 IM 的新建/编辑 Agent 页仍只展示固定的 15 个 PA 工具。本次示例为 `read_x_post`、`read_xiaohongshu_note`、`read_douyin_video`、`download_douyin_video`；不要求修复依赖这些特定名称。

复现：安装可注册的自定义工具 → 启动 Gateway → 打开对应节点的创建页或 Agent 配置页 → 工具候选缺项。是否已在 Agent 白名单授权不应决定候选项是否可见。

单一 M1-fix 的范围与退出标准：

- 节点候选包含共享注册工具；Agent 候选同时包含其工作区工具及共享工具，不混入其他工作区工具，同名覆盖与实际执行一致。
- 保留 PA 内置声明顺序和 default_on 语义，追加的工具默认关闭、名称去重，提供注册描述；缺失 runtime 实例不应再次导致 memory/skill_manage 等声明项消失。
- 已有 Agent 的白名单、显式空名单和 global 固定基础工具不改变；用户可以主动勾选/取消自定义工具，按既有下一轮生效和执行权限契约运行。
- 有失败复现、窄测试、真实隔离 IM/Gateway + 配置页证据、独立代码审查和 CI；修复后归并 current spec。

非目标：安装/重装社交插件、请求第三方平台、热更新工具实现、修改白名单执行或配置切换机制、变更生产服务。

## 根因

基线 `7340a7805`：`upstream_reporter._tools_from_kernel` 读取 `kernel.list_tools()`，但 `capability_projection.project_tools` 忽略入参，只枚举 `PA_DEFAULT_TOOL_IDS` 与 `PA_OPTIONAL_TOOL_IDS`，并丢弃所有描述。IM 原样转发能力目录；配置页用 capabilities.tools 生成候选、用 draft.tool_allowlist 表示选中，缺项发生在 Gateway 投影而非前端选择逻辑。

另一个同属候选发现的边界：SDK 的 `list_tools()` 只返回共享基座；工作区工具已由现有 workspace execution scope 按工作区发现，但 Agent 能力查询未使用该上下文，所以仅补共享投影仍会漏掉工作区插件。查询目录应与现有执行 scope 保持同源，不另建加载规则。

历史意图：feat-379 design 决策 13 为避免 runtime=None 临时 registry 漏掉 memory/skill_manage，改为 profile 的静态声明目录。refactor-406 的 `c4a6eefdc1` 保持 payload 不变，延续固定投影；不是近期意外删除社交工具。修复必须保留完整内置声明与默认值，但不能继续把声明名单当作全部候选。

当前契约依据：`docs/specs/im/agents-nodes.md` 的在线 Gateway 候选解析；`docs/specs/gateway/agent-capabilities.md` 的显式白名单与不自动扩宽；`docs/specs/kernel/tools-hooks.md` 的工作区 extension 隔离及覆盖优先级。当前尚缺用户工具配置候选的明确场景，本 unit 补齐而非把旧缺项行为固化。

## 修复

实施提交 `e8f61810a`：SDK 的中立工具查询增加可选工作区，复用已有 execution scope，不另建加载、缓存或执行机制；Gateway 将 PA 声明与真实注册目录合并，保留默认值/顺序并提供真实描述。Agent 级能力用其自身工作区目录，节点级保持共享目录。未修改配置同步、白名单执行、前端选择或第三方插件。

保留已有能力协议测试的名称/顺序/default_on，改写其空描述假设；Workflow 可选工具测试保留、改为核对真实注册描述。新增 `test_tool_candidate_projection.py` 守住“缺失 runtime 也保留声明”这一纯投影风险；新增 `test_gateway_tool_candidates.py` 从真实加载器和公开能力 payload 守住全局/工作区接线、覆盖与隔离，未重复永久浏览器测试。

Bugfix lite 直接将验证后的场景归并到 `docs/specs/im/agents-nodes.md` 与 `docs/specs/kernel/sdk-boundary.md`，不建立独立 design/verifier/reviewer 或伪造 worker 台账。

## 验证

- Red：共享插件已经注册但能力 payload 中不存在，新增集成测试以 `KeyError: shared_reader` 失败。
- Green：窄测试 28 passed；最终测试夹具改为鸭子类型后，相关 2 项重跑通过。独立代码审查复跑相关 21 项通过、返回 `[]`，报告见 `code-review.md`。
- 本地 CI 等价：agent/PA 分片 1999 passed，remaining 分片 2073 passed；Vitest 84 文件 / 781 tests passed；Ruff check/format、docs-check、critical 级 npm audit 通过。npm audit 仍报告既有 2 low / 3 moderate / 2 high，不在本 unit 修改依赖。
- 真实隔离 IM/Gateway/Vite 与 Playwright 创建/编辑页、勾选保存重开、取消保存、描述/默认值和工作区隔离验证见 `M1-fix/evidence/acceptance.md`。使用真实代理完成无第三方副作用的工作区工具调用；不将该结果当作 X/小红书/抖音业务验证。
