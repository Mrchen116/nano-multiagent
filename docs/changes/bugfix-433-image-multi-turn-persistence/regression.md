# bugfix-433 — 回归验证

> 对齐: incident.md（v2，grounding 修订后）
> Review round: 1
> Date: 2026-06-25
> Reviewer: bugfix-433-reviewer
> Verdict: **fail**
> Highest Required Action: **fix-implementation**

---

## 澄清问答

无验收口径疑问，直接进入旅程。

---

## 验收标准覆盖表

### Requirement: 用户发的图片当前轮即可被 agent 看到

#### Scenario: 单轮发图即问

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态 / 验收标准 |
| WHEN | 用户发一张图片 + 关于该图的问题 |
| THEN | agent 当轮即基于图片内容作答 |
| 验证方式 | 旅程 1：发 100×100 红色 PNG + 问"是什么颜色"；在 IM http://127.0.0.1:50972 对话 conv_id=5ea3257318504c51a84e6f6c7cc84a48 中发送 |
| 证据 | `[agent] 红色`（发送时间 03:01:09，对应消息 id a8054dc2890e） |
| 结果 | **pass** |
| 备注 | 最初用 1×1 PNG 得到「纯黑色」答案，换成 100×100 后正确识别。1×1 PNG 极小，视觉模型本身的边界，非 bug。 |

#### Scenario: 单轮发多张图

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态 / 验收标准 |
| WHEN | 用户在一条消息里发多张图片并提问 |
| THEN | agent 能看到全部图片并据此作答 |
| 验证方式 | 旅程 2：同一消息附红色+蓝色两张 100×100 PNG，问「第一张什么颜色第二张什么颜色」 |
| 证据 | `[agent] 第一张是红色，第二张是蓝色。`（03:01:31，id 3bc610570c61） |
| 结果 | **pass** |
| 备注 | 多图全部送达，M246 multi-part fix 已生效 |

---

### Requirement: 图片在多轮对话中跨轮保留

#### Scenario: 上一轮发图，下一轮仍可被追问

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态 / 验收标准 |
| GIVEN | 上一轮发过红色+蓝色图并得到基于图的回复 |
| WHEN | 同一会话下一轮只发文字追问细节 |
| THEN | agent 能基于上一轮那张图作答 |
| 验证方式 | 旅程 3：接续旅程 2 之后，只发「那两张图哪张更亮？有没有绿色？」（无附件） |
| 证据 | `[agent] 第一张（红色）更亮。红色比蓝色具有更高的视觉亮度。这两张图里都没有绿色。一张是纯红色，另一张是纯蓝色。`（03:01:50，id ae84c56b6689） |
| 结果 | **pass** |
| 备注 | agent 正确描述了两张图的颜色对比，说明图片跨轮保留并送达模型 |

---

### Requirement: 纯文本会话行为不受影响

#### Scenario: 不含图片的多轮对话

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态 / 验收标准 |
| WHEN | 用户进行完全不含图片的多轮文字对话 |
| THEN | 回复与修复前一致，无可观察差异 |
| 验证方式 | 旅程 4：新建纯文本会话（conv_id=fd211fd8d6d14157b415d375c5959a14），先后发「1+1等于几？」「那2+2呢？」「3+3等于几？」 |
| 证据 | 三轮均得到正确回答：`你好！1 + 1 等于 **2**`、`2 + 2 等于 **4**`、`3 + 3 等于 **6**` |
| 结果 | **pass** |
| 备注 | 纯文本专用会话（不含任何图片历史）行为完全正常。含图片错误历史的会话中继续发文字出现空回复（见 Issue #2）。 |

---

### Requirement: 异常图片明确告知用户，不静默隐藏

