# refactor-570 — 产品验收报告

## Round 1 — 2026-09-22

- mode: full；对齐 `motivation.md` 三组不变性场景与 `design.md` Reviewer Runbook。
- executed_base: `2e9c83df9`。
- validated_at: `a3c6e819c1b0147baf60ca8c13f6a76ede6749a4`。
- Verdict: **pass**；highest_required_action: pass；issues_count: 0；needs_re_review: false。

## 环境与证据边界

独立 reviewer 经真实外部 ChannelAdapter.start(on_inbound) 回调发送消息，经真实 Gateway、内核、本机 LLM proxy 和隔离 IM 完成旅程。只替换外部 provider adapter；没有替换 shadow、delivery、HTTP、取消 admission 或数据库。客户端面未改，按 Runbook 以真实 IM REST timeline/history 及图片资源接口观察结果。未连接生产飞书；本次不证明飞书网络或前端视觉像素。

Gateway PID 2045，cwd `/private/tmp/refactor-570-e2e`，进程 PYTHONPATH 指向受审 worktree `src`；核实该树 HEAD 为 validated_at。IM `http://127.0.0.1:60291`，隔离节点 `wt-refactor-570-e2e-97213`，专用 nano 身份。恢复场景只停止该环境 IM PID 97241，按同 cwd、同签名环境、同源码重启为 PID 5132，未重建数据库。结束时真实 `/nodes` 返回该节点 online、owner `u_joya1hjc`。

所有主要证据均来自 IM 用户可见内容；provider-output 只辅助确认离线阶段已到外部出口，不能替代 IM 结果。原始证据位于隔离临时目录 `/tmp/refactor-570-e2e/reviewer-*.json`，关键观察在下文完整摘要，临时环境由 caller 清理。

## 用户旅程体验与验收标准覆盖

### Requirement: Shadow 对话内容与回复状态保持一致 — pass

**Scenario: 回复与更新可见 — pass**

从 `review-normal` 外部聊天发送 `请调用bash执行 printf REVIEW570_TOOL_OK，然后只回复 REVIEW570_DONE。`。IM 会话 `c_p08zxod7` 出现对应用户消息，以及唯一 Agent 消息 `c40e533d183e4861bd7268d11ce6527d`：正文 `REVIEW570_DONE`，delivery_status=completed；同一消息包含 bash call `call_00_koZkz2Bz2QDmCSvO7KLo5427`，status=completed、exit_code=0、stdout=`REVIEW570_TOOL_OK`，并有 token_usage 和 elapsed_ms=3073。没有为正文/工具完成另建重复气泡。证据：`reviewer-normal.json`，后续 `reviewer-final.json` 仍保留同一结果。走现有产品行为并与 motivation/current routing-delivery 契约核对，未用单测代替产品结果。

### Requirement: 已接受回复可以恢复 — pass

**Scenario: 暂时失败后重试 — pass**

从 `review-recover` 发送先 sleep 10、再回复 `REVIEW570_RECOVER_TEXT` 与测试 PNG 的请求。IM 看到工具 running 后停止隔离 IM，使真实 shadow HTTP 同步不可用。离线期间图文候选到达外部出口，图片冻结缓存已经形成。恢复 IM 前删除源 PNG；源图与冻结缓存 SHA-256 均为 `e2c9d9b0342fce014aee4b685fb6adea45873c7ca5d78752286afa6f93e633e2`。

重启同一个 IM 数据环境后，原会话 `c_f9whnb59` 出现完成消息 `329e12478df34aa2962b7b9e8a6d865a`，正文含上述文字与实际 IM 图片路径 `/im/v1/conversations/c_f9whnb59/images/f592d3b7d16140309b2c89ca92be4dbe`。以登录用户 GET 该路径，返回 200、image/png、68 bytes，SHA-256 与删除前原图及冻结缓存相同。包含恢复标记的 Agent 正文恰为一条；20 秒后再次读取 history，全部 message IDs 完全相同，没有新增重复消息。文本与图片均由同一次恢复验证覆盖。

证据：`reviewer-recover-before.json`、`reviewer-frozen-proof.json`、`reviewer-recover-after.json`、`reviewer-image-http-proof.json`、`reviewer-final.json`。

