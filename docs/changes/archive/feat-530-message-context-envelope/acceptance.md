# feat-530 — 验收报告

> 对齐: `spec.md` 的验收标准

> Validation snapshot: `c40a9aa80f3f9107327217b868f11ec664d34bf9 → 6f848d2798f538cf9bdc499b67b19cfedfbbf2fb`

## Verdict

`fail`

- Highest Required Action: `fix-implementation`
- Review round: `1`
- 实际的 Web IM / 飞书 envelope 主路径、跨入口、离线 catch-up、Gateway-only 重启、旧会话升级和 Coding CLI 非回归均通过。
- 但真实飞书群聊的 `/skill:doc ...` 没有再按既有 Kernel 契约改写。provider 请求仍收到 `[Feishu ...] [你] /skill:doc ...`，用户看似得到普通回复，实际却没有确定性进入显式 skill 路径。这是本变更新增 envelope 与相邻既有用户能力组合时出现的 major suspected regression，Round 1 默认严格验收不能通过。

## 用户旅程体验

### 1. Web IM 私聊、原文展示与复制

在隔离 E2E Web IM 中登录测试用户，进入 `e2e` Agent 私聊并发送：

```text
feat-530-review-web-1616。请只根据你收到的当前消息上下文回答：source=<实际来源平台>; local_time=<当前消息的日期时间和时区>; direct_or_group_word_seen=<yes/no>。
```

Agent 回答 `source=Web IM; local_time=2026-08-11 16:14:00 CST (Asia/Shanghai, UTC+8); direct_or_group_word_seen=no`。同一会话再发送一个正文自身以 `[Feishu Mon 2026-08-10 09:17 CST]` 开头的消息，页面展示和实际“Copy message”剪贴板结果都逐字保留用户正文，没有显示派生的 Web IM 时间/channel prefix，也没有把用户自带的 header-shaped 正文吞掉。

运行记录 `.gateway-workspace/e2e/.nanoassistant/sessions/sess_7e672e954362b0ed.jsonl` 显示模型侧两条消息分别带 `[Web IM Tue 2026-08-11 16:14 CST]` 和 `[Web IM Tue 2026-08-11 16:15 CST]`；对应可读历史 `.gateway-workspace/e2e/.nanoassistant/chat_history/sess_7e672e954362b0ed.jsonl` 只保留两条原始正文。provider system prompt 只有 `Time zone: Asia/Shanghai`，没有 PA 会话创建时的 `Current date and time:`。

### 2. 真实飞书私聊、群聊与影子会话

通过测试 App 的真实飞书 direct 发送 `feat-530-review-dm-1786436267`，Agent 回答来源为 `Feishu`、时间为 `Tue 2026-08-11 16:17 CST`。飞书可见正文不含派生 prefix。

在专用测试群发送并 @Bot 的 `feat-530-review-group-1786436293` 后，Agent 回答 `source=Feishu; local_time=Tue 2026-08-11 16:18 CST; sender=你; internal_id_seen=no`。模型侧消息是单条 `[Feishu ...] [你] <正文>`，继续保留既有 sender 语义，没有新增 `Group`、Bot ID、chat ID、host 或 IP。

随后从 Web IM 打开同一飞书 direct 的影子会话，发送 `feat-530-review-shadow-web-1619`。Agent 依据同一 Kernel 会话回答：

```text
previous_source=Feishu; previous_time=Tue 2026-08-11 16:17 CST;
current_source=Web IM; current_time=Tue 2026-08-11 16:19 CST
```

证据位于 `.gateway-workspace/e2e/.nanoassistant/sessions/sess_0d8588ad8a996c21.jsonl`；飞书和 Web IM 两条消息在同一个 session 中分别带各自真实入口，影子会话页面展示的飞书原消息仍是无 prefix 的原文。

### 3. Active steer 与时间推进

