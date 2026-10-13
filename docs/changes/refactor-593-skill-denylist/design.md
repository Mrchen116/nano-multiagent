# 设计

已在对话中确认采用禁用名单；本文件在实现前记录该方案。

- `skills_selection_mode=explicit_denylist` 时，`skills` 保存禁用名称；字段名保留以避免第二套配置同步和指纹通道。旧模式只用于一次迁移输入。
- 原生 DSH 文件 provider/registry/catalog 继续负责发现与动态刷新。Nano 的 list/get 使用同一排除规则，保留 roots、同名覆盖和 Agent scope。
- Node 连接 IM 后，调用受 Gateway 身份保护的迁移入口。IM 从该 Agent 的真实 capabilities 得到完整候选，按旧选择计算禁用名称，经已有 optimistic-lock config operation 同时更新 Node YAML、runtime 与 IM profile。已经迁移的 Agent 不重复转换；离线不猜测候选。
- 创建/编辑页仍用选中态呈现可用技能，保存取消项；隐藏或暂时缺失的禁用名称保留。新 Agent 默认空禁用名单。预览与 SlashPicker 同样解释 mode。
- 新 Skill 创建事实不再追加任何 Agent 的启用名单；后台更新通知和来源记录保留，用户禁用优先。

| Milestone | 范围 | 退出标准 |
|---|---|---|
| M1-selection | contracts、Node/IM、DSH provider、Web、specs/tests | 原生 Session 内复制新增可加载；明确禁用及重启保持；Web 保存/重开一致；旧选择迁移与 config fingerprint 一致 |

## 验证与限制

扩展既有 capabilities、knowledge、configuration 和 SkillSourceSelector 测试，覆盖真实原生 DSH 文件发现与加载。此侧对话禁止子 Agent，不伪造独立设计/代码/产品审查结论；该门禁待主交付流程执行。本次只交付本地独立 worktree，不改生产配置。Web 没有布局重构，保留原分组、勾选和批量交互，只增加默认启用提示；iOS 改为同一勾选语义。
