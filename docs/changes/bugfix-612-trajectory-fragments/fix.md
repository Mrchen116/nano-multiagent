# bugfix-612：完整原生轨迹的传输分片与重组

## Relations

- Related: feat-583, feat-589

## 原始报告

用户截图显示 Personal Agent 的子执行「核对其他面试知识工程论述」报 `trajectory_read_failed: trajectory_frame_too_large`。

用户原话：

> 我要看这个subagent才刚启动，也超过1M了？
> 那查一下这次到底是哪部分超限了，我觉得不合理，既然是单帧限制，那单帧就不应该超吧
> 那修一下我们这层的分片和重组，保留完整轨迹，拿这次 subagent 的数据验证。

附件引用：`codex-clipboard-10dc227e-5939-47e9-926a-42a5f403ecf9.png`（对话附件，不提交图片缓存）。

## 现象 / 复现

生产 Mini 的原生子会话 `b64d6e64-e0bb-4fe3-accf-af3cb479d29d`（父会话 `8d36509c-91d0-423d-97d4-2f6419162253`）于 2026-10-15 11:38:13 +08:00 创建，fork 继承 2018 条事件。

只读解码生产持久日志并按已安装 DSH 的窗口规则重建启动初期 `cursor=2029` 的 opening：224 条事件，快照至少 1,256,641 bytes；其中继承记录 1,252,187 bytes，本次新增记录 3,952 bytes。缺少当时实时 projection/assistant baseline，因此这是重建的体积下限，并非声称捕获了截图对应的原始网络帧。最大单条事件仅 137,909 bytes。用线上同一 `TrajectoryStream` 读取重建 opening 已复现原错误。

退出标准：该真实会话的 opening、后续事件与向前分页能完整通过 Nano 传输，重组后与原始 DTO 相同；每个物理消息仍在 1 MiB 以内；慢观察者、关闭、身份撤销和附件授权继续生效。

## 根因

feat-583 的意图是只读、按需检查官方原生轨迹，观察流独立于业务 ACK，且慢观察者只终止读取。feat-589 明确保留 fork 继承历史，不能通过过滤历史、删除字段或缩短上下文来消除报错。

引入坏行为的提交为 `7e22a91d28`：`TrajectoryStream` 将 DSH 完整 opening DTO 当成必须小于 `1 MiB - 1 KiB` 的传输帧；只按消息数量划页的官方 opening 可以自然大于该上限。原实现只将多个完整帧装入有限批次，没有拆分单个 DTO。Node/IM 专用 WebSocket 对完整响应同样使用 1 MiB 限制，因此 unary 历史分页也需要一致的分片处理。

修复应保持 DSH 的公开读取与原生 DTO，不 fork/patch DSH，不修改 session、surface、分页或执行语义。原始上下文、工具结果、附件元数据和继承事件都须完整保留；附件字节仍经过既有来源授权。

## 修复

M1-fix 在独立 worktree、`codex/bugfix-612-trajectory-fragments` 分支完成；主仓已有 tracked/untracked 内容保持原状。

共享的 browser-safe `@nano/product-contracts/trajectory-wire` 提供 `encodeTrajectoryValue` 和 `TrajectoryValueDecoder`：小 DTO 原样传输，大 DTO 编码为带 transfer/index/final 的有序 JSON 片段，分片携带原 observer/request 身份。保守地按 UTF-16 单元的最坏 JSON 转义成本确定片长，保证 Unicode、代理对和再次 JSON 转义后也不会超过物理预算。重组仅发布完整 DTO；乱序、重复、缺失和身份变化报错，离开观察代际时清理未完成片段。

- Integration 的 native opening/live frame 在进入原有两批次队列前分片。一次较大 DTO 的后续片段等待消费者腾出容量，保留 5 秒积压期限；正常消费不会因同一 DTO 自身需要超过两批而被判慢。新原生帧造成的队列溢出仍按既有规则终止 observer。
- Viewer 在跨 `next` 批次重组后将完整原生帧交给官方客户端。没有复制官方分页、事件解释或 surface 逻辑。
- Node 和 IM 对大型 unary 响应（包括历史分页）复用同一编码。专用 WebSocket 逐片等待 send callback，保留每个物理消息和发送积压的 1 MiB 上限。
- IM 先重组可信节点响应，再执行既有附件来源授权，再对浏览器发送；分片不能旁路附件检查。每片仍受观察身份和资格约束。
- 宿主页面保持请求挂起直到最终片段，连接中断时仍通知所有未完成请求。查看器负责 response 重组，宿主不解释 DSH DTO。
- 新增纯浏览器 export，精确加入既有架构 allowlist；包之间的依赖方向及 DSH 公开出口边界不变。

