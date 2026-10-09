# Design validation — 2026-10-05

## 边界

本记录验证 HTML 评审原型的导航与视觉，未验证 SwiftUI、iOS 键盘、真实消息/管理写入或免费签名。原型的搜索、保存、上传、系统分享和数据均为标出的演示；它表达信息层级和关键操作路径，不实现网络契约。真实产品的全部行为以 spec/coverage 和 M1 退出标准为准。

## 当前基线

代码基线 `e6a5c0ea5`（首文档提交 `ae625313c` 不改产品代码）。在 `/tmp/nano-feat578-design` 建独立 IM/Gateway，随机端口与独立数据库、node identity、workspace；Vite 临时端口 58782。登录脚本自带测试用户，未修改生产账号。

当前浏览器会话边界要求 `IM_BROWSER_ORIGINS` 显式包含临时 Vite origin；首轮未设置时得到 403 `browser origin not allowed`，随后仅给本次测试栈配置精确 origin。短 shell 启动的进程会随宿主回收，最终用 `tmux feat578-design` 持有，清理由本 chat 执行。

本轮实际 Web 图片（均为当前渲染，不是历史原型）：

- `output/feat578/current-web-chat-600.png`：四个底部入口，聊天分类 All/People/Agent/Group/Network；原型据此纠正分类，未创造独立“未读”分类。
- `output/feat578/current-web-agent-600.png`：实际配置分组与固定工作模式；源代码核对 single_thread/global、MENTION/ALWAYS/NO_REPLY，原型同步修正。
- `output/feat578/current-web-me-600.png`：浅灰表面、分组列表、资料/设备/账号/策略/公司/语言/退出。原生沿用信息归属；账号从头像单一进入，采用原生 grouped form。

截图为本机缓存，不提交；审查者可在本机按上述路径读取，或启动本 unit 的 `prototype.html` 复查。它们不证明生产部署版本已更新。

## 原型实际走查

通过 CUA 实际浏览器渲染并点击：

| Viewport / 场景 | 路径与观察 | 代表证据 |
|---|---|---|
| 430×932 聊天 | 四入口→聊天→审批→本次允许→已提交等待确认→返回；输入区保持底部，详情隐藏全局栏 | `output/feat578/prototype-chat-430.png` |
| 430×932 任务 | Tasks→计划图→节点→回聊引用；引用出现在待发草稿，未发送 | `output/feat578/prototype-task-430.png` |
| 430×932 Work | Agent→工作记录→子执行，主执行返回与过程明细入口可见 | `output/feat578/prototype-work-430.png` |
| 390×844 配置 | 长表单滚动到底可操作保存；冲突反馈与重读入口可辨认 | `output/feat578/prototype-config-390.png`、`prototype-config-bottom-390.png` |
| 390×844 通道 | Agent→通道→飞书→删除确认→删除回执；不将提交等同于已停止 | `output/feat578/prototype-delete-390.png` |
| 600×900 我的/权限 | 管理入口无挤压；普通成员策略字段禁用且无保存和容量入口 | `output/feat578/prototype-me-600.png`、`prototype-readonly-600.png` |

一次修正：长聊天 flex 子项缺少 min-height:0，内容会挤压底部 composer，已修正后截图；演示确认按钮嵌套引号导致 dialog 未弹，已转义后真实点击复查通过。演示控制标签改为不可断词分组。宽度先由 DOM 核对实际 CSS viewport，再目视截图，未以 DOM 替代视觉。

尚未验证：真实软件键盘、中文 IME、Dynamic Type、VoiceOver、系统照片/文件/Share Sheet、后台恢复、授权撤销、签名与安装。这些保留为 M1 的原生客户端/真机验收，不能从 HTML 推断通过。

最后复查：390×844 聊天分类全量排布可见（`output/feat578/prototype-list-390.png`）；工作模式、群策略与 feature 文案按当前代码纠正，未改变布局。

## R1 修订复查

- 普通成员身份 → Agent → 日常助手（single_thread）：页面只有公开说明与发消息，无 Work；实际截图 `output/feat578/prototype-single-thread-fixed.png`。
- 同一身份 → 调研 Agent（global）→ 工作记录：主执行/子执行列表仍可进入；实际截图 `output/feat578/prototype-global-nonowner-fixed.png`。
- 复查使用实际浏览器 600px viewport、430px 演示内容宽度；两条受影响路径均点击并目视，无新增布局遮挡。其他已验原型区域未改。
