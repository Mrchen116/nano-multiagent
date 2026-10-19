# R13 隐私提示交互验收

结论：PASS（本轮限定的隐私提示呈现及处理路径）。

## 范围与方法

在隔离 worktree 的真实 IM 服务 `127.0.0.1:53808` 上，以独立 CUA 浏览器 tab 操作；桌面截图为 1280×720。使用 R12 可丢弃测试账号与 binding，注入 4 条明确标记为合成证据的 incident（共 7 次请求、2 位联系人），不运行 LLM，不把 fixture 当作真实分类或通知证据。测试节点离线为既有环境状态，不纳入本轮问题。未修改主测试账号的 5 条既有记录。

窄屏使用主执行者同轮保留的 513×827 实际 IAB 截图，审查者已直接查看图片；这是共享证据，不宣称独立重跑或 390px 覆盖。

## 实际路径与结果

| 路径 | 观察 | 结论 |
|---|---|---|
| 默认折叠 | 单个紧凑摘要显示 Privacy protection / Blocked / 7 requests / 2 people | PASS |
| 联系人聚合 | 展开仅显示初晴 R11 与林悦两组；林悦 6 requests，摘要显示第三条最新理由 | PASS |
| 完整证据 | 林悦详情保留三条原始理由，三条独立原消息链接，重复次数 3 与 2 可见 | PASS |
| 来源与返回 | 点击第二条定位 `r13_message_2`，显示 Original message located；Back to personal assistant 返回 canonical PA | PASS |
| 操作层级 | Got it 独立可见；Future requests 内才显示 misunderstanding、block 及仅限制对助理请求、不影响本人聊天的解释 | PASS |
| Got it | 初晴提示消失，摘要变为 6 requests / 1 person；成功提示明确 privacy protection stays on | PASS |
| 无策略副作用 | `after-dismiss.json` 与 before 的 policy、blocks、source_events 完全相同；仅 incident 4 变 dismissed，其余三条 open | PASS |
| Block 全组 | 对林悦执行 block 后三条 incident 全变 blocked，actor block 写入，policy revision 变 2；隐私摘要消失 | PASS |
| 保留本人聊天 | block 后仍能通过会话列表打开原群聊并阅读两条来源消息 | PASS |
| 桌面与窄屏 | 桌面长理由正常换行、详情可滚动；513px 保留截图显示摘要紧凑、展开文案换行、按钮处于视口内，无可见横向溢出 | PASS |

## 证据

本地原始证据目录：`data/acceptance/feat-616/r13-privacy-notices/`。

- `collapsed.png`、`expanded-details.png`：独立桌面截图。
- `original-message.png`：第二条来源定位。
- `after-dismiss.png`、`after-block.png`、`chat-after-block.png`：真实操作后的界面。
- `before.json`、`after-dismiss.json`、`after-block.json`：持久化状态快照。
- `main-collapsed-en.png`、`main-expanded-en.png`：主执行者的 513×827 窄屏证据，审查者已查看。

## 证据边界

本轮没有重新验收 LLM 隐私判别、通知生成、解除屏蔽后的新请求，也没有制造部分失败；不将以上分支纳入 PASS。misunderstanding 入口与影响说明已检查，未执行其策略变更。未发现本轮实际路径的阻塞体验问题。
