# M1 实施记录

## 基线与范围

- 开发基线：`492b72603cebc5f904f7001b12e3d4475ce55639`（Gate 2 R4 已批准）。独立开发 worktree：`/Users/czj/.codex/worktrees/unit-feat-705/nano-multiagent`，分支 `unit/feat-705`。
- 主线负责角色工具／Context、配置更新／占用／恢复及验收；独立首轮子任务负责根／一级指导、PA 默认、两个随包 Skill 和 Node 创建默认值，提交 `fcd995949`。
- Task 业务、调度、数据与客户端布局不改。父子通信直接复用 DSH；不加 parent-ID 或 send_message 指导，不新增 fork 清理流程。

## 测试策略与既有覆盖

| 风险 | 归属及处置 | 证据 |
|---|---|---|
| Global 根／一级／二级／fork 的工具、初始 Context 与冷恢复 | 扩展既有 `global-child-tools.test.ts`；保留原权限／冷恢复保护，调整已被新分工取代的 Global 通用 child 身份文案断言；SingleThread 原断言保留 | RuntimeClient 真 DSH，捕获实际 llm/stream 请求、native schemas、工具结果及原 ID 冷恢复 |
| 根选择不误撤工作能力、占用仍记账 | 扩展 `capability-state.test.ts` 和上述原生 fixture；不另建平行套件 | 根配置变更期间 child read 仍合法，根继续接新输入；内部完整占用与编辑器选择依赖投影分开 |
| Goal 独立选择与根 fork opt-in | 扩展 `goal-opt-in.test.ts` 的既有配置矩阵 | 默认及显式 fork-only 不改变 Goal，保存／撤回原规则保留 |
| 创建目录与 PA 用户配置 | 保留 Node capabilities、IM personal-agent 测试，仅增加 fork default_on 断言 | 子任务 Node24 红绿，25/25 通过；旧 Persona 不回填保护保留 |
| 内部消息、来源、归属与 Task 边界 | keep communication-native、llm-attribution、task-child-context、native-human-source | 纳入窄回归，未改 Task 执行规则 |
| 自主分工与公开交付 | daily 隔离 Global／PA 真实模型旅程，独立产品验收 | 待版本冻结后执行；不能用 stub 代替 |

## 已执行证据

- 使用本机 dev_host check 核对 Air；固定 Node24、主仓 Python venv；worktree 独立 frozen-lockfile 安装及构建，不复用指向主仓 lib 的 node_modules。
- `/tmp/feat705-baseline-red.log`：临时还原五个 runtime 源文件到 `fcd995949` 构建，修正后的新增原生用例确实失败：一级只得到根所选 subagent/send_message/context 工具，缺 read/write/bash/fork/管理工具。随后原样恢复候选源文件并重建；临时还原未提交。
- `/tmp/feat705-core-tests2.log`：第一组3文件9用例通过，包含无额外二级身份、原生父级 ID／AGENTS、真实内部工具执行、同 ID 冷恢复与 Goal。
- `/tmp/feat705-narrow2.log`：7文件18用例通过，包含根选择变更时一级继续工作及新输入接收。工具占用编辑器只显示真正依赖根选择的调用，后端仍保存全部调用并保护共享 Feature／Skill 撤回。
- 后续增加 fork 的实际 system 内容与父一级一致断言，发现共享 PA／Task／UI 指导只识别普通 child 的真实缺口；通过已有可信 fork 角色识别，统一为 internal execution 解释，保留根直接 fork 和 SingleThread 原规则。`/tmp/feat705-narrow3.log` 最终7文件18用例全部通过，包含新增 fork system 与父一级一致断言。
- 测试注入曾误返回 presentAs 的 disposer，导致后续 agent/created 装配被截断；已修正测试回调。该现象不是产品工具泄漏，不作为产品修复结论。

## 尚待完成

最终窄回归、完整 CI 等价检查、daily Global／PA 实测、独立产品审查、code review＋verification、delta 校正／current 归并、final sync、归档和 PR／远端 CI。当前不宣称已完成这些门禁，不部署或合并。

## 最终请求与运行门禁补充

- `/tmp/feat705-provider-wire2.log`：将新增 Global／PA 两个用例改为本地 Anthropic SSE recording provider（复用 llm-attribution 的公开适配路径），2/2 通过。断言直接消费 HTTP 请求体；metadata 仅从只观察、不替换响应的 llm/stream middleware 取得 native 身份。覆盖一级、普通二级、worker fork 的实际 wire system/tools/messages、原生父级 ID／AGENTS、fork system/tools 与父一级一致，以及同 ID 一级和二级冷恢复；总会话数保持4，没有重复创建。
- 独立静态审查 `45cd9117c` 的 code findings=[]；verification 记录运行证据尚未完成及 delta 需修改旧身份条目。后者已在能力 delta 显式 MODIFIED 同名工具规则与子执行 Context 条目，保留 SingleThread／fork 行为；待独立校正复验。
- 初次后端／前端／daily 构建并行造成多项跨进程和 DOM 超时，已保留 `/tmp/feat705-ci-test.log`、`/tmp/feat705-ci-frontend.log`，仅停止本轮两个过载 CI 及其后代，不作为通过证据。后续对同一完整测试集合限并发复跑，不改断言或超时标准。
- Python 辅助／架构回归129 passed /28 deselected；ruff check、ruff format（97文件）及 docs-check 通过。最终 build、typecheck、packaged iOS runtime 检查通过。daily 真栈已ready，独立产品 reviewer 正在自然旅程验收；ready 不等于验收通过。
