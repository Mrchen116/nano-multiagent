# gateway/external-channels delta

## ADDED Requirements

### Requirement: PA 飞书主人私聊身份与交付

PA 复用首个发送者持久绑定的主人身份。已绑定主人与 PA 的飞书单聊具有与 Web 主人私聊相同的交办权限；主人回复和定时提醒送到该单聊不经过对外披露审查。群聊与其他私聊不取得该豁免。普通工具权限保持有效。

#### Scenario: 主人单聊收发和提醒
- WHEN 已绑定主人通过飞书单聊交办并安排提醒
- THEN PA 在原单聊回复并在到时发送提醒，依据平台回执确认送达

#### Scenario: 失败输出与新输入隔离
- GIVEN 旧输出投影失败
- WHEN 新飞书消息到达
- THEN 新输入继续持久化和接入，重放不造成重复执行

## MODIFIED Requirements

### Requirement: IM 离线时飞书对话不阻塞

普通 Agent 延续离线执行与恢复镜像；正式 PA 需要中央身份和来源授权，不可用时持久保留输入待恢复。旧输出镜像失败不阻塞已可验证的新输入。

#### Scenario: IM 离线时飞书 1:1 对话仍正常
- **GIVEN** IM 服务当前不可达且 plato-bot 为普通 Agent
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** 本次消息可暂不同步到内部 IM

#### Scenario: IM 离线时飞书群聊 @Bot 仍正常
- **GIVEN** IM 服务当前不可达且 plato-bot 为普通 Agent
- **WHEN** 用户在飞书群 @plato-bot 并发消息
- **THEN** plato-bot 仍在群里正常回复
- **AND** 本次消息可暂不同步到内部 IM

#### Scenario: PA 等待中央恢复
- **GIVEN** 正式 PA 的中央服务暂不可用
- **WHEN** 飞书消息到达后中央服务恢复
- **THEN** 输入在本地持久保留，授权可验证后单次接入同一个主会话
