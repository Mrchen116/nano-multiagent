# IM agent-work Specification (delta for bugfix-728)

## ADDED Requirements

### Requirement: Web 回复的 View Work 定位实际发信唤醒

#### Scenario: 同一 Agent 的多次同名唤醒分别发信
- **GIVEN** 同一 Global Agent 的多个唤醒分别发出聊天回复，且实际发信关联已保存
- **WHEN** 用户点击某条回复的 View Work
- **THEN** 进入该 Agent 的 Work，自动定位并展开实际产生该回复的唤醒，按需显示其完整执行与工具记录；不会因唤醒同名而混淆。

#### Scenario: 再次查看较早回复
- **WHEN** 用户重复点击较早回复的 View Work，包括其唤醒已不在最新一页时
- **THEN** 仍能定位并展开其对应记录，不需要逐页寻找；可以继续查看更早记录或回到最新轮次。

#### Scenario: 关联尚未同步或不可用
- **WHEN** 用户打开回复的 Work，但尚无可证实的发信关联
- **THEN** 明确提示该回复的工作记录尚未同步或不可用，不以时间、同名标题或其他轮次猜测关联；已有 Work 仍可读取。
- **AND** 后续同步取得真实关联后可完成定位，仍遵守既有 Work 资格和来源聊天权限。
