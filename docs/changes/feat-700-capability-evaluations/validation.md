# feat-700 Validation

日期：2026-11-02。本轮验证公共页面与 case 建档，不是正式能力评分。用户确认待完成。

## 代码与边界

- Node v24.22.1：evals TypeScript 检查通过；Node/integration 构建通过。
- `pnpm exec vitest run evals/ui packages/dsh-integration/tests/observation-only.test.ts packages/dsh-integration/tests/runtime-profile.test.ts`：5 文件、9 tests 通过。目录折叠窄改后重新执行 evals/ui 4 tests。
- docs-check：282 maintained Markdown sources、68 required routes 通过；git diff --check 通过。
- runtime dependency contract：13 tests 通过。无 DSH private import、内核 fork 或第二套执行循环。
- 已有 runtime-profile 测试 keep，保护普通执行与恢复未退化；新 observation-only 在真实公开 RPC seam 保护归档不触发绝对路径恢复副作用；导航延迟关闭回归在 DOM seam 保护切换 case 不被旧观察流覆盖。检索现有 tests 未有这两种失败原因的同因保护。
- catalog/server 测试保护固定材料接线、已有证据不冒充新执行和本地读取 capability。截图与单次原件哈希仅保存在 ignored output，不进入永久测试。

## 实际页面

- 公共入口：<http://127.0.0.1:59335/10545764-3b0f-4a2c-82d7-edd83324bac9/>；viewer 状态 `output/capability-eval-viewer/state.json`，日志 `output/eval-ui-viewer.log`，运行在 tmux `capability-eval-ui-final`。
- CUA 实际查看酒店照片固定输入、酒店/看板用户参考原图、会议选择步骤和五项判定；页面明确显示已有独立现场不是重新运行结果。
- CUA 打开 Memory 冷答题与 Dreaming 第 1 批，确认原生轨迹加载、真实请求和工具记录可读。默认折叠阶段后两项能力与三个 UI case 同屏可见；展开可访问18阶段。截图 `output/eval-ui-evidence/common-viewer.png`。
- 原 Memory 归档 `longmemeval-window-one-case-20261030-005908` 的 agent-work、analysis、run、trial-summary 共439文件，读取前后 SHA-256 无变化；清单与比较在 `output/eval-ui-original-{before,comparison}.json`。
- 默认页面仅建档，零模型调用。已有 Memory 轨迹仍包含原实验自己的错误和结果，未修改或重新判分。

## 保留服务与边界

按用户“测试完不要关服务”的明确要求，公共 viewer 和原三个产品服务保留，开发 worktree 保留。关闭公共 viewer 可按 state.json 的本轮 pid 发 SIGTERM，只释放它自己的观察流和 DSH；不会停止以下已有产品服务：

- 会议：<http://127.0.0.1:50985/chat/c_f904c9b5844a>，`output/runtime-openiui`。
- 酒店：<http://127.0.0.1:51193/chat/c_4718644999af>，`output/runtime-openiui-clean-hotel`。
- 看板：<http://127.0.0.1:51507/chat/c_b101f7e09046>，`output/runtime-openiui-clean-dashboard`。

这些是上一轮独立上下文现场；看板手机图表过小等已知问题没有冒充修复或通过。本轮不提供正式自动运行/评分，fresh-context 是已记录的执行前协议，尚未交付自动隔离器。未提交运行数据、日志、密钥、PID或截图缓存。
