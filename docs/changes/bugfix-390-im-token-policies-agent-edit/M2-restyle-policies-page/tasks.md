# tasks — bugfix-390-M2: restyle-policies-page

## 目标

把 `policies-page.tsx` 呈现层重写，对齐 `account-page.tsx` 的 settings house style。**字段集与保存逻辑不动**。

## 退出标准（来自 design.md M2 行）

- [reviewer] 策略页观感与同级 account/nodes 页一致——卡片外壳/标题+描述/设计系统配色
- [reviewer] 移动视口呈现与同级页一致、不溢出错位
- [reviewer] loading/save-error 有样式化反馈、字段功能与保存不变
- [worker] 策略页文案全走 i18n，EN/ZH 均补 `settings.policies.*`，无硬编码英文、无缺失 key
- [worker] `npx vitest run` 全绿（policies-page 测试随重写保持绿、不新增失败）
- [worker] `npm run build` tsc 通过
- [worker] progress.md Evidence 含桌面+移动两视口截图，与 account-page 对照结论

## 测试策略

- 用户路径分类：`visual-only`（纯呈现层重写，字段/保存逻辑不变）
- 现有 policies-page.test.tsx 测试通过 aria-label/labelText 查找字段，重写后必须保持 label 可被解析
- 现有测试作为回归保护（不新增测试，维持绿色即可）
- 真实浏览器验收必须：桌面 + 移动两视口截图，与 account-page 对照

## UI 状态矩阵

| 状态 | 适用 | 覆盖方式 |
|---|---|---|
| loading | 是 | 样式化 spinner/placeholder，对齐 account-page |
| error (load) | N/A（现有组件未实现，本 M 不新增） | N/A |
| default（已加载） | 是 | 卡片外壳 + 字段正常填入 |
| submitting | 是 | 保存按钮 disabled + isPending 文案 |
| save error | 是 | 样式化 error alert（对齐 account-page） |
| mobile viewport | 是 | sticky 顶栏 + 返回键，单列布局 |
| desktop viewport | 是 | 居中窄卡 max-w-[620px] |
| dark mode | N/A（项目不支持） | N/A |
| long content | N/A（字段为数字/短文本） | N/A |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | i18n keys（EN/ZH 补 settings.policies.*） | TODO |
| R2 | policies-page.tsx 呈现层重写 | TODO |
| R3 | 浏览器验收截图 + progress.md 补齐 | TODO |
