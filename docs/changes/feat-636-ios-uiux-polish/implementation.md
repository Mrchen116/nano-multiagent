# 实施与验证记录

本地预览，未 push、未创建 PR。用户要求效果确认后再提 PR，因此 unit 暂留 active，后续 final sync、canonical 归并、archive 和远端 CI 在获确认后交付；不以本记录冒充已发布或已装真机。

## 版本与现场

- worktree: `/Users/czj/.codex/worktrees/ios-uiux-polish/nano-multiagent`
- branch: `unit/feat-636-ios-uiux-polish`
- executed_base: `d846b015b8774461bb26b172e458443ce1eb071d`
- 真实隔离 IM `127.0.0.1:54071`，隔离 Node `wt-nano-multiagent-51868`；独立数据、workspace、Gateway 配置与身份。
- iPhone 16e / iOS 26.4 专用模拟器，390×844pt；默认 Dynamic Type `large` 与 `accessibility-medium` 分别验证，不以大字号代表日常密度。
- 确定性中文消息、任务、Work 种子来自既有公开 API 和 WebRelayConnection；模型验证使用本机隔离 HTTP/SSE 端点，不是生产模型质量或真实外部交付证明。
- 原主仓 dirty/untracked 内容未触碰；仅隔离 worktree 的明确源码与 unit 文档属于本任务。

## 优化点与真实画面对照

截图保存在仓外 `/Users/czj/.codex/artifacts/feat-636-uiux/`，不提交缓存。`comparisons/index.html` 为最终自包含逐项画廊；`comparisons/manifest.json` 映射全部截图条件。

| 报告范围 | 结果 | 对照键 |
|---|---|---|
| U1 创建顺序与技术设置 | 名称、用途与说明先行，自动 ID，展开高级设置；同设备模型管理链接 | 01-create |
| U1 原生模型服务 | 我的/设备/创建页常驻入口，原生服务列表、多个模型、测试后保存 | 02-model-entry、14-device；新页面与失败/成功补图 |
| 追加聊天信息层级 | 单聊去掉重复姓名；群聊外置姓名，独立时间分组；运行/失败/用量在气泡下 | 22-chat-direct、23-chat-group；大字号与状态补图 |
| U2 正常 Markdown 大字号省略 | 文本取得完整纵向高度，列表按真实宽度换行 | 09-markdown-default、09-markdown-large |
| U3 Work 层级 | 状态摘要、实际轮次文本与可读工具结果优先，技术结构折叠 | 03-work、03-work-expanded |
| U3 导航副作用 | JSON 内嵌组件只负责内容；独立页面包装承担标题 | 03-work-expanded |
| U4 群策略 | manual 等原值可见、语义符合实际 runtime，非主动选择不迁移 | 04-policy |
| U5 任务概览 | 紧凑元信息、已加载范围、状态计数与定位 | 05-tasks |
| U5 子任务/结构 | 紧凑比较、适应屏幕总览、详细视图与完整节点详情 | 06-subtasks、07-structure |
| U6 PA | 读取本人 binding，双端独立优先区，直接进入现有配置，普通列表去重 | 08-pa-ios、16-pa-web-desktop、17-pa-web-mobile |
| 文案与帮助 | 日常中文、用户需要的运行限制 | 01-create、13-help |
| 单一主保存与 dirty 放弃 | 资料、设备、策略保留导航保存 | 10-profile、11-system-policy、14-device |
| 持久字段标签 | 已填模型值及别名仍可辨认 | 11-system-policy、14-device |
| 大字号长名称 | Agent 名称和元信息允许增高换行 | 15-agents-large |
| 任务关闭语义 | “关闭”只关闭详情，避免“完成”歧义 | 12-task-close |

## 审查后的直接修复

1. Node 只保存一个模型 operation。原生追踪 A 被后续 B 覆盖时，不把 B 成功当作 A 成功；解除无法再回查的旧跟踪，保留草稿并进入显式最新配置核对，避免永久 pending。全新契约测试采用真实单槽时序 A testing → B testing → B succeeded。
2. 本人 PA 从普通列表去重后，优先入口仍复用原联系人搜索字段：iOS 设备名、Web owner 描述，保留既有查找能力。
3. Web 配置有未保存草稿时，点击侧栏 PA（及同一侧栏其他助手）先显示沿用现有语言的离开确认；“继续编辑”保留表单，明确放弃后才跳转，不产生保存请求。此项来自独立真实产品验收，已补先红后绿回归。

4. 原生创建/配置原先仅解码模型路由，新增服务的 UUID 抢占模型选择显示。现读取既有 `display_name` / `provider_display_name`，主模型以可换行的“模型 · 服务”呈现，备用模型同样使用人类可辨认名称；提交仍保留 canonical route ID，不改变后端模型契约。该项来自独立连续旅程验收，最新包定点复验已通过。

## 自动化证据

所有命令在本 worktree 执行，日志只留仓外，不提交凭据、截图或运行文件。

