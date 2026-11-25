# M1 验收与真模型证据（feat-787-dsh-022-upgrade）

## 1. 验收环境与隔离定位

- 开发工作树：`/Users/czj/.t3/worktrees/nano-multiagent/unit-feat-787-dsh-022-u-5c64eade305a14d8`（分支 `unit/feat-787-dsh-022-upgrade`）
- 配套扩展发布：`Mrchen116/dsh-agent-context@0.3.0-rc.12`（commit `fb23f61`，对齐 `@deepseek-ai/*@0.2.2-rc.5`）
- 隔离真实栈（按 `worktree-runtime.md` 启动，验收与独立审查完成后回收）：
  - 运行目录：`/tmp/nano-e2e-787.iPNxw8`（`--profile daily`，临时端口 `56168`，节点 `wt-nano-e2e-787.iPNxw8-20181`）
  - 真实模型：`codexOAuth:gpt-6.2-sol`（主执行）与 `codexOAuth:gpt-6-luna`（工具审批分类器）
  - 出站请求透明抓包：本机回环转发至 `LLM_PROXY`（初轮 `/tmp/nano-e2e-787.iPNxw8/wire-tee-pre-rebase.jsonl` 19 条 + 变基并合入审查修复后 `/tmp/nano-e2e-787.iPNxw8/wire-tee.jsonl` 10 条真实 `/v1/messages` 请求，脱敏剥离鉴权头；回收后销毁）

## 2. 四层验收漏斗结果摘要

| 层次 | 范围与命令 | 结果 |
|---|---|---|
| 第 1 层：静态契约、单测与打包图 | `pnpm peers check`、`pnpm build && pnpm typecheck && pnpm check:ios-runtime`、后端/运行时 Vitest 全量（260 文件）、`pytest -m "not e2e" -q`、前端 Vitest 全量（127 文件 / 1250 用例）、`scripts/build-windows-archives.py` `build_graph()` | 全部通过（0 peer 告警；Windows 发布图 3 档包完整） |
| 第 2 层：上下文缓存前缀重放 | `context-cache-prefix-provider.test.ts`、`fork-prefix-provider.test.ts`、`global-child-tools.test.ts`（更新 `.agents/skills/verify-context-cache-prefix/SKILL.md` 基线至 DSH `0.2.2-rc.5` + `dsh-agent-context 0.3.0-rc.12`） | 3 文件 / 11 用例全部通过 |
| 第 3 层：关键路径真进程 E2E | `./scripts/e2e-critical.sh`（覆盖权限审批、审批分类模型、后台 Bash 超长通知、前台 Subagent + `wait_agent`、Global Inbox `delegate_worker` + 原生轨迹预备、Cron 等） | 22 passed, 1 skipped（macOS LaunchAgent opt-in） |
| 第 4 层：隔离真栈 + 真实模型 + 浏览器原生轨迹 | `daily-engineering`、`daily-quality`、`pa_a19e8ee354e6` 多轮真实任务、冷重启不唤醒校验与多视口浏览器核验 | 全部通过（见下表） |

## 3. 真实模型合成任务与出站 Wire 核验

| 场景编号 | 会话 / 角色 | 覆盖能力与边界 | 结果 |
|---|---|---|---|
| `SYNTH-787-T1` | `daily-engineering`（主会话 `51fbb433-2cc9-442b-87e6-0157e746aea1`，开启 `plugin_manager`） | `read` 缺失文件报错记录；两次 `apply_patch`（多文件新建 + 更新并 `Move to: notes/final-787.md`）在 Codex Auto 下工作区内免审放行；`cordis_inspect_list`（`Service`/`Event`/`Config`/`Tool`）与 `cordis_inspect_query`（查询 `Tool.listTools` 中 `apply_patch` 契约）；`schedule_create`/`list`/`delete`（`787-probe`）；`delegate_worker` 后台复核 | 成功完成，物理文件与调度清理一致 |
| `SYNTH-787-T2` | `daily-engineering`（在线撤回 `plugin_manager` 后同会话） | 撤回 `plugin_manager` 后 `cordis_inspect_*` 从下发工具集移除；无独立搜索源及官方 DeepSeek 凭据时 `web_search` 回退 `duckduckgo` 并清晰报告验证拦截说明 | 成功完成 |
| `SYNTH-787-T3` | `daily-engineering`（开启 `subagent_fork`） | 调用 `subagent_fork`，子会话读取两份文件并在后台结算后触发第 4 轮回传 `FORK-SUBCALL-787-OK` | 成功完成 |
| `SYNTH-787-Q1` / `Q2` | `daily-quality`（私聊 `c_k8yqq0pt`，连续两轮，`plugin_manager` 开启） | `wire-tee` 捕获连续 9 次同根会话 `/v1/messages` 请求（`[01]..[05]` 与 `[08]..[12]`，`msgs` 从 5 递增至 21）：`tools` 含 `apply_patch`、`cordis_inspect_list`、`cordis_inspect_query`、`wait_agent`、`interrupt_agent`，不含 `working_directory`、`subagent_oar`、`team_task_*`；去 `cache_control` 后历史 `messages` 与 `system` 严格前缀保持 | 成功完成（`LIVE-RAW-787-OK`、`WIRE-PREFIX-787-OK`） |
| `SYNTH-787-PA1` / `PA2` & `POSTFIX-PA` | `pa_a19e8ee354e6`（个人助手私聊 `c_42fd2ec0cdae`，`plugin_manager` 开启） | 修复 `allowsCordisInspect` 后重采 `wire-tee.jsonl`（`[01],[03],[04],[06]`）：`tools=46` 完整包含 `apply_patch`、`cordis_inspect_list`、`cordis_inspect_query` 以及合流自 `origin/develop` 的 `read_messages`/`search_messages`/`threads`/`download_attachment`，PA 真实调用 `cordis_inspect_list` 并回复 `POSTFIX-PA-INSPECT-OK` | 成功完成 |
| `SYNTH-787-POSTFIX-ENG` | `daily-engineering`（私聊 `c_eat9ucs1`，`plugin_manager` 关闭、`subagent_fork` 开启） | 重采 `wire-tee.jsonl`（`[00],[02],[05],[07]..[09]`）：主会话与 `subagent_fork` 子会话均为 `tools=41`（`plugin_manager=false`、`cordis_inspect_*=false`、`memory_maintenance=true` 前缀完全一致），且软链目录 `/tmp/...` 下全 10 条请求 `working directory changed` 虚假消息为 0 | 成功完成（`POSTFIX-ENG-OK`） |

