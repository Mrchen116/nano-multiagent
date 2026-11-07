开源调研已经完成第一轮。只读核对源码与公开资料，未安装、未运行候选，也没有改仓库。以下版本和热度是调研当时的快照。最后的验证是后续建议。

**一、Codex computer use 真实形态（一句话）**
它是 **code-mode 式分层能力，不是截图→坐标闭环**：插件 `computer-use@openai-bundled` / `unified-computer-use@openai-bundled` 把 MCP server `node_repl` / `cua_repl` 接进来，模型写 JS 调 `tools.mcp__node_repl__js({code:'await nodeRepl.emitImage(await tab.screenshot())'})`——持久 JS VM 里直接操作活对象（`tab`/DOM/CDP），截图是模型**主动 emit** 的证据；外加 macOS bundle-id 级 allow/deny、`allow_locked_computer_use`、`computer_use` confirmation policy + guardian 审查、托管开关 `allow_browser_and_computer_use`。证据等级 **源码实证**（`plugin/src/bundled_hooks.rs`、`protocol/src/mcp.rs:42`、`config/src/computer_use.rs`、`core/src/mcp_tool_call.rs:1421`、`code_mode.rs:7047/7132/7188-7195`）。**执行体不在开源 codex 仓**（无 cua 目录/crate，插件内容落 `$CODEX_HOME/plugins/cache`），所以只能抄形状。另更正：`screenshot_urls`/`AppScreenshot` 是应用目录展示元数据，不是运行截图。

**二、候选短名单**
1. **vercel-labs/agent-desktop**（Apache-2.0，15.7k★，v1.2.0 今日发）AX 树+稳定 ref+默认无焦点后台动作+stdio MCP+回读验证，最像 Codex 的"手"；缺 REPL 与 per-app allowlist。
2. **trycua/cua 的 Cua Driver**（驱动本体 MIT）AX+Apple Events+CDP、permission modes、配 Lume macOS VM 沙箱，治理面最全；perception 扩展是 AGPL，Spaces app 是 FSL/收费。
3. **openclaw/Peekaboo**（MIT，Swift）截图+AX+MCP+自带 agent，一体好用；要 macOS 15+。
4. **bytedance/UI-TARS-desktop**（Apache-2.0，39.6k★）开箱可用的像素 VLM agent；绑 VLM endpoint，缺 1/3/5 层。
5. **simular-ai/Agent-S**（Apache-2.0）OSWorld SOTA 研究框架；必须额外配 grounding 模型，坐标级动作。
（**axuse 设计最像 Codex 但是 PolyForm Noncommercial，不能用**；bytebot、macos-automator-mcp 已归档。）

**三、最推荐路径**
路径 A：把 agent-desktop 以 **stdio MCP 经 `dsh-mcp-client`** 装进一个 configuration-only workspace plugin（`cordis.patch.yml`+`dsh.bundle.patch`，不改 PA/不碰 dsh-integration/不动工具白名单）。工具名天然 `mcp__<server>__<tool>`，与 codex 同形。核到本仓**已有**治理面可直接复用：`NanoApproval` 挂 `tools/pre-execute` 全量审、LLM 分类器 ruleset(nano/codex/dsh)、`alwaysAllowTools`/`hardDeny`/`unattendedFallback`、`route()` 子 Agent→回父、schedule→unattended 拒、审计域 `nano_approval`（只记工具名**不记参数**）。所以读类工具进 alwaysAllowTools、写类走分类器 + IM/飞书 owner-only 卡。待验证衔接点：MCP 工具是否真走同一条 pre-execute（读契约成立，未实跑）。

**四、主要风险**
TCC 授权归属是"启动进程的那个 app"不是 shell（换宿主就重授；IDE 派生 shell 会归错身份）；Screen Recording 无法 MDM 静默授予；AX 返回 `kAXErrorSuccess` 不等于动作生效（agent-desktop 源码专门处理"AX 撒谎"）；后台按键够不到菜单栏、AX 无语义 drag；Retina 像素/point 坐标必须归一化；危险键（cmd+q/cmd+alt+esc）必须默认 hard deny。另：GUI 任务 10–50 动作，若每步都过分类器（30s/60s 超时）不可接受，必须量。

**五、最该先做的实验（半天，隔离用户或 macOS VM）**
装 agent-desktop，对 Finder/TextEdit/系统设置/一个 Electron/一个 canvas 五类目标各跑"snapshot→ref 动作→回读验证"，记录 ref 数、STALE_REF、回读一致性、调用次数与耗时；三个负例（cmd+q、后台菜单项、多窗口同名元素）必须被拦或明确报错；最后经 DSH MCP 再跑一遍确认审批卡能拦。**通过判据：3 个负例全拦 + ≥4/5 目标动作与回读一致 + canvas 失败必须是 typed error 而非静默错点。** 结果直接决定走 A 还是先做 B（自研薄插件补策略/参数级日志）。
