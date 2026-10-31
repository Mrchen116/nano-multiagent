# refactor-682 — 产品验收报告

> 对齐 motivation.md 全部用户侧 Scenario；后端 HTTP 产品入口验收，按 design.md Runbook 无需新增 Web/iOS 视觉验收。
> Round 1 validation snapshot: `0812c67efe12174c429c372103fb8842891eed64`，2026-10-31。

## Verdict

**fail（必验场景尚有 inconclusive，等待隔离故障与断连窗口）**。本轮独立观察得到在线缓存与配置保存回读的有效证据；尚不足以交付。

## 用户旅程体验

以专用 nano 测试主人登录 `http://127.0.0.1:60392`，调用 Web 同源产品 settings/config/section 入口。独立核对节点 online、P/E/Q + PA 四角色、研发日常群及 PA 私聊，符合 `.e2e-daily.json`。E/Q 使用 sol/high、PA 使用 astra/medium，三者均 global/codex。IM PID 84967、Node PID 85081，启动时间晚于验收 commit，执行路径均指向本 worktree 的构建产物；构建完成状态采用 caller 交接，未重跑构建。

第一次 E settings 读取约 9 秒返回 HTTP 200，但 ready=false、display.source=unavailable、timeout，彼时未注入故障。后续 E/Q/PA 冷读分别 6.013/6.284/6.250 秒成功；这些样本均超过设计冷读 p95 <5 秒目标，样本数不足以计算可靠 p95。caller 随后告知同机正在运行高并发 native 测试；本报告不据此消除观察，也不自行归因。

随后的 60 次、32 并发 E/Q/PA settings 全部 HTTP 200、ready=true、current，最大 0.6433 秒；各角色 captured_at 保持原确认时间。E 推理强度 high→medium 保存成功，settings 回读 medium 且 ready=true；使用旧 profile_version 重发被 409 拒绝，最后已恢复 high。未发送真实 LLM 消息，未访问生产。

## Reference Artifacts Reviewed

motivation.md、design.md（含 Runbook）、本 unit IM delta-spec、current `docs/specs/im/agents-nodes.md`、`docs/development/worktree-runtime.md`、change-reviewer skill。原型/viewport：N/A，本 unit 明确保持交互与 UI 不变。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 | 待复核 | 无注入时首个 E 冷读 timeout，后续三个冷读 6 秒以上 | 在独占性能窗口复验，保留原始失败 |
| 2 | 验收缺口 | 故障降级/恢复、故障时分区、断连/权限变化未完成 | 等待 caller 的故障材料与 soak 结束后窗口 |

## 验收标准覆盖

| Scenario（motivation.md） | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 在线打开与连续刷新 | E/Q/PA 正常 settings；60 次32并发；`concurrent-warm.json`、`*-initial.json`、`settings.json` | inconclusive | 缓存通过，首次冷读timeout需复核 |
| 目录异常后重试 | 尚未注入受控故障 | inconclusive | 不以未注入首次timeout替代受控异常完整证据 |
| 离线与权限变化 | 无凭据 settings 401（`baseline.json`） | inconclusive | 尚未断连/重连与已登录身份权限撤销 |
| 保存配置与下一轮生效 | `original-config.json`、`save-config.json`、`saved-settings.json`、`conflict-config.json`、`restored-config.json` | inconclusive | 保存回读/版本冲突通过；下一轮能力由独立 native/context 验证补足，不声称已发送模型任务 |
| 独立分区继续可用 | 正常 plugins section 200 | inconclusive | 需在目录故障期间复验插件、任务、统计和渠道 |

本轮原始 HTTP 证据保存在本机 `/tmp/catalog-product-acceptance/`（包含专用测试身份 auth，不能提交或展示该文件）；本报告仅提交不含凭据的结论。错误猜测的 section 路径 `/tasks`、`/statistics`、`/channels` 返回 404，仅用于确定入口，不计为产品缺陷。

## 上层文档同步

- [x] `SPEC.md`：需要反映临时官方 DSH 子进程职责，由 orchestrator 收尾核对。
- [x] `docs/specs/im/agents-nodes.md`、Gateway agent-capabilities：需要归并已验证 delta-spec，当前仍含当场解析旧契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — 最终构建独占窗口复验

> Validation snapshot: `bf0cdfdc32df872c9c40a0461c8284652d142d2f`，2026-10-31 16:11–16:15 CST。
> **最终 Verdict: pass**。首轮未完成项全部由下表补齐；首轮 timeout 保留为真实观察，不将负载解释当作已证实根因。

### 版本、环境与证据边界

