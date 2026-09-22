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
