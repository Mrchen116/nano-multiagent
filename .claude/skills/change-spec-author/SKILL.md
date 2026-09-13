---
name: change-spec-author
description: "需要建立 change unit 并对齐需求、问题或重构目标，或修订其首文档时使用；普通小修、技术设计和实施不触发。"
---

# Change Spec Author

产出能交给设计/实施角色的首文档，说明用户要什么、成功标准和范围。是否建 unit、Full/lite 的选择以 [change-workflow](../../../docs/development/change-workflow.md) 为准；已有 unit 继续使用，不重复立项。

## 约束

- 原始需求和澄清答复保留用户原话，附件保留引用；Agent 解读单独标注。
- 只澄清影响用户体验、范围或验收的未决问题，一次一个，附推荐和理由。已有明确答案或授权自主决定的事项直接沿用，不凑问题数量。
- 未完成澄清的结论段留空，不把未回答的选项写成要求。范围和非目标遵循用户决定。
- 现状、用户点名的参考和根因结论要有依据；相关 current specs 与实现不一致时说明差异，不能把坏现状或外部参考自动当作目标契约。
- 只修改 `docs/changes/<unit>/` 首文档，不写产品代码、不建实施分支；技术选型与实现保真要求交给 design。

## 产物与完成

新建时在仓库根运行一次 [next_unit_id.py](scripts/next_unit_id.py) `<type>`，使用原子保留的编号；不重复调用来预览编号。命名与目录归属见 [changes](../../../docs/changes/README.md)。

按类型选模板：新功能 [spec](assets/spec.md)，小 bug [fix](assets/fix.md)，Full bug [incident](assets/incident.md)，重构/性能 [motivation](assets/motivation.md)。填写时参考 [内容边界](references/authoring.md)，无需读取其他模板。

完成时原话、场景、范围和适用的根因/迁移/性能证据齐全，无待定结论或模板残留。Full 验收使用 Requirement/Scenario，每个 Requirement 至少一个可追溯的 WHEN/THEN Scenario；验收写用户可观察结果。无用户面时给依据，实施层标准留给 design。

首文档在 `main` 上只提交并推送本 unit 文件，保留其他工作。Full 交给 `change-design-author`；lite 只完成 fix 的“现象/复现、根因”，交给默认 orchestrator 或用户点名的 simple 流程回填“修复、验证”。
