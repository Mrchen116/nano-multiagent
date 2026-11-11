# IM Personal Agent Specification (delta for feat-759)

## MODIFIED Requirements

### Requirement: 来源限制与风险提醒明确

仅替换原“默认职责复用可编辑补充指令”场景，其他来源/风险场景保持不变。

#### Scenario: 默认职责由系统提供
- **WHEN** 首次创建或使用PA
- **THEN** 服务方式、持续推进和Skill默认指导由系统提供，不向custom_prompt或ROLE写入默认文案。用户长期个性约定通过ROLE维护。
- **AND** 旧用户配置只在获授权部署时按一次性提示词迁移，不自动覆盖现有ROLE或Skill选择。
