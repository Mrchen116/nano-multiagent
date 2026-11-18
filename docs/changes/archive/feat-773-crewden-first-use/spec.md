# feat-773: Crewden 首次使用与日常协作体验

## 原始需求

> I want to improve the experience for new users after they register, so they can register and start using the product smoothly. Please first help me review the current shortcomings and areas that need optimization, including the ugly parts of the frontend. I want to turn it into a commercial product-level experience. Not need to follow any skills. You can depend on your own idea

> 直接开worktree开始弄，快修模式，不用先写spec。没做到一个阶段性的效果，给我截图，我要看前后对比

## 澄清与验收记录

本 unit 在实现后整理，依据同一聊天中的连续反馈，不补造事前设计门禁。

- 用户要求登录前解释产品；进一步明确 IM 是载体，PA 和专职 Agent 长期、主动且跨聊天协作，价值包含团队效率。
- 用户选择英文品牌 Crewden、聊天框结合机器人意象的 logo，明确“别用图片生成，纯svg写”。
- 用户要求官网到注册、安装、创建 PA、首次聊天以及登录后工作区风格连贯，并要求真实模型与视频展示。
- “用户发消息后就不需要有对应指引了”：首次合作说明不能继续占据已有聊天，不打印 ROLE。
- 用户否定大面积深黄/绿色块和机械面罩，要求“灵动活泼但简洁”；PA 与普通 Agent 创建时可选择不同轮廓与颜色，群聊里能辨认。
- 用户要求 PA 列表展示真实最新消息；语言选择收敛为按需操作；去掉 Me、参与者重复名单、类型标签等冗余；电脑信息从头像详情查看。
- 用户确认私聊名按实际查看者显示对方，PA 旁观显示双方；手动改名和群名保留。
- 最终用户验收原话：“我觉得差不多，做收尾吧”。

## 用户场景与验收标准

### Requirement: 登录前能理解协作价值并自然进入使用
#### Scenario: 首次访问
- **WHEN** 访客打开官网并进入注册或登录
- **THEN** 通过可交互场景理解自己、PA、同事和专职 Agent 如何合作，品牌与语言一致，按钮进入真实流程；演示明确是示意而非真实运行结果。

### Requirement: 安装与首次使用有清楚且可恢复的下一步
#### Scenario: 从新账号开始
- **WHEN** 用户注册、连接电脑、配置可用模型并创建助手
- **THEN** 每一步显示当前真实状态和下一步，不以技术概念说明替代操作；错误和已有绑定沿用有效恢复入口。
#### Scenario: 第一次交办
- **WHEN** PA 或 Global 尚无历史
- **THEN** 给出低门槛任务草稿及可展开的合作说明，不覆盖已有输入；用户发言后引导退场，职责保存由真实对话确认。

### Requirement: 日常聊天清晰且具有亲和力
#### Scenario: 创建并辨认助手
- **WHEN** 创建 PA 或普通 Agent 并进入私聊或群聊
- **THEN** 可选头像保持跨页面一致，两类角色有轮廓差异，已有角色有稳定默认形象。
#### Scenario: 再次回来与查看详情
- **WHEN** 用户返回工作区、切换会话或查看群成员
- **THEN** 看到真实最近消息、未读和时间；标题和消息避免重复身份说明，群聊、观察与代发仍能辨认来源，运行详情按需查看。

### Requirement: 会话名称符合读取者视角
#### Scenario: 主人、助手和观察者读取同一私聊
- **WHEN** 用户或 Agent 查看未改名的站内私聊
- **THEN** 参与者看到对方姓名，观察者看到双方姓名；会话查询与 Inbox 一致，自定义标题、外部渠道名、群名与稳定身份不受影响。

## 范围与非目标

范围为 Web 官网、认证、首次安装/创建引导、登录后主要页面、头像元数据与会话显示名，以及配套 PA/Global 引导内容。没有重做原生 iOS UI、执行运行时或权限模型。没有授权生产部署、发布新安装包或自动合并 PR；当前公开 v1.0.3 与本分支配置协议不匹配的问题单独记录，不能把本地候选安装成功称为公开发布完成。
