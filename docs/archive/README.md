# Archive

本目录保存已经退出 current 生命周期、但仍有历史解释或取证价值的独立材料。修改当前产品、架构、行为或流程时，
从 [`docs/README.md`](../README.md) 路由到对应 canonical 文档；archive 不能覆盖 current。

| 历史材料 | 内容 | 当前入口 |
|---|---|---|
| [`product-source-materials/`](product-source-materials/README.md) | 已完成原则蒸馏的早期需求稿与蓝图 | [`docs/product/`](../product/README.md) |
| [`implementation-narratives/`](implementation-narratives/README.md) | 已被代码和 current specs 取代的实现说明 | [`SPEC.md`](../../SPEC.md) 与 [`docs/specs/`](../specs/README.md) |
| [`migration-plans/`](migration-plans/README.md) | 已实施的独立迁移计划 | 对应 current specs |
| [`audits/`](audits/README.md) | 已结束、只对当时基线负责的审计 | 新问题重新进入 active change 或 issue |
| [`legacy-development-records/`](legacy-development-records/README.md) | 旧 TDD control-tower 的任务、进度、验收和经验记录 | [`docs/changes/`](../changes/README.md) |

新材料只有在已经明确退出 current、写清替代入口和退役原因后才进入这里。完整交付的 change unit 继续保存在
`docs/changes/archive/`，不要搬到本目录。