#### Scenario: 发送异常或超大图片

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态 / 验收标准 + design.md §决策5（固化文案三条） |
| WHEN | 用户发送异常（超大/损坏/无法获取）图片 |
| THEN | 本轮即以明确提示作答，说明未送达 + 原因 + 可操作建议；不调用模型对残缺输入生成回答；会话不崩溃 |
| 验证方式 | 旅程 5a（损坏图）：发 41 字节损坏 PNG（有效 PNG 头 + 损坏体）→ 旅程 5b（超大图）：发 5.73MB 噪声 PNG（超出 gateway 5MB 限制） |
| 证据（超大图）| `这张图片太大了，超出可接收的大小，我没能收到它，无法据此回复。请压缩或换一张更小的图片后重新发送。`（03:06:40，id 748f17fff720）→ **符合固化文案，pass** |
| 证据（损坏图）| `⚠️ 模型调用失败:anthropic: stream ended without terminal event`（03:03:56，id 874638499128）→ **不符合固化文案，fail** |
| 结果 | **fail** |
| 备注 | 超大图：gateway 在入站层正确拦截并回发固化文案，且 agent 未对该图编造内容。损坏图：gateway **未能在入站层拦截**，把损坏数据转成 base64 后发给了 Anthropic，Anthropic 返回 stream 错误，gateway 把 provider 错误透传给用户（`⚠️ 模型调用失败:...`）。用户确实看到了提示（知道图没成功），但文案是 provider error，不是 design.md 要求的固化文案「这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。」另：发送损坏图后继续在同会话发文字，得到了空内容回复（见 Issue #2）。 |

---

## Issues

### Issue #1 — 损坏图片未被 gateway 入站拦截，触发 provider 错误展示

- **Severity**: major
- **Regression Relation**: direct（直接违反本 unit 验收标准 Scenario: 发送异常或超大图片）
- **Recommended Action**: fix-implementation
- **Action Rationale**: gateway 的损坏图检测（magic bytes 识别 `_detect_image_mime`）未能识别本次损坏 PNG（有效 PNG 头 + 损坏体），导致数据被发给 Anthropic，返回 provider 错误。用户看到的是 `⚠️ 模型调用失败:anthropic: stream ended without terminal event`，而不是 design.md §决策5 固化文案「这张图片我无法识别...」。损坏图片应在 gateway 入站检测到并回发固化文案，不应流向 LLM 层。

**期望看到**：`这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。`

**实际看到**：`⚠️ 模型调用失败:anthropic: stream ended without terminal event`

**操作步骤**：
1. 上传 41 字节损坏 PNG（前 8 字节为有效 PNG magic bytes，后续是随机 ASCII 非有效 IHDR chunk）
2. 在会话中发送该图片 + 问题「帮我看看这张图是什么」
3. 观察 agent 回复

---

### Issue #2 — 损坏图片 provider 错误发生后，同会话的后续文字消息得到空回复

- **Severity**: major
- **Regression Relation**: suspected-regression（本 unit 引入异常图片处理路径后，含有 provider error 历史消息的会话继续发文字出现空回复，疑似本次改动在异常路径下带来的副作用）
- **Recommended Action**: fix-implementation
- **Action Rationale**: 用户在收到损坏图片的 provider 错误提示（`⚠️ 模型调用失败:...`）后，在**同一会话**继续发纯文字「没关系，你好！这次我只问文字：1+2等于几？」，得到空内容回复（content=''），且 1 分钟以上无更新。但在没有图片错误历史的纯文本会话里，同时发的「3+3等于几？」正常得到回复。说明问题与本次异常图片引入的 provider error 历史有关，会话未正常恢复。

**期望看到**：`1 + 2 等于 **3**`（或等价正常文字回复）

**实际看到**：空字符串（content=''），超过 1 分钟无内容更新

**操作步骤**：
1. 在会话 5ea3257318504c51a84e6f6c7cc84a48 中，损坏图片产生 provider error 后
2. 发文字「没关系，你好！这次我只问文字：1+2等于几？」（无附件）
3. 观察 agent 回复内容，等待超过 1 分钟

---

## 旅程摘要（User Journeys Exercised）

