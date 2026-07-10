// Lightweight i18n for the IM prototype.
// Lang is stored on window.__imLang ("en" | "zh"). App owns the React state
// and writes to window.__imLang on every render, so changing it re-renders
// the whole tree and every t() call below sees the new language.

window.IM_I18N = {
  // Top bar / navigation
  "nano IM": "nano IM",
  "internal": "内部",
  "Chat": "聊天",
  "Agents": "智能体",
  "Me": "我的",
  "Back": "返回",

  // User menu
  "Account": "账户",
  "Profile and gateway": "个人资料与网关",
  "Nodes": "节点",
  "Sign out": "退出登录",
  "owned": "已拥有",
  "online": "在线",
  "offline": "离线",
  "running": "运行中",
  "Open profile menu": "打开个人资料菜单",
  "Profile": "个人资料",
  "Language": "语言",
  "English": "English",
  "中文": "中文",

  // Conversation sidebar
  "Messages": "消息",
  "+ Group": "+ 群聊",
  "New group chat": "新建群聊",
  "Search…": "搜索…",
  "All": "全部",
  "Agent": "智能体",
  "Group": "群组",
  "Network": "网络",
  "Agent↔Agent": "智能体↔智能体",
  "No conversations": "暂无会话",

  // New group modal
  "Select agents, then give the group a name.": "选择智能体，并为群聊命名。",
  "Group name (optional)": "群聊名称（可选）",
  "Auto-generated from participants": "根据参与者自动生成",
  "Cancel": "取消",
  "Create group": "创建群聊",
  "Group created": "群聊已创建",

  // Mention
  "Mention agent": "提及智能体",

  // Message pane
  "Select a conversation": "选择一个会话",
  "Pick a thread to chat with your agents.": "选择一个会话与你的智能体对话。",
  "No messages yet": "暂无消息",
  "Send the first message.": "发送第一条消息。",
  "Message…": "发送消息…",
  "(type @ to mention)": "（输入 @ 以提及）",
  "Message ": "发送给 ",
  "Enter to send · Shift+Enter new line": "Enter 发送 · Shift+Enter 换行",
  " · @ to mention": " · @ 以提及",
  "Config": "配置",
  "working": "处理中",
  "failed": "失败",

  // Tool calls / token chip
  "INPUT": "输入",
  "OUTPUT": "输出",
  "tool call": "次工具调用",
  "tool calls": "次工具调用",
  " · running": " · 运行中",
  "output tokens": "输出 token",
  "context used": "已用上下文",
  "context window": "上下文窗口",
  " used": " 已用",
  "⚠ Context nearly full — consider /compact": "⚠ 上下文几乎已满 — 建议执行 /compact",
  "↑ Context above 70% — watch for degradation": "↑ 上下文已超 70% — 注意可能降级",
  "tok": "tok",
  "ctx": "ctx",

  // Settings page — agent list
  "+ New": "+ 新建",
  "Select an agent": "选择一个智能体",
  "Choose an agent to view or edit its configuration.": "选择一个智能体来查看或编辑其配置。",
  "Choose an agent from the list.": "请从列表中选择一个智能体。",

  // Agent form
  "Identity": "身份",
  "Agent ID is permanent and used in mentions and API calls.": "Agent ID 永久不可更改，用于提及与 API 调用。",
  "Name and purpose shown to users and other agents.": "向用户和其他智能体展示的名称与用途。",
  "Agent ID *": "Agent ID *",
  "Agent ID": "Agent ID",
  "Lowercase letters, numbers, _ and -": "仅限小写字母、数字、_ 和 -",
  "e.g. my_agent": "例如 my_agent",
  "Display Name *": "显示名称 *",
  "Display Name": "显示名称",
  "e.g. My Agent": "例如 我的智能体",
  "Description": "描述",
  "Short summary shown in group chats.": "在群聊中展示的简短描述。",
  "What does this agent do?": "这个智能体能做什么？",
  "Behavior": "行为",
  "System prompt is the primary behavior contract.": "系统提示词是行为的核心约定。",
  "System Prompt *": "系统提示词 *",
  "System Prompt": "系统提示词",
  "Defines role, tone, and constraints.": "定义角色、语气与约束。",
  "Group Reply Policy": "群聊回复策略",
  "When this agent replies in group conversations.": "智能体在群聊中的回复策略。",
  "MENTION — Reply only when @-mentioned": "MENTION — 仅在被 @ 提及时回复",
  "ALWAYS — Reply to every group message": "ALWAYS — 回复每条群消息",
  "NO_REPLY — Silent in groups": "NO_REPLY — 群聊中保持沉默",
  "Access & Model": "权限与模型",
  "Keep allowlists minimal.": "白名单尽量精简。",
  "Skills": "技能",
  "Tool Allowlist": "工具白名单",
  "Default Model": "默认模型",
  "Platform default": "平台默认",
  "(default)": "（默认）",
  "Workspace & Runtime": "工作区与运行时",
  "Read-only. Managed by the owning node.": "只读。由所属节点管理。",
  "Workspace Root": "工作区路径",
  "Profile Version": "配置版本",
  "Owning Node": "所属节点",
  "Last Updated": "最近更新",

  // New agent / detail
  "New agent": "新建智能体",
  "Configure identity, behavior, and tool access.": "配置身份、行为与工具权限。",
  "Create agent": "创建智能体",
  "Create agent →": "创建智能体 →",
  "Open chat ↗": "打开会话 ↗",
  "Save": "保存",
  "✓ Saved": "✓ 已保存",
  "No changes": "无改动",
  "● Unsaved changes": "● 有未保存的改动",
  "Discard": "放弃",
  "Save Agent": "保存智能体",
  "Required": "必填",
  "Lowercase letters, numbers, _ and - only": "仅允许小写字母、数字、_ 和 -",

  // Nodes page
  "Gateway nodes connected to this workspace.": "已连接到此工作区的网关节点。",
  "Total nodes": "节点总数",
  "Online": "在线",
  "Offline": "离线",
  "Total agents": "智能体总数",
  "Alias": "别名",
  "Friendly name shown in the UI.": "界面中展示的友好名称。",
  "Live Snapshot": "实时快照",
  "Heartbeat": "心跳",
  "Version": "版本",
  "All saved": "全部已保存",
  "+ New agent on node": "+ 在此节点新建智能体",
  "agents": "个智能体",
  "version": "版本",

  // Account page
  "Your profile and default gateway configuration.": "你的个人资料和默认网关配置。",
  "Your identity inside the workspace.": "你在该工作区中的身份。",
  "User ID": "用户 ID",
  "Shown in conversations and group chats.": "在会话和群聊中展示。",
  "Gateway": "网关",
  "Controls which node routes your messages by default.": "控制默认由哪个节点为你转发消息。",
  "Default Entry Node": "默认入口节点",
  "Choose from your owned nodes.": "从你拥有的节点中选择。",
  "— Select a node —": "— 选择一个节点 —",
  "Default": "默认",
  "Member since": "加入时间",
  "Owned nodes": "拥有的节点",
  "Save account": "保存账户",

  // Tweaks panel
  "Tweaks": "调节",
  "Appearance": "外观",
  "Accent color": "强调色",
  "Dark sidebar": "深色侧边栏",
  "Compact messages": "紧凑消息",
  "Show avatars": "显示头像"
};

window.__imLang = window.__imLang || (function () {
  try { return localStorage.getItem("im_lang") || "en"; }
  catch { return "en"; }
})();

// Translate a string. en is the source; zh is looked up in IM_I18N. Returns the
// source string if no translation is registered, so partially-translated UIs
// degrade gracefully to English.
window.t = function (en) {
  if (window.__imLang === "zh" && window.IM_I18N[en] != null) return window.IM_I18N[en];
  return en;
};
