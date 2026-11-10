/** Model- and user-visible product boundary shared by the tool surface and approval. */
export const BROWSER_PRODUCT_BOUNDARY = '不下载、不上传、不处理 JS 对话框、不操作地址栏与浏览器界面、不执行自主脚本。';

export const BROWSER_AUTHORIZED_FORMS = '用户授权后可在 Agent 的隔离浏览器中登录、提交表单和发送网页消息，均遵循既有审批。';

/** Extra sentence shown in the interactive approval card for page actions. */
export const BROWSER_APPROVAL_REASON = `${BROWSER_AUTHORIZED_FORMS}${BROWSER_PRODUCT_BOUNDARY}需要改动页面状态的动作要先读后做；不接受坐标点击。`;