在上述影子会话启动一个会等待 15 秒的工具调用，运行期间追加 `feat-530-review-active-steer-1620`。最终 Agent 回答 `steer_source=Web IM; steer_time=Tue 2026-08-11 16:20 CST`。provider 最终请求 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-11_16-17-49_422_sess_0d8588ad8a996c21/2026-08-11_16-20-20_055-req-anthropic_messages.json` 中，追加内容使用和 normal submit 相同的 `[Web IM Tue 2026-08-11 16:20 CST]` envelope；本旅程没有改变 active steer 既有的独立持久化语义。

### 4. 离线 catch-up、重启与旧会话升级

先停 Gateway，在飞书群于 `16:21:36` 发送未 @Bot 的背景消息 `feat-530-review-catchup-1786436495`；两分钟后恢复 Gateway，并于 `16:23:27` 发送带 @Bot 的触发消息。Agent 回答背景时间为 `16:21`、当前消息为 `16:23`，而不是把 catch-up 消息伪装成恢复/触发时刻。`.gateway-workspace/e2e/.nanoassistant/sessions/sess_261a3c3bca818ddd.jsonl` 的组合用户 turn 同样保留两条各自的 `Feishu` 时间和 sender。

随后只重启 Gateway、保留同一 IM/config/data/session binding；在同一个 `sess_23e6d71fa05a1582` 中继续发言，Agent 不调用工具即可回答重启前一条消息是 `Feishu 16:23`、当前消息是 `Feishu 16:26`。

为真实验证升级兼容，临时以 `origin/main@c40a9aa80` 启动旧 Gateway，在同一会话写入原始消息 `feat-530-review-oldraw-1786436931`；再切回本 unit Gateway 继续发送 `feat-530-review-mixed-1786436989`。同一 transcript 的旧消息保持无 prefix，新消息得到 `[Feishu Tue 2026-08-11 16:29 CST]`；Agent 回答 `old_source=unknown; old_time=unknown; current_source=Feishu; current_time=Tue 2026-08-11 16:29 CST`。provider 请求 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-11_16-23-57_625_sess_23e6d71fa05a1582/2026-08-11_16-29-52_198-req-anthropic_messages.json` 也同时包含未猜测的旧 raw 消息和带可靠 envelope 的新消息。

### 5. Coding CLI 非回归

从临时工作目录运行真实产品入口：

```text
PYTHONPATH=<unit>/src <repo>/.venv/bin/python -m coding_cli.main \
  --text "feat-530-review-cli-1635。请只回答 cli_context_received=yes。"
```

CLI session `sess_da3b8180be9a5068` 返回 `cli_context_received=yes`。provider 请求 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-11_16-32-26_399_sess_da3b8180be9a5068/2026-08-11_16-32-26_399-req-anthropic_messages.json` 中 user content 仍是逐字原文，没有 PA envelope；system prompt 仍有 `Current date and time: 2026-08-11T08:32:26.394243+00:00`，证明 CLI 沿用原行为。

### 6. 真实飞书群聊 `/skill:*` 相邻能力回归

在专用飞书群以真实用户身份发送并 @Bot：

```text
/skill:doc feat-530-review-group-skill-1786437213。请只回答 skill_journey_received=yes。 @测试agent
```

飞书收到两条重复的 `skill_journey_received=yes`（重复出站是已知 #272，见 Side Findings）。更关键的是，该回复不能证明 skill 被触发：provider 请求 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-11_16-23-30_147_sess_261a3c3bca818ddd/2026-08-11_16-33-35_978-req-anthropic_messages.json` 的实际 user content 仍为：

```text
[Feishu Tue 2026-08-11 16:33 CST] [你] /skill:doc feat-530-review-group-skill-1786437213。请只回答 skill_journey_received=yes。 @测试agent
```

它没有变成既有契约要求的 `Use the "doc" skill for this request.`。模型 reasoning 也把原始 slash 文本当普通指令理解并直接服从“只回答”，说明这是 silent failure，而不是展示层差异。

## Reference Artifacts Reviewed

N/A。spec/design 没有引用需要 must-match 的前端原型、设计稿或 reference screenshot。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| R1-I1 | major | 真实飞书群聊中，新增 envelope 与既有 sender 形成两个连续 `[...]` 后，`/skill:doc ...` 没有按既有契约改写；普通 LLM 回复掩盖了 skill 未确定性触发 | `fix-implementation`，本 unit 修复后重验真实群聊 `/skill:*`，并确认 provider user content 已改写 |

### R1-I1 — 飞书群聊显式 skill 命令静默失效

- Severity: `major`
- Regression Relation: `suspected-regression`
- Recommended Action: `fix-implementation`
- Action Rationale: 本 unit 为真人群聊消息新增模型侧 envelope；真实组合入口已经观察到 `/skill:doc` 不再满足 current Kernel 的显式 skill 改写契约。该 suspected regression 直接影响本 unit 的可接受性，Round 1 默认归入实现修复，不做源码归因。
- User impact: 群聊用户以为自己显式选择了 skill，Agent 也可能给出看似合理的普通回复，但运行时没有确定性进入所选 skill，结果与审计都不可信。
- Reproduction: 飞书测试群发送 `/skill:doc feat-530-review-group-skill-1786437213...` 并 @Bot；检查上述 provider request，实际 user content 仍含原始 `/skill:doc`。
- Expected: 既有 `docs/specs/kernel/skills.md` 要求命令前一个 sender 标注时仍改写为 `[sender] Use the "doc" skill for this request.`；新增 channel/time envelope 后，该用户能力仍应成立。

