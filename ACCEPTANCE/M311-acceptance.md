# Browser acceptance for mention and agent-to-agent DM

- Scope ID: M311
- Verdict: fail
- Reviewed By: product-acceptance-reviewer
- Blocking Issues: 0
- Major Issues: 1
- Minor Issues: 1
- Re-review Required: yes

## Scope

本次仅验收两个真实用户旅程：在 Web IM 群聊中 `@` 某个 agent 并观察其是否实际回复；以及让该 agent 通过 `send_message` 给另一个 agent 发私信，再确认该私信是否送达且前端可见。范围不包含修 bug、不包含代码实现评审。

## Materials Read

- `README.md`
- `docs/operator-runbook.md`
- `docs/NodeGateway-SPEC.md`
- `docs/spec-implementation-conflicts.md`

## User Journeys Exercised

- 在浏览器打开 `http://127.0.0.1:8011/`，进入 `Chat`/`Settings`，确认 `Alpha`、`Beta` 均能从真实 UI 被发现
- 在浏览器里创建群聊（先是默认 `Alpha + Beta`，后是 fresh 会话 `M311 Fresh Group`），并使用 mention picker 真实点选 `Alpha`
- 在群聊里发送 `@Alpha ...` 指令，观察 `Alpha` 是否在群里回复
- 在浏览器设置页为 `Alpha` 打开 `send_message` 工具并保存，再在 fresh 群聊内重新触发 `send_message(to=Beta)`
- 在浏览器左侧会话列表点击 `Direct agent chat`，确认 agent-to-agent direct chat 是否可见、是否出现对应私信内容

## Actual Steps

1. 浏览器打开 `http://127.0.0.1:8011/`，进入 `Chat` 首页。
2. 点击 `Create group chat`，勾选 `Alpha` 与 `Beta`，创建群聊 `Alpha + Beta`。
3. 在群聊 composer 输入 `@`，真实点选 mention picker 中的 `Alpha`，发送要求其在群里回复并给 `Beta` 发私信的消息。
4. 观察到 `Alpha` 在群里真实回复 `M311-ACK ... I don’t have a send_message tool available here ...`。
5. 切到 `Settings -> Agents -> Alpha`，在 `Tools` 中勾选 `send_message`，点击 `Save Agent`。
6. 回到 `Chat`，新建 fresh 群聊 `M311 Fresh Group`，再次通过 mention picker 点选 `Alpha`，发送要求其回复 `M311-FRESH-ACK` 并向 `Beta` 发送 `M311-FRESH-DM` 的消息。
7. 在 fresh 群聊里观察 `Alpha` 回复。
8. 点击左侧 `Direct agent chat`，检查 agent-to-agent 会话详情中的实际私信内容。

## Observed Results

- 初次群聊 mention：`Alpha` 确实在群里回复，说明“浏览器里 @agent 回复”成立。
- 初次尝试 DM：群里回复明确表示当前会话没有 `send_message` 工具。
- 打开 `send_message` 后的 fresh 群聊：`Alpha` 在群里回复 `M311-FRESH-ACK ... timed out twice ...`。
- 同一轮 fresh 验证里，左侧出现可点击的 `Direct agent chat`；点击后，前端详情页真实显示 `M311-FRESH-DM`，而且出现了两条重复消息。
- 因此，“agent-to-agent 私信真的送达”和“前端看得到 agent-to-agent 聊天”两项都被真实浏览器确认；但当前产品反馈与实际投递结果不一致。

## Passes

- 真实浏览器入口可用：打开 `http://127.0.0.1:8011/` 会进入 Web IM，而不是要求手工拼 dev server 地址。
- 群聊 mention 路径可用：在群聊 composer 输入 `@` 后，真实弹出 `Alpha` / `Beta` mention 候选，并可点击 `Alpha`。
- 旅程 1 已通过：在 `Alpha + Beta` 群聊里发送 `@Alpha ...` 后，浏览器中实际出现 `Alpha` 回复：`M311-ACK ...`。证据：`.playwright-cli/page-2026-03-24T16-58-34-367Z.png`
- `send_message` 可通过真实前端配置打开：`Settings -> Agents -> Alpha -> Tools -> send_message -> Save Agent`。证据：`.playwright-cli/page-2026-03-24T17-00-44-085Z.png`
- 旅程 2 的“送达 + 前端可见”已被真实浏览器确认：在 `M311 Fresh Group` 里触发 `Alpha` 发私信后，左侧出现并可点击 `Direct agent chat`，打开后前端能看到 `M311-FRESH-DM`。证据：`.playwright-cli/page-2026-03-24T17-04-50-137Z.png`

## Issues

### Issue 1 — send_message 反馈与实际送达不一致且发生重复投递
- Severity: major
- Type: reliability
- User Impact: 用户在群里会被明确告知“超时两次、请重试”，但实际私信已经送达，而且被重复送达两次；这会诱导重复操作并制造重复 agent-to-agent 消息。
- Reproduction: 1) 浏览器进入 `Settings -> Agents -> Alpha`；2) 勾选 `send_message` 并保存；3) 浏览器创建 fresh 群聊 `M311 Fresh Group`；4) 在群里通过 mention picker 点选 `Alpha`，发送 `@Alpha please reply ... send_message to send Beta exactly "M311-FRESH-DM"`；5) 观察群内回复，再点击左侧 `Direct agent chat`。
- Expected: 群里反馈应与真实投递结果一致；若送达成功，应报告成功且只出现一条 `M311-FRESH-DM`。
- Actual: 群里 `Alpha` 回复 `M311-FRESH-ACK send_message to Beta timed out twice; please retry or confirm delivery.`，但 `Direct agent chat` 中实际出现了两条已送达的 `M311-FRESH-DM`。
- Evidence: `.playwright-cli/page-2026-03-24T17-04-22-305Z.png`; `.playwright-cli/page-2026-03-24T17-04-50-137Z.png`
- Basis: 本次验收目标第 2 条要求验证“私信是否真的送达 + 前端里是否看得到 agent-to-agent 聊天”；产品判断上，错误失败反馈与重复投递不可接受。

### Issue 2 — agent-to-agent 线程列表预览未刷新到最新私信
- Severity: minor
- Type: feedback
- User Impact: 即使 agent-to-agent 私信已经在会话详情里可见，用户从左侧列表仍看到旧预览，降低发现性并削弱对“刚刚已经送达”的信心。
- Reproduction: 完成上面的 fresh 群聊触发后，点击左侧 `Direct agent chat`；同时观察左侧该线程的 preview 文案。
- Expected: 左侧线程 preview 应更新到最新私信（如 `M311-FRESH-DM`），或至少同步到当前最后一条消息。
- Actual: 左侧 `Direct agent chat` 仍显示旧预览 `M310 ping Beta`，与详情页中的 `M311-FRESH-DM` 不一致。
- Evidence: `.playwright-cli/page-2026-03-24T17-04-49-034Z.yml`; `.playwright-cli/page-2026-03-24T17-04-50-137Z.png`
- Basis: `docs/spec-implementation-conflicts.md` 已把 agent-agent direct 定义为用户可发现、可查看；列表预览不同步会削弱 discoverability。

## Retest Focus

- 在 fresh 群聊里再次验证 `@Alpha` -> 群内回复 -> `send_message(to=Beta)`，并确保：
- 群内状态反馈与真实投递结果一致，不再出现“超时但其实已送达”
- agent-to-agent direct chat 只产生一条目标私信，不重复
- 左侧线程列表 preview 与 direct chat 详情页中的最新消息一致