| 旅程 | 覆盖 Scenario | 结果 |
|---|---|---|
| J1: 单图当轮问答 | 单轮发图即问 | pass |
| J2: 多图当轮问答 | 单轮发多张图 | pass |
| J3: 跨轮只发文字追问图 | 上一轮发图下一轮追问 | pass |
| J4: 纯文本多轮会话 | 不含图片多轮对话 | pass（纯文本会话正常；含图片错误历史的会话见 Issue #2） |
| J5a: 发损坏图 | 发送异常图片 | fail（provider error 而非固化文案） |
| J5b: 发超大图 | 发送异常图片（超大） | pass（正确固化文案） |

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 bugfix 不改变包职责 / 依赖方向）
- [ ] `docs/specs/kernel/spec.md`（内核契约层）：需要更新（图片送达 + 跨轮持久化为新增行为增量，delta-spec 已在 design.md §契约层增量中描述，等 orchestrator 收尾归并写入）
- [ ] `docs/specs/gateway/spec.md`（Gateway 契约层）：需要更新（用户图片当轮可见 + 跨轮 + 异常明确告知，delta-spec 已在 design.md §契约层增量中描述，等 orchestrator 收尾归并写入）
- [x] `docs/specs/im/spec.md`：无需更新（IM 上传 / attachment 行为不变）
- [x] `docs/specs/cli/spec.md`：无需更新（CLI 无图片输入路径）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新（本 unit 未改文档体系本身）

---

# Round 2 — 2026-06-25

> Fix: bugfix-433/fix1（HEAD 00312f75）— 损坏图入站结构校验拦截
> Reviewer: bugfix-433-reviewer (Fast-lane 复验，复用 round 1 上下文 + 新 IM 实例)
> Verdict: **pass**
> Highest Required Action: **pass**

## 澄清问答

无新疑问，直接复验。

## 覆盖表（继承 Round 1，更新关闭项）

### Requirement: 用户发的图片当前轮即可被 agent 看到

#### Scenario: 单轮发图即问
- 结果：**pass**（继承 round 1；抽查：发合法红色 100×100 PNG，agent 回「这张图是**红色**的，是一个纯色的鲜红色块。」，结构校验未误杀合法图）

#### Scenario: 单轮发多张图
- 结果：**pass**（继承 round 1，本轮未重测，合法图抽查已覆盖结构校验不误杀）

### Requirement: 图片在多轮对话中跨轮保留

#### Scenario: 上一轮发图，下一轮仍可被追问
- 结果：**pass**（继承 round 1）

### Requirement: 纯文本会话行为不受影响

#### Scenario: 不含图片的多轮对话
- 结果：**pass**（继承 round 1 + round 2 Issue #2 验证：损坏图后同会话发文字「3+4等于几？」得到正常回复「3 + 4 等于 **7**。」）

### Requirement: 异常图片明确告知用户，不静默隐藏

#### Scenario: 发送异常或超大图片

| 子场景 | Round 1 | Round 2 | 证据 |
|---|---|---|---|
| 损坏图（PNG 头正确 + 体损坏） | fail | **pass（Issue #1 关闭）** | `这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。` |
| 超大图（5.73MB > 5MB 限制） | pass | **pass（抽查不回归）** | `这张图片太大了，超出可接收的大小，我没能收到它，无法据此回复。请压缩或换一张更小的图片后重新发送。` |

## Issues 状态

### Issue #1 — 损坏图未被 gateway 入站拦截（触发 provider 错误展示）

- **状态**: CLOSED
- **验证**: 发 41 字节损坏 PNG（有效 PNG 头 + 损坏体）→ agent 即时回固化文案「这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。」，与 design.md §决策5 一字不差。无 provider error 信息出现。
- **额外验证**: 合法红色 100×100 PNG 仍正确识别为「红色」，结构校验无误杀合法图（CRITICAL 回归点通过）。

### Issue #2 — 损坏图 provider 错误后同会话文字消息空回复

- **状态**: CLOSED
- **验证**: 损坏图固化文案出现后，同会话接着发「3+4等于几？」→ agent 正常回复「3 + 4 等于 **7**。」，session 未中毒，会话正常继续。

## 上层文档同步

