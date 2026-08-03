# refactor-489-M18: fix-verification-report — Tasks

> 对齐: code-review CONFIRMED finding；仅限 `verification.md` 第 7--9 行和本 milestone 记录。

## 目标

移除 `verification.md` Summary 元数据三行的尾随空白，使从 original validation base 到当前 unit head 的 Git diff 格式检查可执行且通过；不改报告文字、结论或任何实现。

## 退出标准

- [ ] `verification.md` 第 7--9 行仅移除每行末尾空格，报告内容不变。
- [ ] `git diff --check 0b9607147df21e6e11e1c7b27cccba6005ce6ab6...HEAD` 通过。
- [ ] `scripts/docs_check.py` 通过，且范围只含 `verification.md` 与 `M18-fix-verification-report/`。
- [ ] 在最新 `origin/unit/refactor-489` 上完成 rebase、验证、合入、推送与 milestone worktree/branch 清理。

## 测试策略

- 被测行为（来自退出标准）：Git 的 diff whitespace 检查不再报告 verification Summary 元数据行；文档路由/完整性仍然有效。
- 已有测试在：无；这是 Markdown whitespace repair，现有的 `git diff --check` 与 docs-check 已是最低可执行验证入口。
- 落层/目录/marker：N/A；不新增或修改测试。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；命令、基线和结果写入 `progress.md`。

### 受影响的既有测试处置

无；搜索范围：`tests/` 与 `src/` 未进入 M18 scope，改动只处理 verifier report 的三处 Markdown 尾随空格及本 milestone 记录；理由：没有既有测试资产的行为、层级或 harness 被改变。

## Roadpoints

### R1 — 修复已确认的报告尾随空格

- 状态: DONE
- 步骤: 仅删除第 7--9 行行尾空格并检查 diff 只显示空白删除。
- 验证: 指定 `git diff --check` range 与 `sed -n '7,9l'`。

### R2 — final sync、门禁与交付

- 状态: DOING
- 步骤: 运行 docs-check 和范围审计；rebase 最新 unit 后重跑，再在 unit lock 内合并推送并清理。
- 验证: docs-check、指定 diff check、clean worktree、unit push。
