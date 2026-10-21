# IM agent-work Specification (delta for feat-630)

## ADDED Requirements

### Requirement: 工作记录补传与聊天沟通独立且恢复后完整可查

#### Scenario: 大结果在中断后恢复回看
- **WHEN** 受支持大小的工具参数或结果经历分段同步、中断、重复传输和恢复，用户重新打开 Work
- **THEN** 可以回看完整正文、真实顺序及父子归属，不新增重复条目或把未完成的记录报为完整。

#### Scenario: 工作记录暂未同步
- **WHEN** 工作记录仍在补传而实时聊天可用
- **THEN** 聊天消息与必要操作照常进行，普通聊天不增加同步实现、确认阶段或运维诊断信息；用户仍可主动打开现有 Work。
