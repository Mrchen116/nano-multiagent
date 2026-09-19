# refactor-568: Gateway 工具事件投影单一归属

## Relations
- Depends on: 无
- Related: refactor-480、refactor-564；不进入 bugfix-567 入站附件修改范围。

## 原始诉求
见 [original-request.md](original-request.md)。用户授权自主选择、建立 unit、完成修改并提出 PR。

## 澄清记录
无待决用户问题；以下是 Agent 基于扫描证据选择的内部重构范围。

## 现状痛点
来源报告：[architecture snapshot](../../research/architecture-reviews/architecture-review-20260919-133016-c5f1d5620.html)，基线 `c5f1d5620c6323821a430fc3d53feefeb180fd89`（dirty，报告记录完整清单）。observer 的 shadow 和 live 分支分别构建工具 start/end payload，重复写入/删除 running_tool_calls；异常终结又分别重建失败投影。修改 presenter 透传或终态规则时必须跨分支核对，实时和持久化可能漂移。

## 目标状态
工具事件解释、在途状态和异常清理由同一内部 module 负责；observer 继续负责路由、shadow 写入顺序和 await/detach。不是按文件大小机械拆分。不修改 Kernel、IM 协议、数据库或 UI。

## 用户侧验收标准（不变性）
### Requirement: 工具过程和结果可回看
#### Scenario: 正常与失败工具
- **WHEN** 用户请求 Agent 执行工具并查看回复或历史
- **THEN** 工具名称、参数摘要、展开 detail、emoji、完成或失败原因及权限 verdict 与重构前一致。
### Requirement: 中断可收口
#### Scenario: 运行中工具被终结
- **WHEN** 正在执行工具的运行被中断
- **THEN** 工具停止转圈，保留原参数与展示信息，已完成工具不被改写。
### Requirement: 外部历史不依赖 IM 在线
#### Scenario: IM 离线与恢复
- **WHEN** 外部聊天运行经历 IM 离线并恢复
- **THEN** 工具历史与原有 shadow 恢复语义一致；实时与历史的现有字段省略规则保持不变。

## 影响范围
Gateway runtime_delivery 内部工具投影和现有 observer 回归；保留其他事件族、权限绑定和发布路径。

## 迁移与回滚策略
纯内存职责迁移，无数据迁移。保留工厂调用契约和 running_tool_calls 注入观察面；一条提交回退产品代码即可恢复旧实现。
