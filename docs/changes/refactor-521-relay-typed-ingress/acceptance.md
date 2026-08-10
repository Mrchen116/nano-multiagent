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