## Side Findings

- 飞书真实 direct/group 旅程中，单次 Kernel/provider run 会出现两条相同 Bot 出站回复。该问题已由并行工作流登记为 #272，不属于本 unit envelope 行为，本轮不重复建 issue，也不计入 R1-I1。
- Runbook 使用的 `$IM_URL/health` 在本轮隔离 IM 返回 404；同一实例的 `/openapi.json` 可访问，launcher readiness 与所有真实旅程正常。建议后续单独校正文档探针。
- Web IM 侧栏搜索是 conversation 筛选，不是 message-body search，产品当前没有可独立操作的正文搜索入口。本轮通过两端原文展示/复制及可读历史原文不含派生 prefix，验证 envelope 没有污染正文；没有把侧栏搜索的 `No conversations` 误判成 message-body 搜索失败。

## 验收标准覆盖

### Requirement: PA Agent 能理解每条真人消息发生的时间 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长会话跨越一天中的多个时段 | `spec.md` | 同一 PA session 先后经 Feishu 16:17、Web IM 16:19、active steer 16:20 发言，并追问前后时间；同时检查 PA system prompt 没有 stale current datetime | `sess_0d8588ad8a996c21.jsonl`；16:20 provider request | pass | 验收窗口压缩到数分钟，但逐消息时间推进、先后判断和不再固定会话创建时间三项用户结果均被直接验证。 |
| channel 提供消息发生时间 | `spec.md` | Gateway 离线时发送群背景消息，恢复后以新消息触发 catch-up，追问两条发生时间 | `sess_261a3c3bca818ddd.jsonl`：背景 `16:21`、触发 `16:23` | pass | 采用飞书 create time，而非 catch-up/触发时间。 |
| channel 没有提供消息发生时间 | `spec.md` | 从 Web IM 浏览器提交不携带用户指定来源时间的真人消息，询问当前消息本地时间 | `sess_7e672e954362b0ed.jsonl`；Agent 回答 `16:14 CST` | pass | Web IM 用户入口仍获得 Gateway 时间位置。 |

### Requirement: PA Agent 能识别每条真人消息的实际入口 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一影子会话从飞书继续到 Web IM | `spec.md` | 真实飞书 direct 发言后，在 Web IM 同一影子会话继续发言并追问两条入口 | `sess_0d8588ad8a996c21.jsonl`；Agent 回答 `Feishu → Web IM` | pass | 同一 session 逐消息区分实际入口。 |
| 群聊继续保留既有参与者语义 | `spec.md` | 真实飞书群 @Bot；另走离线 group buffer catch-up | `sess_261a3c3bca818ddd.jsonl`；live group 回复 `sender=你; internal_id_seen=no` | pass | 模型侧保留 sender，不新增 `Group` 或路由内部字段。 |
| 私聊只表达有价值的来源平台 | `spec.md` | Web IM direct 与飞书 direct 分别询问来源，并检查 provider user content | `sess_7e672e954362b0ed.jsonl`、`sess_0d8588ad8a996c21.jsonl` | pass | 两条均有平台名；实际 envelope 没有 `Direct`。 |

### Requirement: 上下文 envelope 不改变用户消息原文 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在原入口查看和复制消息 | `spec.md` | Web IM 实际查看并点击两条用户消息的 Copy；飞书 history 读取真实用户消息 | 浏览器剪贴板逐字等于 raw body；飞书 message IDs `om_x100b6899e472ccb0c3a40f429a17ffe`、`om_x100b6899e2a9a0a0ddc4965381ea1fb` | pass | 额外用用户自带 `[Feishu ...]` header-shaped 正文确认不会误删正文。 |
| 外部消息同步到影子会话 | `spec.md` | 飞书 direct 后从 Web IM 打开 shadow，比较两端正文和 readable history | Web IM shadow 实际页面；`.gateway-workspace/e2e/.nanoassistant/chat_history/sess_0d8588ad8a996c21.jsonl` | pass | 两端正文无派生 prefix；当前产品没有 message-body search UI，raw persistence 证明正文无需携带 prefix。 |

### Requirement: 新消息的时间与入口可稳定延续 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 重启后继续既有会话 | `spec.md` | 仅重启 Gateway，保留 IM/config/data/session binding；同一飞书 direct session 继续发言且禁用工具检索 | `sess_23e6d71fa05a1582.jsonl` lines 14-15：重启前 `16:23`、重启后 `16:26` | pass | 同一 Kernel session 恢复，不是 full-stack 新会话。 |
| 功能启用前的旧消息缺少可靠上下文 | `spec.md` | 以 `origin/main@c40a9aa80` 真实写入 raw 消息，再升级到本 unit 并继续同一 session | `sess_23e6d71fa05a1582.jsonl` lines 17,20-21；16:29 provider request | pass | 旧消息保持 raw/unknown，新消息才获得 Feishu 时间与入口。 |

