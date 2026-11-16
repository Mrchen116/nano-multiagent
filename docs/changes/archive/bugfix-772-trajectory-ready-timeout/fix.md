# bugfix-772: 轨迹首帧等待有界失败

## Relations

- 原始能力：`feat-583-native-dsh-trajectory`；配对预热：`bugfix-704-agent-pages-performance`。
- Current：`docs/specs/im/agent-work.md` 的“原生轨迹在查看时读取，连接状态如实呈现”。

## 原始报告

用户原话：“这是咋了”“刷新也一样的。你准确定位到具体问题”“是不是跟我这个有关系”（附代理配置聊天）。“所以能做修复并验证码”。
截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-7ad49e15-d033-4e4f-8d99-e94430d450d5.png`。

追加纠正（PR #528 未合并时）：用户针对手动“重新读取”指出“不能自动吗，为啥要用户按这么蠢”。本轮据此将首帧超时恢复改为有界自动重读，无须用户完成第一次恢复动作。

Agent 对本次修复的解读：修复已确认的无限首帧等待，并验证超时反馈、重新读取与正常读取。没有合并或生产部署授权。

## 现象 / 复现

Web 查看 Dreaming 原生轨迹时持续加载；刷新无效。生产轨迹文件存在且执行 completed。浏览器 WS 握手成功但未收到业务首帧；同版本隔离读取成功。诊断操作误触发旧 DSH 致命异常，终止并由 supervisor 重建后，同代理配置的原页面及整页刷新均恢复。

确定性复现：真实 IM 接受 browser/node 两侧观察 WebSocket，但节点不发送 ready。配对期限过后浏览器仍连接且继续等待。须覆盖两种连接先后顺序。

证据边界：旧 DSH 内部具体等待点及最初触发因素未知；恢复对照指向进程状态，不能据此证明或排除代理曾参与触发。本 unit 修复无限等待，不能声称解决未知的 DSH 内部故障。

## 根因

`apps/im-server/src/trajectory.ts` 在 browser/node 配对完成时清除唯一计时器；配对成功不等于 runtime 完成 `trajectory.prepare`。`apps/node/src/trajectory.ts` 只有 prepare 返回才发送 ready。因而双方握手后、ready 前缺少失败出口，前端没有 close/error 就持续 loading。

最初只读轨迹设计（feat-583 design 的 IM/Node/runtime 节）要求临时观察连接受现有授权约束、关闭回收、读取不激活 Agent。`96d664a1fcc37fbb1e97deabcdd4c646f50f3ee6` 为 bugfix-704 引入页面预热，计时器负责未认领票据，双方配对即取消；测试覆盖配对与未认领过期，却没有覆盖配对后 runtime 不返回的阶段。该提交是当前“配对即取消”的来源，不认定它是首次发生无限等待的提交。

修复必须保留：一次性票据与未认领过期；两种配对顺序；已准备首帧的预热复用；ready 后慢速分页和实时更新没有固定短期限；退出/撤权仍回收连接；重新读取不重新执行任务。不重启生产运行时、不改 DSH 私有实现、不更改代理。

## 本次审查安排

唯一 milestone：M1-fix。

| 必须回答的问题 | 能力 | 方法 |
| --- | --- | --- |
| 首帧一直不返回能否有界结束并允许新观察连接，正常 ready 是否解除期限 | 独立 change-code-review | 真实 IM 子进程与 WebSocket 回归；已有票据/权限/分片回归保留；最终契约一并校对 |
| 用户能否辨认超时并操作重新读取 | frontend-experience-review 自检，独立审查者核实证据 | 隔离真实 Web 页面受控首帧故障、实际点击恢复；明确受控节点与真实 DSH 的证据边界 |

## 修复

IM 继续保留原有 15 秒未配对/未认领期限。两端配对后，如尚无 ready，切换为 30 秒首帧等待；超时以 1013 和可读原因关闭两侧连接，并走现有 observer 清理。收到 ready 且浏览器已认领时取消计时器。浏览器复用已有错误提示和重新读取入口；初次读取失败隐藏 iframe 的过时加载占位，已初始化后的网络错误标为 interrupted 并保留已有内容。首帧超时后由浏览器间隔 1 秒自动申请新观察连接，最多额外尝试 2 次；恢复中说明正在自动恢复，耗尽后再显示失败与手动重读。离开视图清除待发重试，权限拒绝不自动重试。不更改 DSH 或代理。

准备阶段超时只能结束观察连接；如果旧 DSH 内部仍不返回，本次修复不重启该进程，也不宣称强制取消其底层等待。既有 Node 在迟到 prepare 返回后会关闭失效观察。

## 验证

- Red：同一新增测试在修前真实 IM 子进程上，两端配对后 35 秒未关闭，抛出 AbortError；`/tmp/nano-772-red.log`。
- Green：`pnpm exec vitest run apps/im-server/tests/e2e/trajectory.test.ts apps/node/tests/trajectory.test.ts`，2 文件、11 测试通过；两种配对顺序超时关闭、新观察重试收到 ready、成功后静默 31 秒仍可读。`/tmp/nano-772-green.log`。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime` 通过；Python 非 E2E 136 passed，ruff check/format 通过。
- Web 新增可见状态回归在修前因错误态 iframe 仍可见而失败（`/tmp/nano-772-ui-red.log`），修后 8 项轨迹组件测试通过（`/tmp/nano-772-ui-green.log`）。
- 隔离浏览器受控首帧故障在 30 秒显示超时并隐藏旧加载画面；解除阻塞并点击重新读取后，真实 DSH 约 2.6 秒返回 ready，同一 Dreaming 轨迹内容可见。
- 完整门禁、独立审查与证据边界见 [review.md](review.md)。

### 测试策略

扩展既有 `apps/im-server/tests/e2e/trajectory.test.ts`，从真实 HTTP/WS 接口观察首帧超时和恢复，不读取私有 timer。原有预热复用、未认领票据、权限撤销、分片和节点代理测试 keep。新增一个连贯测试承担此前未覆盖的“配对成功不等于 ready”失败原因；不新增平行的前端计时器测试。一次性浏览器夹具与截图在本机保存，夹具运行结束删除，不提交生产轨迹副本。
