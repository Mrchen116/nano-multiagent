# refactor-521 — 验收报告

> 对齐: `motivation.md` / `design.md`

> Validation snapshot: `48d19d8a7809805efcb7631e75079cc09daf2eab → 2e7134497f4841c06cd66ce30388bd109ade3c98`
>
> Review round: 1 · Revalidation mode: full

## Verdict

pass

本轮在 unit 隔离栈独立重走了全部 4 个 Scenario。Web direct、群聊门控/显式提及/协议静默/裸 `/new`、relay 重放，以及专用 Feishu profile 的真实外部私聊与 IM shadow 同步均保持既有用户结果；未发现阻塞或非阻塞产品问题。

## 用户旅程体验

1. **Web direct 回原会话**
   - 以隔离用户 `nano` 登录真实 Web IM，打开 direct conversation `b7c4359455b74f168e04d22f78b71013`（`R521 Direct`）。
   - 发送 `请只回复这段验收码：R521-DIRECT-1786337371`。
   - 页面同一会话先显示用户消息，再显示 `e2e` 的流式终态回复 `R521-DIRECT-1786337371`；回复耗时显示 `4.0s`，未跳转或新建可见会话。

2. **Web group 门控、静默与全群重置**
   - 在真实三方 group conversation `90100c924e0448bf9adb27b3a79b4efd`（Test User + `e2e` + `e2e-peer`）发送未提及消息 `R521-GROUP-BG-1786337452`，等待后时间线只有该用户消息，没有 Agent 气泡。
   - 随后发送 `@e2e ... R521-GROUP-MENTION-1786337476`，同一群只出现 `e2e` 的一条同码回复。
   - 发送要求 Agent 严格只输出 `NO_REPLY` 的消息 `R521-NOREPLY-1786337536`；run 收口后 provisional 气泡消失，Agent 消息数回到 1，时间线没有 `NO_REPLY` 字面量或多余摘要。
   - 发送精确裸 `/new`；同一群立即分别出现 `e2e`、`e2e-peer` 各一条 `已开始新会话。`，没有缺失或额外确认。

3. **Web relay 同 key 重放**
   - 在上述 group 以 `Idempotency-Key: R521-REPLAY-1786337613` 发送 `@e2e 请只回复这段重放码：R521-REPLAY-1786337613`，等首轮完成后用同 key、同 payload 再投一次。
   - 两次 POST 均返回同一用户 message id `ba35420bfe5a471089f6903795c3a4fb`；最终时间线只有 1 条用户消息和 1 条 `e2e` 回复 `15142630b258402996ad156592d8ac4b`，回复耗时 `3009ms`。
   - Web 页面中同一群只看到一组该重放码，未出现重复用户消息、重复 Agent 回复或永久 running 占位。

4. **真实 Feishu external → 原 chat + IM shadow**
   - `e2e-up.sh --feishu` 通过固定 App/Bot identity 与 listener lock，`e2e-feishu-probe.py` 输出 `Feishu E2E ingress probe passed (profile=e2e-feishu-testagent)`。
   - 使用该非 default profile 的测试用户身份，在固定测试 Bot 的真实私聊发送 `请只回复这段验收码：R521-FEISHU-1786337737`；发送 message id 为 `om_x100b68a1d27fe0a0c073b1db9521103`。
   - 原 Feishu chat `oc_3b9bdbedb101b1b9ccf6353ac68c4777` 随后收到测试 Bot 的一条同码回复，message id 为 `om_x100b68a1d2342900dd35481da82dfb6`；匹配该 nonce 的可见消息恰为用户、Bot 各一条。
   - IM 同时生成 direct shadow `6dc8e7fcba0748149ef72053453d5126`（`e2e · feishu`）。公开时间线先出现用户消息 `fd79ffee33ad4a5093b9387a7ddac002`，再出现 Agent 终态 `5e6be695131d4e979d995b5e24aef5fe`；Agent 项含 1 段 thinking、`elapsed_ms=1003` 和稳定 kernel message id。Web conversation 列表同步显示该 shadow、同码 preview 与 2 条 unread。

Web UI 由主 checkout 的依赖启动；`2e713449...` 与所用主 checkout `691e3b5c...` 在 `src/IM/frontend/` 下无文件差异。所有 IM/Gateway 数据、端口、workspace、node identity 与 Feishu credentials 均来自 unit 隔离运行，不使用个人 Gateway 或生产 Bot。

## Reference Artifacts Reviewed

N/A。该重构没有原型、设计稿或视觉一致性契约。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| — | — | 未发现产品问题 | 无 |

## 验收标准覆盖