### Requirement: 非 PA 入口保持既有行为 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户继续使用 Coding CLI | `spec.md` | 临时 cwd 运行真实 `coding_cli.main --text` 并检查 provider 请求 | `sess_da3b8180be9a5068`；16:32 provider request | pass | user content 无 PA envelope；system 仍有 CLI `Current date and time:`。 |
| PA 产生非真人入站消息 | `spec.md` | N/A | N/A | not-applicable | 疑似实现层 Scenario，应属 `design.md`；heartbeat/cron/subagent/internal 没有统一真人可操作入口，reviewer 不伪造内部调用。 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 没有改变跨包依赖或部署顶点。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要更新；修复 R1-I1 后，由 orchestrator 将最终 PA envelope/system prompt 行为归并到 `docs/specs/gateway/`、`docs/specs/kernel/` 的 canonical，并确保 `docs/specs/kernel/skills.md` 的显式 skill 契约仍成立。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；没有新增 agent 工作约定。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；没有改变文档体系。

需要更新项将在本 unit 最终实现和复验收敛后，由 orchestrator 收尾归并；本轮 reviewer 不修改长青 spec。

---

# Round 2 — 2026-08-11

> Validation snapshot: `c40a9aa80f3f9107327217b868f11ec664d34bf9 → 255b41d0499336bd27136a0c523a3c45bef2bede`

> Revalidation mode: targeted Fast-lane；继承 Round 1 覆盖表，仅复验 `R1-I1` 真实飞书群聊 `/skill:*` 及同一入口的可见相邻副作用。

## Verdict

`pass`

- Highest Required Action: `pass`
- Review round: `2`
- `R1-I1` 已关闭。真实飞书群聊的实时单条 `/skill:doc`，以及“普通背景消息 + 当前 `/skill:doc` 触发 group buffer”两种形态，provider user content 都进入既有显式 skill 改写路径；session transcript 进一步出现真实 `skill_view(name="doc")` 调用。
- Round 1 其他 Scenario 结论全部继承；targeted 旅程没有观察到新的需修 issue。

## Targeted 用户旅程

### 1. 实时单条群聊 `/skill:doc`

在隔离的本 unit Gateway + IM + 真实飞书测试 App 中，以真实用户身份向专用群发送并 @Bot：

```text
/skill:doc feat-530-r2-single-skill-1786438436。请只回答 r2_single_skill_received=yes。 @测试agent
```

飞书用户侧保留原始 slash 正文，并收到一条 `r2_single_skill_received=yes`。provider 请求：

```text
/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-11_16-53-26_227_sess_441cd5caa06c4bca/2026-08-11_16-53-59_952-req-anthropic_messages.json
```

中的实际 user content 已变为：

```text
[Feishu Tue 2026-08-11 16:53 CST] [你] Use the "doc" skill for this request.
User input:
feat-530-r2-single-skill-1786438436。请只回答 r2_single_skill_received=yes。 @测试agent
```

`.gateway-workspace/e2e/.nanoassistant/sessions/sess_441cd5caa06c4bca.jsonl` 紧接该 user turn 记录 `skill_view`、参数 `{"name":"doc"}`。测试 workspace 本身没有名为 `doc` 的 skill，因此工具诚实返回 `Skill 'doc' not found`；这不影响本轮判定，因为被复验的契约是 slash 已确定性进入显式 skill 改写/预执行路径，而不是测试环境必须安装示例 skill。

### 2. Round 1 关键形态：普通背景消息后由 `/skill:doc` 触发 group buffer

先向同一飞书群发送一条不 @Bot 的普通背景消息：

```text
feat-530-r2-background-1786438474。这是普通群背景消息，不触发 Agent。
```

随后发送并 @Bot：

```text
/skill:doc feat-530-r2-buffer-skill-1786438488。请只回答 r2_buffer_skill_received=yes。 @测试agent
```

provider 请求：

```text
/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-11_16-53-26_227_sess_441cd5caa06c4bca/2026-08-11_16-54-52_277-req-anthropic_messages.json
```

保留第一条普通背景消息，同时把后段唯一的 slash 命令改写为：

```text
[Feishu Tue 2026-08-11 16:54 CST] [你] feat-530-r2-background-1786438474。这是普通群背景消息，不触发 Agent。
[Feishu Tue 2026-08-11 16:54 CST] [你] Use the "doc" skill for this request.
User input:
feat-530-r2-buffer-skill-1786438488。请只回答 r2_buffer_skill_received=yes。 @测试agent
```

