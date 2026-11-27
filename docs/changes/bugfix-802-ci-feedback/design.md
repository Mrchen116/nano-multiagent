# bugfix-802 实现记录

本文在实现后整理。基线为 develop 的 `3b4c0f022`。

- 独立的 PR job 检出代码，用 runner 自带的 Python 3 将 PR 分支名传给标准库脚本。脚本退出码决定 job 结果。原有后端和 iOS 检查照常调度。
- 两个 Vitest 用例分别持有阶段列表，以单调时钟记录阶段开始时刻。Vitest 的 onTestFinished 钩子从相邻时刻计算各段耗时，输出一行带有 test-phases 标记的 JSON。名称来自测试代码中的固定字符串。插件用例仍保留原有 pending RPC 失败诊断。
- 产品路径、断言和基线超时预算均沿用。No spec delta。开发流程中的 CI 说明已更新。回退本次提交即可恢复原来的步骤和日志。
