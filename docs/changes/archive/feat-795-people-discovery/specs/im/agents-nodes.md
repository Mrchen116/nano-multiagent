# im/agents-nodes.md (delta for feat-795)

## MODIFIED Requirements

### Requirement: 登录用户可发现人和 Agent，管理配置保持个人归属

#### Scenario: 从目录直接发起聊天
- **WHEN** 有效账号按名字、用户名或稳定 ID 搜索联系人
- **THEN** 可辨认自己及私人 Agent，获批团队成员还可辨认公司成员（含公开 `@username`）和公司 Agent 并直接私聊，不要求已有 Gateway、好友申请或管理者逐人授权；无匹配时显示空结果。

#### Scenario: 公开 Agent 资料与配置分开
- **GIVEN** 公司 Agent 或公开 PA 由另一人管理
- **WHEN** 用户浏览该 Agent 资料
- **THEN** 能看到名字、管理者、在线状态及工作模式（普通公司 Agent 显示已知设备名，全局公司 Agent 可进入 Work；他人公开 PA 不暴露设备名与私人 Work），能向该 Agent 发消息；当管理者对应的用户为当前可见非本人团队成员时，还可从管理者字段直接向该真人同事发起私聊；不能读取完整配置、凭据或保存管理修改。

#### Scenario: 一个人多 Gateway，单台离线
- **WHEN** 用户绑定多台 Gateway，其中一台离线
- **THEN** 可辨认各 Agent 所属设备与在线状态，其余设备和人际沟通正常；设备及其 Agent 仍只有原管理者管理。
