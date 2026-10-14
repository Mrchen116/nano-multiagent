# 实施与自检

## 测试策略

- 风险与 seam：账号/策略实际表单保存、放弃、无效值、异步重新读取不覆盖草稿、请求失败后可恢复；最低层为既有 React Testing Library 页面测试。只读和容量身份辨认仍由既有 company-access 测试负责，不复制权限测试。
- `account-page.test.tsx` rewrite-merge：旧设备逐行呈现断言改为电脑管理摘要入口；保留保存/放弃，补空白名/保存失败、后台刷新和读失败重试。
- `policies-page.test.tsx` rewrite-merge：完整六字段保存用解析后的 JSON 验证，避免把键顺序当协议；补空数字/非整数、失败草稿与容量故障独立、后台刷新与读失败恢复。
- `company-access.test.tsx` rewrite-merge：普通成员从禁用控件改为只读文本，保留权限与容量用户名识别覆盖。
- 先修改行为测试在旧实现取得3项失败（摘要入口、空白名校验、只读文本）；完成新实现后相关3文件19项全部通过。无新永久测试文件、无一次性浏览器脚本混入测试套件。

## 验证结果

- `npm run build`：通过，568 modules；有既有大包与动态导入提示，不影响生成。
- 前端全套 `npm test`：93文件 / 879测试通过（修复后最终全套）；`npm audit --audit-level=critical`：0 vulnerabilities。
- `pnpm build` 与 `pnpm typecheck`：通过（仅构建本地 installer candidate，没有发布）。`pnpm test` 初次有一项未改动usage测试超时；单项重跑通过，保持15s timeout并限制maxWorkers=2后的完整80文件/296测试通过。未修改后端/测试/timeout，不能据此认定并发为唯一根因。
- Python helpers：56 passed / 31 deselected；ruff check/format通过。日志临时定位 `/tmp/nano-feat604/`，最终归档记录必要摘要。

## 真实页面自检

- 真实静态构建由隔离 IM 提供。中文桌面账号的身份/用户名、资料编辑、折叠账号详情、独立空间与关联管理符合原型；显示名保存为测试姓名后，个人菜单同步，刷新仍保留。[桌面账号](account-desktop.png)。
- 管理员策略先呈现实际占用和剩余，再呈现未执行预设；展开可见账号，长中文姓名/用户名、1GiB满额成员与用量可辨认。[桌面策略](policies-desktop.png)。
- 390px真实响应式下编辑最后一个留存字段，然后停止本次IM并提交。31天草稿保留，失败文字/保存按钮/真实四项底栏同屏；恢复同一IM后直接重试成功，刷新读回31天。[手机失败](policies-mobile-failure.png)。
- 320px账号实际渲染，长显示名自然换行，表单与保存动作不横向溢出，真实底栏保持可达。[320px账号](account-mobile-320.png)。
- 本段是实施者自检，不替代独立产品验收；只声明上述状态，不推导其余身份、英文窄屏和其他故障已通过。永久测试与真实自检共同支持后续独立验收。

## 审查修复

- 独立静态审查复现两页旧GET晚于PATCH返回会覆盖保存结果。新增既有页面回归测试在旧实现2项失败；成功回调取消同key在途读取后，3文件21项通过，frontend build再次通过。首文档/design/delta未改变。
- 独立产品R1实际覆盖除S7后台交错之外的全部场景；保存失败/恢复已有真实证据，后台交错需在修复后的静态构建上补独立产品验证，不用组件测试冒充。


## 最终独立门禁与归并

- 设计 Gate 2 R2：Approved，0 CRITICAL / 0 WARNING；[设计审查](../../design-review.md)。
- 静态 code review R2：Approved，W1闭合、findings=[]；[代码审查](../../code-review.md)。verifier R2：PASS，0 CRITICAL / 0 WARNING，三条delta均aligned；[一致性验证](../../verification.md)。
- 产品 reviewer R2：pass，S1–S9全部通过；[真实产品验收](../../acceptance.md)。R1独立覆盖桌面/390/320、中英文、五种团队资格、正常/满额/未知容量、只读、键盘和实际导航/失败恢复。R2通过真实浏览器后台可见性变化和透明延迟fixture，补齐两页编辑中返回、保存成功后旧GET返回四条顺序。不能用静态/组件测试替代这项证据。
- M1退出标准：账号职责分层、真实容量与历史预设分层、可恢复编辑、双语响应式与独立门禁均完成。此前S7证据缺口和W1已经闭合，没有开放milestone或设计问题。
- 三条已审delta原文归并至 `docs/specs/im/auth-tenancy.md`，入口计数10→13。未扩展后端执行、权限或原生iOS范围；SPEC/AGENTS无需更新。

### Final sync与门禁有效性

原始执行对象保留，不把rebase后的提交冒充重新执行：

| Gate | executed_base | validated_at | 原始结论 |
|---|---|---|---|
| Gate 2 R2 | ee03471d60c1df85251b1f41e618bcdb4871193b | ef2304bbde34f79d2ceebf213cf3ba6e0288cfbc | Approved 0/0（原报告reviewer_target） |
| Code review / verifier R2 | 9ebe12f8553a593f6179784b0276849fb14e5358 | 49795346290faadb5039fb1b371db5f6d145562a | Approved / PASS，delta aligned |
| Product reviewer R2 | 9ebe12f8553a593f6179784b0276849fb14e5358 | 49795346290faadb5039fb1b371db5f6d145562a | pass，S1–S9 |

最终sync的effective_base为 `c17f53ab632e76d9e9099eb38b64808baea3f0f7`。rebase无冲突，旧实现/修复分别对应新提交f8e873193/542f68a04；产品代码与受审版本一致。最终effective_through在PR body记录精确交付HEAD。

main增量仅bugfix-607的composer caret修复及其文档：global.css变更限于 `.chat-composer-highlight-mirror` / `.chat-composer-highlight-input` 的滚动槽和换行；没有改变账号/策略、共享token/表单/导航或权限。最终归并仅机械添加已审三条Requirement、更新入口计数与整目录归档，没有新行为。逐项判断后保留Gate2、静态和真实体验结论；保留R1体验通过基于它实际观察的具体场景，不只基于代码未变。最终docs-check/diff-check/archive检查和远端CI另作交付核对。

### 最终测试定位与局限

- 修复后focused：3文件21测试通过；frontend全套：93文件879测试通过，23.02s；build再次通过。临时日志 `/tmp/nano-feat604/save-race-green.log`、`frontend-tests-final.log`、`frontend-build-final.log`。
- 根构建/typecheck、80文件296测试（maxWorkers=2且timeout未改）、Python56测试、ruff及未变依赖audit沿用已执行证据。main的composer CSS只影响前端，未使这些后端检查失效。
- 所有真实验收在隔离IM和测试账号中完成；没有部署生产、合并PR、发布Node安装器或宣称原生/实机验收。
- reviewer专用Chrome无痕窗口和两个本地标签已由reviewer关闭，保留用户原有窗口。IM32125、延迟proxy37001和原型server由本worktree创建者在交付时停止；没有Gateway/DSH/LLM进程需要清理。

- sync后补跑：frontend build通过；三文件21测试通过（4.32s），日志 `frontend-build-synced.log` / `frontend-focused-synced.log`。最终归档后docs-check、diff-check和唯一archive检查均通过；远端CI结果在PR实时查看。
