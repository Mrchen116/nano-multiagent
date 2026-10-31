# As-built Design

本文在实现后整理，非事前设计审批。

## 结构与决定

- AgentDetailPage/CronCard 保持原查询与取消链路，在展示层按 enabled 筛选。后端目录仍保留 inactive 历史，避免改变其他消费者的语义。
- schedule-display.ts 使用原生 Intl 将六种 DSH schedule 记录转换为本地化说明。周期规则保留原时区，下一次执行时间使用浏览器时区并显式标注。
- 原生 details/summary 收纳指令；自定义 cron 表达式放在详情。当前协议没有业务 Task 关联字段，本次不猜测或解析标题生成任务链接。
- 不新增轮询，沿用原查询缓存、焦点刷新与取消后失效机制。
- 本次无模型可见 Context 变更；无运行时迁移。回滚前端提交即可恢复原展示；底层历史没有写入或删除。

## 验证

cron-card.test.tsx 覆盖失效过滤、active 过时计划保留、详情、取消 ID、空态与周期格式；相邻 agent-features-panel 与 agent-edit 回归一起运行。

浏览器截图使用修改前后实际 CronCard 及原 CSS，以相同隔离 fixture（5 条失效单次计划 + 1 条有效每日计划）渲染，另检查全失效空态。不是完整后端 E2E，也不是生产部署截图。截图位于本机 Codex visualizations，本仓不提交图片缓存。

用户验收待本轮截图反馈。尚未满足快速开发归档门禁。

## 契约

目标为 docs/specs/im/agents-nodes.md；候选差异见 delta-spec.md，用户验收后再归并 current spec。

## 实现基线与运行证据

Base: `99354a6a1afaf2a2f495d2e5abf62f1027c3eade`；代码范围为 CronCard、schedule-display、cron-card 测试、相邻 feature panel 测试及 zh/en 词条。本次提交保存完整实现，最终验证见 code-review.md。

截图目录：`/Users/czj/.codex/visualizations/2026/10/31/01a190b0-fde5-7af1-9f6c-9424cf25229c/`，含 plans-before.jpg、plans-after.jpg、plans-empty.jpg 与 preview-source 重现入口。预览数据不包含生产内容；截图不是线上状态。

## 视觉修订（基于 75609c7c9）

按用户反馈完善视觉：沿用设置页连续画布，计划采用圆角细边界、低饱和绿色图标、类型标签和独立的下次执行时间；原生 details 的整行 summary 支持鼠标与键盘展开。取消操作保留可访问名称、原接口和所有保护，移入详情末尾降低干扰。单次计划不重复展示“单次”文字。

formatSchedule 返回 rule/next 两部分供不同层级展示；Intl 日期和规则语义不变。窄屏把时间标注与值分行。新增 CSS 限定 im-plan(s) 类名，不覆盖其他设置模块。

新增截图 plans-designed.jpg、plans-designed-details.jpg、plans-designed-empty.jpg、plans-designed-mobile.jpg。使用真实组件与设置容器 CSS，fixture 为 5 条失效历史、1 条每日计划和 1 条单次计划（均为隔离测试数据），在 390px 窄屏核实无溢出。不是生产截图。
