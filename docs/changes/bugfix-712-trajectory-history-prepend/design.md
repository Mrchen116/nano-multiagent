# bugfix-712: As-built Design

> 本文在实现后根据实际 diff 整理，不代表事前设计门禁。

## 实现范围

- Base: `2ac6007`；分支 `fix/trajectory-history-prepend`。
- 完整 dirty 范围：本 unit 文档、trajectory-contract.ts、trajectory-request-header-definition.ts、trajectory-snapshot-builder.ts 和 tests/history-paging.test.ts，均在 packages/trajectory-ui 下（文档除外）。

## 最终结构与关键决策

Session 分页 → 官方 ConversationNodeAssembler 依赖重放 → trajectory-system-message Definition → 本仓 TrajectorySnapshotBuilder → 既有 UI。

Definition 无显示内容时贡献 `{ kind: 'hidden' }`，保留 context key 和事件锚点。builder 接受同 key upsert，跳过 hidden，避免已发布节点被撤回，也避免陈旧请求头/系统提示词继续参与展示。隐藏贡献只属于浏览器本仓 UI，不持久化、不改变协议或官方依赖。

未引入第二套 renderer、runtime patch、private import 或全文重载绕过。回滚本次三个产品文件即可回到原行为（也会恢复分页异常）。无数据迁移及部署迁移要求。

## 验证定位

- tests/history-paging.test.ts 使用锁定公开浏览器注册工厂和真实 assembler，注册本仓 Definitions，比较可见事件与请求事实。
- 既有 navigation / run-navigation 测试 keep；上游 tests/upstream 为参考，未修改或假报进入默认门禁。
- 新建独立 history-paging.test.ts：其 owner 为分页组装公开 seam；现有两个测试文件只覆盖导航模型，不能暴露本问题。根 pnpm test 长期收集本测试。
- 两个新增测试在原 Definition 上均以 withdrew materialized target 失败，修复后通过；覆盖每个分页切点、单条多页、重复页、不确定→已知及恢复后追加。
- 用户验收待完成。未连接截图中的真实 Gateway；确定性组件验证不能替代真实浏览器工作页验收。

## Canonical 文档影响

无行为契约新增：恢复 docs/specs/im/agent-work.md 已有“系统提示词/上下文完整检查”和“继续读取更早内容”要求，无 spec delta。

## 收尾

完整 code review 和验证记录见 code-review.md。未获用户实际验收，不归档，不创建 PR，不部署。云端分支保留供继续验收和交付。
