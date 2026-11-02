# 公共评测页面

从之前 Memory 单题原生轨迹入口提取的公共页面层，按能力、实验、case、阶段展示材料与证据。当前登记 Memory 与 Intelligent UI；后续 Agent 并行等能力可以添加自己的 case 和阶段，无须复制页面。

页面层不决定各能力的执行与评分协议。Memory 继续使用 `evals/memory` 的准备、冷答题和评分；Intelligent UI 本轮已建四个 case，尚未新增自动运行与评分。不要将“建档”“已有证据”或“原生轨迹可读”当成评测通过。

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm eval-ui
```

终端返回本机地址。默认展示 case 库，零模型调用。要查看之前的单题 Memory 归档：

```sh
pnpm eval-ui --memory-archive /absolute/path/to/experiment --output /absolute/path/to/viewer-state
```

旧归档应包含 `agent-work/{gateway.yaml,metadata.json,runtime/}`、`analysis/metrics.json`、`run/report.json` 和 `trial-summary.md`。此适配器只接受旧版一归档一 case，避免将同一份 session 错配给多题。运行目录必须为本地受控目录，不从网页接受任意文件路径。

归档的 native runtime 会复制到 viewer 自有目录；原件不初始化、不修改。`apps/node` 的显式 `evaluation-archive` 入口只经公开 integration client 建立禁用执行的读取环境。只转发已授权 observer 的轨迹读取和导航，不提供模型或产品工具执行入口。关闭查看器会释放观察流和自己的 DSH 子进程。前端仍复用 `packages/dsh-trajectory-viewer` 的原生组件，不重新解释或渲染 DSH 事件。

`--ui-evidence /absolute/path/to/links.json` 可给 Intelligent UI case 挂接**已有**独立复测现场：

```json
{"hotel":{"url":"http://127.0.0.1:PORT/chat/ID"},"dashboard":{"url":"http://127.0.0.1:PORT/chat/ID"},"meeting-confirmation":{"url":"http://127.0.0.1:PORT/chat/ID"}}
```

这些是已有现场链接，页面明确标注不是本轮新执行。运行目录保存 state.json 供恢复入口，不存入 Git。Ctrl-C 关闭本查看器；不停止这些外部既有产品服务。用户明确要求保留预览时记录入口、目录及后续清理方式。

## 来源与边界

页面布局和原生 MessagePort 桥来自本机 Memory 单题入口（`longmemeval-window-one-case-20261030-005908/viewer`）；原入口与轨迹原件保留。已去除题号、机器路径、固定阶段数及模型请求数等硬编码。共享目录在 `catalog.ts`，页面是 `index.html` / `app.js`，原生轨迹桥为 `native.js`，Memory 归档读取由 `apps/node/src/evaluation-archive.ts` 承担。

本轮不搬迁 Memory 题集、不改变正式分数/协议，不增加并行调度器、公共评分器或自动纠错。没有把实验观察范围扩大成完整产品链路证明。
