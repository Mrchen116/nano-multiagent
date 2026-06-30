# M5-fix-config-consistency

## 目标

修复 verifier WARNING + code review 发现的配置层 consistency bug：
1. botOpenId 被配置解析丢弃（CRITICAL correctness bug）
2. feishu 顶层 `enabled: false` 语义丢失（correctness bug）
3. GroupContextStore buffer key 格式不一致（verifier WARNING）

## 退出标准

- `_parse_feishu_accounts` 保留 botOpenId 字段
- feishu 顶层 `enabled: false` 时跳过所有 account 解析
- FeishuAdapter 的 `_group_buf_key` 与 InboundPipeline 的 `_group_buf_key_for_agent` 格式一致
- 所有 feishu 相关测试全绿
- 全量非 e2e 测试无回归

## 测试策略

- 被测行为(来自退出标准):
  1. config.yaml 含 botOpenId 时，解析后的 ChannelConfig.settings 包含 botOpenId
  2. config.yaml 中 feishu 顶层 enabled=false 时，不解析任何 account
  3. FeishuAdapter 和 InboundPipeline 对同一会话生成相同 group buffer key
- 已有测试在: `tests/unit/test_feishu_config.py`(扩展) / `tests/unit/test_feishu_adapter.py`(扩展)
- 落层/目录/marker: tests/unit/ , marker: 无
- 可选依赖 importorskip: 无
- 本 milestone 产生的一次性验收证据: 无

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 配置解析修复 + buffer key 统一 | TODO |
