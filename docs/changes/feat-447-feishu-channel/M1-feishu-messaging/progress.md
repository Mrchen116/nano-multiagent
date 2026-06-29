# feat-447-M1 — Progress

## R1 — 飞书 config 解析 + lark-oapi 依赖

- Context: 飞书 channel 需要在 config.yaml 中以 `channels.feishu.accounts` 结构配置多个 Bot，每个 account 绑定一个 agentId。现有 `_parse_channels` 只支持平铺 list 格式，需扩展支持 feishu accounts 子列表。
- Decision: 在 `_parse_channels` 中检测 `name == "feishu"` + `"accounts" in item` 时调用新函数 `_parse_feishu_accounts`，将 accounts 展开为独立 `ChannelConfig(name="feishu:<acct_name>")`。每个 ChannelConfig 的 settings 携带 appId/appSecret/agentId 供 adapter 使用。lark-oapi SDK 作为主依赖加入 pyproject.toml。
- Rationale: 跟 design 决策 2 一致（config.yaml 的 channels.feishu.accounts 列表）。复用现有 ChannelConfig 结构，不引入新配置抽象。Disabled accounts 在解析期跳过，不产生 ChannelConfig。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_config.py` — 11 passed（单 account / 多 account / 禁用排除 / 缺字段报错 / 混合 channel / 空列表 / settings 携带）
  - Entry: N/A（纯配置解析，无运行时入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 纯逻辑变更，回归由全量 `pytest -m "not e2e"` 覆盖（3126 passed）
  - Visual/Interaction: N/A
- Rollback: `git revert b433599a` 回退 config 解析；`git revert 1b839230` 回退测试文件
- Commits: C1=1b839230, C2=b433599a
- Next: R2 — FeishuClient 封装 lark-oapi WSClient

## R2 — FeishuClient 封装 lark-oapi WSClient

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
  - Visual/Interaction: N/A
- Rollback:
- Commits:
- Next:

## R3 — FeishuAdapter 消息收发 + 群聊 mention 门控

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
  - Visual/Interaction: N/A
- Rollback:
- Commits:
- Next:

## R4 — main.py 注册 + 集成测试

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
  - Visual/Interaction: N/A
- Rollback:
- Commits:
- Next:
