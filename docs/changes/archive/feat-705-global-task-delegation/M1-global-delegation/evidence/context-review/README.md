# Global／PA 初始上下文对照审阅副本

打开 [对照网页](index.html)。网页、样式与脚本均随本 unit 提交，可以从本地文件离线查看；角色、层级和视图切换通过页面 hash 工作。

## 内容与证据边界

- 包含 main／PR 的普通 Global、PA 主会话，以及各自一级／二级 subagent 共六组对照；保留完整 System、全行差异、工具定义与逐工具 token 统计、初始消息审阅内容和来源说明。
- 本副本来自现有实际捕获对照页，不从源码重建 System。每份捕获各自的 commit、时间、session、父子关系和原始请求哈希见 [捕获来源](capture-provenance.json)；不同次采样不拼成新的执行链。
- main 基线为0287088be；最新根捕获为4fe6ab6e5，各级沿用未受后续变更影响的原始捕获。其后的2d661b862仅调整Dreaming整理反思，不改变这些主／子会话上下文。本页不包含Dreaming专项System比较。
- 保留全部对照行、空行和未改行。只将本机用户目录前缀替换为 `[HOME]/`，系统临时目录前缀替换为 `[TMP]/`；其余内容保持。审阅副本不是未经处理的原始请求。
- [审阅清单](review-manifest.json)逐份记录原始System与本副本的SHA-256及行数。token数沿用脱敏前实际捕获的o200k_base估算，不是对占位符文本重新分词；不是模型计费值。
- 原始provider/upstream请求、完整日志、截图与历史页面均不纳入Git。网页中相应入口标注“仅本地保留”；当前System审阅文本、diff、token统计与来源说明可随本目录读取。
- 这些是受控初始上下文采样，不代表模型自主选择分工或主动通知行为已经验收。

## 原件定位

原对照页保存在 `/Users/czj/.codex/visualizations/2026/11/03/01a1a053-5049-7c50-84bf-f7834cb78910/global-context-review/`，原始请求还由本 worktree 的 `.cache/feat705-context-capture/` 各阶段manifest定位；均不随本副本提交。

保留预览服务上的原页面为 `http://127.0.0.1:62610/review/feat705-global-context/index.html`，服务停止后以本目录离线审阅副本为准。