| 命令 / 范围 | 结果 | 证据 |
|---|---|---|
| `pnpm install --frozen-lockfile`、`pnpm build` | 通过，准备真实隔离 IM/Node | `/tmp/nano-feat636-e2e.log` |
| Web 完整 `vitest run` | 102 文件、951 测试通过（首次完整实现；后续只改 PA 搜索/离开保护，相关范围重新测试） | `/tmp/nano-feat636-web-all.log` |
| Web detail/list/rail 定向测试 | 3 文件、34 测试通过，包含后续全部 Web 修复 | `/tmp/nano-feat636-web-final-related.log` |
| PA 离开保护先红后绿 | 红测确认直接 navigate；修后继续编辑/放弃路径通过 | `/tmp/nano-feat636-web-dirty-red.log`、上项绿测 |
| `npm run build` | 通过，包含最终 Web 修复 | `/tmp/nano-feat636-web-build3.log` |
| iOS generic simulator `build.sh build` | 通过 | `/tmp/nano-feat636-ios-after3.log` |
| 最新 iOS `build.sh test` | 44 XCTest + 21 Swift Testing / 4 suites 通过，含时间分组、模型状态覆盖和既有发送/交互契约 | `/tmp/nano-feat636-ios-test5.log`、相应 xcresult |
| `pnpm check:ios-runtime` | 通过，包内运行资源未漂移 | `/tmp/nano-feat636-runtime-check.log` |
| `scripts/docs-check` | 通过（250 maintained Markdown / 67 routes；最终文档复核同样通过） | `/tmp/nano-feat636-docs-check.log`、`/tmp/nano-feat636-docs-check-final.log` |
| `git diff --check` | 通过 | 本地复核 |

最终源码本地快照 `b1d926f27`（完整首版）及 `3200455b0`（用户追加的消息气泡精简），均未 push。最新 iOS `build.sh test` 为 `/tmp/nano-feat636-ios-test5.log`，44 XCTest + 21 Swift Testing / 4 suites 通过；新增时间分组覆盖首条、相邻不足5分钟、恰好5分钟、跨日、fractional ISO和配置boundary。先红日志 `/tmp/nano-feat636-chat-time-red.log` 是尚未实现符号的编译红，不冒充旧产品可见行为失败。最终 Release arm64 archive4 通过（`/tmp/nano-feat636-ios-archive4.log`），从3200455b0源码生成未签名IPA，尚未分发。原生模拟器预览编译时 HEAD 为 b1d926f27，working-tree 聊天源码随后完整提交为3200455b0；各源码 SHA256 在仓外 source-manifest.json 留证，不将包内 revision 字段冒充发布版本。

最终画廊含 **23 组 / 46 张原始对照图**。两组验收追加为模型名称、Web 草稿离开保护，明确不是旧版已有页面；两组聊天姓名/时间反馈前图为本轮首版 b1d926f27，明确区别最初 d846 基线。默认/辅助大字号、Web 桌面/手机分开；09 滚动位置不同、14 运行计数变化、18 草稿名称/用途不同，比较目标和条件均注明。09 默认和大字号后图已更新为最终聊天层级，额外附大字号群聊、宽表格最右侧完整内容，共56张自包含PNG（含独立复验补充的运行/失败/用量画面）。Playwright实际依次切换23项并解码全部46张对照图，操作聊天分类、原图放大和关闭；最终渲染图已亲自查看，唯一console404为未配置favicon，页面资源完整。验收浏览器已关闭。

横向表格通过 CUA 定位实际文本元素后 `scroll(elementID, 'right', ...)` 成功，最右列完整显示“预留改签空间 / 近车站，可取消 / 不赶路，留出午休”；此前坐标 scroll/drag 无效是自动操作路径限制，已不再作为该交互的最终 inconclusive。图片 `after/24-markdown-table-scrolled.png`。复制正文曾实际出现“已复制正文”toast，最终包独立产品 reviewer 也已亲自触发“已复制正文”toast。表格在默认和辅助大字号均实操到最右侧完整可读；回左动作在当前工具路径无位移，额外方向覆盖保持明确边界，不冒充全方向实操证明。

消息状态补证在额外隔离会话“聊天信息层级检查”中：会话通过现有 API 创建，8条展示消息复制隔离 fixture 的真实 agent 消息行并设置持久内容/日期/状态。服务原 API/原生 store 读取并呈现；该种子只证明日期、sender、running/failed/usage 的 UI，不冒充真实模型执行成功/失败。原有对照消息保持不变。脚本和ID清单只留仓外，既有发送/交互行为由正式回归和原验收承担。

## 角色与边界

Gate 2 R3 已通过。独立 code-review R1 的 2 项已在 R2 关闭；R2 同时覆盖 Web 离开保护 delta，无存活代码 finding。独立产品 reviewer 已完成 Web 正常、搜索、无 PA 身份、他人 PA 权限与失败恢复，原生 full acceptance 另见追加报告。独立产品最终局部closure已到（acceptance Round6），包含新聊天层级、时间边界、默认/大字号、运行失败用量、复制与横向表格；full verifier 最终 PASS，0 CRITICAL / WARNING / SUGGESTION，13/13 Scenario 与6项 corrected delta 全部 aligned；本次预览不提前执行用户确认后的PR交付。当前不声称 PR/CI/生产/真机交付完成。

## 本地预览收尾

本轮创建的 Playwright 验收会话均已关闭；本轮 prototype/gallery HTTP、模型 HTTP/SSE、选择性 PA 失败代理及 fixture relay/control 均已停止。`e2e-down.sh --wt` 返回 `STOPPED`，隔离 Node/IM 已停止；专用模拟器2D7CB8A5-EC2A-46C6-9D5C-C823EEED3EC1已 shutdown，字体恢复large、浅色。端口54071/63680/63681/63682/63683无监听，原Node/IM PID无存活进程。保留 managed worktree 和自包含23组画廊便于用户确认，不归档、不提PR、不改变生产或用户手机。