同一 session transcript 再次记录 `skill_view(name="doc")`，飞书只收到一条 `r2_buffer_skill_received=yes`。这直接复现并关闭 Round 1 的“已有群背景 + 当前 slash 触发”失败形态，而不只是验证一个无 backlog 的理想入口。

## Reference Artifacts Reviewed

N/A，继承 Round 1。

## 问题关闭

| Issue | Round 1 | Round 2 evidence | 结论 |
|---|---|---|---|
| R1-I1 — 飞书群聊显式 skill 命令静默失效 | provider 收到 `[Feishu ...] [你] /skill:doc ...`，无改写 | 实时单条和普通背景后的 group buffer 均收到 `[Feishu ...] [你] Use the "doc" skill...`，且 transcript 有真实 `skill_view(name="doc")` | closed |

Round 2 无新增 blocking / major / minor issue。

## 验收标准覆盖更新

| Scenario / Issue | 继承或复验方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| R1-I1 真实飞书群聊 `/skill:*` 未改写 | targeted 真实飞书实时单条 + 普通背景后的 group buffer | 16:53、16:54 两份 provider request；`sess_441cd5caa06c4bca.jsonl` 的 `skill_view` turns | pass | 原始 slash 不再进入 provider；显式预执行可审计。 |
| 群聊继续保留既有参与者语义 | 在两条 targeted 请求中同时检查 envelope/sender 与正文 | provider content 保留 `[Feishu ...] [你]`，Feishu history 保留原始用户正文 | pass | 修复没有移除时间、channel 或 sender，也没有污染用户可见正文。 |
| Round 1 其余 11 个 Scenario | Fast-lane 继承 Round 1 覆盖表 | Round 1 acceptance evidence | inherited | 这些路径不在本轮 focus 中，不重复复验。 |

## Side Findings

- 第一次启动测试 Gateway 前已向群发送一条 slash，随后又发送第二条 slash 触发 catch-up；两条 slash 被合并到一个 turn 时只第一条改写。current contract 未定义一个组合 turn 中同时执行两个显式 skill 命令，本轮不把该 setup artifact 计为 R1-I1；R1-I1 的实际形态（普通背景 + 唯一 slash）已单独复现并通过。若未来产品要支持一个 group buffer 内多个显式 skill 命令，应另行明确语义。
- Round 2 两条有效 targeted 旅程各只收到一条 Bot 回复；没有再次观察到 Round 1 Side Finding 中的重复出站。该窄观察不替代 #272 的独立关闭流程。

## 上层文档同步

继承 Round 1：`SPEC.md`、`AGENTS.md` / `CLAUDE.md`、`docs/specs/CONTRIBUTING.md` 无需更新；`docs/specs/gateway/` 与 `docs/specs/kernel/` 的最终 canonical 归并仍由 orchestrator 收尾完成。

---

# Round 3 — 2026-08-12

> Validation snapshot: `5dd22bb4fa2fbcbd10d247ff3f3c77f71f598535 → d2e7032ea7b963bdf8089c93d00e12bfab6b9c95`

> Revalidation mode: full。Round 1/2 的 live evidence 只作为历史背景；以下结论全部来自本轮在 exact head `d2e7032` 上重新执行的隔离 Web IM、真实飞书和 Coding CLI 用户旅程。

## Verdict

`fail`

- Highest Required Action: `fix-implementation`
- Review round: `3`
- feat-530 的 10 个可由真实用户入口执行的 Scenario 全部通过；两个仅能靠内部故障注入/非真人入口构造的 Scenario 标为 `not-applicable`，没有用单测或源码推断代替。
- current-main 相邻控制的直接处理均通过：真实飞书群 `/skill:lark-im` 被确定性改写并调用 `skill_view`；群聊裸 `/effort max` 不触发，明确 @Bot 后只更新目标 Agent；Workflow 启用后的 `/workflows` 和 Web IM `/effort max` 均返回正确控制结果。
- 但 fresh Web IM 在 Workflow 已启用、有效模型支持 effort 时，slash 面板仍不显示 `/workflows` 或 `/effort`。命令能手工输入并执行，不等于用户可发现能力成立；这是本轮唯一 major suspected regression，默认严格验收不能通过。

## User Journeys Exercised

### 1. Web IM 与真实飞书同一影子会话

先用专用测试 App 的真实 Feishu ingress probe 产生 `nano-e2e-feishu-probe-bdf369d40577e6a0`，再在隔离 Web IM 的同一 `e2e · feishu` 影子会话发送 `feat-530-r3-web-1153`。Agent 回答：