## 验证

修前在已构建 product-contracts 的基线运行新增大 opening 回归测试，得到实际 `trajectory_frame_too_large` 红测。

永久回归保护：扩展 `trajectory-stream.test.ts`、viewer `transport.test.ts`、IM `trajectory.test.ts` 和前端 `agent-trajectory.test.tsx`，分别保护队列/关闭、跨批次发布、来源授权和中断通知；既有慢观察者、冷读取不激活与身份撤销测试保留。新建 product-contracts codec 测试保护 Unicode/转义/交错与错误边界；Node 专用 socket 之前没有所属覆盖，因此新增 Node `trajectory.test.ts` 验证实际 socket 逐片发送。没有提交生产原始数据或一次性验证脚本。

### 本次真实子 Agent 数据

只读获取生产 `.jsonl.zstd`，在临时目录用已安装 DSH 的公开 format catalog 解码。隔离 fixture 仅改 child header 的 workspace cwd，并为其父级建立隔离的空只读 header/产品 binding；原子会话全部 2097 条逻辑事件保持原样。独立 DSH 进程、IM 临时数据库/端口、节点 identity 和 socket 均由测试 fixture 管理，不执行生产任务，也不修改生产持久状态。

- 重建启动期 opening：1,256,641 bytes → 2 个 runtime 批次，最大 955,285 bytes，重组 DTO 深相等。
- 实际 cold follow → NodeTrajectory → IM 专用 WebSocket → MessagePort → viewer transport：opening 238 条事件，向前 7 页，完整取回 2097 条事件（含 2018 条继承事件）。最大 WebSocket 消息 973,000 bytes。
- 原始与重组事件 SHA-256 均为 `768d07f78777a6ac3cabfe8c6d641316773dd6b3fef215f3bde46795295f2ed7`（应用既有 inline-image 权限清理后的同一 DTO 表示）。节点 heartbeat 同时返回 ACK。
- 真实数据仅为临时验收材料，不进入永久测试集。完整 raw fixture 和一次性 harness 位于本机 `/tmp/nano-612-*`；脱敏结果 `/tmp/nano-612-real-result.json`。

### 浏览器与常规检查

使用 Playwright CLI 打开本机原生 viewer bundle 的 opaque iframe，连接同一授权观察 socket 的临时测试桥。真实子会话首屏进入 `ready`，能看到工具与最终助手输出；点击「加载更早的历史」后仍为 `ready`，继承的 runtime-context 记录可见，无 `trajectory_frame_too_large` 或历史读取中断。此 browser harness 验证原生组件与 MessagePort 接收；宿主 React 的断线请求跟踪由前端回归测试验证，不将测试桥称为生产页面验收。

- 浏览器证据：`output/playwright/bugfix-612-real-opening.png` 与本机 `/tmp/nano-612-browser-*.log`，不提交截图与原始页面内容。
- `pnpm build`、`pnpm typecheck`：通过。
- `pnpm test --exclude '**/trajectory-real-replay.validation.test.ts'`：87 files / 323 tests 通过；排除的是等待人工浏览器操作的临时 harness，交付前移除。
- frontend `npm run test`：96 files / 887 tests 通过；`npm audit --audit-level=critical` 无漏洞；`npx vite build` 通过。
- `pytest -m 'not e2e' -q`：56 passed / 31 deselected；ruff check/format 与 docs-check 通过。docs-check 使用仓库已有 Python venv 的 PATH。
- 定向 runtime/transport/IM/Node/codec 回归：16 tests 通过；宿主前端轨迹：4 tests 通过。

未修改、重启或部署生产服务；PR merge 与生产部署分别由后续明确授权执行。