### Requirement: 内置 Web IM 消息路由与回复保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 直聊消息仍回复原会话 | `motivation.md` Requirement A / Scenario 1；`docs/specs/gateway/routing-delivery.md` | 真实 Web IM direct 发送唯一验收码，观察同一会话的用户消息、流式过程与终态 | conversation `b7c435...`；user `9d54e6...`；Agent `1e9622...`；页面同一 region 显示两条同码消息 | pass | 与变更前既有 direct 路由/回复行为一致 |
| 群聊触发与静默保持一致 | `motivation.md` Requirement A / Scenario 2；`docs/specs/gateway/routing-delivery.md` | 同一真实多 Agent 群依次走未提及、显式 `@e2e`、协议 `NO_REPLY`、裸 `/new` | group `90100c...`；背景码无 Agent 回复；mention 仅 `e2e` 回复；`NO_REPLY` 无残留；`/new` 由 `e2e`、`e2e-peer` 各确认一次 | pass | 覆盖 group gate、上下文触发、协议静默与全群重置；无额外/缺失可见消息 |

### Requirement: 外部 channel 与 shadow 投递保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 外部消息仍回到原通道原目标 | `motivation.md` Requirement B / Scenario 3；`docs/specs/gateway/external-channels.md` | 专用 Feishu profile 的测试用户向固定测试 Bot 发真实私聊；分别观察原 Feishu chat 与 IM shadow | Feishu chat `oc_3b9...` 中 user `om_x100...1103` → Bot `om_x100...dfb6`；shadow `6dc8e7...` 中 user `fd79ff...` → Agent `5e6be6...`，thinking=1、elapsed=1003ms | pass | 原 chat 与 shadow 都只出现一次同码结果，顺序和终态过程事实一致 |
| 中继断线与重放不产生重复可见结果 | `motivation.md` Requirement B / Scenario 4；`docs/specs/im/gateway-relay.md` | 按 Scenario 的二选一路径，以相同 relay idempotency key 对同一 Web group payload 重放并观察最终页面 | key `R521-REPLAY-1786337613`；两次响应同 user id `ba3542...`；时间线 user=1、Agent=1，Agent `151426...` completed | pass | 采用“同一 relay 消息重放”路径；没有重复或永久缺失终态 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**；没有跨包职责或依赖方向增量。
- [x] `docs/specs/<包>/`（长青行为契约层）：**无需更新**；本 unit 明确保持 Gateway routing/external 与 IM relay current behavior，不引入行为增量。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；没有开发或协作约束变化。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**；没有文档体系变更。

无需更新的上层文档没有 PR/commit 链接。

---

# Round 2 — 2026-08-10

> Validation snapshot: `b5eee0bbeb3269c53a50d223925a79bbadbc8471 → 329aa76d3826d175631f2cddcc117c87ce438693`
>
> Production fix delta: `b5eee0bbeb3269c53a50d223925a79bbadbc8471...dda6e8aaff6280f59d7c64c347e3eb2392436dd7`
>
> Review round: 2 · Revalidation mode: targeted

## Verdict

pass

本轮定向重验 code-review P1 的真实产品回归面：同一个专用 Feishu 私聊在首次建立 shadow 后再次入站刷新 binding，随后分别触发后台 agent 文本和附件预处理失败。两类可见结果都在原 Feishu chat 各投递一次，并在同一个内部 IM shadow conversation 各持久一次；未见目标丢失、重复或改投其他会话。

## 定向用户旅程

1. **真实 Feishu binding 建立与二次入站刷新**
   - 隔离栈以 `e2e-up.sh --feishu` 启动，使用非 default 专用 profile `e2e-feishu-testagent` 的测试用户身份，向固定测试 Bot 的真实私聊发送 `R521-R2-BIND-1786343065`。原 chat `oc_3b9bdbedb101b1b9ccf6353ac68c4777` 中用户消息 `om_x100b68a2a7674cb0dd152fa01b87220` 收到 Bot 回复 `om_x100b68a2a4cf28a4dda708e6472062e`。
   - 在同一 chat 立即再发 `R521-R2-REFRESH-1786343065`，用户消息 `om_x100b68a2a48928b4c4f7428ae33391d` 收到 Bot 回复 `om_x100b68a2a44840a0c42c224a6f4d05b`。内部 IM 仍只有一个 direct shadow `676acaf999b6493dbceeee040f3bca91`（`e2e · feishu`），其中绑定与刷新的用户/回复分别为 `7eaede6eae2b45be923cbf37579d2dac` / `d915129be840469bb5111a18e275fbee` 和 `ce744c5d4b9042d882c8e11a90823216` / `a630cd9597a443aea13a5d9b90cc803f`。