环境细节：首次请求使用 macOS `/tmp` 符号链接路径，初次图片候选被现有路径保护拒绝；真实 Agent 改用 `/private/tmp` 后形成上述已接受候选。IM 中另有初次失败的空正文气泡 `ed45b4bc82804ee6a54e5226a389b2ae`，它不是恢复造成的重复回复；本次已接受图文候选只恢复一次。没有修改受审实现来避开该规则。

### Requirement: 已失效 run 不晚发正文 — pass

**Scenario: 取消后的旧回复 — pass**

从 `review-stop` 要求前台 bash `sleep 40; printf REVIEW570_OLD_RESULT` 并在返回后输出 `REVIEW570_OLD_BODY`。IM 会话 `c_ytrc08er` 中，原气泡 `ef15c726c13a4d248997710e97331e73` 的工具已为 running 后，从相同真实外部入口发送 `/stop`。IM 随后显示停止回复 `已停止当前操作。`（消息 `18efc32206a147d287178565fd4904a5`）。

原气泡保持相同 ID，正文为空，delivery_status=completed；工具 `call_00_OqiyOMyeVBNR6xbePB1s8701` 从 running 清理为 failed、reason=interrupted、output=`[Request interrupted by user for tool use]`。等待 45 秒，超过原命令 40 秒执行期后，Agent 正文中没有 `REVIEW570_OLD_BODY`，也无新增旧结果气泡；最终其他旅程结束后的 history 再次保持该结果。不是人工放行取消 hook，也未注入伪造 terminal 快照。

证据：`reviewer-stop-before.json`、`reviewer-stop-after.json`、`reviewer-final.json`。本旅程证明真实用户停止后的旧运行没有晚发正文且工具清理完成；未通过私有接口强造取消后的已保存候选。

## Reference Artifacts Reviewed

N/A。无前端变更或 must-match 原型；验收依据是 motivation 场景和 design Runbook，当前行为参考 `docs/specs/gateway/routing-delivery.md`、`external-channels.md`。

## 问题清单

无 blocking / major / minor 问题；未提交外部 issue。macOS `/tmp` 路径保护为旅程中的环境输入差异，纠正真实路径后完成全部期望结果，不构成本 unit 行为回归结论。

## 上层文档同步

- [x] `SPEC.md`：无需更新；无跨包行为变化。
- [x] `docs/specs/gateway/`：无需更新；本次验证保持已有交付、冻结图片和取消语义。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；未改变文档体系。

## 资源交接

reviewer 启动的替代隔离 IM 为 PID 5132，exec session 10735；已交回 caller 按本轮统一清理职责关闭。Gateway 与其余环境仍由 caller 统一清理。未启动永久测试、未修改源码/受审设计/受版本控制的配置。

## Round 2 — 2026-09-22：真实飞书补充验收

- mode: full（以真实飞书补齐 Round 1 的合成 provider 边界）。
- executed_base: `2e9c83df9`；validated_at: `b8c621245ae4bf14c71694892f92686aa8068c1d`（本轮运行 worktree HEAD；本 unit 源码与 Round 1 的 `a3c6e819c` 等同）。
- Verdict: **fail**；highest_required_action: **fix-implementation**；issues_count: **1 major**；needs_re_review: **true**；gh_issues_filed: 0。
- Round 1 的观察继续保留，但真实飞书补测发现 `/stop` 未停止正在执行的任务，不能以 Round 1 的合成入口通过结果覆盖本轮失败。

### 真实运行边界

使用 `lark-im` / `lark-shared` skill，所有消息发送和历史/资源读取固定专用 profile `e2e-feishu-testagent`，发送身份 `--as user`。执行前独立校验 profile verified、App 和 Bot 与专用 env 相符，未输出或提交凭据及用户/Bot 身份 IDs。只向专用测试 Bot 发常规验收消息，无生产 Bot 操作。

隔离栈 `/private/tmp/refactor-570-feishu` 为真实 `--feishu` 栈，Gateway PID 14421 的 cwd、PYTHONPATH 已核对指向隔离环境与受审 worktree。真实飞书 WebSocket 入站、真实 Bot API 出站、真实内核/LLM/IM，无合成 adapter。IM `http://127.0.0.1:49724`，专用 nano 身份。故障注入只停止隔离 IM PID 14380；保留数据库和签名环境，以同 cwd、同源码重启为 PID 15250（session 53695）。

