# feat-447-M3: 增强错误处理 — Tasks

> 对齐: ../design.md

## 目标

飞书消息发送路径具备分级错误处理能力：rate limit 自动重试、auth 错误自定义异常、server 错误重试、adapter 层捕获并通知用户。

## 退出标准

- [x] send_message 对 429 以指数退避重试（最多 3 次）
- [x] send_message 对 401/403 抛出 FeishuAuthError
- [x] send_message 对 5xx 重试一次
- [x] send_message 对其他错误抛出 FeishuAPIError
- [x] feishu_adapter.send 捕获 FeishuAuthError 并记录结构化日志
- [x] feishu_adapter.send 捕获 FeishuAPIError 并记录结构化日志
- [x] 结构化日志包含 error_code、chat_id 等上下文
- [x] 所有新增行为有对应单元测试覆盖

## 测试策略

- 被测行为（来自退出标准）：
  - send_message 429 rate limit → 指数退避重试最多 3 次
  - send_message 401/403 → FeishuAuthError
  - send_message 5xx → 重试一次后失败
  - send_message 200 → 成功返回
  - feishu_adapter.send 捕获 FeishuAuthError → logger.error + re-raise
  - feishu_adapter.send 捕获 FeishuAPIError → logger.error + re-raise
- 已有测试在：`tests/unit/test_feishu_client.py`（扩展）、`tests/unit/test_feishu_adapter.py`（扩展）
- 落层/目录/marker：tests/unit/，marker：无
- 可选依赖 importorskip：有，lark_oapi
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无

## Roadpoints

### R1 — feishu_client 错误分类与重试 ✅ DONE

- 步骤:
  1. 定义 FeishuAPIError、FeishuAuthError 异常类（在 feishu_client.py 顶部）
  2. 重构 send_message：指数退避重试 429（0.5/1/2s），5xx 重试一次
  3. 错误分类：检查 response.code 映射到异常类型
- 验证: pytest tests/unit/test_feishu_client.py -xvs — 17 passed

### R2 — feishu_adapter 错误通知 ✅ DONE

- 步骤:
  1. send() 方法 catch FeishuAuthError → logger.error（extra 含 error_code, chat_id, agent_id, adapter）+ re-raise
  2. send() 方法 catch FeishuAPIError → logger.error（extra 含 error_code, chat_id, agent_id, adapter）+ re-raise
  3. adapter 不吞异常，但记录结构化日志供运维排查
- 验证: pytest tests/unit/test_feishu_adapter.py -xvs — 14 passed

### R3 — 单元测试 ✅ DONE

- 步骤:
  1. 在 test_feishu_client.py 扩展：7 个新测试覆盖 429 重试、401/403 auth error、5xx 重试、未知错误、成功路径
  2. 在 test_feishu_adapter.py 扩展：2 个新测试覆盖 send 捕获 FeishuAuthError/APIError 后的行为
  3. 测试重试逻辑中 mock time.sleep
- 验证: pytest tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py — 30 passed; 全量 feishu 测试 — 45 passed
