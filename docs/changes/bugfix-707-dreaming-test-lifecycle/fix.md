# bugfix-707: 自动 Dreaming 轨迹回归等待实际会话释放

## 原始报告

> 主分支为啥有失败？能修吗？

本问题来自 bugfix-706 本地验证；本 unit 修复独立的后台回归不稳定性，保留日期实现。

## 现象 / 复现

主分支 `43cc90051` 在本机运行 dreaming-runtime.test.ts：自动整理用例报 `RpcError: generation_changed`，其余五项通过。单独重跑自动用例又通过，说明是时序相关失败。原始日志 `/tmp/bugfix706-main-baseline.log`、单用例通过日志 `/tmp/bugfix707-dreaming-repro.log`。

同一提交 GitHub CI（run 41656197526）及前两次 main CI 均成功；不能把本机失败表述为主分支远端 CI 失败。上轮同时运行前端、构建、后端及隔离起栈，原生运行时测试还出现资源竞争下的 deadline/timeout；不把全部失败推断为一个产品缺陷。

目标：自动整理完成后，回归测试在真实临时会话释放后核对其完整持久轨迹与重启一致性；不放宽断言、不吞掉 generation_changed、不扩大生产 deadline。完整本地后端复验隔离执行并限制 worker 数量，检查是否仍有独立失败。

## 根因

自动用例由 `326dac00ed` 加入，沿用手动用例的完成判断。手动工具调用等待维护 Promise 完成；自动路径只轮询 review.status=completed。Dreaming 的 apply 先保存 completed，再提交进度、写入应用回执，随后 execute 才释放 handle。测试观察 completed 并不代表临时 session 已释放。

NativeTrajectory 正确地把 live session 的释放报告为 generation_changed，防止跨代读取混合数据；本测试却在自动释放边界打开 follow，偶发拿到该错误。保留这一生产边界以及原有应用结果、工具权限、原始输入、宿主回执与重启轨迹相等断言；用 fixture 内公开 session/disposed 事件确认该临时会话已经脱离 live store，再读取持久轨迹。无需改变生产状态、提示词、来源或 DSH 接入。
