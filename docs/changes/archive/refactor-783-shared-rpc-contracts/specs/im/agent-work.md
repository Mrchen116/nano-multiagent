# IM Agent Work Specification (delta for refactor-783)

## ADDED Requirements

### Requirement: Global 的历史工具权限记录可读，旧决定不能授权当前执行

#### Scenario: 主人从历史工作记录提交决定

- **GIVEN** Global 的历史权限记录仍显示待处理，提交者有管理权限，选项、节点代际、生命周期与轮次状态通过 IM 检查
- **WHEN** 主人提交决定，IM 将该请求送达支持历史请求明确拒绝的在线节点
- **THEN** 节点按原请求身份回复已结束，IM 返回 409 request_ended，工作记录仍可查看。该决定不会放行任何当前工具调用。
