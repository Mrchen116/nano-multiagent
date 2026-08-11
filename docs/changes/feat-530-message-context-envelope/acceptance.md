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
