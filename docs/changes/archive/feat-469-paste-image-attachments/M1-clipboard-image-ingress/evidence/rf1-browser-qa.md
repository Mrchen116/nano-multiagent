# RF1 Browser QA — 页面错误所有权隔离

## 环境

- Browser: bundled Chromium 148.0.7778.96
- Viewport: 1440×900
- Entry: worktree 隔离 IM + Gateway 的真实 `/chat/:conversationId` 页面
- IM: `http://127.0.0.1:49905`
- Source conversation: `ef2bc9d2f3544dcb95c16147df86e989`
- Target conversation: `6ba0dde4726842278730267b0baedf1e`

测试通过 Playwright `route.fetch()` 请求真实 IM endpoint，只延迟将真实响应交还页面，以确定性制造两个异步竞态；未伪造 endpoint 的状态码或 response body。

## 场景 1：附件失败后，并发文本发送成功

1. 在 source conversation 同时发起附件上传与文本发送。
2. 先向页面交还上传 endpoint 的真实 413 响应。
3. 确认附件错误 toast 出现。
4. 再向页面交还消息 endpoint 的真实 201 响应。
5. 确认文本消息已出现，附件错误 toast 仍可见。

结果：`uploadStatus=413`，`sendStatus=201`，`alertVisibleAfterSend=true`。

证据：`rf1-concurrent-send-toast.png`。

## 场景 2：切换会话后的迟到附件失败

1. 在 source conversation 发起附件上传并暂缓向页面交还响应。
2. 导航到 target conversation，等待目标会话加载完成。
3. 向旧页面请求交还真实 413 响应。
4. 确认 target conversation 没有出现附件错误 toast。

结果：`uploadStatus=413`，`targetAlertCount=0`。

证据：`rf1-switched-conversation-no-toast.png`。

## 诊断

- Console errors: 2 条刻意触发的 413 resource errors。
- HTTP failures: 2 个刻意触发的附件上传 413。
- Failed requests: 0。
- 产品布局、toast 视觉和附件 chip 语义未改变。