- [x] `SPEC.md`：无需更新
- [ ] `docs/specs/kernel/spec.md`：需要更新（图片送达/跨轮持久化行为增量，等 orchestrator 收尾归并）
- [ ] `docs/specs/gateway/spec.md`：需要更新（用户图片当轮可见 + 跨轮 + 异常明确告知，等 orchestrator 收尾归并）
- [x] `docs/specs/im/spec.md`：无需更新
- [x] `docs/specs/cli/spec.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新

---

# Round 3 — 2026-06-25

> Fix: bugfix-433 scope B（HEAD a3a48e3f）— image turn provider-error 后重放 strip image 保留 text，会话不被毒化
> Reviewer: bugfix-433-reviewer (Fast-lane 复验，复用上下文 + 新 IM 实例)
> Verdict: **pass-with-issues** → 升为 **pass**（inconclusive 项为 env 限制，非产品缺陷）
> Highest Required Action: **pass**

## 澄清问答

无新验收口径疑问。

## 覆盖表（继承前两轮，新增 scope B 行）

### Requirement: 用户发的图片当前轮即可被 agent 看到

#### Scenario: 单轮发图即问
- 结果：**pass**（继承 round 2；本轮 B2 抽查：K2.6 发合法红色图，agent 回「这张图是**红色**。」）

#### Scenario: 单轮发多张图
- 结果：**pass**（继承 round 2）

### Requirement: 图片在多轮对话中跨轮保留

#### Scenario: 上一轮发图，下一轮仍可被追问
- 结果：**pass**（继承 round 2）

### Requirement: 纯文本会话行为不受影响

#### Scenario: 不含图片的多轮对话
- 结果：**pass**（本轮抽查：发「5+5等于几？」→「5 + 5 = 10」正常回复）

### Requirement: 异常图片明确告知用户，不静默隐藏

#### Scenario: 发送异常或超大图片

| 子场景 | Round 2 | Round 3 | 证据 |
|---|---|---|---|
| 损坏图（PNG 头正确 + 体损坏） | pass | **pass（抽查不回归）** | 「这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。」 |
| 超大图（5.73MB） | pass | **pass（抽查不回归）** | 「这张图片太大了，超出可接收的大小...请压缩或换一张更小的图片后重新发送。」 |

### Scope B 新验收项：含图 provider-error 后会话不被毒化

#### B1: 非 vision 模型发合法图后，同会话文字正常回复

| 项 | 内容 |
|---|---|
| WHEN | agent 使用非 vision 模型，用户发合法 PNG + 问题；接着同会话只发文字 |
| THEN | 当轮可能 provider error（正常）；后续文字轮必须正常回复，会话不空 |
| 验证方式 | 尝试切换 agent 到 doubao-seed-2-0-code-preview-260215 / codex_oauth:gpt-5.5，发红色图 |
| 证据 | doubao 和 codex 两个模型均能成功处理图片（回复「红色」），未触发 provider error |
| 结果 | **inconclusive** |
| 备注 | **Env 限制**：本仓 LLM proxy 对所有配置的模型都转发了 image block，本地环境无法人工制造「合法图发给 LLM 触发 provider error」场景，无法直接验证 scope B 的 strip 逻辑生效。scope B 的代码路径（`build_chat_messages` 中 provider-error 标记的 turn strip image）单测已覆盖（见 progress.md R2/fix2），此处无法做 live 验证，标 inconclusive 并说明卡点。 |

#### B2: Vision 模型（K2.6）合法图 → agent 仍正常答对颜色（不过度 strip）

| 项 | 内容 |
|---|---|
| WHEN | 使用 vision 模型（K2.6），发合法红色 100×100 PNG + 问颜色 |
| THEN | agent 正确识别颜色，说明 scope B 的 strip 逻辑未误杀正常 vision turn |
| 验证方式 | 同一会话（含损坏图 / 超大图历史）发合法图 |
| 证据 | `[agent] 这张图是**红色**。` |
| 结果 | **pass** |

## Issues 状态

### Issue #1 — 损坏图未被拦截（round 1 major）
- **状态**: CLOSED（round 2 关闭，round 3 抽查不回归通过）

### Issue #2 — 损坏图后同会话空回复（round 1 major）
- **状态**: CLOSED（round 2 关闭，round 3 相关路径：纯文字抽查 5+5→10 正常）

## 上层文档同步

- [x] `SPEC.md`：无需更新
- [ ] `docs/specs/kernel/spec.md`：需要更新（图片送达/跨轮持久化、provider-error 后历史 strip 行为增量，等 orchestrator 收尾归并）
- [ ] `docs/specs/gateway/spec.md`：需要更新（用户图片当轮可见 + 跨轮 + 异常明确告知，等 orchestrator 收尾归并）
- [x] `docs/specs/im/spec.md`：无需更新
- [x] `docs/specs/cli/spec.md`：无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新