```text
probe_source=Feishu; current_source=Web IM;
current_local_time=Wed 2026-08-12 11:52 CST;
direct_or_group_word_seen=no
```

同一 Kernel session `sess_92a8a13d460d7693` 的 transcript 依次保存 `[Feishu ... 11:51 CST]` 与 `[Web IM ... 11:52 CST]`。三次 Web IM provider 请求的 system prompt SHA-256 均为 `dd9ecf82410f163fac43b9a11d269f38ab588f496a9e1c1cb9dab061c67b0931`，只含 `Time zone: Asia/Shanghai`，没有 PA session-created current datetime。

另发送正文自身以 `[Feishu Mon 2026-08-10 09:17 CST]` 开头的 `feat-530-r3-header-exact-1156`。发送前 textbox value、页面气泡和点击 `Copy message` 后的剪贴板三者逐字一致；模型侧只在其外层增加 `[Web IM Wed 2026-08-12 11:53 CST]`。`.nanoassistant/chat_history/` 保持原始正文，不泄露派生 envelope。

### 2. 真实飞书 direct、group sender 与显式 skill

专用用户 `J` 向测试 Bot 私聊发送 `feat-530-r3-dm-1159`，Agent 回答 `source=Feishu; local_time=Wed 2026-08-12 11:54 CST; direct_word_seen=no`；飞书历史中的用户正文没有 header。

在专用群 `nano feat-530 e2e` 真实 @Bot 发送 `feat-530-r3-group-shape-1158`，Agent 逐字报告：

```text
annotations=[Feishu Wed 2026-08-12 11:55 CST] [你]
```

只出现平台/时间与既有 sender，没有 `Group` 或内部路由 ID。随后发送 `/skill:lark-im feat-530-r3-skill-valid-1201 ... @测试agent`；provider user content 被改写为：

```text
[Feishu Wed 2026-08-12 11:57 CST] [你] Use the "lark-im" skill for this request.
User input:
feat-530-r3-skill-valid-1201。请只回答 r3_skill_valid=yes。 @测试agent
```

同一 transcript 记录真实 `skill_view(name="lark-im")` 工具结果，飞书收到 `r3_skill_valid=yes`。

### 3. 群聊 `/effort` 目标门控

在同一专用群发送未 @任何 Agent 的裸 `/effort max`，等待五秒没有 Bot 回复。随后发送 `/effort max @测试agent`，只有测试 Bot 返回 `已将当前会话的推理档位设为 max。`。这证明新 envelope 没有让未明确目标的群命令变成全群控制，也没有阻止明确目标命令。

### 4. Gateway 重启、离线 group catch-up 与旧会话升级

只停止本 worktree Gateway、保留隔离 IM；在 Gateway 离线时于 `11:58:31` 向专用群发送未 @Bot 的 `feat-530-r3-offline-background-1158`。切回 exact-head Gateway 后，于 `11:59:12` 发送 @Bot 触发消息。Agent 回答背景消息为 `Feishu 11:58 CST`、当前消息为 `Feishu 11:59 CST`，而不是把背景消息标成恢复/触发时刻；同一 group session 的组合 turn 保留两条各自的 envelope 与 `[你]`。

为验证升级前旧消息，短暂以 detached `executed_base@5dd22bb4f`、同一隔离 config/data 启动旧 Gateway，在既有 direct session 写入 raw `feat-530-r3-oldraw-1201`；再切回 `d2e7032` 继续同一 session。`sess_92a8a13d460d7693` 中旧 turn 保持无 prefix，新 turn 为 `[Feishu Wed 2026-08-12 12:01 CST] feat-530-r3-after-upgrade-1202...`。Agent 回答：

```text
old_source=unknown; old_time=unknown;
current_source=Feishu; current_time=Wed 2026-08-12 12:01 CST
```

### 5. Workflow、active steer 与 Coding CLI

在 fresh 隔离 Web IM 的 Agent Config 中真实选择 `Workflow` 并保存，profile 从 v1 更新到 v2。手工发送 `/workflows` 返回 `暂无 Workflow 运行记录。`；手工发送 `/effort max` 返回 `已将当前会话的推理档位设为 max。`，说明 header 没有破坏命令处理。

同一 Web IM 会话启动 `bash sleep 12` 的长轮次，运行中追加 `feat-530-r3-active-steer-1206`。最终回复为 `long_done=yes; steer_source=Web IM; steer_time=Wed 2026-08-12 12:06 CST`；provider 请求 `2026-08-12_12-06-18_782-req-anthropic_messages.json` 中追加内容确实是 `[Web IM Wed 2026-08-12 12:06 CST] ...`。本轮只验证既有 try-steer 收到同格式 model parts，不扩张其持久化/恢复语义。