caller 提供最终 `pnpm build` / `pnpm typecheck` 成功日志 `/tmp/refactor-682-final-{build,typecheck}.log`，最终 Node 重启记录 `/tmp/refactor-682-final-node-restart.log`；IM 实现相对首轮未变，沿用同一 IM/数据库。独立确认 HEAD、真实节点 online、HTTP 当前结果。独占阶段无其他测试负载。只有后端产品 HTTP 流程变化，本轮不评价新版 main 前端画面。

原始请求脚本及 HTTP JSON 在 `/tmp/catalog-product-acceptance/`；仓库保存已去除配置正文、凭据和工具描述的精简证据 [product-acceptance.json](evidence/product-acceptance.json)。插件 fixture 描述 `/tmp/refactor-682-fixture.json`，E workspace 的 inspection-blocker 仅在 inspection 进程且 block-inspection flag 存在时同步阻塞。读取其 marker 确认实际进入 worker（inspection_id `536c80a3-1afd-4e7b-bc09-1aae23465ee5`、PID 2501），没有以模拟 HTTP 响应代替故障。

### 真实操作与整体可交付性

最终 E/Q/PA 冷读分别 1.8712/1.2843/1.2891 秒返回 ready/current。E 配置 high→medium，保存 1.4697 秒成功，settings 正确回读；旧版本保存 409，恢复 high 成功。恢复后的32并发冷读全部 ready/current，最大 1.3234 秒、唯一 captured_at。当前独占冷样本全部低于5秒；样本较少，不声称形成长时 p95 结论，长时门禁由 caller 单独完成。

故障通过真实 `POST /im/v1/agents/daily-engineering/plugins` 的 set_bundle off/on 推进目录失效，然后设置 flag。首次立即连续 off/on 得到既有 409 pending 提示；等待插件状态完成后再次开启成功，不绕过异步状态。settings 实际挂起 7.1862 秒后返回 last_known、ready=false、live_capabilities=null、timeout，已保存配置保留。期间插件、cron、usage section 均200/current，channels 200空列表，Q settings 1.3449秒 ready=true。移除 flag 后，E 在1.3317秒恢复 current/ready；此恢复未重启 Node 或聊天 runtime。

随后用固定 Node24 CLI 对本次隔离 `.gateway-config.yaml` 执行 `apps/node/lib/cli.js stop --config .gateway-config.yaml`，读取 settings 为 offline/last_known/ready=false；PATCH config 返回409 agent_node_offline，capabilities 返回503。执行同 CLI `start --config .gateway-config.yaml`，Node PID2587；重连后的 settings 1.3036秒返回online/ready。登录身份通过正式 auth/logout 撤销，随后同 access token settings 返回401 session revoked or expired；重新登录恢复测试身份。此前过期token也明确401，无当前目录泄露。

可见体验保持现有协议：正常打开可编辑，失败仍展示最近内容且只读；独立分区不被目录失败拖住；重试/重连恢复，无需新增操作或要求重启聊天进程。没有发送真实模型消息。普通/Global/PA 下一轮实际工具与 prompt assembly 保真采用已交接 native 测试证据：`evidence/implementation.md` 的 Round 3、`/tmp/refactor-682-fidelity-r3.log` 及最终全量/定向回归记录；这是确定性执行能力证据，不能解释为真实模型任务验收。本 reviewer 未读取实现定位根因。

### 首轮未完成项逐项关闭

| Scenario（motivation.md） | Round 2 决定性证据 | 结果 |
|---|---|---|
| 在线打开与连续刷新 | E/Q/PA独占冷读1.28–1.87秒；32并发冷读全ready、共享确认时间；首轮60并发缓存证据仍有效 | pass |
| 目录异常后重试 | marker确认同步挂起；7.186秒last_known且live=null；移除flag后1.332秒恢复；Q正常 | pass |
| 离线与权限变化 | stop后offline只读、保存409、cap503；start后online ready；logout后原身份401；更细绑定/owner迟到fencing由独立契约验证覆盖 | pass |
| 保存配置与下一轮生效 | 最终构建模型推理选择保存回读、旧版本409、恢复high；实际执行权限/assembly采用上述native保真证据 | pass |
| 独立分区继续可用 | 同一次目录挂起窗口plugins/cron/usage为current，channels200，Q ready | pass |

Round 1 问题1在最终独占窗口不能复现；原观测保留，不声称任何负载下均无超时。问题2所列必要产品旅程全部完成。未发现阻塞产品问题（0 blocking / 0 major / 0 minor）。更长时资源与性能门禁仍归caller，不用本报告替代100刷新/30分钟soak、CI或代码审查。

16:15 CST 释放隔离栈给 caller；block-inspection flag 已删除，fixture恢复enabled，E reasoning_effort恢复high，Node在线。未启动额外服务，未改受控配置或产品实现。上层文档同步职责沿用首轮勾选，等待orchestrator归并。
