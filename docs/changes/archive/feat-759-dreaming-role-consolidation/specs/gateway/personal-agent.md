# Gateway Personal Agent Specification (delta for feat-759)

## MODIFIED Requirements

### Requirement: 默认服务指导复用普通配置和 Skill

本需求改为“系统维护PA默认服务指导与Skill协作”。PA默认指导定位为长期帮助主人履责、追求目标、兼顾工作生活；共享Global系统段提供内部委派与公开交付分工。默认服务指导来自系统，不保存在可编辑配置中。

#### Scenario: 用户调整服务方式
- **WHEN** 主人希望调整长期帮助目标、分工或服务习惯
- **THEN** 通过同一ROLE入口确认和保存；不提供custom_prompt。PA固定主人关系、来源与权限边界保持原有效力。

#### Scenario: 主请求与记忆整合获得PA定位
- **WHEN** PA发起主请求或Dreaming整合
- **THEN** 获得系统PA默认服务指导与已确认ROLE；普通Global和内部worker不获得根PA的专属服务段。

原跨轮次持续工作、重要观察后的私人准备及Skill选择场景保持不变。
