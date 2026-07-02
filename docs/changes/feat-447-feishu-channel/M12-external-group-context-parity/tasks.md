# feat-447-M12: external-group-context-parity — Tasks

> 对齐: `../design.md` Milestone `feat-447-M12`

## 目标

飞书群聊与内部 IM 群聊的上下文语义等价：未 @ 的真实群消息同步到 IM shadow 并进入同一 `GroupContextStore`，后续 @Bot/纯 @Bot 可 drain 背景；Feishu mention 解析保留用户可见 @ 正文，`@所有人` 不触发 Bot；若平台只投递 @Bot 事件，Gateway 有明确可诊断 warning/health 证据。

## 退出标准

- [x] FeishuClient mention 解析保留用户可见 @ 正文，同时输出 `mentioned_agent_ids` / `mention_only` metadata；不把 `@<bot>` 从正文删掉。
- [x] `@所有人` / `@all` 不进入目标 agent 的 `mentioned_agent_ids`，也不触发 Bot，只作为普通群上下文可见。
- [ ] 未 @ 群消息走 `sync_only` 并复用 `GroupContextStore` external key；后续 @Bot 或纯 @Bot drain 同一 external key。代码路径和 Feishu group history catch-up 已有单测覆盖；真实 Feishu app 当前既未投递普通未 @ 群消息，也缺 bot 历史读取权限，live 阻塞见 progress.md R3。
- [ ] 纯 @Bot 不变成空文本，IM shadow sync 不再 400；纯 @ 消息可在 IM shadow group 中实时出现，并能触发 agent 使用之前未 @ 背景。纯 @ 非空和 IM shadow 已通过；“之前未 @ 背景”真实 live 因当前 app 缺 `im:message.group_msg` 阻塞，见 progress.md R3。
- [x] `@bot hi` 在 IM 和 LLM context 均保留 @ 与 hi，不能只剩 hi。
- [x] 如果飞书平台/app 只投递 @Bot 事件，有 health/warning 或可诊断证据表明权限/订阅缺失。
- [x] 单测覆盖未 @ -> 纯 @ drain、mention-only 非空化、`@bot hi` 不删 @、`@所有人` 不触发 Bot、平台普通群消息缺失的 health/warning。
- [x] 全量非 e2e 测试无回归；live-critical 证据按 progress.md 记录，若平台未投递普通群消息则明确记录权限/事件订阅不足。

## 测试策略

- 被测行为（来自退出标准）：mention 正文保真 + metadata；`@所有人` 非 Bot trigger；未 @ `sync_only` -> 纯 @ drain external buffer；mention-only 非空 IM/kernel 路径；Feishu 普通群消息投递能力 warning/health 诊断。
- 已有测试在：扩展 `tests/unit/test_feishu_client.py`、`tests/unit/test_feishu_adapter.py`、`tests/unit/test_feishu_mentions.py`、`tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py`、`tests/unit/test_feishu_config.py` / `tests/unit/test_feishu_integration.py`，分别覆盖 client parse、adapter delivery、pipeline group buffer、config/channel construction。
- 落层/目录/marker：`tests/unit/`，marker: 无；真实飞书 live-critical 是一次性验收证据，不落永久 e2e。
- 可选依赖 importorskip：已有 Feishu tests 使用 `pytest.importorskip("lark_oapi")`；新增用例复用。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 Feishu 群 live nonce、Gateway/IM 日志、IM conversation/message id、飞书 message id 或时间戳，记录在 progress.md。

## 前端/UI 状态

用户路径分类：N/A（本 milestone 不改前端 UI；IM live mention 展示复用 M11 message.created 路径）

UI 状态矩阵：N/A

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| mention-only 变空导致 IM shadow 400 | FeishuClient + adapter + pipeline 单测；live 纯 @Bot 证据 | 单测落库，live 证据不落库 |
| @Bot 正文被删导致 IM/LLM 只剩 hi | FeishuClient parse 单测 + pipeline parts 单测 | 是 |
| 未 @ 背景不能被纯 @ drain | pipeline external key 单测 + Feishu group history catch-up 单测 + live nonce | 单测落库，live 证据不落库 |
| 飞书 app 只投递 @Bot 事件时不可诊断 | config/adapter health warning 单测 + live 日志 | 是 |

## Roadpoints

### R1 — Mention 正文保真与结构化 metadata

- 状态: DONE
- 步骤:
  - 扩展 FeishuClient parse tests，先证明 `@bot hi` 当前会被删 @、纯 @Bot 会变空、`@所有人` 应保留可见文本。
  - 实现 mention placeholder 到用户可见 @ 文本的规范化；新增 raw/mention_only/normalized mention metadata 承载字段。
  - Adapter 基于结构化 mentions 只把目标 Bot 写入 `mentioned_agent_ids`，把 `mention_only` 透传 metadata。
- 验证:
  - `pytest -q tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py`

### R2 — External group buffer key 与纯 @ drain

- 状态: DONE
- 步骤:
  - 扩展 pipeline group context tests，先证明未 @ Feishu `sync_only` 背景和后续纯 @Bot 共享 external key 且 current message 非空。
  - 修正 pipeline/adapter 必要处，确保 `mention_only` 不影响 shadow sync、session/run 触发和 `_build_message_parts`。
- 验证:
  - `pytest -q tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py`

### R3 — 普通群消息投递能力 warning/health 诊断与收尾验收

- 状态: DONE
- 步骤:
  - 增加 Feishu channel 配置/adapter health warning，用于指出缺少普通群消息投递能力会阻断 M12 live 验收。
  - 扩展 config/channel tests 覆盖 warning/health。
  - 运行窄测、全量非 e2e，并执行/记录真实 Feishu live-critical 证据或环境 blocker。
- 验证:
  - `pytest -q tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py`
  - `pytest -m "not e2e"`