结果来自飞书用户身份历史、消息资源下载和 IM 用户 REST history/图片 GET；不以 saga、API 返回成功或单测作为交付证明。没有做 GUI 像素或客户端交互验收，不声称实测 GUI 显示。临时原始证据在 `/tmp/refactor-570-feishu/reviewer-*.json`；关键直接证据如下，测试身份历史中的旧消息没有计为本次成功。

### Requirement: Shadow 对话内容与回复状态保持一致 — pass

**Scenario: 回复与更新可见 — pass（真实飞书）**

用户消息 `om_x100b64114b16c0a4b3e05f64942a8a7` 要求 bash `printf FEISHU570_TOOL_OK` 后回复 `FEISHU570_NORMAL_DONE`。真实飞书收到唯一对应 interactive 消息 `om_x100b641148d490b8b1a0ca650e0c62f`，历史内容为：

```text
FEISHU570_NORMAL_DONE
---
📝 deepseek:deepseek-v4-flash · ctx 4%
```

IM 会话 `c_9tr53sne` 的 Agent 气泡 `7acf86d0c109401199d3293321c1ebab` 正文严格为 `FEISHU570_NORMAL_DONE`，没有运行信息 footer；delivery_status=completed，同一气泡含 bash completed、exit_code=0、stdout=`FEISHU570_TOOL_OK`。随后图片与停止旅程后仍未出现正常回复的重复气泡。

证据：`reviewer-normal-feishu.json`、`reviewer-normal-im.json`、`reviewer-final-im.json`，以及只保留本轮消息字段的 `reviewer-round2-feishu-evidence.json`。

### Requirement: 已接受回复可以恢复 — pass

**Scenario: 暂时失败后重试 — pass（真实飞书图文，含真实图片资源）**

1. 在真实路径 `/private/tmp/refactor-570-feishu/.gateway-workspace/e2e/.nanoassistant/exports/feishu570.png` 准备 64×64 RGB PNG，179 bytes。发用户消息 `om_x100b6411479080a0b2a654e88d0e11c`，要求 sleep 10 后回复 `FEISHU570_RECOVER_IMAGE` 和该图片。
2. IM history 确认前台工具 running 后停止隔离 IM。IM 离线期间，真实飞书已收到 interactive 消息 `om_x100b641144a4a884b2562e13abfd138`，包含标记、`img_v3_0215p_cbb527e2-7cf6-4c5f-abd3-a094c5fd874g` 图片资源和运行信息 footer。
3. 在 IM 恢复前删除源 PNG，随后用原数据库/签名环境重启 IM。原气泡 `29f21b2619d24e3a9de70a54d5c2cb76` 补齐 completed 正文与图片链接；恢复前后该会话全部 message IDs 相同，没有创建另一个图片回复。最终停止旅程结束后再次读取，两端均只有一个对应图文回复。
4. 以真实飞书用户身份，从上述消息下载 image 资源，实际获得 PNG 179 bytes；以 IM 登录身份 GET `/im/v1/conversations/c_9tr53sne/images/f8551c52fa0d4c02aec7b2a1ce0633d2`，实际获得 200、image/png、179 bytes。两个下载文件与删除前原图 SHA-256 均为 `97781656d41f8c2391e0d1002c8ba25776cf150d895d2bf054a45df4d0ec5e28`。由源文件已不存在而两端仍获得完全相同图片，证明恢复没有依赖重读原文件。

证据：`reviewer-image-source.json`、`reviewer-recover-before-im.json`、`reviewer-recover-offline-feishu.json`、`reviewer-feishu-image-proof.json`、`reviewer-im-image-proof.json`、`reviewer-recover-after-im.json`、`reviewer-final-feishu.json`、`reviewer-final-im.json`。本轮实际覆盖真实飞书出口，不再只保留 Round 1 的合成 provider 恢复证据。图片资源下载发生于恢复后，飞书卡片及 image key 在 IM 离线期间已直接观察到。

### Requirement: 已失效 run 不晚发正文 — fail

**Scenario: 取消后的旧回复 — fail（真实飞书）**