## 4. 浏览器原生轨迹与多视口交互核验

> [!NOTE]
> 由于桌面宿主窗口遮挡时 T3 内置预览返回 `The browser is not producing screenshot frames`，按工作流规则切换至同环境 Playwright Chromium 对同一隔离栈 `http://127.0.0.1:56168` 执行真实浏览器自动化与几何测量。

1. **真实栈走查捕获并修复的两项集成缺陷**：
   - `packages/dsh-trajectory-viewer/src/config-forms.ts` & `boot.jsx`：补齐 `dsh-client-ui-theme@0.2.2-rc.5` 新增的 `codeFontSize`、`terminalFontSize`、`textFontFamily`、`codeFontFamily`、`terminalFontFamily` 只读投影字段及 `ui-conversation` 配置段，并调整卸载时先 `ctx.fiber.dispose()` 再 `reference.release()`，消除退出订阅报错；新增 `config-forms.test.ts` 直接用上游 `Schemastery` Schema 锁住字段全集。
   - `packages/dsh-integration/src/trajectory.ts`：`dsh-agent-context` 为工具结果打 `[id: N]` 标签时会发出新的替换 `tool/result` 事件（新 `seq`），而上游 `SessionToolResults` 按首次 `tool/result` 的 `seq` 保存在内存；新增存活会话级有界映射 `liveToolSeqs`（上限 1000，随 `session/disposed` 释放），使替换后的 `seq` 能实时定位到内存原始结果，并在 `trajectory-tool-results.test.ts` 锁住末端活跃 `seq` 断言。
2. **工具栏多视口几何测量（无横向溢出、无裁切或挤压）**：
   - 桌面全宽 `1440x900`（工具栏宽 `1062px`，`scrollWidth === clientWidth === 1062`）：`时长`（`x=6..60`）、`⊟ 轮次`（`62..108.4`）、`⊟ 调用`（`110.4..156.9`）、`⊟ 子调用`（`158.9..217.3`）、`搜索轨迹`（`900..1049`）。
   - 窄屏 `960x800`（工具栏宽 `814px`，`scrollWidth === clientWidth === 814`）：四个折叠/时长按钮（`x=6..217.3`）与搜索框（`652..801`）单行完整可见。
   - 紧凑视口 `640x800`：工具栏与记录列表正常浏览，无运行时异常或空白。
3. **双结果视图、冷态降级与子执行钻取**：
   - **存活会话实时结构化结果**（`daily-quality` `cordis_inspect_list`）：WebSocket `toolResults/watch` 返回 `{"available":true,"value":{"providers":[...]}}`，右侧「结果」页签同时展示结构化 `原始结果` 与文本 `渲染结果`。
   - **冷态历史会话降级且不唤醒**（Gateway 重启后直接打开 `daily-engineering` 主会话 `51fbb433-...`）：`initialCatalog.agentAvailable` 在打开与点击查看「结果」前后均保持 `false`，「结果」页签展示「原始结果仅在实时工具调用中可用」并完整保留持久化 `渲染结果`。
   - **失败工具错误保留**（`read` `notes/missing-787.md`）：列表与检查器「概述/结果」均保留失败状态与文件不存在错误原文。
   - **折叠、搜索与 `subagent_fork` 范围定位**：`轮次`、`调用`、`子调用` 折叠摘要与关键字搜索联动正常；钻取进入 `subagent_fork` 子执行显示面包屑 `← 返回发起点 Main Agent › 核验两份测试文件` 及 `定位起点` / `定位终点` 控件。
   - **设置页能力开关核对**：`apply_patch` 出现在能力配置页，而 `cordis_inspect_*`、`working_directory`、`subagent_oar` 未暴露为独立开关；浏览器 `consoleErrors` 与 `pageErrors` 均为 `[]`。
