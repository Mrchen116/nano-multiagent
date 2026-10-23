---
status: research-snapshot
recorded-at: 2026-08-13
nano-baseline: 9c2d8a526bfca8b53977d5694f57326cded70cef
source-baseline: claude-code-local-reconstruction@0991eac5ccd518d6bd0486752f61a42f9ad68fa8; claude-code-cli@2.1.227
upstream: claude-code-local-reconstruction; installed-claude-code
upstream-baseline: claude-code-local-reconstruction@0991eac5ccd518d6bd0486752f61a42f9ad68fa8; claude-code-cli@2.1.227 (runtime build 2.1.227.387)
latest-verified: claude-code-cli@2.1.232
current-owner: pending-adoption
---

# Claude Code Auto Mode Classifier — 2026-08-13

本研究包核验 Claude Code Auto Mode 的三个时间面：nano 当初参考的本地重建源码基线、本机已安装 Claude Code 2.1.227 的完整 provider artifact，以及独立下载的最新版 2.1.232 follow-up trace。它回答旧的 `Network Services` 硬拦截从哪里来、当前 Claude Code 是否仍使用它、当前两阶段分类器如何分工，以及 classifier 前后还有哪些非 LLM permission path、失败与 approval 回路。

这是带日期、基线和本机 trace locator 的研究快照，不代表 nano-multiagent 已采用现行 Claude Code 策略，也不覆盖 current code、spec 或权限行为。若决定改造 Nano Auto Mode，必须单独建立 change unit，并在实现后把最终契约归并到相应 current owner。

| 材料 | 作用 |
|---|---|
| [`research.md`](research.md) | 来源、运行时 capture manifest、观察、推论、局限与待验证项 |
| [`claude-code-2.1.227-classifier-system.deidentified.json`](claude-code-2.1.227-classifier-system.deidentified.json) | 当前 runtime 的完整 system blocks；仅一个静态 access-token shell 示例按 manifest 脱敏 |
| [`claude-code-2.1.227-classifier-stage-inputs.json`](claude-code-2.1.227-classifier-stage-inputs.json) | Stage 1 / Stage 2 的完整 classifier user-message blocks、模型参数与原始 system 哈希 |
| [`claude-code-2.1.232-follow-up.md`](claude-code-2.1.232-follow-up.md) | 最新版获取哈希、2.1.232 两阶段 block trace、相对 2.1.227 的 policy delta 与 Nano gap ledger |
| [`Claude Code Auto Mode Classifier 两阶段机制.md`](Claude%20Code%20Auto%20Mode%20Classifier%20%E4%B8%A4%E9%98%B6%E6%AE%B5%E6%9C%BA%E5%88%B6.md) | 两阶段 classifier 的 runtime capture、Nano 差异和采用边界 |
| [`Claude Code Auto Mode Permission Mechanism 重建.md`](Claude%20Code%20Auto%20Mode%20Permission%20Mechanism%20%E9%87%8D%E5%BB%BA.md) | 公开 decision order、binary Bash fast paths、真实 probe、failure/circuit-breaker/subagent/message 生命周期与 Nano 重实现边界 |
| [`../../upstreams.md`](../../upstreams.md) | 本地参考仓的使用和基线记录规则 |

## 范围与结论摘要

1. **旧来源已证实。** Nano 的 `auto_mode_gate.py` 中保留的 `Network Services` 规则，来自固定的本地 Claude Code 重建基线；相对该原 prompt，Nano 的 `BASE_PROMPT` 仅把产品名 `Claude Code` 泛化为 `an AI coding assistant`，该规则逐字相同。
2. **当前 shipped runtime 已变。** 已安装的 Claude Code 2.1.227（classifier build `2.1.227.387`）在一次真实分类中提交了 110,492 字符的 `You are a security monitor for autonomous AI coding agents.` prompt；它不含旧 `Network Services` 标题。
3. **当前仍是条件式两阶段。** 同一受控操作先触发 Stage 1 的 `<block>yes</block>`，继而触发 Stage 2；两次请求具有相同 system blocks、相同 classifier transcript，只追加不同阶段 suffix。Stage 2 考虑用户明确授权与例外后返回 `<block>no</block>`。
4. **对 loopback E2E 的直接含义有限但明确。** 当前 prompt 的 `Expose Local Services` 针对非 loopback/不明网络的暴露、隧道和反向 shell，并明确将项目工作目录中的开发服务归入 Local Operations ALLOW exception。它不等价于批准外发消息：Feishu Bot 的对外发送仍要按收件目标、内容与授权单独判断。
5. **prompt seam 不是完整机制。** 官方 contract、2.1.227 binary 与两个最小 runtime probe 共同确认：规则、read-only、sandbox auto-allow、Bash AST/clamp、安全 circuit breaker、normal/no-verdict denial、headless fallback、subagent 和 `SendMessage` review 都在 classifier 外或围绕 classifier 生效。因此当前 prompt artifact 只能作为上游 policy/input-contract 材料，不能直接覆盖 Nano 的 prompt constants。
6. **`mkdir` 的 winning path 已闭合。** 2026-08-14 的同命令 debug trace 明确记录 `Skipping auto mode classifier for Bash: would be allowed in acceptEdits mode`；结合官方对 Accept Edits 固定本地文件命令的说明，可排除该次运行命中 sandbox auto-allow。此前计划的 no-sandbox 对照不再需要。
7. **最新版 2.1.232 已独立复核。** isolated binary 的真实 `curl | bash` trace 仍执行 2,112/10,240 token 的条件式两阶段，Stage 1 与 Stage 2 均 block，action 未执行而主 Agent/run 继续；相对 2.1.227 policy 的真实文本增量包括 remote-device Chrome-MCP 边界与 `Third-Party Attack` soft deny。
8. **Subagent 三 checkpoint 已有 runtime 证据。** 2.1.232 对 delegation spawn、child 的唯一 Bash action 和 untrusted completion hand-back 分别调用 classifier；三次 Stage 1 allow 都位于对应 dispatch/result 交付前。
9. **`SendMessage` 在 delivery 前按内容复审。** nonexistent-target trace 中，classifier transcript 带有 recipient、content 和 summary，allow 后才 dispatch；工具随后明确 `Not sent`，没有真实外发。

完整 system prompt 与两阶段 classifier input 已保存为 study artifact；因静态示例触发 secret scanner，system artifact 仅把一个示例替换为等义无 token 文本。原始 system 的 text 与 canonical JSON SHA-256、唯一替换位置和本机原件 locator 都记录在 [`claude-code-2.1.227-classifier-stage-inputs.json`](claude-code-2.1.227-classifier-stage-inputs.json) 与 [`research.md`](research.md)。