最后从临时 cwd 运行真实 `coding_cli.main --text`，session `sess_36559fd27730d5af` 返回 `cli_context_received=yes`。provider user content 为逐字原文，无 PA envelope；system prompt 仍有 `Current date and time: 2026-08-12T04:02:16.188747+00:00`。

## Reference Artifacts Reviewed

N/A。spec/design 没有引用 must-match 原型、设计稿或 reference screenshot。

## Issues

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| R3-I1 | major | Web IM 中 Agent 已保存启用 Workflow，`/workflows` 与 `/effort max` 也可手工执行，但 slash 面板没有这两个动态命令候选 | `fix-implementation`；修复后从 fresh Agent profile 重验启用 Workflow → 新聊天输入 `/` 的完整候选，并确认选择后可发送 |

### R3-I1 — 已启用 Workflow 的动态 slash 命令不可发现

- Severity: `major`
- Regression Relation: `suspected-regression`
- Recommended Action: `fix-implementation`
- Action Rationale: 本轮 current-main integration 明确要求确认相邻 `/effort` 与已启用 Workflow 的用户命令没有退化；fresh exact-head 用户旅程中，Config 已显示 `Workflow` pressed、profile v2，命令也能直接执行，但同屏 slash picker 违反 current `docs/specs/im/web-chat-ux.md` / `workflows.md` 的动态发现承诺。该异常影响本 unit 的 current-main 可接受性，默认交实现修复，不做源码归因。
- User impact: 用户启用 Workflow 后仍无法从产品内发现 `/workflows`，也看不到当前模型支持的 `/effort` levels；只有已经记住隐藏命令的用户才能手工操作。
- Reproduction:
  1. 在 fresh 隔离 Web IM 打开 `e2e` Agent Config，选择 `Workflow` 并保存；确认 profile v2 与 `Workflow` pressed。
  2. 打开该 Agent 的全新 direct chat，在 composer 输入 `/`，等待两秒。
  3. 实际候选只有 `/stop`、`/new`、`/compact` 与 skills；`/workflows`、`/effort` option count 均为 0。
  4. 直接输入并点击 Send 后，`/workflows` 与 `/effort max` 都返回正确控制结果，证明问题是用户发现面缺失，而不是命令处理失败。
- Expected: Workflow 启用时 slash picker 可发现 `/workflows`；有效模型支持 selectable reasoning 时可发现 `/effort` 与 levels。

## Side Findings

- 真实 Feishu direct/group 的普通模型回复仍会为单个 Kernel run 产生两条相同 Bot 出站；控制确认 `/effort max` 只出现一次。本轮不重复建 issue，沿用既有 #272。
- Runbook 的完整 `e2e-up.sh` 初次连接可用，但脚本退出后手工重启 Gateway 会让隔离 IM 的 channel-control SQLite reopen 报 `unable to open database file`，导致 node offline；飞书本地自治仍继续工作。为避免把 harness 生命周期问题混进 Workflow 判断，本轮另起 fresh full stack完成 Workflow UI/命令旅程。该限制没有替代或取消任何 feat-530 Scenario 的用户面实证。

## 验收标准覆盖

### Requirement: PA Agent 能理解每条真人消息发生的时间 — 组内结论:pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长会话跨越一天中的多个时段 | `spec.md` | 同一 direct session 从 Feishu 11:51、Web IM 11:52 延续到 Feishu 12:01；另在 Web IM 12:06 active steer；追问先后并核对 stable system prompt | `sess_92a8a13d460d7693.jsonl`；`sess_c4bc8914aeb58d69` provider request；stable system SHA | pass | 验收窗口压缩到跨小时边界；逐消息先后、时间推进和不再固定 session-created current datetime 均直接可见。 |
| channel 提供消息发生时间 | `spec.md` | Gateway 离线 11:58 发送群背景，11:59 恢复后触发 catch-up | `sess_69baf6f9aa5720ed.jsonl`；飞书 message `om_x100b688ab8b540a0b4c374dd349fffd` | pass | 采用 provider create time 11:58，不是 catch-up/触发时刻 11:59。 |
| channel 没有提供消息发生时间 | `spec.md` | N/A | N/A | not-applicable | 缺失 provider timestamp 只能由内部 fault injection 构造；真实 Web IM 与 Feishu 用户入口都会给出 occurrence time。reviewer 不用 mock/API 伪造真人旅程。 |

