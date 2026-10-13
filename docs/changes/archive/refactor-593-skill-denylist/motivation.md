# Skill 选择改为禁用名单

## 用户决定

用户原话：“workspace和全局都采用黑名单制，也就是用户配置的时候，没选的，就不加载”；已确认“后来新建或导入的 Skill 不在禁用名单里，默认可用”“用户明确禁用过的 Skill 刷新、重启后仍禁用”，并接受全局新增 Skill 对可访问该目录的 Agent 默认可用。用户随后要求“那没问题，改”。

## 当前问题

Agent 经 Bash 复制 daily-journal-write 到自己的技能目录后，文件已核验成功，但 explicit_allowlist 未包含名称，原生 skill 工具返回 unknown。白名单把技能文件发现与使用之间增加了配置同步要求。已有 skill_manage(create) 自动启用无法覆盖复制导入。

### Requirement: 新技能默认可用

#### Scenario: Workspace 与全局新名称默认可用

- WHEN 在 Agent 可发现的 Workspace 或共享全局根目录新增有效 Skill
- THEN 当前 Session 后续步骤可发现并加载该 Skill，无需手工勾选或重启；其他 Workspace 的私有 Skill 不泄漏。

### Requirement: 明确禁用持续有效

#### Scenario: 两端保存后刷新重开和同名重建

- WHEN 用户取消选择已有 Skill 并保存
- THEN 模型目录、按名加载、显式命令、预览和 SlashPicker 都排除该名称；重启及同名重新创建不能自动启用。

### Requirement: 旧选择保真迁移

#### Scenario: 已有候选选择保留，迁移后新增默认启用

- WHEN 已有 allowlist Agent 升级
- THEN 以迁移时实际候选集合计算禁用名单，保留已选和未选状态；之后新增名称默认可用。原 default discovery 对应空禁用名单。

## 范围

配置、Node/IM 持久化与迁移、原生 provider 过滤、Web 创建/编辑/预览/SlashPicker、自进化创建通知。工具权限不变；不部署生产、不处理另两个审批及静默结束问题。


### Requirement: 既有工具与知识策略不变

#### Scenario: 修改 Skill 选择不改变工具与进化开关
- **WHEN** 用户保存两端 Skill 选择并查看相邻工具/进化配置
- **THEN** 既有工具选择和进化开关保持，来源记录与真实后台通知继续有效；F3/F4 规则不变
