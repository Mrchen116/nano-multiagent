# M1 实施与验证

## 实施

- 主 Agent 在用户指定 develop 分支端到端实施，未派实施 worker；设计审查见 ../design-review.md。
- 能力选择与组合集中到 skill-composition；流程、模板、统一 review、模型派发与索引同步；退休旧 reviewer/verifier，保留历史报告。两处历史审计链接固定到当时提交，不改历史结论。
- `.agents/skills` 为真实受跟踪目录；docs-check 原先只认旧 .claude 路径，新增坏引用回归先复现漏报，再改到实际目录。

## 已执行检查

使用主仓已有 Python venv 只读运行工具，未改该环境。系统 Python 缺 yaml/pytest 的首次命令失败属于环境，不计测试失败；切到项目已有 venv 后基线 docs-check 和 48 项相关测试通过。

- 新增 `test_skill_reference_is_checked_through_the_repository_alias`：修前返回空问题导致断言失败；修后坏引用被发现，补上受跟踪目标后通过。
- docs-check：275 maintained Markdown sources / 69 required routes 通过，包含实际 skill 源；此前基线只扫描 218 sources。
- `pytest tests/unit/test_docs_check.py tests/contract/test_change_workflow_documentation_contract.py tests/contract/test_change_skill_archive_contract.py tests/unit/test_change_spec_author_next_unit_id.py -q`：48 passed。
- 15 个新增/修改 skill 入口通过 skill-creator quick_validate；git diff --check 通过。
- 退休的固定角色矩阵文本测试绑定旧实现结构；生命周期 optional spec review、归档规则等现有保护保留。新增测试保护链接遗漏，未逐句锁定新文案。

## 交付边界

本轮不启动 Nano 服务、不修改产品源码、不改生产；不运行 TS/Web/iOS 全套来替代 skill 验证。独立审查与有界演练结果归 ../review.md。develop 为用户自然需求试验基线，暂不创建 main PR，unit 保留 active；不能从静态校验推导 token 节省或真实需求可靠性。
