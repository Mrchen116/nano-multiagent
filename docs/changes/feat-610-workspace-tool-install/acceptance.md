# feat-610 — 产品验收报告

> 对齐：spec.md 全部 7 个 Scenario；Round 1，full。
> Validation snapshot：`9182699fca58d42fbf166f3de7445c635dcb3527 → 33ef0d76d342a10c411ccbc0828f82d0d564e810`。
> 执行日期：2026-10-15（Asia/Shanghai）；checkout `codex/feat-610-workspace-tools`，开始时 HEAD 与 validated_at 一致、工作树干净。调用方已在此版本构建并准备隔离栈；reviewer 未修改实现或构建产物。

## Verdict

**pass**。7 个用户场景均完成真实产品路径验证；无 blocking / major 问题。Highest Required Action：pass。

## 用户旅程体验

通过 Web IM 使用的真实 HTTP 消息、配置、fork 和审批接口驱动 IM → Node → DSH → 真实 `deepseek:deepseek-v4-flash`。没有使用确定性模型，也没有绕过聊天直接调用 runtime RPC。没有更改客户端；本单元没有新增 UI，按 design Runbook 授权的接口代驱动，不声称浏览器视觉或移动端验收。

用户先建立带口令的既有聊天，再要求助手自己写一个整数翻倍工具。模型自行查阅已安装 DSH 的工具作者说明、写 package/patch/JS，随后调用 `plugin_manager` 安装并在同一轮实际调用新工具。Reviewer 只描述目标与产品手册中的 bundle 形态，没有代写成功实现。创作过程约 5 分钟，包含模型自行探索和人工审批等待；最终回复区分了安装状态与真实执行结果，并保留旧口令。后续同 workspace 另一聊天无需安装直接调用；另一 workspace 查不到且真实调用被拒绝。

首次配置准备将测试 Agent 的显式空工具集通过正常配置 API 设为 `read/write/edit/bash/glob/grep/plugin_manager`，符合场景 GIVEN 的“已获准管理与文件写入”；`web_search` 保持禁用。安装开始后未再改工具选择，两个新名字从未写入白名单。故意加载失败后收到 `application: failed` 和具体错误，模型修正同一源目录并重装成功。两次正常节点重启分别证明安装与撤销选择持久化。整个过程可由聊天结果完成判断，无需用户改白名单或以重启促使安装生效。

正常 Auto 审核数次返回 `Reviewer returned no valid verdict`，产品给出人工审批卡。Reviewer 在专用测试授权内通过正常 `allow_once` 路径批准具体读取/写入/工具执行；其余调用正常自动通过。未关闭 Auto 或扩大权限。该回退没有阻断目标，不把模型审批服务稳定性认定为本单元实现缺陷。

## 环境与证据

- IM：`http://127.0.0.1:54267`；节点：`wt-nano-multiagent-96374`；专用测试账号 nano。
- A：Agent `e2e`，workspace 为本 worktree `.gateway-workspace/e2e`；B：`e2e-peer`，`.gateway-workspace/e2e-peer`。
- A 原聊天 `c_pp1ump8j`；从初始口令回复 fork 的同 workspace 聊天 `c_c2gdxrqz`；B 聊天 `c_fnnsjlbc`。fork 在安装后进行，但取安装前口令消息为分叉点，第二聊天未继承安装操作正文。
- 本地完整 HTTP timeline 与 WS 事件：`/tmp/feat610-review/a-timeline.json`、`a2-timeline.json`、`b-timeline.json` 和同目录 `*.jsonl`。这些为本次本机证据，不提交。报告下方保留可复查消息 ID 和结果。
- 重启前 Node/DSH PID `96473/98548`；第一次正常 `pnpm pa restart --config <worktree>/.gateway-config.yaml` 后 `99934/99938`，新心跳 `2026-10-14T16:12:42.704Z`；第二次 `505/511`，新心跳 `2026-10-14T16:14:13.707Z`。两次 `pa status` 均 ready=true；只重启隔离节点，未动共享模型代理或生产。
- `before-restart.json`、`after-restart1.json`、`after-restart2.json` 保留配置与节点观测；前后静态白名单完全相同。

## Reference Artifacts Reviewed

N/A。spec/design 无原型、reference screenshot 或 must-match 视觉要求。已读取 design Runbook、worktree-runtime 与 current agent-capabilities spec。

## 问题清单

无阻塞问题。以下是证据边界，不作为本单元缺陷：

- A 中要求真实模型强行调用缺席的 `web_search` 时，模型未发该调用，曾重复调用其它已安装工具；用户补充“停止重复”后结束。A 的结论依据实际配置保持与模型可用目录缺席，不伪称获得了 A 的执行层拒绝。B 在相同静态工具选择下确实发出 `web_search`，得到 `UNKNOWN_TOOL`。不以模型自述代替其他场景的实际工具结果。
- Auto 分类偶发无有效判定，使用既有人工回退完成；未调查实现根因或修改审核配置。