### Requirement: PA Agent 能识别每条真人消息的实际入口 — 组内结论:pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一影子会话从飞书继续到 Web IM | `spec.md` | 真实 Feishu probe 后在 Web IM 同一 shadow 继续并询问两条入口 | `sess_92a8a13d460d7693.jsonl`；浏览器回复 `Feishu → Web IM` | pass | 同一 Kernel session 逐消息区分实际入口。 |
| 群聊继续保留既有参与者语义 | `spec.md` | 真实飞书群 @Bot、显式 skill、离线 group buffer | `sess_69baf6f9aa5720ed.jsonl`；Agent 报告 `annotations=[Feishu ...] [你]` | pass | 没有新增 Group 或内部路由 ID。 |
| 私聊只表达有价值的来源平台 | `spec.md` | 真实飞书 direct 与 Web IM direct 分别询问来源 | 飞书 `om_x100b688aa65210b0b3e434bef1c9bf5`；Web session `sess_92a8a13d460d7693` | pass | 两端有平台名，均无 Direct。 |

### Requirement: 上下文 envelope 不改变用户消息原文 — 组内结论:pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在原入口查看和复制消息 | `spec.md` | Web IM 查看并点击 Copy；飞书 history 读取 direct/group 用户消息 | clipboard 逐字等于 `feat-530-r3-header-exact-1156` 原始 body；本轮飞书 message IDs | pass | 派生 header 不进入气泡/复制；用户自带合法 header 不被误删。 |
| 外部消息同步到影子会话 | `spec.md` | Feishu probe 后在 Web IM 打开 `e2e · feishu` shadow；比较两端正文与 readable history | Web IM shadow；`.nanoassistant/chat_history/sess_92a8a13d460d7693.jsonl` | pass | 两端显示 raw body；当前产品仍没有 message-body search UI，未用会话筛选冒充正文搜索。 |

### Requirement: 新消息的时间与入口可稳定延续 — 组内结论:pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 重启后继续既有会话 | `spec.md` | 只重启 exact-head Gateway；恢复同一 group session 并 catch-up 11:58 背景后继续 11:59 触发 | `sess_69baf6f9aa5720ed.jsonl` | pass | 同一 session 的 normal/group-buffer历史保持原时间与 Feishu 来源。 |
| 功能启用前的旧消息缺少可靠上下文 | `spec.md` | `executed_base@5dd22bb4f` 写入 raw old turn，升级到 exact head 后继续同一 direct session | `sess_92a8a13d460d7693.jsonl` lines 13,16-17 | pass | 旧消息 raw/unknown；新消息才有 Feishu envelope。 |

### Requirement: 非 PA 入口保持既有行为 — 组内结论:pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户继续使用 Coding CLI | `spec.md` | 临时 cwd 运行真实 `coding_cli.main --text` 并检查 provider payload | `sess_36559fd27730d5af`；12:02 provider request | pass | user content 无 PA envelope；system 保留 CLI current datetime。 |
| PA 产生非真人入站消息 | `spec.md` | N/A | N/A | not-applicable | heartbeat/cron/subagent/internal notification 没有统一真人可操作入口；这是实现来源分类 Scenario，reviewer 不伪造内部调用。 |

## Current-main Adjacent Controls

| Journey | Evidence | Result | Notes |
|---|---|---|---|
| 真实 Feishu 群 `/skill:lark-im` | provider 改写 + transcript `skill_view(name="lark-im")` + 飞书回复 | pass | 命令须位于正文开头；把真实 @mention 放在 slash 前会成为普通正文，不算有效命令。 |
| 群聊 `/effort` 仅作用明确 target | 裸 `/effort max` 无回复；`/effort max @测试agent` 单条控制确认 | pass | 未观察到 envelope 扩大控制范围。 |
| Workflow 已启用后的 `/workflows` | UI 保存 profile v2；直接命令返回“暂无 Workflow 运行记录” | pass | 命令 handler 正常。 |
| Web IM `/effort max` | 直接命令返回“已将当前会话的推理档位设为 max” | pass | 命令 handler 正常。 |
| Workflow / effort slash 发现 | fresh chat 输入 `/`；对应 option count 均为 0 | fail | R3-I1。 |
| active steer envelope | long tool run 中追加真人消息；provider 收到 `[Web IM ... 12:06 CST]` | pass | 不对既有 durability 作新断言。 |

## 上层文档同步

- [x] `SPEC.md`：无需更新；本轮未发现跨包顶点架构变化。
- [x] `docs/specs/<包>/`：feat-530 的 canonical 已反映逐消息 envelope；R3-I1 与现有 `docs/specs/im/web-chat-ux.md` / `workflows.md` 契约不一致，需要修实现而非改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；没有新增工作约定。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；没有改变文档体系。
