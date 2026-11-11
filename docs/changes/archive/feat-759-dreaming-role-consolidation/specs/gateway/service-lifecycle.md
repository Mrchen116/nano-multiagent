# Gateway Service Lifecycle Specification (delta for feat-759)

## MODIFIED Requirements

### Requirement: IM 服务在线时 Gateway 主动连出并保持双向通信

仅更新当前 Agent 配置快照场景：live 配置不再包含 custom_prompt。ROLE 正文经独立角色接口读取，不属于运行配置快照。其他下行管理帧的身份、恢复和权限契约保持不变。