## 验收标准覆盖

### Requirement: Agent 可自助创作并安装工具 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在既有聊天创建并使用新工具 | spec.md 同名 Scenario；design Runbook | 原聊天先记口令，再由真实模型创作、安装、立即调用 | 用户 `02b8a1836578421db56efa06ea6838b1`；回复 `5396431d1906441286f02352c2b0acf6`：模型 write 三个 bundle 文件；install 返回 `application: applied`、`tools: [orchid610_double]`；调用 `n=21` 返回 `{value:42,marker:ORCHID610}`；回复保留口令 | pass | 安装未改白名单、未重启；真实工具调用而非 bash 计算 |

### Requirement: 新装工具按 workspace 隔离且持续可用 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同 workspace 的多个聊天共享新装工具 | spec.md 同名 Scenario | 从安装前消息 fork 另一聊天，直接要求调用 | 聊天 `c_c2gdxrqz`，用户 `73b49d6123b74f1f92fd855f9efba8ad`；回复 `d4485057c54a454b9a2a108577035f06`，原生调用 `orchid610_double({n:17})` → `{value:34,marker:ORCHID610}` | pass | 新聊天未安装或写文件 |
| 其他 workspace 不获得私有工具 | spec.md 同名 Scenario | B 查管理列表与 capabilities；真实模型追加实际调用尝试 | 回复 `7cbb97059add42819d3c7fdbdf452f31`：`list_bundles={entries:[],diagnostics:[]}`；B capabilities 无 orchid 工具。回复 `4bb371bf31994388a1ce358a0294f0f1` 中实际 `orchid610_double({n:11})` → `ToolNotFoundError / UNKNOWN_TOOL` | pass | 无 B 安装；实际错误来自 tool result |
| 重启后继续使用 | spec.md 同名 Scenario | 正常重启隔离 Node 后继续 A 原聊天 | 用户 `1e061681d1c94394ac0ca64a9fecca45`；回复 `c32346bef98a47b19ed6a35b670fce9a`：double(31) → 62/ORCHID610；repair(31) → 32；原口令仍在 | pass | 未重装、未改配置、未新建聊天 |

### Requirement: 自建工具不改变其他已有工具选择 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 安装不重新启用既有禁用工具 | spec.md 同名 Scenario | 安装前排除 web_search；安装及重启后核对正常配置与聊天可用目录，新工具同时实调 | `before-restart.json`、`after-restart1.json`、`after-restart2.json` 的 allowlist 均只有准备时 7 项；A 回复 `b65603b2cb594182b9b1135cefcbf4cb` 的新工具 double(23) 实调 → 46，同时目录无 web_search；另一聊天 `1ddfa603e16c4b5fb7638e7d749b5cdd` 同样不可用。B 回复 `4bb371bf31994388a1ce358a0294f0f1` 的实际 web_search → UNKNOWN_TOOL | pass | A 未生成 web_search 调用，不能声称 A 派发拒绝已验；配置与可用目录保持证据成立 |

### Requirement: 安装与停用结果准确可恢复 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 安装失败后修正重试 | spec.md 同名 Scenario | 模型创作第二 bundle，顶层故意抛错，安装后调用旧工具，再自行修正重装并调用新工具 | 用户 `323bba044f924020a86ab1f30823c4fd`；回复 `f84b9ba1b2f5425cba52fffada113f80`：首装 `application:failed`，warnings 含 `ORCHID610_LOAD_FAIL`（包管理 exitCode=0 不掩盖加载失败）；double(9) → 18；模型重写 tool.mjs 后重装 `application:applied`，repair(9) → 10 | pass | 重装使用同源目录，无重启；未把失败声称为可用 |
| 停用或移除自建工具 | spec.md 同名 Scenario | 同聊天停用 double bundle、移除 repair bundle，立即尝试；再正常重启后查状态及再次实际调用 | 回复 `eaf55d06b8114acf8ad84cef84627d03`：set_bundle false / remove_bundle 都 applied，tools 最终 []；两工具 n=5 均 UNKNOWN_TOOL。第二次重启回复 `b0c82836429f46b9829e75b1f118f26f`：list 保留 double enabled=false、repair 缺席；两工具 n=7 均 UNKNOWN_TOOL | pass | 覆盖停用与移除两条分支，源目录保留；无需重启即可撤销，重启后不恢复 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，本次未改变既有包边界。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要由 orchestrator 收尾归并本 unit delta-spec；当前仍描述静态两层工具，尚未反映 workspace 自助安装自动启用例外。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 交付与清理

本报告未提交，遵守 caller 的“只写 acceptance.md、不提交”。Reviewer 未启动额外服务；隔离共享栈由 caller 最终清理。两次 `pa restart` 后应以实际 lifecycle state 核实当前 PID `505` / DSH `511`，不能将原 `.gateway.pid` 外部 marker 当作仍有效的当前进程身份。本地脚本、事件与 workspace 产物未暂存。
