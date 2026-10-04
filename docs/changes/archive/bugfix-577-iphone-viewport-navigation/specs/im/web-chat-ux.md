# IM Web Chat UX Specification (delta for bugfix-577)

## ADDED Requirements

### Requirement: 手机输入与可视区域变化保持界面可操作

Web IM 在手机浏览器与主屏 Web App 中 SHALL 保持输入、导航和页面边界完整；不以禁止用户主动缩放来获得布局稳定。

#### Scenario: 输入聚焦后仍保持页面比例
- **WHEN** 用户在手机登录表单、搜索或聊天输入区聚焦、输入并结束编辑，再切换站内页面
- **THEN** 页面不会因输入动作额外放大或横向裁切，字段和关键操作无需刷新或手动缩小即可使用
- **AND** 聊天文字与高亮保持对齐，用户仍可主动缩放

#### Scenario: 可用高度随浏览器栏和键盘变化
- **WHEN** 手机浏览器栏变化，或用户弹出和收起软件键盘编辑消息
- **THEN** 标题返回、当前需要的输入和发送操作保持可见可用，结束输入后恢复正常布局
- **AND** 列表页一级导航保留安全区；具体会话仍隐藏全局底栏，历史滚动和草稿行为保持

### Requirement: 主屏 Web App 正常站内导航保持应用内体验

#### Scenario: 从未登录入口安装后登录并导航
- **WHEN** 用户将当前IM页面以Web App添加到主屏幕，从图标启动并登录，再在聊天、Tasks、Agents、Me及详情间导航
- **THEN** 站内页面保持应用内体验，不因这些跳转出现覆盖标题、导航或输入区的系统浏览器控件
- **AND** 登录仍返回既有目标页面

#### Scenario: 已登录再次启动
- **WHEN** 用户已登录后重新打开主屏应用，或刷新详情并返回列表
- **THEN** 页面保持可用宽度与高度，登录及路由语义保持，不需要反复重新安装才能继续使用

### Requirement: Web IM 手机换行与发送使用明确分开的操作

手机聊天输入框的键盘换行 SHALL 插入新行，发送箭头 SHALL 发送当前完整内容；不让标为换行的按键直接发送。

#### Scenario: 手机键盘编辑多行消息
- **WHEN** 用户在手机输入框按换行键，包括提及或斜杠前缀正在显示候选时
- **THEN** 输入框保留多行草稿，不自动发送或选取候选；候选仍可点击选取
- **AND** 点击发送箭头发送包含换行的完整消息，中文输入法确认候选不触发发送

#### Scenario: 编辑期间不重复保留底部安全区
- **WHEN** 手机键盘或输入辅助条使可视高度收缩
- **THEN** composer仅保留正常内边距，不额外重复Home指示条留白
- **AND** 收起后恢复正常底部安全区，不要求失焦才能恢复

## REMOVED Requirements

### Requirement: Web IM 移动端输入法回车发送消息

## MODIFIED Requirements

### Requirement: Web IM 桌面与移动端在聊天页保持一致的滚动与交互体验

桌面浏览器与移动浏览器进入同一聊天页，均具备分页加载、composer自动增高、正文可选择、整条复制和eligible fork能力。输入快捷键符合设备输入方式：桌面Enter发送、Shift+Enter换行；手机键盘换行、点击发送箭头发送，候选点击选择。

#### Scenario: 在手机端向上滚动加载历史
- **WHEN** 终端用户在移动设备上打开同一聊天并向上滚动
- **THEN** 同样触发加载更早消息,且阅读位置保持稳定

#### Scenario: 在手机端长按 Agent 回复 fork
- **GIVEN** 当前消息是符合既有 fork 资格的 Agent 回复
- **WHEN** 终端用户长按该消息的普通区域并选择“从此处分支”
- **THEN** 触发既有 fork 流程并给出明确反馈
- **AND** 长按该消息正文仍保留系统文本选择能力

#### Scenario: desktop 与 mobile 使用同一消息动作资格
- **WHEN** 同一条消息分别显示在 desktop toolbar/context menu 与 mobile context menu
- **THEN** 整条复制和 fork 的出现、enabled、disabled 与 in-flight 状态一致
