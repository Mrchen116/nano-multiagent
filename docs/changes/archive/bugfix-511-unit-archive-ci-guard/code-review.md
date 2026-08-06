# bugfix-511: Code Review

## Review scope

- Base: `eaaed4c3e`
- Head: `b393ea873`
- Review mode: `full`
- Included commits: `b393ea873 fix(workflow): enforce archived unit PR delivery`
- Included uncommitted files: `incident.md`, `design.md`

## Round 1

- Result: 1 confirmed documentation finding; no surviving code finding.
- Findings:
  - Confirmed: `design.md` 把既有 `Python checks` 写成 GitHub required hard gate，但实时查询显示
    main 没有 branch protection，生效 ruleset 也没有 `required_status_checks`。红灯会阻止 CI
    全绿及 orchestrator 交付判定，但不会从 GitHub 权限层禁止人工合并。
  - Refuted candidate: 把归档检查合入 `docs_check.py`。两者职责不同；归档脚本需要在依赖安装前
    用标准库快速失败，而 `docs_check.py` 依赖 `yaml` 与 `markdown_it` 并检查所有 unit 的通用
    文档完整性。保持独立脚本更符合当前边界。
- Resolutions:
  - 将 incident/design 中的 `required`、`hard gate` 和“自然阻止合入”表述统一校正为
    “使 `Python checks` 失败，阻止 CI 全绿与 orchestrator 宣称可交付”。
  - 明确记录仓库当前没有 GitHub required status check，本次按用户确认范围不修改 ruleset。
- Tests after fixes: 文档 finding 不改变实现；closure review 对全部相关表述逐处复核。

## Closure

- Follow-up mode: `closure`
- Findings closed: 1
- Remaining findings: None
- Final result: Passed
