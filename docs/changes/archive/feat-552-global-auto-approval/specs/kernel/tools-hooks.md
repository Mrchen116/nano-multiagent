# Tools and Hooks — feat-552 delta

目标：`docs/specs/kernel/tools-hooks.md`。依据 design D1–D3/D6/D7。

## ADDED Requirements

### Requirement: Auto 不因宽许可忽略工具明确拒绝

#### Scenario: 明确 deny 与整工具 allow 同时存在
- **WHEN** Auto 工具检查明确拒绝当前动作
- **THEN** 内置安全表与宽工具许可不能短路该结果；工具检查保持单次、执行器不重复查策略。

### Requirement: Auto 直接放行工作目录内的普通文件写入

#### Scenario: 新建、覆盖和编辑普通工作区文件
- **WHEN** Auto 中的内置 `write` 或 `edit` 操作普通工作区文件，且传入路径和解析后的目标均在当前 session 工作目录内
- **THEN** 直接执行而不请求审批模型，包括 Cron 到点发起的写入；覆盖和编辑仍受读取与文件变更检查约束。

#### Scenario: 目录外或敏感目标不享受工作区免审
- **WHEN** 目标位于工作目录外，符号链接跨越目录边界，或传入路径/解析目标命中敏感路径检查
- **THEN** 不因该文件操作享受工作区免审；目录外动作保留权限分类流程，敏感路径保留显式确认要求。
- **AND** Auto 未启用时，不采用这条直接放行路径。

### Requirement: Bash Auto 免审精确到命令语法与参数

#### Scenario: 只读参数与写参数
- **WHEN** 相同 Git 或查询命令的参数分别构成读取与修改动作
- **THEN** 按固定 CC 等价规则区分，不能仅因命中 git config/branch/tag/remote 等前缀就把写操作免审。

#### Scenario: 复合命令
- **WHEN** 命令带管道、重定向、引号、子命令或替换
- **THEN** 按 CC 同等语法和各段检查组合结果；可证明只读的组合不因简化 parser 多审，无法证明只读不当作 allow。

### Requirement: 应用消息工具能提供来源说明且普通数据不升级

#### Scenario: 声明宿主结果投影与说明
- **WHEN** 应用工具使用现有结果投影并提供固定 auto_classifier_context_instructions
- **THEN** 成功结果上下文物化并绑定实际调用，说明进入独立 Auto Gate system prompt；不从模型参数或工具结果正文提取 system 指令。

#### Scenario: 稳定历史与实时属性
- **WHEN** 工具卸载/替换、结果恢复或正文被修改
- **THEN** 已物化上下文不被当前工具重写；只有运行态登记的消息/调用及相同上下文可拥有实时属性，持久化的 live 自报不生效。

### Requirement: 工具结果区分授权、执行与审核故障

#### Scenario: 动作未执行
- **WHEN** 原因是模型拒绝、工具明确 deny、用户否决、必须人工、模型不可用、解析失败或超限
- **THEN** 保留原 denied 结果兼容及可区分原因；自动判断、人工决定与配置 fallback 分开记录。

#### Scenario: 历史动作 outcome
- **WHEN** 后续审批读取旧动作状态
- **THEN** 实际执行、失败、拒绝、发送待处理与后台启动按真实状态描述；成功不成为以后动作的授权背书。
