# bugfix-582: 修复前端依赖审计阻塞

## Relations

- Related: bugfix-493
- Related: bugfix-580

## 原始报告

> CI没过的原因是啥

> 那你先单独一个pr把这个问题分析，解决。

Agent 解读：从 main 建立独立 PR，修复阻塞 PR #326 的前端 dependency audit，保留完整安全门禁和既有测试覆盖；不混入任务删除修复、不合并或部署。本项按 Bugfix lite 的单个 M1-fix 交付，无产品行为变化。

## 现象 / 复现

基线 `d87ffa3d19160d45d309f281b0ace4ff92f55a38` 的前端 lockfile 锁定 `vitest@3.2.7 -> tinypool@1.1.1`。PR #326 的 [Frontend checks](https://github.com/Mrchen116/nano-multiagent/actions/runs/37874571161/job/113640075333) 在 `npm ci` 成功后，`npm audit --audit-level=critical` 返回 1；报告 2 low、2 moderate、3 high、2 critical。后续 Vitest 步骤被跳过。

验收要求：Node 20 下 clean install 可复现；完整依赖树的 critical audit 通过；既有前端测试和生产构建通过；独立 PR 的所有 CI checks 通过。不得使用 omit-dev、ignore、降低审计级别或减少测试来绕过失败。

## 根因

`npm ci` 忠实安装锁定版本。`package.json` 的 `vitest: ^3.2.4` 只能解析到 3.x；2026-10-09 查询 npm registry，3.x 最新仍为 3.2.7，其依赖范围 `tinypool: ^1.1.1` 无法取得 2.x 的安全修复。仅重跑 CI 或重新安装不会改变该依赖树。

上游 [worker options advisory](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3) 的修复版为 tinypool 2.1.1，[run options advisory](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) 的修复版为 2.1.2：已有原型污染可使 worker options 继承恶意值并执行攻击者模块。本仓 tinypool 仅通过测试工具引入，风险位置是开发机和 CI worker；审计结果不等于已经证实公网 IM 可被此漏洞利用。npm 的 2 critical 包条目包含 tinypool 以及受影响的上层 vitest，并不代表两条独立生产入侵路径。

原始 CI 由 feat-388 引入；bugfix-493 在 commit `aad4595fd02e1a7a439c519c5d35305c744f9302` 更新到 Vitest 3.2.7 并增加完整依赖树的 critical 硬门。相关 tinypool advisories 于 2026-10-05 进入 GitHub Advisory Database，新风险被现有门禁正确拦截，属于依赖老化而非任务删除代码回归。必须保留 Node 20、可重复安装、完整 Vitest 覆盖以及开发依赖审计。

