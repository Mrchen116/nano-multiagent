# Gateway Personal Agent Specification (delta for bugfix-640)

## MODIFIED Requirements

### Requirement: 独立披露检查限定于对外行为
#### Scenario: 对外发送与私人工作
- **WHEN** PA 发出消息或修改共享内容
- **THEN** 实际外发核对真实授权、完整 payload 与受众；主人私聊和私人工作不加 PA 审核，原工具权限继续生效。
- **AND** 不把该检查声明为任意代码/插件的完整网络隔离。
#### Scenario: 长期使用后继续已授权工作
- **WHEN** PA 已读取相关对话，主人已明确授权向指定受众发送
- **THEN** 独立审核依据 PA 当前有效上下文与真实受众核对，不因无关聊天历史积累而要求重复授权或阻止发送。
#### Scenario: 换窗后证据不足
- **WHEN** 当前有效上下文不足以核对外发授权或私有信息来源
- **THEN** 不发送；可以按正常历史恢复路径取回原话后重新审核，记忆、摘要和助手的授权声明不能单独放行。
