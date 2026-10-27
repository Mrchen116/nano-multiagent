# perf-670: As-built Design

> 按用户选择的快修模式，在实现后根据实际代码与测试整理；没有事前设计门禁或 milestone。

## 实现范围与结构

Follow-up base 为 PR #416 head `2d1dcd25041a3939f2aab34e5e576d2409d6c0db`。复用其工作分支和开发 checkout；原 PR 负责同源 UI 与可选 Vite，本 unit 负责按需构建。

按 codebase-design 方法把输入枚举、内容哈希、共享包构建、成功记录与失败语义集中在 `scripts/e2e_ui.py`。`e2e-up.sh` 仍是唯一服务启动入口，在服务启动前调用 helper；外部无需新增参数。`prepare_ui(repo)` 的接口是“准备好当前 checkout 的两套 UI 或抛错”，不向调用者暴露缓存状态机。

两套 UI 各自拥有 `.cache/e2e-ui/<name>.json`，记录 inputs/outputs 的 SHA-256。输入覆盖源文件树、public、根构建配置、包清单/锁文件、Node 版本、相关构建环境、`.env*`、共享包源码与实际 lib 导出；扫描本地文件，因此覆盖未提交文件和删除，不按 mtime/Git HEAD 判断。根锁文件变化保守重建两套，不做依赖锁切片优化。

主前端依赖 product-contracts；轨迹查看器依赖 product-contracts 与 trajectory-ui。失效时先构建相应共享包，同次准备 product-contracts 只构建一次。仅主前端失效时不构建轨迹查看器。输出也按完整文件树内容验证，捕获缺失 chunk 和其他命令覆盖 dist；成功标记不放在 dist 内。

同 checkout 采用 OS 文件锁串行执行准备，进程退出自动释放。写入记录前校验入口存在且源输入未在构建期间改变；开始重建先移除旧成功记录，失败向上传播。固定 VITE_IM_API_BASE_URL 为空，运行时代理端口不进入缓存键。默认不跨 worktree 复用。

## 验证策略与边界

永久行为测试为 `tests/integration/test_e2e_ui.py`：从真实 helper 命令入口驱动临时文件树，以小型本地构建替身验证实际构建选择、产物、失败状态，不运行模型或昂贵前端构建；原有 `test_worktree_stack_lifecycle_e2e.py` 保留，负责真实服务启动/失败/清理，不重复缓存矩阵。

先用原有无条件构建行为取得失败：仅后端修改后的第二次准备仍执行两套构建。实现后 13 项窄测试通过。真实构建测量和完整运行验证另在本机保存，最终结果见 code-review 与 PR Validation；不把替身测试描述成真实浏览器/模型证据。

已完成的真实测量：首次 16.370 秒、无变化 0.196 秒，日志位于 `/Users/czj/.codex/experiments/pa667-startup/build-reuse-review/`。原 PR 的真实模型/浏览器验收证据保留，本轮不重新消耗模型验证未改变的回复路径。

## 失败、兼容和运维

没有缓存标记的历史产物需要首次构建；依赖安装和后端 build 仍是原有前置条件。构建失败不报 ready；产物/输入无法验证时保守重建或失败，不以旧产物兜底。缓存只说明 UI 构建仍有效，不替代测试或服务健康检查。回滚无运行数据迁移，不新增生产部署动作。

## 文档与用户确认

长期操作说明归并到 `docs/development/worktree-runtime.md`；无业务 spec delta、无 UI 原型或模型 Context 改动。用户原话“测好了再更新pr”授权 Agent 完成验证后交付，优先于默认亲自验收步骤；不声称用户亲自执行测试。