[Vitest 4 迁移说明](https://v4.vitest.dev/guide/migration.html#pool-rework) 确认 4.x 已移除 tinypool。registry 显示 Vitest 4.1.11 支持 Node 20 与 Vite 7，且 @vitest/mocker 为已修复版本。优先采用上游支持的升级路径，避免强制覆盖 Vitest 3 的跨大版本传递依赖。

## 修复

仅将直接依赖 Vitest 的范围改为 `^4.1.11`；针对当前 audit 列出的包执行显式 lock-only 更新，未运行批量 `npm audit fix --force`，未增加 overrides。运行环境为 Node 20.20.2 / npm 10.8.2。

| 包 | 原版本 → 新版本 | 风险与处置 |
|---|---|---|
| vitest / @vitest/* | 3.2.7 → 4.1.11 | 移除 tinypool，使用新版 worker pool；同时修复 [mocker 任意文件读取](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)；测试脚本/配置保持原行为 |
| tinypool / vite-node | 1.1.1 / 3.2.4 → 移除 | 已不再被 Vitest 使用；lockfile 无残余节点 |
| @babel/core | 7.29.0 → 7.29.7 | 构建期 [sourceMappingURL 文件读取](https://github.com/advisories/GHSA-4x5r-pxfx-6jf8)，连同受支持的 Babel 内部依赖更新 |
| browserslist | 4.28.1 → 4.29.3 | 构建期 [缓存耗尽](https://github.com/advisories/GHSA-c83g-rgw3-j3cx) 与 [不可信 stats 异常/原型写入](https://github.com/advisories/GHSA-73wf-gq98-2v4g)，刷新受支持范围及浏览器数据 |
| baseline-browser-mapping | 2.10.0 → 2.11.28 | 构建工具依赖的 [无效输入进程终止](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv) |
| esbuild | 0.27.3 → 0.28.2 | [Windows dev-server 文件读取](https://github.com/advisories/GHSA-g7r4-m6w7-qqqr)，仍在当前 Vite 声明范围内；平台二进制同步 |
| nanoid | 3.3.17 → 3.3.20 | PostCSS 依赖的 [零长度 custom generator 死循环](https://github.com/advisories/GHSA-2v37-7h3g-55p8) |
| source-map-js | 1.2.1 → 1.2.2 | PostCSS 依赖的 [恶意 indexed source-map 拒绝服务](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) |

上述剩余项均在工具链中，当前产品没有将这些输入直接暴露为公网服务；本项不以此作永久豁免，而是采用已存在的兼容范围修复。React、路由、业务源码和测试断言未改动。Vitest 4 将 `vi.fn` 泛型扩展为可调用/可构造类型联合，构建暴露两个过宽的测试 mock 声明：聊天 fixture 改为推断实际返回类型，任务图 fixture 显式声明函数签名；不改变 mock 运行逻辑。npm 同步补齐既有 Tailwind 可选 WASM 包的嵌套依赖元数据，Tailwind 版本未变。

CI 仅更新 Vitest 版本说明注释，Node 20、完整依赖审计与测试命令保持原样。no spec delta：不改变 IM/Gateway 的用户可观察契约，不新增长期文档或平行测试。既有 audit gate 保护安全回归，86 个测试文件保持 keep，由完整运行验证新 runner 的兼容性。

## 验证

验证时间：2026-10-09。实现提交：`ec496f344fa26a02b1bcff75216cac463d696c1c`；基线：`d87ffa3d19160d45d309f281b0ace4ff92f55a38`。

- Red：原 lockfile 在 Node 20.20.2 / npm 10.8.2 下 `npm ci` 成功，`npm audit --audit-level=critical` 退出 1；完整 JSON 为 9 项（2 low / 2 moderate / 3 high / 2 critical）。
- Green：最终 lockfile clean `npm ci` 成功；`npm audit --json` 为全等级 0；`npm audit --audit-level=critical` 退出 0。检查 lockfile 无 tinypool 节点、生产依赖节点相对基线无变化。
- 最终依赖树的 `npm run test -- --reporter=dot`：86 files / 808 tests passed。随后仅修改两个 mock 的类型声明，`npm run build`（tsc + Vite）通过，受影响的两个文件 65 tests passed；完整套件结论 retained，不新增/删除/跳过测试。
- Python：`python -m pytest -m 'not e2e' -n 4 --dist worksteal`：4119 passed、29 warnings，93.38s。使用主仓已有 `.venv`，无 Python 代码改动。
- Ruff check、Ruff format、docs-check、git diff --check 通过。最初 docs-check 用系统 Python 缺少 PyYAML，指定项目 `.venv` 后通过，未修改环境依赖。
- 独立 `change-code-review`：固定 base..implementation head 的 full review，返回 `[]`；核对全部 lockfile 变化、Node 20 engines、依赖范围、`npm ls --all`、类型适配和 CI 门禁。
- Final sync：origin/main 仍为上述基线，无 main 增量；审查后只有验证文档补充与 unit 归档，代码与依赖树未改变，审查及测试结论 retained。no spec delta。

本机证据位于 `/tmp/bugfix-582-audit-before.json`、`/tmp/bugfix-582-audit-after.json`、`/tmp/bugfix-582-validation.log`、`/tmp/bugfix-582-build-focused.log`、`/tmp/bugfix-582-python.log`，不提交日志或构建产物。远端 CI 的结果记录在本 PR；归档不表示合并或部署。
