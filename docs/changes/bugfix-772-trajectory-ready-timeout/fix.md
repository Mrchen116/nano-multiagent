# bugfix-772: 轨迹首帧等待有界失败

## Relations

- 原始能力：`feat-583-native-dsh-trajectory`；配对预热：`bugfix-704-agent-pages-performance`。
- Current：`docs/specs/im/agent-work.md` 的“原生轨迹在查看时读取，连接状态如实呈现”。

## 原始报告

用户原话：“这是咋了”“刷新也一样的。你准确定位到具体问题”“是不是跟我这个有关系”（附代理配置聊天）。“所以能做修复并验证码”。
截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-7ad49e15-d033-4e4f-8d99-e94430d450d5.png`。

Agent 对本次修复的解读：修复已确认的无限首帧等待，并验证超时反馈、重新读取与正常读取。没有合并或生产部署授权。

## 现象 / 复现

Web 查看 Dreaming 原生轨迹时持续加载；刷新无效。生产轨迹文件存在且执行 completed。浏览器 WS 握手成功但未收到业务首帧；同版本隔离读取成功。诊断操作误触发旧 DSH 致命异常，终止并由 supervisor 重建后，同代理配置的原页面及整页刷新均恢复。

确定性复现：真实 IM 接受 browser/node 两侧观察 WebSocket，但节点不发送 ready。配对期限过后浏览器仍连接且继续等待。须覆盖两种连接先后顺序。

证据边界：旧 DSH 内部具体等待点及最初触发因素未知；恢复对照指向进程状态，不能据此证明或排除代理曾参与触发。本 unit 修复无限等待，不能声称解决未知的 DSH 内部故障。

## 根因

`apps/im-server/src/trajectory.ts` 在 browser/node 配对完成时清除唯一计时器；配对成功不等于 runtime 完成 `trajectory.prepare`。`apps/node/src/trajectory.ts` 只有 prepare 返回才发送 ready。因而双方握手后、ready 前缺少失败出口，前端没有 close/error 就持续 loading。

最初只读轨迹设计（feat-583 design 的 IM/Node/runtime 节）要求临时观察连接受现有授权约束、关闭回收、读取不激活 Agent。`96d664a1fcc37fbb1e97deabcdd4c646f50f3ee6` 为 bugfix-704 引入页面预热，计时器负责未认领票据，双方配对即取消；测试覆盖配对与未认领过期，却没有覆盖配对后 runtime 不返回的阶段。该提交是当前“配对即取消”的来源，不认定它是首次发生无限等待的提交。

修复必须保留：一次性票据与未认领过期；两种配对顺序；已准备首帧的预热复用；ready 后慢速分页和实时更新没有固定短期限；退出/撤权仍回收连接；重新读取不重新执行任务。不重启生产运行时、不改 DSH 私有实现、不更改代理或增加自动重试。

## 本次审查安排

唯一 milestone：M1-fix。

| 必须回答的问题 | 能力 | 方法 |
| --- | --- | --- |
| 首帧一直不返回能否有界结束并允许新观察连接，正常 ready 是否解除期限 | 独立 change-code-review | 真实 IM 子进程与 WebSocket 回归；已有票据/权限/分片回归保留；最终契约一并校对 |
| 用户能否辨认超时并操作重新读取 | frontend-experience-review 自检，独立审查者核实证据 | 隔离真实 Web 页面受控首帧故障、实际点击恢复；明确受控节点与真实 DSH 的证据边界 |

## 修复

由实施阶段回填。

## 验证

由实施阶段回填。
