# M56 - 工具契约对齐（read 返回字符串格式）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`
- Result:
  - `24 passed`（2026-03-04，接手续跑基线）
  - 结论：门禁已可通过，按既有 R1 C1/C2 结果继续推进 R1 文档与 R2。

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

### R1.1 文本 read 契约与截断提示对齐
- Context:
  - read 文本链路原返回 `content` 字符串，且截断提示、首行超限引导与设计细化文案存在偏差。
  - 约束：仅允许改 `read.py` 与 read 相关测试，不触碰 bash/edit/write/task。
- Decision:
  - 文本返回统一为 `content=[{"type":"text","text":...}]`。
  - 对齐三类提示：`Showing lines`、`(xx limit)`、`{remaining} more lines`，并在首行超限时输出 `Use bash: sed -n ... | head -c ...`。
  - `offset` 越界错误保留 `details.offset/details.total_lines`。
- Rationale:
  - 先锁死字符串与结构契约，再最小实现，可避免提示文案与结构字段在重构时漂移。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`（`24 passed`）。
  - Entry: `ReadTool.run` 文本分支在 unit+contract+integration 均验证了 offset/limit/截断边界与 details 契约。
- Rollback:
  - `2b9ef35`（R1 红测基线，便于重做实现）。
- Commits: C1=`2b9ef35`, C2=`e57bbd6`, C3=`本提交`
- Next:
  - 进入 R2：补图片 part 新契约红测并改 mapper 兼容。
