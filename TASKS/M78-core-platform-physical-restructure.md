# M78 - 多产品架构重构五期：core/platform 物理分层与兼容门面

## 目标
物理重组 src/nano_multiagent 为 core/platform 结构，保留兼容门面。

## 策略
- 不重命名顶层包（nano_multiagent 不变）
- shim 文件保留旧 import 路径
- 每步后 pytest -q 验证
- 不破坏 CLI HTTP-only contract

---

## R1 - 移动 session/stores → platform/persistence/session

### Acceptance
1. platform/persistence/session/ 目录存在，含 base/jsonl_store/sqlite_store
2. session/stores/__init__.py 保留为 shim，re-export 原有符号
3. pytest -q 全绿（≥548 passed）
4. 旧 import `from nano_multiagent.session.stores import SQLiteSessionStore` 仍可用

### Tests Plan
- unit: 不新增（现有覆盖已足够）
- contract: 已有 session store 相关 contract 测试，迁移后须保持绿
- integration: 已有 session/service 集成测试
- e2e: 无需新增

### Expected Tests
- 现有 tests/ 中涉及 session.stores 的测试迁移后仍绿

### DoD
test_command 全绿 + C1/C2/C3 提交完成 + PROGRESS 更新

### 状态：TODO

---

## R2 - 移动 llm/protocols → platform/llm/providers

### Acceptance
1. platform/llm/providers/ 含 anthropic/ 和 openai_compat/
2. llm/protocols/__init__.py 为 shim
3. pytest -q 全绿

### Tests Plan
- unit: 现有覆盖
- contract: test_llm_interfaces_contract.py
- integration: 现有 LLM 相关测试

### DoD
test_command 全绿 + C1/C2/C3

### 状态：TODO

---

## R3 - 移动 tools/builtins + loader + safety → platform/tools

### Acceptance
1. platform/tools/builtins/ 含 bash/edit/read/task/write
2. platform/tools/loader.py 和 platform/tools/safety.py 存在
3. 旧 import 路径 tools/builtins, tools/loader, tools/safety 均有 shim
4. pytest -q 全绿

### Tests Plan
- unit: 现有 tool builtin 测试迁移后仍绿
- contract: 无需新增
- integration: 现有集成测试

### DoD
test_command 全绿 + C1/C2/C3

### 状态：TODO

---

## R4 - 移动 hooks/builtins + loader → platform/hooks

### Acceptance
1. platform/hooks/builtins/ 含 bash_risk_gate/default_status/realtime_stream/usage_metrics
2. platform/hooks/loader.py 存在
3. 旧 import 路径 hooks/builtins, hooks/loader 有 shim
4. pytest -q 全绿

### Tests Plan
- unit: 现有 hook builtin 测试
- integration: 现有 hook 集成测试

### DoD
test_command 全绿 + C1/C2/C3

### 状态：TODO

---

## R5 - 移动 server → platform/http_api

### Acceptance
1. platform/http_api/ 含 app/auth/deps/routes/sse
2. server/__init__.py 为 shim re-export 原符号
3. pytest -q 全绿
4. CLI HTTP-only contract test 仍绿

### Tests Plan
- unit: 现有 server 测试
- contract: test_cli_http_only_contract.py
- integration/e2e: 现有集成测试

### DoD
test_command 全绿 + C1/C2/C3

### 状态：TODO

---

## R6 - 移动 sdk → platform/sdk

### Acceptance
1. platform/sdk/ 含 client.py
2. sdk/__init__.py 为 shim
3. pytest -q 全绿

### Tests Plan
- unit: 现有 SDK 测试

### DoD
test_command 全绿 + C1/C2/C3

### 状态：TODO

---

## R7 - 验证 core 不 import platform 内容

### Acceptance
1. core/ 下文件不 import FastAPI/sqlite3/.nano/.codex/filesystem extension discovery
2. 生成 platform/ 的 __init__.py 暴露顶层符号
3. pytest -q 全绿

### Tests Plan
- contract: 新增测试 test_core_no_platform_imports.py 验证 core 模块无禁止 import

### DoD
test_command 全绿 + C1/C2/C3

### 状态：TODO