用户消息 `om_x100b641141bb9090b3c262fc5d08c4b` 要求执行 `sleep 40; printf FEISHU570_OLD_RESULT`，工具返回后只回复 `FEISHU570_OLD_BODY`。IM 原气泡 `907a54ff803f40a2a9df360149f626fb` 已显示 bash running 后，以相同真实用户身份发送 `/stop`（`om_x100b6411410668acb1aab51a9941a0f`）。

本次真实飞书新增回复 `om_x100b6411412bf8a4b2e90ee9f24bd03` 却为 `当前没有正在执行的操作。`，IM 工具仍为 running。停止发送后等待 46 秒（超过原任务 40 秒）：

- 飞书新增 interactive `om_x100b64115c9f34a8b494f58630f99ba`，正文为 `FEISHU570_OLD_BODY`，说明旧任务继续完成并发送。
- IM 原气泡变为 completed，正文同样为 `FEISHU570_OLD_BODY`。
- bash 工具实际 duration_ms=40070、exit_code=0、stdout=`FEISHU570_OLD_RESULT`、status=completed，没有 interrupted 清理。

证据：`reviewer-stop-before-im.json`、`reviewer-stop-new-feishu.json`、`reviewer-final-feishu.json`、`reviewer-final-im.json`、`reviewer-round2-feishu-evidence.json`。采集早期曾匹配到同一专用测试会话的历史停止确认，已通过本轮前 message ID 集合排除，未将历史消息当作本次停止成功。

### 问题清单

| ID | Severity | Regression Relation | 期望 / 实际 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| R2-1 | major | unclear | 运行中 `/stop` 应停止任务、清理工具且无旧正文；真实飞书回复“当前没有正在执行的操作。”，40 秒工具完成后两端仍收到旧正文 | fix-implementation（交 owner 定位并决定 unit 归属） | 违反必验场景，阻塞本轮产品验收。reviewer 未读实现定位，不能据此断言由本 refactor 引入，也不能将未知原因降为非阻塞 |

### Reference Artifacts Reviewed / 上层文档

无 GUI must-match 原型；本轮验证真实飞书消息结构和资源、IM 用户可见历史。`SPEC.md`、`docs/specs/gateway/`、`AGENTS.md`/`CLAUDE.md`、`docs/specs/CONTRIBUTING.md` 无新增预期行为待写回；不能把本轮观察到的取消失败改写成新契约。待 owner 完成定位/处置后，以真实飞书重验 R2-1，继承本轮失败项。

### 资源交接

新隔离 IM PID 15250，exec session 53695；无额外 keepalive，shell 直接等待该 IM 子进程。已交回 caller 统一清理。reviewer 只追加本报告，不改受审源码/配置/设计，不创建永久测试，不独立 push。

### Round 2 补充裁决 — 专用 Bot 存在第二个 listener

在上述报告提交后，caller 提供了运行归属证据：同机另一个 task 的 Gateway PID 90293 使用相同专用飞书 App；其 readonly 入站记录命中了本次 `/stop` 消息 `om_x100b6411410668acb1aab51a9941a0f`，而本次隔离栈仅收到 normal/image/long 三条消息，没有收到该 `/stop`。这解释了本次任务持续运行、另一个 Gateway 却返回“当前没有正在执行的操作。”的观察。此处归属证据来自 caller 的只读调查，reviewer 未读取实现定位或修改其他 task。

- 原始飞书/IM 观察和上方 R2-1 保留，不覆写历史证据。
- **R2-1 状态改为环境阻塞、产品结论 inconclusive**；不是已证实的 PR 回归。`取消后的旧回复` 场景当前结果为 **inconclusive**，需唯一 listener 环境重新执行。
- **Round 2 最终 Verdict 仍为 fail（环境无法证明必验停止场景）**；已确认产品问题数 0、环境阻塞数 1；highest_required_action 改为 **out-of-unit（caller 隔离 listener 后复验）**，needs_re_review=true。撤销上方对实现修复的要求，不能依据本轮证据要求修改本 refactor。
- 正常回复及图片恢复证据仍有效：它们在本次 IM 会话中观察到完整对应内容和工具结果，图片冻结恢复由本次栈实际完成。
- 已停止继续发验收消息，等待 caller 获得他人 task 服务操作授权并提供唯一 listener 前置。reviewer 不自行停止或恢复其他 task 的 Gateway。
