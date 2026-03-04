# M56 - 工具契约对齐（read 返回字符串格式）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`
- Result:
  - `1 failed, 19 passed`（2026-03-04）
  - 失败点：`tests/unit/test_tools_builtins.py::test_bash_without_timeout_does_not_inject_default`
  - 归因：`bash` 工具相关，超出 M56 allowed_scope（本里程碑不修复）。

### Plan（一次性拆分）
- Context:
  - 现状 `read` 文本返回 `content` 为字符串，不符合工具细化文档要求的 content parts 契约。
  - 图片 part 仍为 `image_url + mime_type`，与目标 `data + mimeType` 不一致；截断提示文案也未对齐 `Showing lines...` 规范。
- Decision:
  - 拆为 `R1 文本契约` 与 `R2 图片契约+mapper兼容` 两个 Roadpoint，按 C1/C2/C3 执行。
  - 先写红测锁定字符串与字段契约，再以最小实现改 `read`，最后补 mapper 兼容。
- Rationale:
  - 先以测试明确外部契约，再改实现可降低“文案细节/字段名”回归风险。
- Evidence:
  - Tests: 基线门禁已记录（存在 1 个 M56 范围外失败）。
  - Entry: 变更入口限定在 `read.py` 与指定三类测试文件；mapper 仅在 image part 兼容需要时改动。
- Rollback:
  - 回退到本计划提交前稳定点（`milestone/M56` 初始 commit）。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 进入 R1：补文本契约红测（content parts / Showing lines / 首行超限 / details 契约）。