2. **后台 agent 文本回到原 Feishu chat 与同一 shadow**
   - 在上述已刷新的真实 Feishu chat 要求 Agent 用 `run_in_background=true` 执行 `sleep 3 && echo R521-R2-BG-1786343131`。原 chat 先收到一条「已启动」（`om_x100b68a2a0ae38b4c1cc1091784eddf`），后只收到一条后台结果 `R521-R2-BG-1786343131`（`om_x100b68a2a067f0bcc42228e7336d2c6`）。
   - 同一 shadow `676acaf999b6493dbceeee040f3bca91` 中，本次前台「已启动」为 `2cfeb879bf644b6a91dadb1a44118e96`，后台结果只有一条 `a635aa66773c4cf68b39b7cdfde0cf5f`。
   - 为在真实 Web IM 列表中直接观察实时回传，同一 chat 再跑一次 `R521-R2-BGSHADOW-1786343488`：Feishu Bot 结果只有 `om_x100b68a34a2fd4b0c3810bab56ca3c3` 一条，shadow 结果只有 `745545698c15443ea3ff54319e20c551` 一条。Web 不刷新即把同一 `e2e · feishu` 的 preview 更新为该 nonce，unread 从 5 增到 7，对应且仅对应「已启动」和后台结果两条新 Agent 消息。

3. **附件预处理失败回到原 Feishu chat 与同一 shadow**
   - 使用同一测试用户和 chat 发送真实 Feishu 文件 `R521-R2-UNSUPPORTED-1786343214.unsupported`（`om_x100b68a2bdc6c4acc493ccd34a8226e`）。Gateway 在提交 Agent run 前拒绝不支持类型，原 chat 只收到一条友好失败 `om_x100b68a2bd47acb4c4c5cc093a79aa4`：「收到文件信息，但该文件类型 `.unsupported` 不受支持…」。
   - 真实 Web IM 在唯一 `e2e · feishu` 会话中显示同一失败 preview 与 5 unread。该 shadow 的公开消息时间线中，文件入站为 `03203fb733f44ac0a63b6858ff0b1523`，失败输出只有 `04ea1a2d84ff415b9998cf444c5d7338` 一条。

## 证据边界

- **直接产品证据**：所有入站都由专用 Feishu profile 的真实测试用户发往真实测试 Bot；原 Feishu chat 中直接观察到绑定、刷新、后台回传与预处理失败；真实 Web IM 中直接观察到唯一 shadow 的失败 preview，以及后台结果在线实时替换 preview 并增加 unread。
- **辅助精确计数证据**：以同一隔离用户调用 IM 对外 OpenAPI 读取上述真实会话，证明 `676acaf999b6493dbceeee040f3bca91` 是唯一 `e2e · feishu` shadow，12 条完整时间线中两次后台结果与一次预处理失败均各只有一条 Agent 消息。这仅用于对 Web 可见结果做 id/message-level 计数，没有手工构造 `ReplyContext`，也没有用 unit test 代替用户旅程。

Web UI 由主 checkout 的现有依赖启动；`329aa76d...` 与所用主 checkout `6a5860b4...` 在 `src/IM/frontend/` 下无文件差异。所有 IM/Gateway 数据、端口、workspace、node identity 和 Feishu credentials 均来自 unit 隔离运行；本轮启动的 IM、Gateway 和 Vite 均已停止，监听端口已释放。

## 继承覆盖

Round 1 已通过的 4/4 前台场景（Web direct、Web group 门控/静默/裸 `/new`、Web relay 重放、真实 Feishu 前台回复 + shadow）本轮按 fast-lane 继承，不重跑。本轮仅重验 `b5eee0bb...dda6e8aaf` 针对 durable external shadow target 的修复面；未观察到需要升级 full revalidation 的影响扩大。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| — | — | 未发现产品问题 | 无 |

## 定向验收覆盖

| 目标 | 验证方式 | 结果 |
|---|---|---|
| 二次 external inbound 不丢失 anchored shadow target | 同一 Feishu chat 先发 `BIND` 再发 `REFRESH`，两轮均回原 chat，内部仍只有 shadow `676acaf9...` | pass |
| 后台 agent 文本同时到达 external + shadow | 真实 Feishu `run_in_background` 两次；每个 nonce 在 Feishu 和同一 shadow 都各有且仅有一条后台结果 | pass |
| 预处理失败同时到达 external + shadow | 真实 Feishu `.unsupported` 文件；原 chat 与同一 shadow 各一条同文失败 | pass |

## 上层文档同步

- [x] `SPEC.md`：**无需更新**；本轮是既有 external/shadow 行为的定向回归。
- [x] `docs/specs/<包>/`：**无需更新**；`docs/specs/gateway/external-channels.md` 已是后台文本与预处理失败的 canonical contract。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；没有开发或协作约束变化。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**；没有文档体系变更。

无需更新的上层文档没有 PR/commit 链接。
