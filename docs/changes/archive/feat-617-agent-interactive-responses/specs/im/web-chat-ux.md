# IM web-chat-ux Specification (delta for feat-617)

## ADDED Requirements

### Requirement: 通用交互支持连续本地探索

#### Scenario: 多种组件、计算与动作
- **WHEN** 用户改变参数、切换视图或操作步骤与重置
- **THEN** 相应内容立即联动，不需要每次调用模型，不强制表单或单个提交按钮。

#### Scenario: 提问后继续探索
- **WHEN** 用户将当前结果交给 Agent 解释，随后继续改变条件
- **THEN** 界面仍可操作，新请求保留当时状态；查询或工具失败不抹掉已可读的内容。

#### Scenario: 查询与业务动作边界
- **WHEN** 交互调用应用提供的查询或修改工具
- **THEN** 读取遵守当前用户权限，修改由明确动作触发；只显示实际返回的接收或执行结果，不将请求入队报为业务完成。
