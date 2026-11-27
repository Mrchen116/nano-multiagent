use crate::config::{sha256_hex, DesktopPaths, StoredSessionEntry};
use crate::generated_contracts::{
    UserNotificationKindContract, UserStreamNotificationHint, WireEnum,
};
use futures_util::{SinkExt, StreamExt};
#[cfg(test)]
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{HashMap, VecDeque};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;
use tokio::sync::watch;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::HeaderValue;
use tokio_tungstenite::tungstenite::Message as TungsteniteMsg;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DesktopNotificationRecord {
    pub kind: String,
    pub title: String,
    pub body: String,
    pub target_route: String,
}

#[derive(Debug, Clone, Default)]
pub struct WindowAttentionState {
    pub visible_and_focused: bool,
    pub current_route: String,
}

pub trait DesktopUiBridge: Send + Sync {
    fn window_attention(&self) -> WindowAttentionState;
    fn update_current_route(&self, route: &str) -> Option<String>;
    fn update_unread_badge(&self, total_unread: u64);
    fn activate_route(&self, target_route: &str);
    fn clear_session_navigation(&self) {}
    fn focus_window(&self) {}
    fn notify_host_context_updated(&self) {}
    fn reload_webview(&self, target_route: Option<&str>);
    fn set_locale(&self, _locale: &str) {}
}

#[derive(Default)]
pub struct NoopUiBridge {
    pub badge_count: Mutex<u64>,
    pub activated_routes: Mutex<Vec<String>>,
    pub focus_count: Mutex<u64>,
    pub context_update_count: Mutex<u64>,
    pub attention: RwLock<WindowAttentionState>,
    pub pending_route: Mutex<Option<String>>,
}

impl DesktopUiBridge for NoopUiBridge {
    fn window_attention(&self) -> WindowAttentionState {
        self.attention.read().unwrap().clone()
    }

    fn update_current_route(&self, route: &str) -> Option<String> {
        if let Some(target) = self.pending_route.lock().unwrap().take() {
            if target != route {
                self.attention.write().unwrap().current_route = target.clone();
                return Some(target);
            }
        }
        self.attention.write().unwrap().current_route = route.to_string();
        None
    }

    fn update_unread_badge(&self, total_unread: u64) {
        *self.badge_count.lock().unwrap() = total_unread;
    }

    fn activate_route(&self, target_route: &str) {
        *self.pending_route.lock().unwrap() = Some(target_route.to_string());
        self.attention.write().unwrap().current_route = target_route.to_string();
        self.activated_routes
            .lock()
            .unwrap()
            .push(target_route.to_string());
    }

    fn clear_session_navigation(&self) {
        self.pending_route.lock().unwrap().take();
        self.attention.write().unwrap().current_route.clear();
    }

    fn focus_window(&self) {
        *self.focus_count.lock().unwrap() += 1;
    }

    fn notify_host_context_updated(&self) {
        *self.context_update_count.lock().unwrap() += 1;
    }

    fn reload_webview(&self, _target_route: Option<&str>) {}
}

#[derive(Debug, Clone)]
pub struct ActiveDaemonSession {
    pub im_origin: String,
    pub session: StoredSessionEntry,
}

impl ActiveDaemonSession {
    pub(crate) fn same_principal(&self, other: &Self) -> bool {
        self.im_origin == other.im_origin && self.session.user_id == other.session.user_id
    }

    pub(crate) fn notification_link(&self, route: &str) -> url::Url {
        let mut link = url::Url::parse("crewden-desktop://open").unwrap();
        link.query_pairs_mut()
            .append_pair("notification_scope", &self.notification_scope())
            .append_pair("route", route);
        link
    }

    pub(crate) fn notification_scope(&self) -> String {
        sha256_hex(format!("{}\0{}", self.im_origin, self.session.user_id).as_bytes())
    }
}

#[derive(Debug, Clone, Default)]
struct ConvSummaryEntry {
    unread: u64,
    muted: bool,
    title: String,
}

pub struct NotificationCenterState {
    unread_total: Mutex<u64>,
    conversations: Mutex<HashMap<String, ConvSummaryEntry>>,
    ws_connected: AtomicBool,
}

impl Default for NotificationCenterState {
    fn default() -> Self {
        Self {
            unread_total: Mutex::new(0),
            conversations: Mutex::new(HashMap::new()),
            ws_connected: AtomicBool::new(false),
        }
    }
}

pub(crate) fn apply_hint_conversation_unread(
    center: &NotificationCenterState,
    ui: &dyn DesktopUiBridge,
    attention: &WindowAttentionState,
    payload: &Value,
    hint: &UserStreamNotificationHint,
) {
    let cid = non_empty_str(&payload["conversation_id"])
        .or(hint.conversation_id.as_deref())
        .unwrap_or("");
    if cid.is_empty() {
        return;
    }
    let focused_here =
        attention.visible_and_focused && is_viewing_conversation_route(&attention.current_route, cid);
    if !focused_here {
        if let Some(unread) = hint.conversation_unread {
            center.upsert_conversation(
                &json!({
                    "conversation_id": cid,
                    "unread_count": unread,
                    "is_muted": hint.is_muted,
                    "title": hint.conversation_title.as_deref().unwrap_or(""),
                }),
                ui,
            );
        }
    }
}

impl NotificationCenterState {
    pub fn set_unread(&self, total: u64) {
        *self.unread_total.lock().unwrap() = total;
    }

    pub fn unread(&self) -> u64 {
        *self.unread_total.lock().unwrap()
    }

    pub fn set_ws_connected(&self, connected: bool) {
        self.ws_connected.store(connected, Ordering::SeqCst);
    }

    pub fn is_ws_connected(&self) -> bool {
        self.ws_connected.load(Ordering::SeqCst)
    }

    pub fn clear_conversations(&self, ui: &dyn DesktopUiBridge) {
        self.conversations.lock().unwrap().clear();
        self.set_unread(0);
        ui.update_unread_badge(0);
    }

    pub fn replace_conversations(&self, items: &[Value], ui: &dyn DesktopUiBridge) {
        let mut next: HashMap<String, ConvSummaryEntry> = HashMap::with_capacity(items.len());
        for item in items {
            if let Some(cid) = item["id"].as_str() {
                let muted = item["is_muted"].as_bool().unwrap_or(false);
                let row_unread = compute_conversation_row_unread(
                    item["unread_count"].as_i64(),
                    item["local_unseen"].as_bool().unwrap_or(false),
                );
                let title = item["title"].as_str().unwrap_or("").to_string();
                next.insert(
                    cid.to_string(),
                    ConvSummaryEntry {
                        unread: if muted { 0 } else { row_unread },
                        muted,
                        title,
                    },
                );
            }
        }
        let total: u64 = next.values().map(|c| c.unread).sum();
        *self.conversations.lock().unwrap() = next;
        self.set_unread(total);
        ui.update_unread_badge(total);
    }

    pub fn upsert_conversation(&self, item: &Value, ui: &dyn DesktopUiBridge) {
        let Some(cid) = item["id"]
            .as_str()
            .or_else(|| item["conversation_id"].as_str())
        else {
            return;
        };
        let total: u64 = {
            let mut guard = self.conversations.lock().unwrap();
            let entry = guard.entry(cid.to_string()).or_default();
            if let Some(muted) = item["is_muted"].as_bool() {
                entry.muted = muted;
                if muted {
                    entry.unread = 0;
                }
            }
            if let Some(unread) = item["unread_count"].as_u64() {
                entry.unread = if entry.muted { 0 } else { unread };
            }
            if let Some(title) = item["title"].as_str() {
                if !title.is_empty() {
                    entry.title = title.to_string();
                }
            }
            guard.values().map(|c| c.unread).sum()
        };
        self.set_unread(total);
        ui.update_unread_badge(total);
    }

    pub fn on_message_created(
        &self,
        cid: &str,
        is_self: bool,
        explicit_unread: Option<u64>,
        ui: &dyn DesktopUiBridge,
    ) {
        if cid.is_empty() || is_self {
            return;
        }
        let total_opt = {
            let mut guard = self.conversations.lock().unwrap();
            let entry = guard.entry(cid.to_string()).or_default();
            if entry.muted {
                None
            } else {
                entry.unread = explicit_unread.unwrap_or_else(|| entry.unread.saturating_add(1));
                Some(guard.values().map(|c| c.unread).sum::<u64>())
            }
        };
        if let Some(total) = total_opt {
            self.set_unread(total);
            ui.update_unread_badge(total);
        }
    }

    pub fn snapshot_maps(&self) -> (HashMap<String, bool>, HashMap<String, String>) {
        let guard = self.conversations.lock().unwrap();
        let mut muted = HashMap::with_capacity(guard.len());
        let mut titles = HashMap::with_capacity(guard.len());
        for (cid, entry) in guard.iter() {
            muted.insert(cid.clone(), entry.muted);
            if !entry.title.is_empty() {
                titles.insert(cid.clone(), entry.title.clone());
            }
        }
        (muted, titles)
    }
}

pub fn compute_conversation_row_unread(unread_count: Option<i64>, local_unseen: bool) -> u64 {
    let base = unread_count.filter(|v| *v > 0).map(|v| v as u64).unwrap_or(0);
    if local_unseen {
        base.max(1)
    } else {
        base
    }
}

pub fn compute_unread_badge_total(items: &[Value]) -> u64 {
    items
        .iter()
        .filter(|item| !item["is_muted"].as_bool().unwrap_or(false))
        .map(|item| {
            compute_conversation_row_unread(
                item["unread_count"].as_i64(),
                item["local_unseen"].as_bool().unwrap_or(false),
            )
        })
        .sum()
}

pub fn parse_frame_notification_hint(frame: &Value) -> Option<UserStreamNotificationHint> {
    let raw = frame.get("notification_hint")?;
    serde_json::from_value(raw.clone()).ok()
}

fn resolve_hint_message_body(hint: &UserStreamNotificationHint, en: bool, fallback: &str) -> String {
    if let Some(preview) = hint.preview_text.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        return preview.chars().take(90).collect();
    }
    if hint.has_interactive_card == Some(true) {
        return if en {
            "[Interactive card]".to_string()
        } else {
            "[交互卡片]".to_string()
        };
    }
    if let Some(att) = hint.attachment_name.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        return att.to_string();
    }
    fallback.to_string()
}

/// Pure classifier driven by server-projected `notification_hint` with exhaustive contract matching.
pub fn classify_from_notification_hint(
    hint: &UserStreamNotificationHint,
    muted_conversations: &HashMap<String, bool>,
    conv_titles: &HashMap<String, String>,
    attention: &WindowAttentionState,
    locale: &str,
) -> Option<DesktopNotificationRecord> {
    if !hint.eligible || hint.replayed == Some(true) {
        return None;
    }
    let Some(WireEnum::Known(kind)) = hint.kind.as_ref() else {
        return None;
    };
    let cid = hint.conversation_id.as_deref().unwrap_or("");
    let is_muted = muted_conversations.get(cid).copied().unwrap_or(hint.is_muted);
    if is_muted && !hint.mentions_viewer && *kind != UserNotificationKindContract::WorkPermission {
        return None;
    }

    if *kind == UserNotificationKindContract::WorkPermission {
        let aid = hint.agent_id.as_deref().unwrap_or("");
        if attention.visible_and_focused
            && !aid.is_empty()
            && attention
                .current_route
                .contains(&format!("/settings/agents/{}", aid))
            && attention.current_route.contains("view=work")
        {
            return None;
        }
    } else if attention.visible_and_focused
        && !cid.is_empty()
        && is_viewing_conversation_route(&attention.current_route, cid)
    {
        return None;
    }

    let en = locale.trim().to_ascii_lowercase().starts_with("en");
    let sender = hint
        .sender_name
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .or_else(|| conv_titles.get(cid).map(String::as_str))
        .or_else(|| hint.conversation_title.as_deref().filter(|s| !s.is_empty()));

    let (title, body) = match *kind {
        UserNotificationKindContract::HumanMessage => {
            let s = sender.unwrap_or(if en { "New message" } else { "新消息" });
            let b = resolve_hint_message_body(
                hint,
                en,
                if en {
                    "Sent a new message"
                } else {
                    "发来一条新消息"
                },
            );
            (s.to_string(), b)
        }
        UserNotificationKindContract::Mention => {
            let s = sender.unwrap_or(if en { "New message" } else { "新消息" });
            let b = resolve_hint_message_body(
                hint,
                en,
                if en {
                    "Mentioned you"
                } else {
                    "在会话中 @提及了你"
                },
            );
            let t = if en {
                format!("{} mentioned you", s)
            } else {
                format!("{} 在会话中 @提及了你", s)
            };
            (t, b)
        }
        UserNotificationKindContract::MessageCompleted => {
            let s = sender.unwrap_or(if en { "Assistant" } else { "助手" });
            let fallback = if hint.has_interactive_card == Some(true) {
                if en {
                    "[Interactive card]"
                } else {
                    "[交互卡片]"
                }
            } else if en {
                "Reply completed"
            } else {
                "已完成本轮回复"
            };
            let b = resolve_hint_message_body(hint, en, fallback);
            let t = if en {
                format!("{} · Reply ready", s)
            } else {
                format!("{} · 回复完成", s)
            };
            (t, b)
        }
        UserNotificationKindContract::ChatPermission => {
            let tool = hint
                .tool_name
                .as_deref()
                .unwrap_or(if en { "tool action" } else { "工具执行" });
            let t = if en {
                "Tool approval requested".to_string()
            } else {
                "工具权限待确认".to_string()
            };
            let b = hint
                .preview_text
                .as_deref()
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(|s| s.chars().take(90).collect())
                .unwrap_or_else(|| {
                    if en {
                        format!("Conversation requested approval for {}", tool)
                    } else {
                        format!("会话请求授权执行 {}", tool)
                    }
                });
            (t, b)
        }
        UserNotificationKindContract::WorkPermission => {
            let agent_name = sender
                .or(hint.agent_id.as_deref())
                .unwrap_or(if en { "Assistant" } else { "助手" });
            let t = if en {
                format!("{} · Tool approval needed", agent_name)
            } else {
                format!("{} · 等待工具授权", agent_name)
            };
            let b = if en {
                "Click to open Agent Work and review the pending permission".to_string()
            } else {
                "点击打开助手 Work 视图处理待决权限请求".to_string()
            };
            (t, b)
        }
    };

    Some(DesktopNotificationRecord {
        kind: kind.as_str().to_string(),
        title,
        body,
        target_route: hint.target_route.clone(),
    })
}

fn strip_mention_xml(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut rest = raw;
    while let Some(start) = rest.find("<mention") {
        out.push_str(&rest[..start]);
        if let Some(end) = rest[start..].find("/>") {
            out.push_str("@提及 ");
            rest = &rest[start + end + 2..];
        } else {
            out.push_str(&rest[start..]);
            return out;
        }
    }
    out.push_str(rest);
    out.trim().to_string()
}

fn mentions_user(content: &str, self_user_id: &str) -> bool {
    if self_user_id.is_empty() {
        return false;
    }
    let needle_double = format!("target_id=\"{}\"", self_user_id);
    let needle_single = format!("target_id='{}'", self_user_id);
    content.contains("<mention")
        && (content.contains(&needle_double) || content.contains(&needle_single))
}

/// Unwrap canonical `/im/ws/user` frame `{ op: "event", event_type, event_id?, conversation_id?, data: { ... } }`
/// (or direct test envelopes with `payload` / flat fields) into `(event_type, normalized_payload, event_id)`.
pub fn unwrap_user_stream_frame(frame: &Value) -> Option<(String, Value, Option<u64>)> {
    let event_type = frame["event_type"]
        .as_str()
        .or_else(|| frame["type"].as_str())
        .unwrap_or("")
        .to_string();
    if event_type.is_empty() {
        return None;
    }
    let raw_body = frame
        .get("data")
        .or_else(|| frame.get("payload"))
        .unwrap_or(frame);
    let mut body = raw_body.clone();
    if let Some(obj) = body.as_object_mut() {
        if !obj.contains_key("conversation_id") {
            if let Some(cid) = frame["conversation_id"].as_str() {
                obj.insert("conversation_id".to_string(), json!(cid));
            }
        }
    }
    let event_id = frame["event_id"]
        .as_u64()
        .or_else(|| body["event_id"].as_u64())
        .filter(|id| *id > 0);
    Some((event_type, body, event_id))
}

fn non_empty_str<'a>(val: &'a Value) -> Option<&'a str> {
    val.as_str().map(str::trim).filter(|s| !s.is_empty())
}

fn normalize_user_id(raw: &str) -> &str {
    let trimmed = raw.trim();
    trimmed.strip_prefix("user:").unwrap_or(trimmed)
}

fn is_thread_audience_allowed(payload: &Value, self_user_id: &str) -> bool {
    let Some(_thread_root) = non_empty_str(&payload["thread_root_message_id"]) else {
        return true;
    };
    let Some(notify_ids) = payload["thread_notify_user_ids"].as_array() else {
        return true;
    };
    let target = normalize_user_id(self_user_id);
    if target.is_empty() {
        return false;
    }
    notify_ids
        .iter()
        .filter_map(|v| v.as_str())
        .any(|uid| normalize_user_id(uid) == target)
}

fn is_viewing_conversation_route(current_route: &str, cid: &str) -> bool {
    if cid.is_empty() {
        return false;
    }
    let base = format!("/chat/{}", cid);
    if current_route == base {
        return true;
    }
    let Some(rest) = current_route.strip_prefix(&base) else {
        return false;
    };
    rest.starts_with('?') || rest.starts_with('#') || rest.starts_with('/')
}

fn build_conversation_target_route(cid: &str, thread_root_id: Option<&str>) -> String {
    let mut base = format!("/chat/{}", cid);
    if let Some(root) = thread_root_id.map(str::trim).filter(|s| !s.is_empty()) {
        let mut serializer = url::form_urlencoded::Serializer::new(String::new());
        serializer.append_pair("thread", root);
        base.push('?');
        base.push_str(&serializer.finish());
    }
    base
}

fn has_interactive_card(payload: &Value) -> bool {
    non_empty_str(&payload["interactive"]["source"]).is_some()
        || payload["has_interactive_card"].as_bool().unwrap_or(false)
}

fn extract_attachment_preview(payload: &Value, en: bool) -> Option<String> {
    if let Some(name) = non_empty_str(&payload["file_name"]) {
        return Some(name.to_string());
    }
    if let Some(arr) = payload["attachments"].as_array() {
        if let Some(first_name) = arr.first().and_then(|item| non_empty_str(&item["file_name"])) {
            return Some(first_name.to_string());
        }
        if !arr.is_empty() {
            return Some(if en {
                "Attachment".to_string()
            } else {
                "[附件]".to_string()
            });
        }
    }
    None
}

/// Pure classifier for `/im/ws/user` canonical events covering the 4 required Desktop notification types.
pub fn classify_user_stream_event(
    event_type: &str,
    payload: &Value,
    self_user_id: &str,
    muted_conversations: &HashMap<String, bool>,
    conv_titles: &HashMap<String, String>,
    attention: &WindowAttentionState,
) -> Option<DesktopNotificationRecord> {
    classify_user_stream_event_with_senders(
        event_type,
        payload,
        self_user_id,
        muted_conversations,
        conv_titles,
        &HashMap::new(),
        attention,
    )
}

pub fn classify_user_stream_event_with_senders(
    event_type: &str,
    payload: &Value,
    self_user_id: &str,
    muted_conversations: &HashMap<String, bool>,
    conv_titles: &HashMap<String, String>,
    pending_agent_senders: &HashMap<String, String>,
    attention: &WindowAttentionState,
) -> Option<DesktopNotificationRecord> {
    classify_user_stream_event_localized(
        event_type,
        payload,
        self_user_id,
        muted_conversations,
        conv_titles,
        pending_agent_senders,
        attention,
        "zh",
    )
}

pub fn classify_user_stream_event_localized(
    event_type: &str,
    payload: &Value,
    self_user_id: &str,
    muted_conversations: &HashMap<String, bool>,
    conv_titles: &HashMap<String, String>,
    pending_agent_senders: &HashMap<String, String>,
    attention: &WindowAttentionState,
    locale: &str,
) -> Option<DesktopNotificationRecord> {
    let en = locale.trim().to_ascii_lowercase().starts_with("en");
    match event_type {
        "message.completed" => {
            if payload["delivery_status"].as_str() == Some("failed") {
                return None;
            }
            if payload["sender_type"].as_str() == Some("user") {
                return None;
            }
            if let Some(uid) = non_empty_str(&payload["sender_user_id"]) {
                if normalize_user_id(uid) == normalize_user_id(self_user_id) {
                    return None;
                }
            }
            if !is_thread_audience_allowed(payload, self_user_id) {
                return None;
            }
            let cid = payload["conversation_id"].as_str().unwrap_or("");
            if cid.is_empty() || muted_conversations.get(cid).copied().unwrap_or(false) {
                return None;
            }
            if attention.visible_and_focused
                && is_viewing_conversation_route(&attention.current_route, cid)
            {
                return None;
            }
            let thread_root = non_empty_str(&payload["thread_root_message_id"]);
            let target_route = build_conversation_target_route(cid, thread_root);
            let msg_id = payload["message_id"].as_str().unwrap_or("");
            let sender = non_empty_str(&payload["sender"]["display_name"])
                .or_else(|| non_empty_str(&payload["sender_display_name"]))
                .or_else(|| non_empty_str(&payload["sender_name"]))
                .or_else(|| pending_agent_senders.get(msg_id).map(String::as_str))
                .or_else(|| conv_titles.get(cid).map(String::as_str))
                .unwrap_or(if en { "Assistant" } else { "助手" });
            let fallback_done = if has_interactive_card(payload) {
                if en { "[Interactive card]" } else { "[交互卡片]" }
            } else if en {
                "Reply completed"
            } else {
                "已完成本轮回复"
            };
            let raw_content = payload["content"].as_str().unwrap_or("");
            let preview = strip_mention_xml(raw_content);
            let body: String = preview.chars().take(90).collect();
            let resolved_body = if !body.is_empty() {
                body
            } else if has_interactive_card(payload) {
                fallback_done.to_string()
            } else if let Some(att) = extract_attachment_preview(payload, en) {
                att
            } else {
                fallback_done.to_string()
            };
            Some(DesktopNotificationRecord {
                kind: "message_completed".to_string(),
                title: if en {
                    format!("{} · Reply ready", sender)
                } else {
                    format!("{} · 回复完成", sender)
                },
                body: resolved_body,
                target_route,
            })
        }
        "message.created" => {
            let cid = payload["conversation_id"].as_str().unwrap_or("");
            if cid.is_empty() || !is_thread_audience_allowed(payload, self_user_id) {
                return None;
            }
            let sender_type = non_empty_str(&payload["sender_type"])
                .or_else(|| non_empty_str(&payload["sender"]["type"]))
                .unwrap_or("");
            // Explicit card publications (`publishAgent`) emit a terminal `message.created`
            // with `delivery_status == "completed"` and no follow-up `message.completed`.
            if sender_type == "agent"
                && payload["delivery_status"].as_str() == Some("completed")
                && has_interactive_card(payload)
            {
                return classify_user_stream_event_localized(
                    "message.completed",
                    payload,
                    self_user_id,
                    muted_conversations,
                    conv_titles,
                    pending_agent_senders,
                    attention,
                    locale,
                );
            }
            let sender_user_id = non_empty_str(&payload["sender_user_id"])
                .or_else(|| non_empty_str(&payload["sender"]["id"]))
                .unwrap_or("");
            if sender_type != "user"
                || sender_user_id.is_empty()
                || normalize_user_id(sender_user_id) == normalize_user_id(self_user_id)
            {
                return None;
            }
            let content = payload["content"].as_str().unwrap_or("");
            let is_mention = mentions_user(content, self_user_id);
            if !is_mention && muted_conversations.get(cid).copied().unwrap_or(false) {
                return None;
            }
            if attention.visible_and_focused
                && is_viewing_conversation_route(&attention.current_route, cid)
            {
                return None;
            }
            let thread_root = non_empty_str(&payload["thread_root_message_id"]);
            let target_route = build_conversation_target_route(cid, thread_root);
            let sender_name = non_empty_str(&payload["sender_display_name"])
                .or_else(|| non_empty_str(&payload["sender"]["display_name"]))
                .or_else(|| non_empty_str(&payload["sender_name"]))
                .or_else(|| conv_titles.get(cid).map(String::as_str))
                .unwrap_or(if en { "New message" } else { "新消息" });
            let clean = strip_mention_xml(content);
            let body: String = clean.chars().take(90).collect();
            let resolved_body = if !body.is_empty() {
                body
            } else if has_interactive_card(payload) {
                if en {
                    "[Interactive card]".to_string()
                } else {
                    "[交互卡片]".to_string()
                }
            } else if let Some(att) = extract_attachment_preview(payload, en) {
                att
            } else if en {
                "Sent a new message".to_string()
            } else {
                "发来一条新消息".to_string()
            };
            Some(DesktopNotificationRecord {
                kind: if is_mention {
                    "mention".to_string()
                } else {
                    "human_message".to_string()
                },
                title: if is_mention {
                    if en {
                        format!("{} mentioned you", sender_name)
                    } else {
                        format!("{} 在会话中 @提及了你", sender_name)
                    }
                } else {
                    sender_name.to_string()
                },
                body: resolved_body,
                target_route,
            })
        }
        "permission.request" => {
            let req_obj = payload.get("permission_request").unwrap_or(payload);
            let status = req_obj["status"]
                .as_str()
                .or_else(|| payload["status"].as_str())
                .unwrap_or("pending");
            if status != "pending" || !is_thread_audience_allowed(payload, self_user_id) {
                return None;
            }
            let cid = payload["conversation_id"]
                .as_str()
                .or_else(|| req_obj["conversation_id"].as_str())
                .unwrap_or("");
            if cid.is_empty() || muted_conversations.get(cid).copied().unwrap_or(false) {
                return None;
            }
            if attention.visible_and_focused
                && is_viewing_conversation_route(&attention.current_route, cid)
            {
                return None;
            }
            let thread_root = non_empty_str(&payload["thread_root_message_id"])
                .or_else(|| non_empty_str(&req_obj["thread_root_message_id"]));
            let target_route = build_conversation_target_route(cid, thread_root);
            let tool = non_empty_str(&req_obj["tool_name"])
                .or_else(|| non_empty_str(&req_obj["tool"]))
                .or_else(|| non_empty_str(&payload["tool_name"]))
                .or_else(|| non_empty_str(&payload["tool"]))
                .unwrap_or(if en { "tool action" } else { "工具执行" });
            Some(DesktopNotificationRecord {
                kind: "chat_permission".to_string(),
                title: if en {
                    "Tool approval requested".to_string()
                } else {
                    "工具权限待确认".to_string()
                },
                body: if en {
                    format!("Conversation requested approval for {}", tool)
                } else {
                    format!("会话请求授权执行 {}", tool)
                },
                target_route,
            })
        }
        "agent.work.updated" => {
            let status = payload["status"]
                .as_str()
                .or_else(|| payload["main_execution"].as_str())
                .unwrap_or("");
            if status != "waiting_permission" {
                return None;
            }
            let agent_id = payload["agent_id"].as_str().unwrap_or("");
            if agent_id.is_empty() {
                return None;
            }
            let target_route = format!("/settings/agents/{}?view=work", agent_id);
            if attention.visible_and_focused
                && attention
                    .current_route
                    .contains(&format!("/settings/agents/{}", agent_id))
                && attention.current_route.contains("view=work")
            {
                return None;
            }
            let agent_name = non_empty_str(&payload["display_name"])
                .or_else(|| non_empty_str(&payload["agent_name"]))
                .unwrap_or(agent_id);
            Some(DesktopNotificationRecord {
                kind: "work_permission".to_string(),
                title: if en {
                    format!("{} · Tool approval needed", agent_name)
                } else {
                    format!("{} · 等待工具授权", agent_name)
                },
                body: if en {
                    "Click to open Agent Work and review the pending permission".to_string()
                } else {
                    "点击打开助手 Work 视图处理待决权限请求".to_string()
                },
                target_route,
            })
        }
        _ => None,
    }
}

#[cfg(target_os = "macos")]
pub(crate) mod macos_notify {
    #![allow(deprecated)]
    use crate::host_server::{handle_deep_link_url, HostSharedState};
    use objc2::rc::Retained;
    use objc2::runtime::{AnyObject, ProtocolObject};
    use objc2::{define_class, msg_send, ClassType};
    use objc2_foundation::{
        NSBundle, NSDictionary, NSObject, NSObjectProtocol, NSString, NSUserNotification,
        NSUserNotificationCenter, NSUserNotificationCenterDelegate,
    };
    use std::sync::{OnceLock, RwLock, Weak};

    static HOST: OnceLock<RwLock<Weak<HostSharedState>>> = OnceLock::new();
    static MAC_DELEGATE_INIT: OnceLock<()> = OnceLock::new();

    define_class!(
        #[unsafe(super(NSObject))]
        #[name = "CrewdenDesktopNotificationDelegate"]
        struct CrewdenNotificationDelegate;

        unsafe impl NSObjectProtocol for CrewdenNotificationDelegate {}

        unsafe impl NSUserNotificationCenterDelegate for CrewdenNotificationDelegate {
            #[unsafe(method(userNotificationCenter:didActivateNotification:))]
            fn did_activate(
                &self,
                center: &NSUserNotificationCenter,
                notification: &NSUserNotification,
            ) {
                if let Some(info) = notification.userInfo() {
                    let key = NSString::from_str("notification_link");
                    if let Some(value) = info.objectForKey(&key) {
                        if let Some(link) = value.downcast_ref::<NSString>() {
                            if let Some(host) = HOST.get().and_then(|h| h.read().unwrap().upgrade()) {
                                handle_deep_link_url(&host, &link.to_string());
                            }
                        }
                    }
                }
                center.removeDeliveredNotification(notification);
            }
        }
    );

    impl CrewdenNotificationDelegate {
        fn new() -> Retained<Self> {
            unsafe { msg_send![Self::class(), new] }
        }
    }

    pub fn clear_delivered() {
        if NSBundle::mainBundle().bundleIdentifier().is_some() {
            NSUserNotificationCenter::defaultUserNotificationCenter().removeAllDeliveredNotifications();
        }
    }

    pub fn install_click_handler(host: Weak<HostSharedState>) {
        // Never swizzle NSBundle: only post native Notification Center banners when running inside
        // a real `.app` bundle (where CFBundleIdentifier is `work.crewden.desktop`).
        let main_bundle = NSBundle::mainBundle();
        if main_bundle.bundleIdentifier().is_none() {
            return;
        }
        *HOST.get_or_init(RwLock::default).write().unwrap() = host;
        MAC_DELEGATE_INIT.get_or_init(|| {
            let delegate = CrewdenNotificationDelegate::new();
            let proto = ProtocolObject::from_retained(delegate);
            let center = NSUserNotificationCenter::defaultUserNotificationCenter();
            unsafe {
                center.setDelegate(Some(&proto));
            }
            // Intentionally leak the singleton delegate so unretained NSUserNotificationCenter.delegate stays valid for process lifetime.
            std::mem::forget(proto);
        });
    }

    pub fn send_native_notification(title: &str, body: &str, link: &str) {
        if NSBundle::mainBundle().bundleIdentifier().is_none() {
            return;
        }
        let notif = NSUserNotification::new();
        let ns_title = NSString::from_str(title);
        let ns_body = NSString::from_str(body);
        let key_route = NSString::from_str("notification_link");
        let val_route = NSString::from_str(link);
        notif.setTitle(Some(&ns_title));
        notif.setInformativeText(Some(&ns_body));
        let val_any: Retained<AnyObject> = Retained::into_super(Retained::into_super(val_route));
        let dict = NSDictionary::from_retained_objects(&[&*key_route], &[val_any]);
        unsafe {
            notif.setUserInfo(Some(&dict));
        }
        NSUserNotificationCenter::defaultUserNotificationCenter().deliverNotification(&notif);
    }
}

#[cfg(target_os = "windows")]
mod windows_notify {
    use crate::config::DesktopPaths;
    use std::sync::OnceLock;
    use windows::core::HSTRING;
    use windows::Data::Xml::Dom::XmlDocument;
    use windows::UI::Notifications::{ToastNotification, ToastNotificationManager};
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    pub const WINDOWS_AUMID: &str = "work.crewden.desktop";
    const TOAST_ICON_PNG: &[u8] = include_bytes!("../icons/128x128.png");
    static AUMID_REGISTERED: OnceLock<()> = OnceLock::new();

    fn xml_escape(input: &str) -> String {
        let mut out = String::with_capacity(input.len() + 16);
        for ch in input.chars() {
            match ch {
                '&' => out.push_str("&amp;"),
                '<' => out.push_str("&lt;"),
                '>' => out.push_str("&gt;"),
                '"' => out.push_str("&quot;"),
                '\'' => out.push_str("&apos;"),
                _ => out.push(ch),
            }
        }
        out
    }

    fn ensure_windows_aumid_and_protocol(paths: &DesktopPaths) {
        if paths.is_isolated_autostart() {
            return;
        }
        AUMID_REGISTERED.get_or_init(|| {
            let icon_path = paths.desktop_home.join("crewden-toast-icon.png");
            let _ = std::fs::create_dir_all(&paths.desktop_home);
            let _ = std::fs::write(&icon_path, TOAST_ICON_PNG);

            let hkcu = RegKey::predef(HKEY_CURRENT_USER);
            if let Ok((aumid_key, _)) =
                hkcu.create_subkey(format!(r"Software\Classes\AppUserModelId\{}", WINDOWS_AUMID))
            {
                let _ = aumid_key.set_value("DisplayName", &"Crewden");
                let _ = aumid_key.set_value("IconBackgroundColor", &"0");
                let _ = aumid_key.set_value("IconUri", &icon_path.to_string_lossy().to_string());
            }
            if let Ok(exe) = std::env::current_exe() {
                if let Ok((proto_key, _)) = hkcu.create_subkey(r"Software\Classes\crewden-desktop") {
                    let _ = proto_key.set_value("", &"URL:Crewden Desktop");
                    let _ = proto_key.set_value("URL Protocol", &"");
                }
                if let Ok((cmd_key, _)) =
                    hkcu.create_subkey(r"Software\Classes\crewden-desktop\shell\open\command")
                {
                    let cmd = format!("\"{}\" \"%1\"", exe.display());
                    let _ = cmd_key.set_value("", &cmd);
                }
            }
        });
    }

    pub fn clear_delivered() {
        if let Ok(history) = ToastNotificationManager::History() {
            let _ = history.ClearWithId(&HSTRING::from(WINDOWS_AUMID));
        }
    }

    pub fn send_native_toast(paths: &DesktopPaths, title: &str, body: &str, link: &str) -> bool {
        ensure_windows_aumid_and_protocol(paths);
        let xml_str = format!(
            "<toast activationType=\"protocol\" launch=\"{}\"><visual><binding template=\"ToastGeneric\"><text id=\"1\">{}</text><text id=\"2\">{}</text></binding></visual></toast>",
            xml_escape(link),
            xml_escape(title),
            xml_escape(body),
        );
        let Ok(doc) = XmlDocument::new() else {
            return false;
        };
        if doc.LoadXml(&HSTRING::from(xml_str)).is_err() {
            return false;
        }
        let Ok(toast) = ToastNotification::CreateToastNotification(&doc) else {
            return false;
        };
        if let Ok(notifier) =
            ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from(WINDOWS_AUMID))
        {
            return notifier.Show(&toast).is_ok();
        }
        false
    }
}

pub(crate) fn clear_delivered_notifications(paths: &DesktopPaths) {
    // Isolated hosts must not modify the installed application's Notification Center.
    if paths.is_isolated_autostart() {
        return;
    }
    #[cfg(target_os = "macos")]
    macos_notify::clear_delivered();
    #[cfg(target_os = "windows")]
    windows_notify::clear_delivered();
}

fn deliver_os_notification(
    host: &crate::host_server::HostSharedState,
    active: &ActiveDaemonSession,
    item: &DesktopNotificationRecord,
) {
    if std::env::var("CREWDEN_SUPPRESS_OS_NOTIFICATIONS").as_deref() == Ok("1") {
        return;
    }
    host.with_notification_session(active, || {
        let link = active.notification_link(&item.target_route);
        #[cfg(target_os = "macos")]
        macos_notify::send_native_notification(&item.title, &item.body, link.as_str());
        #[cfg(target_os = "windows")]
        windows_notify::send_native_toast(&host.paths, &item.title, &item.body, link.as_str());
    });
}

struct SessionCursorTracker {
    im_origin: String,
    user_id: String,
    owner_id: String,
    locale: String,
    cursor: Option<u64>,
    notified_work_status: HashMap<String, String>,
    notified_completed_messages: VecDeque<String>,
    notified_dedupe_keys: VecDeque<String>,
    owned_agents: std::collections::HashSet<String>,
    foreign_agents: std::collections::HashSet<String>,
}

/// Spawn the resident Rust background `/im/ws/user` notification & badge daemon.
pub fn spawn_notification_daemon(
    host_state: Arc<crate::host_server::HostSharedState>,
    mut session_rx: watch::Receiver<Option<ActiveDaemonSession>>,
) {
    tokio::spawn(async move {
        let mut tracker: Option<SessionCursorTracker> = None;
        loop {
            let current = session_rx.borrow_and_update().clone();
            let Some(active) = current else {
                tracker = None;
                host_state.notification_center.set_ws_connected(false);
                if session_rx.changed().await.is_err() {
                    return;
                }
                continue;
            };

            let same_principal = tracker
                .as_ref()
                .map(|t| t.im_origin == active.im_origin && t.user_id == active.session.user_id)
                .unwrap_or(false);
            if !same_principal {
                tracker = Some(SessionCursorTracker {
                    im_origin: active.im_origin.clone(),
                    user_id: active.session.user_id.clone(),
                    owner_id: active.session.owner_id.clone(),
                    locale: "zh".to_string(),
                    cursor: None,
                    notified_work_status: HashMap::new(),
                    notified_completed_messages: VecDeque::with_capacity(64),
                    notified_dedupe_keys: VecDeque::with_capacity(128),
                    owned_agents: std::collections::HashSet::new(),
                    foreign_agents: std::collections::HashSet::new(),
                });
            }
            let tracker_ref = tracker.as_mut().unwrap();

            tokio::select! {
                changed = session_rx.changed() => {
                    host_state.notification_center.set_ws_connected(false);
                    if changed.is_err() {
                        return;
                    }
                }
                _ = run_single_session_stream(&host_state, &active, tracker_ref) => {
                    host_state.notification_center.set_ws_connected(false);
                    tokio::time::sleep(Duration::from_secs(2)).await;
                }
            }
        }
    });
}

async fn sync_conversations_and_cursor(
    host: &crate::host_server::HostSharedState,
    active: &ActiveDaemonSession,
    access_token: &str,
) -> Option<u64> {
    let center = &host.notification_center;
    let ui = host.ui_bridge.as_ref();
    let http_client = &host.http_client;
    let im_origin = &active.im_origin;
    let sync_url = format!("{}/im/v1/sync", im_origin);
    if let Ok(res) = http_client
        .get(&sync_url)
        .bearer_auth(access_token)
        .send()
        .await
    {
        if res.status().is_success() {
            if let Ok(sync_json) = res.json::<Value>().await {
                if let Some(items) = sync_json["items"].as_array() {
                    host.with_notification_session(active, || center.replace_conversations(items, ui));
                }
                return sync_json["max_event_id"].as_u64();
            }
        }
    }

    // Fallback to GET /im/v1/conversations if /im/v1/sync is unavailable
    let convs_url = format!("{}/im/v1/conversations", im_origin);
    if let Ok(conv_res) = http_client
        .get(&convs_url)
        .bearer_auth(access_token)
        .send()
        .await
    {
        if conv_res.status().is_success() {
            if let Ok(conv_json) = conv_res.json::<Value>().await {
                if let Some(list) = conv_json["items"]
                    .as_array()
                    .or_else(|| conv_json.as_array())
                {
                    host.with_notification_session(active, || center.replace_conversations(list, ui));
                }
            }
        }
    }
    None
}

async fn enrich_work_updated_payload(
    http_client: &reqwest::Client,
    im_origin: &str,
    access_token: &str,
    payload: &Value,
) -> Value {
    if payload.get("status").is_some() || payload.get("main_execution").is_some() {
        return payload.clone();
    }
    let Some(agent_id) = non_empty_str(&payload["agent_id"]) else {
        return payload.clone();
    };
    let mut url = match url::Url::parse(im_origin) {
        Ok(u) => u,
        Err(_) => return payload.clone(),
    };
    if let Ok(mut segs) = url.path_segments_mut() {
        segs.extend(["im", "v1", "agents", agent_id, "work"]);
    }
    url.query_pairs_mut()
        .append_pair("view", "summary")
        .append_pair("catalog", "separate")
        .append_pair("limit", "1");

    let Ok(res) = http_client
        .get(url)
        .bearer_auth(access_token)
        .send()
        .await
    else {
        return payload.clone();
    };
    if !res.status().is_success() {
        return payload.clone();
    }
    let Ok(work_json) = res.json::<Value>().await else {
        return payload.clone();
    };
    let mut enriched = payload.clone();
    if let Some(obj) = enriched.as_object_mut() {
        if let Some(main_exec) = work_json["main_execution"].as_str() {
            obj.insert("main_execution".to_string(), json!(main_exec));
        }
        if let Some(title) = work_json["main_session"]["title"].as_str() {
            if !title.is_empty() {
                obj.insert("display_name".to_string(), json!(title));
            }
        }
    }
    enriched
}

async fn ensure_agent_owned_by_session(
    http_client: &reqwest::Client,
    im_origin: &str,
    access_token: &str,
    tracker: &mut SessionCursorTracker,
    agent_id: &str,
) -> bool {
    if agent_id.is_empty() {
        return false;
    }
    if tracker.owned_agents.contains(agent_id) {
        return true;
    }
    if tracker.foreign_agents.contains(agent_id) {
        return false;
    }
    let agents_url = format!("{}/im/v1/agents", im_origin);
    let Ok(res) = http_client
        .get(&agents_url)
        .bearer_auth(access_token)
        .send()
        .await
    else {
        return false;
    };
    if !res.status().is_success() {
        return false;
    }
    let Ok(agents_json) = res.json::<Value>().await else {
        return false;
    };
    if let Some(list) = agents_json["items"]
        .as_array()
        .or_else(|| agents_json.as_array())
    {
        for item in list {
            let Some(aid) = item["agent_id"]
                .as_str()
                .or_else(|| item["id"].as_str())
            else {
                continue;
            };
            let item_owner = item["owner_id"].as_str().unwrap_or("");
            if !item_owner.is_empty() && item_owner == tracker.owner_id {
                tracker.foreign_agents.remove(aid);
                tracker.owned_agents.insert(aid.to_string());
            } else {
                tracker.owned_agents.remove(aid);
                tracker.foreign_agents.insert(aid.to_string());
            }
        }
    }
    if tracker.owned_agents.contains(agent_id) {
        true
    } else {
        tracker.foreign_agents.insert(agent_id.to_string());
        false
    }
}

async fn run_single_session_stream(
    host_state: &crate::host_server::HostSharedState,
    active: &ActiveDaemonSession,
    tracker: &mut SessionCursorTracker,
) {
    let http_client = &host_state.http_client;
    let center = &host_state.notification_center;
    let ui = host_state.ui_bridge.clone();

    // 1. Exchange refresh_token for a fresh access_token via serialized host refresh lock
    //    so background reconnects never race with WebView JTI rotation!
    let Ok(refresh_json) =
        crate::host_server::refresh_stored_session_serialized(host_state, &active.im_origin).await
    else {
        return;
    };
    let Some(access_token) = refresh_json["access_token"].as_str().map(str::to_string) else {
        return;
    };
    let self_user_id = refresh_json["user"]["id"]
        .as_str()
        .unwrap_or(&active.session.user_id)
        .to_string();
    if let Some(owner_id) = refresh_json["user"]["owner_id"].as_str() {
        if !owner_id.is_empty() && owner_id != tracker.owner_id {
            tracker.owner_id = owner_id.to_string();
            tracker.owned_agents.clear();
            tracker.foreign_agents.clear();
        }
    }
    let user_locale = refresh_json["user"]["locale"].as_str().unwrap_or("zh");
    tracker.locale = user_locale.to_string();
    ui.set_locale(&tracker.locale);

    // 2. Seed initial unread counts, mute preferences, and baseline max_event_id from GET /im/v1/sync
    let synced_max = sync_conversations_and_cursor(
        host_state,
        active,
        &access_token,
    )
    .await;
    let resume_cursor = match tracker.cursor {
        Some(existing) => existing,
        None => {
            let baseline = synced_max.unwrap_or(0);
            tracker.cursor = Some(baseline);
            baseline
        }
    };

    // 3. Mint WS ticket and connect to /im/ws/user
    let ticket_url = format!("{}/im/v1/auth/ws-ticket", active.im_origin);
    let Ok(ticket_res) = http_client
        .post(&ticket_url)
        .bearer_auth(&access_token)
        .json(&json!({}))
        .send()
        .await
    else {
        return;
    };
    if !ticket_res.status().is_success() {
        return;
    }
    let Ok(ticket_json) = ticket_res.json::<Value>().await else {
        return;
    };
    let Some(ticket) = ticket_json["ticket"].as_str() else {
        return;
    };

    let Ok(mut ws_url) = url::Url::parse(&active.im_origin) else {
        return;
    };
    let ws_scheme = if ws_url.scheme() == "https" {
        "wss"
    } else {
        "ws"
    };
    let _ = ws_url.set_scheme(ws_scheme);
    ws_url.set_path("/im/ws/user");
    ws_url.query_pairs_mut().append_pair("ticket", ticket);

    let Ok(mut req) = ws_url.as_str().into_client_request() else {
        return;
    };
    if let Ok(origin_hdr) = HeaderValue::from_str(&active.im_origin) {
        req.headers_mut().insert("Origin", origin_hdr);
    }

    let Ok((mut ws_stream, _)) = tokio_tungstenite::connect_async(req).await else {
        return;
    };

    // 4. Complete `/im/ws/user` handshake immediately with `{ op: "resume", after_event_id }`
    //    so IM marks this subscriber `ready = true` without waiting for the 30s fallback timer!
    let resume_frame = json!({
        "op": "resume",
        "after_event_id": resume_cursor,
    })
    .to_string();
    if ws_stream
        .send(TungsteniteMsg::Text(resume_frame))
        .await
        .is_err()
    {
        return;
    }
    host_state.with_notification_session(active, || center.set_ws_connected(true));

    let mut pending_agent_senders: HashMap<String, String> = HashMap::new();
    let mut pending_agent_cards: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut ping_interval = tokio::time::interval(Duration::from_secs(25));
    ping_interval.tick().await;

    loop {
        tokio::select! {
            _ = ping_interval.tick() => {
                if ws_stream
                    .send(TungsteniteMsg::Text("{\"op\":\"ping\"}".to_string()))
                    .await
                    .is_err()
                {
                    break;
                }
            }
            next_msg = ws_stream.next() => {
                let Some(Ok(msg)) = next_msg else {
                    break;
                };
                let Ok(text) = msg.into_text() else {
                    continue;
                };
                let Ok(frame) = serde_json::from_str::<Value>(&text) else {
                    continue;
                };

                match frame["op"].as_str() {
                    Some("pong") => continue,
                    Some("membership_changed") => break,
                    Some("resync_required") => {
                        if let Some(latest_max) = sync_conversations_and_cursor(
                            host_state,
                            active,
                            &access_token,
                        )
                        .await
                        {
                            tracker.cursor = Some(latest_max);
                        }
                        break;
                    }
                    _ => {}
                }

                let Some((event_type, mut payload, event_id)) = unwrap_user_stream_frame(&frame) else {
                    continue;
                };
                let frame_hint = parse_frame_notification_hint(&frame);
                if let Some(eid) = event_id {
                    let prev = tracker.cursor.unwrap_or(0);
                    if eid <= prev {
                        continue;
                    }
                    tracker.cursor = Some(eid);
                }

                // Synchronize unread badge and conversation mute/title cache
                match event_type.as_str() {
                    "conversation.updated" | "conversation.preference_updated" | "conversation.read" => {
                        host_state.with_notification_session(active, || center.upsert_conversation(&payload, ui.as_ref()));
                    }
                    "conversation.membership_changed"
                    | "conversation.deleted"
                    | "message.receipts_changed"
                    | "message.discarded" => {
                        if event_type == "message.discarded" {
                            if let Some(mid) = non_empty_str(&payload["message_id"]) {
                                pending_agent_senders.remove(mid);
                                pending_agent_cards.remove(mid);
                            }
                        }
                        let _ = sync_conversations_and_cursor(
                            host_state,
                            active,
                            &access_token,
                        )
                        .await;
                    }
                    "message.created" => {
                        let cid = payload["conversation_id"].as_str().unwrap_or("");
                        let sender_uid = non_empty_str(&payload["sender_user_id"])
                            .or_else(|| non_empty_str(&payload["sender"]["id"]))
                            .unwrap_or("");
                        let sender_type = non_empty_str(&payload["sender_type"])
                            .or_else(|| non_empty_str(&payload["sender"]["type"]))
                            .unwrap_or("");
                        if sender_type == "agent" {
                            if let Some(mid) =
                                non_empty_str(&payload["message_id"]).or_else(|| non_empty_str(&payload["id"]))
                            {
                                if let Some(sname) = non_empty_str(&payload["sender"]["display_name"])
                                    .or_else(|| non_empty_str(&payload["sender_display_name"]))
                                    .or_else(|| non_empty_str(&payload["sender_name"]))
                                {
                                    if pending_agent_senders.len() >= 128 {
                                        pending_agent_senders.clear();
                                    }
                                    pending_agent_senders.insert(mid.to_string(), sname.to_string());
                                }
                                if has_interactive_card(&payload) {
                                    if pending_agent_cards.len() >= 128 {
                                        pending_agent_cards.clear();
                                    }
                                    pending_agent_cards.insert(mid.to_string());
                                }
                            }
                        }
                        let attention_now = ui.window_attention();
                        let focused_here = attention_now.visible_and_focused
                            && is_viewing_conversation_route(&attention_now.current_route, cid);
                        if let Some(ref hint) = frame_hint {
                            host_state.with_notification_session(active, || apply_hint_conversation_unread(
                                center,
                                ui.as_ref(),
                                &attention_now,
                                &payload,
                                hint,
                            ));
                        } else {
                            let allowed_in_thread = is_thread_audience_allowed(&payload, &self_user_id);
                            let is_self_author = !sender_uid.is_empty()
                                && normalize_user_id(sender_uid) == normalize_user_id(&self_user_id);
                            if non_empty_str(&payload["thread_root_message_id"]).is_some() {
                                if allowed_in_thread && !is_self_author {
                                    let _ = sync_conversations_and_cursor(
                                        host_state,
                                        active,
                                        &access_token,
                                    )
                                    .await;
                                }
                            } else if allowed_in_thread && !focused_here {
                                host_state.with_notification_session(active, || center.on_message_created(
                                    cid,
                                    is_self_author,
                                    payload["unread_count"].as_u64(),
                                    ui.as_ref(),
                                ));
                            }
                        }
                    }
                    "message.completed" | "permission.request" => {
                        if let Some(ref hint) = frame_hint {
                            let attention_now = ui.window_attention();
                            host_state.with_notification_session(active, || apply_hint_conversation_unread(
                                center,
                                ui.as_ref(),
                                &attention_now,
                                &payload,
                                hint,
                            ));
                        }
                    }
                    _ => {}
                }

                if matches!(
                    event_type.as_str(),
                    "agent.created"
                        | "agent.updated"
                        | "agent.deleted"
                        | "agent.status_changed"
                        | "agent.lifecycle.changed"
                ) {
                    tracker.owned_agents.clear();
                    tracker.foreign_agents.clear();
                }

                if let Some(ref hint) = frame_hint {
                    if !hint.eligible || hint.replayed == Some(true) {
                        continue;
                    }
                    if tracker
                        .notified_dedupe_keys
                        .iter()
                        .any(|seen| seen == &hint.dedupe_key)
                    {
                        continue;
                    }
                    let (muted_by_conv, titles_by_conv) = center.snapshot_maps();
                    let attention = ui.window_attention();
                    if let Some(notif) = classify_from_notification_hint(
                        hint,
                        &muted_by_conv,
                        &titles_by_conv,
                        &attention,
                        &tracker.locale,
                    ) {
                        if tracker.notified_dedupe_keys.len() >= 128 {
                            tracker.notified_dedupe_keys.pop_front();
                        }
                        tracker.notified_dedupe_keys.push_back(hint.dedupe_key.clone());
                        deliver_os_notification(host_state, active, &notif);
                    }
                    continue;
                }

                let is_terminal_agent_card_create = event_type == "message.created"
                    && non_empty_str(&payload["sender_type"])
                        .or_else(|| non_empty_str(&payload["sender"]["type"]))
                        == Some("agent")
                    && payload["delivery_status"].as_str() == Some("completed")
                    && has_interactive_card(&payload);
                if event_type == "message.completed" || is_terminal_agent_card_create {
                    if let Some(mid) = non_empty_str(&payload["message_id"]).map(str::to_string) {
                        if pending_agent_cards.remove(&mid) {
                            if let Some(obj) = payload.as_object_mut() {
                                obj.insert("has_interactive_card".to_string(), json!(true));
                            }
                        }
                        if tracker.notified_completed_messages.iter().any(|x| x == &mid) {
                            continue;
                        }
                        if tracker.notified_completed_messages.len() >= 64 {
                            tracker.notified_completed_messages.pop_front();
                        }
                        tracker.notified_completed_messages.push_back(mid);
                    }
                }

                // Only notify `agent.work.updated` (`waiting_permission`) for Agents owned by this session's owner_id!
                if event_type == "agent.work.updated" {
                    let aid_initial = payload["agent_id"].as_str().unwrap_or("");
                    if !ensure_agent_owned_by_session(
                        http_client,
                        &active.im_origin,
                        &access_token,
                        tracker,
                        aid_initial,
                    )
                    .await
                    {
                        continue;
                    }
                    payload = enrich_work_updated_payload(
                        http_client,
                        &active.im_origin,
                        &access_token,
                        &payload,
                    )
                    .await;
                    let aid = payload["agent_id"].as_str().unwrap_or("");
                    let status = payload["status"]
                        .as_str()
                        .or_else(|| payload["main_execution"].as_str())
                        .unwrap_or("");
                    if !aid.is_empty() {
                        let prev = tracker
                            .notified_work_status
                            .insert(aid.to_string(), status.to_string());
                        if prev.as_deref() == Some("waiting_permission")
                            && status == "waiting_permission"
                        {
                            continue;
                        }
                    }
                }

                let (muted_by_conv, titles_by_conv) = center.snapshot_maps();
                let attention = ui.window_attention();
                if let Some(notif) = classify_user_stream_event_localized(
                    &event_type,
                    &payload,
                    &self_user_id,
                    &muted_by_conv,
                    &titles_by_conv,
                    &pending_agent_senders,
                    &attention,
                    &tracker.locale,
                ) {
                    deliver_os_notification(host_state, active, &notif);
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn classifies_canonical_im_ws_user_data_envelopes_and_respects_mute_and_focus() {
        let mut muted = HashMap::new();
        muted.insert("muted-conv".to_string(), true);
        let mut titles = HashMap::new();
        titles.insert("c1".to_string(), "研发群".to_string());
        let mut pending_agents = HashMap::new();
        pending_agents.insert("m-agent-1".to_string(), "研发助手 PA".to_string());

        let hidden = WindowAttentionState {
            visible_and_focused: false,
            current_route: "/chat/c1".to_string(),
        };
        let focused_same = WindowAttentionState {
            visible_and_focused: true,
            current_route: "/chat/c1".to_string(),
        };

        // 1. Canonical non-streaming `message.completed` (where `sender` came from earlier `message.created` in `data`)
        let completed_frame = json!({
            "op": "event",
            "event_type": "message.completed",
            "event_id": 12,
            "conversation_id": "c1",
            "data": {
                "message_id": "m-agent-1",
                "content": "整理完毕",
                "token_usage": null,
                "delivery_status": "completed"
            }
        });
        let (et, body, eid) = unwrap_user_stream_frame(&completed_frame).unwrap();
        assert_eq!(eid, Some(12));
        let completed = classify_user_stream_event_with_senders(
            &et,
            &body,
            "u-self",
            &muted,
            &titles,
            &pending_agents,
            &hidden,
        )
        .unwrap();
        assert_eq!(completed.kind, "message_completed");
        assert_eq!(completed.title, "研发助手 PA · 回复完成");
        assert_eq!(completed.target_route, "/chat/c1");
        assert!(classify_user_stream_event(
            "message.completed",
            &json!({ "conversation_id": "c1", "content": "整理完毕" }),
            "u-self",
            &muted,
            &titles,
            &focused_same,
        )
        .is_none());
        assert!(classify_user_stream_event(
            "message.completed",
            &json!({ "conversation_id": "muted-conv", "content": "quiet" }),
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .is_none());

        // 2. Canonical `message.created` with top-level `sender_type` + `sender_user_id` inside `data`
        let self_frame = json!({
            "op": "event",
            "event_type": "message.created",
            "conversation_id": "c1",
            "data": {
                "message_id": "m-self",
                "sender_type": "user",
                "sender_user_id": "u-self",
                "content": "mine"
            }
        });
        let (et_self, body_self, _) = unwrap_user_stream_frame(&self_frame).unwrap();
        assert!(classify_user_stream_event(
            &et_self,
            &body_self,
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .is_none());

        let mention_frame = json!({
            "op": "event",
            "event_type": "message.created",
            "conversation_id": "muted-conv",
            "data": {
                "message_id": "m-mention",
                "sender_type": "user",
                "sender_user_id": "u-peer",
                "sender": { "type": "user", "id": "u-peer", "display_name": "小林" },
                "content": "请看下 <mention type=\"user\" target_id=\"u-self\" /> 这个构建"
            }
        });
        let (et_men, body_men, _) = unwrap_user_stream_frame(&mention_frame).unwrap();
        let mention = classify_user_stream_event(
            &et_men,
            &body_men,
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .unwrap();
        assert_eq!(mention.kind, "mention");
        assert_eq!(mention.target_route, "/chat/muted-conv");

        // 3. Canonical `permission.request` (`permission_request` nested inside `data`) -> /chat/<id>
        let perm_frame = json!({
            "op": "event",
            "event_type": "permission.request",
            "conversation_id": "c1",
            "data": {
                "message_id": "m-perm",
                "permission_request": {
                    "request_id": "req-1",
                    "tool_name": "bash",
                    "tool_input": { "command": "ls" },
                    "question": "Allow bash?",
                    "options": ["allow", "deny"],
                    "status": "pending"
                }
            }
        });
        let (et_perm, body_perm, _) = unwrap_user_stream_frame(&perm_frame).unwrap();
        let chat_perm = classify_user_stream_event(
            &et_perm,
            &body_perm,
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .unwrap();
        assert_eq!(chat_perm.kind, "chat_permission");
        assert_eq!(chat_perm.target_route, "/chat/c1");

        // 4. `agent.work.updated` (`main_execution == "waiting_permission"`) -> /settings/agents/<id>?view=work
        let work_perm = classify_user_stream_event(
            "agent.work.updated",
            &json!({ "agent_id": "eng-1", "display_name": "研发助手 E1", "main_execution": "waiting_permission" }),
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .unwrap();
        assert_eq!(work_perm.kind, "work_permission");
        assert_eq!(work_perm.target_route, "/settings/agents/eng-1?view=work");

        // 5. Muted conversation suppresses `permission.request`, and English locale formats localized copy
        assert!(classify_user_stream_event(
            "permission.request",
            &json!({ "conversation_id": "muted-conv", "permission_request": { "tool_name": "bash", "status": "pending" } }),
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .is_none());

        let en_done = classify_user_stream_event_localized(
            "message.completed",
            &json!({ "conversation_id": "c1", "message_id": "m-agent-1", "content": "All done" }),
            "u-self",
            &muted,
            &titles,
            &pending_agents,
            &hidden,
            "en-US",
        )
        .unwrap();
        assert_eq!(en_done.title, "研发助手 PA · Reply ready");
    }

    #[test]
    fn filters_unfollowed_group_threads_and_deep_links_followed_threads_and_interactive_cards() {
        let muted = HashMap::new();
        let mut titles = HashMap::new();
        titles.insert("c-group".to_string(), "产品讨论群".to_string());
        let mut pending_agents = HashMap::new();
        pending_agents.insert("m-card-done".to_string(), "交互助手".to_string());

        let hidden = WindowAttentionState {
            visible_and_focused: false,
            current_route: "/chat".to_string(),
        };
        let focused_prefix_neighbor = WindowAttentionState {
            visible_and_focused: true,
            current_route: "/chat/c-group-2".to_string(),
        };

        // 1. Unfollowed group thread reply (`thread_notify_user_ids` excludes `u-self`) is suppressed
        assert!(classify_user_stream_event(
            "message.created",
            &json!({
                "conversation_id": "c-group",
                "message_id": "m-t1",
                "thread_root_message_id": "root-42",
                "thread_notify_user_ids": ["u-other"],
                "sender_type": "user",
                "sender_user_id": "u-peer",
                "sender_display_name": "阿杰",
                "content": "这个话题里继续讨论"
            }),
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .is_none());

        // 2. Followed group thread reply (`thread_notify_user_ids` includes `u-self`) deep-links to `?thread=root-42`
        //    and is NOT falsely suppressed when focused on a prefix-neighbor route `/chat/c-group-2`
        let followed_thread = classify_user_stream_event(
            "message.created",
            &json!({
                "conversation_id": "c-group",
                "message_id": "m-t2",
                "thread_root_message_id": "root-42",
                "thread_notify_user_ids": ["u-other", "u-self"],
                "sender_type": "user",
                "sender_user_id": "u-peer",
                "sender_display_name": "阿杰",
                "content": "已同步给你"
            }),
            "u-self",
            &muted,
            &titles,
            &focused_prefix_neighbor,
        )
        .unwrap();
        assert_eq!(followed_thread.kind, "human_message");
        assert_eq!(followed_thread.target_route, "/chat/c-group?thread=root-42");

        // 3. Thread-scoped `permission.request` respects `thread_notify_user_ids` and deep-links to `?thread=`
        assert!(classify_user_stream_event(
            "permission.request",
            &json!({
                "conversation_id": "c-group",
                "thread_root_message_id": "root-42",
                "thread_notify_user_ids": ["u-other"],
                "permission_request": { "tool_name": "bash", "status": "pending" }
            }),
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .is_none());
        let thread_perm = classify_user_stream_event(
            "permission.request",
            &json!({
                "conversation_id": "c-group",
                "thread_root_message_id": "root-42",
                "thread_notify_user_ids": ["u-self"],
                "permission_request": { "tool_name": "bash", "status": "pending" }
            }),
            "u-self",
            &muted,
            &titles,
            &hidden,
        )
        .unwrap();
        assert_eq!(thread_perm.target_route, "/chat/c-group?thread=root-42");

        // 4. Card-only Agent completion (`has_interactive_card` or terminal `publishAgent` `message.created`)
        let card_completed = classify_user_stream_event_with_senders(
            "message.completed",
            &json!({
                "conversation_id": "c-group",
                "message_id": "m-card-done",
                "content": "",
                "has_interactive_card": true,
                "delivery_status": "completed"
            }),
            "u-self",
            &muted,
            &titles,
            &pending_agents,
            &hidden,
        )
        .unwrap();
        assert_eq!(card_completed.kind, "message_completed");
        assert_eq!(card_completed.body, "[交互卡片]");

        let publish_card_created = classify_user_stream_event_localized(
            "message.created",
            &json!({
                "conversation_id": "c-group",
                "message_id": "m-pub-card",
                "thread_root_message_id": "root-99",
                "thread_notify_user_ids": ["u-self"],
                "sender_type": "agent",
                "sender_user_id": "agent:pa",
                "sender_display_name": "PA",
                "content": "",
                "delivery_status": "completed",
                "interactive": { "format": "openui", "source": "root = Text(\"Hi\")" }
            }),
            "u-self",
            &muted,
            &titles,
            &pending_agents,
            &hidden,
            "en",
        )
        .unwrap();
        assert_eq!(publish_card_created.kind, "message_completed");
        assert_eq!(publish_card_created.title, "PA · Reply ready");
        assert_eq!(publish_card_created.body, "[Interactive card]");
        assert_eq!(publish_card_created.target_route, "/chat/c-group?thread=root-99");
    }

    #[test]
    fn matches_shared_unread_badge_golden_vectors_and_syncs_read_and_mute_frames() {
        #[derive(Deserialize)]
        struct VectorFile {
            cases: Vec<UnreadCase>,
        }
        #[derive(Deserialize)]
        struct UnreadCase {
            id: String,
            conversations: Vec<Value>,
            expected_row_unread: HashMap<String, u64>,
            expected_badge_total: u64,
        }

        let raw = include_str!("../../../src/IM/shared/unread-badge-test-cases.json");
        let parsed: VectorFile = serde_json::from_str(raw).expect("valid unread vector json");
        let center = NotificationCenterState::default();
        let ui = NoopUiBridge::default();

        for case in parsed.cases {
            for item in &case.conversations {
                let cid = item["id"].as_str().unwrap();
                let row = compute_conversation_row_unread(
                    item["unread_count"].as_i64(),
                    item["local_unseen"].as_bool().unwrap_or(false),
                );
                assert_eq!(row, case.expected_row_unread[cid], "{}:{}", case.id, cid);
            }
            assert_eq!(
                compute_unread_badge_total(&case.conversations),
                case.expected_badge_total,
                "pure {}",
                case.id
            );
            center.replace_conversations(&case.conversations, &ui);
            assert_eq!(center.unread(), case.expected_badge_total, "center {}", case.id);
            assert_eq!(
                *ui.badge_count.lock().unwrap(),
                case.expected_badge_total,
                "badge {}",
                case.id
            );
        }

        // Verify live `conversation.read` and `conversation.preference_updated` badge sync
        center.replace_conversations(
            &[
                json!({ "id": "c-agent", "unread_count": 4, "is_muted": false }),
                json!({ "id": "c-team", "unread_count": 2, "is_muted": false }),
            ],
            &ui,
        );
        assert_eq!(center.unread(), 6);

        center.upsert_conversation(
            &json!({ "conversation_id": "c-agent", "unread_count": 0, "is_muted": false }),
            &ui,
        );
        assert_eq!(center.unread(), 2);
        assert_eq!(*ui.badge_count.lock().unwrap(), 2);

        center.upsert_conversation(
            &json!({ "conversation_id": "c-team", "unread_count": 2, "is_muted": true }),
            &ui,
        );
        assert_eq!(center.unread(), 0);
        assert_eq!(*ui.badge_count.lock().unwrap(), 0);

        // Verify `message.completed` (e.g. streaming Agent @mention in a group thread) and
        // `permission.request` materialize `conversation_unread` on the Desktop badge unless focused
        let unfocused = WindowAttentionState {
            visible_and_focused: false,
            current_route: "/chat/other".to_string(),
        };
        let completed_hint = parse_frame_notification_hint(&json!({
            "notification_hint": {
                "eligible": true,
                "kind": "mention",
                "dedupe_key": "message:m-stream-men",
                "is_muted": false,
                "mentions_viewer": true,
                "conversation_id": "c-agent",
                "conversation_title": "Agent Thread",
                "conversation_unread": 1,
                "target_route": "/chat/c-agent?thread=root-1"
            }
        }))
        .unwrap();
        apply_hint_conversation_unread(
            &center,
            &ui,
            &unfocused,
            &json!({ "conversation_id": "c-agent" }),
            &completed_hint,
        );
        assert_eq!(center.unread(), 1);
        assert_eq!(*ui.badge_count.lock().unwrap(), 1);

        let focused_same_chat = WindowAttentionState {
            visible_and_focused: true,
            current_route: "/chat/c-agent?thread=root-1".to_string(),
        };
        let perm_hint = parse_frame_notification_hint(&json!({
            "notification_hint": {
                "eligible": true,
                "kind": "chat_permission",
                "dedupe_key": "perm:req-1",
                "is_muted": false,
                "mentions_viewer": false,
                "conversation_id": "c-agent",
                "conversation_unread": 3,
                "target_route": "/chat/c-agent?thread=root-1"
            }
        }))
        .unwrap();
        apply_hint_conversation_unread(
            &center,
            &ui,
            &focused_same_chat,
            &json!({ "conversation_id": "c-agent" }),
            &perm_hint,
        );
        assert_eq!(center.unread(), 1, "focused active chat must not inflate badge");
        apply_hint_conversation_unread(
            &center,
            &ui,
            &unfocused,
            &json!({}),
            &perm_hint,
        );
        assert_eq!(center.unread(), 3);
        assert_eq!(*ui.badge_count.lock().unwrap(), 3);
    }

    #[test]
    fn consumes_notification_hint_for_external_shadow_work_short_circuit_and_mute_override() {
        let mut muted = HashMap::new();
        muted.insert("muted-grp".to_string(), true);
        let titles = HashMap::new();
        let hidden = WindowAttentionState {
            visible_and_focused: false,
            current_route: "/chat".to_string(),
        };

        // 1. Owner's own Feishu/WeChat mirror message (`eligible: false`) is suppressed
        let self_mirror_frame = json!({
            "op": "event",
            "event_type": "message.created",
            "notification_hint": {
                "eligible": false,
                "dedupe_key": "message:m-self-wx",
                "is_muted": false,
                "mentions_viewer": false,
                "conversation_id": "wx-shadow",
                "target_route": "/chat/wx-shadow"
            }
        });
        let self_hint = parse_frame_notification_hint(&self_mirror_frame).unwrap();
        assert!(classify_from_notification_hint(&self_hint, &muted, &titles, &hidden, "zh").is_none());

        // 2. External peer inbound message (`eligible: true`) notifies even though `sender_user_id == owner`
        let peer_frame = json!({
            "op": "event",
            "event_type": "message.created",
            "notification_hint": {
                "eligible": true,
                "kind": "human_message",
                "dedupe_key": "message:m-peer-wx",
                "is_muted": false,
                "mentions_viewer": false,
                "conversation_id": "wx-shadow",
                "conversation_title": "客户微信",
                "sender_name": "张客户",
                "preview_text": "合同已发你",
                "target_route": "/chat/wx-shadow"
            }
        });
        let peer_hint = parse_frame_notification_hint(&peer_frame).unwrap();
        let peer_notif = classify_from_notification_hint(&peer_hint, &muted, &titles, &hidden, "zh").unwrap();
        assert_eq!(peer_notif.kind, "human_message");
        assert_eq!(peer_notif.title, "张客户");
        assert_eq!(peer_notif.body, "合同已发你");
        assert_eq!(peer_notif.target_route, "/chat/wx-shadow");

        // 3. Muted @mention passes while ordinary muted message is suppressed
        let muted_mention_hint = parse_frame_notification_hint(&json!({
            "notification_hint": {
                "eligible": true,
                "kind": "mention",
                "dedupe_key": "message:m-men",
                "is_muted": true,
                "mentions_viewer": true,
                "conversation_id": "muted-grp",
                "sender_name": "小林",
                "preview_text": "@Owner 请确认",
                "target_route": "/chat/muted-grp?thread=root-1"
            }
        }))
        .unwrap();
        let men_notif =
            classify_from_notification_hint(&muted_mention_hint, &muted, &titles, &hidden, "zh").unwrap();
        assert_eq!(men_notif.kind, "mention");
        assert_eq!(men_notif.target_route, "/chat/muted-grp?thread=root-1");

        // 4. Non-waiting `agent.work.updated` carries `eligible: false` (short-circuits HTTP polling!)
        let work_idle_hint = parse_frame_notification_hint(&json!({
            "notification_hint": {
                "eligible": false,
                "dedupe_key": "work:pa_main:3",
                "is_muted": false,
                "mentions_viewer": false,
                "agent_id": "pa_main",
                "target_route": "/settings/agents/pa_main?view=work"
            }
        }))
        .unwrap();
        assert!(classify_from_notification_hint(&work_idle_hint, &muted, &titles, &hidden, "en").is_none());

        // 5. `waiting_permission` `agent.work.updated` fires `work_permission` without HTTP round-trips
        let work_perm_hint = parse_frame_notification_hint(&json!({
            "notification_hint": {
                "eligible": true,
                "kind": "work_permission",
                "dedupe_key": "work-perm:pa_main:s1:t1",
                "is_muted": false,
                "mentions_viewer": false,
                "agent_id": "pa_main",
                "sender_name": "PA Main",
                "target_route": "/settings/agents/pa_main?view=work"
            }
        }))
        .unwrap();
        let work_notif =
            classify_from_notification_hint(&work_perm_hint, &muted, &titles, &hidden, "en").unwrap();
        assert_eq!(work_notif.kind, "work_permission");
        assert_eq!(work_notif.title, "PA Main · Tool approval needed");
        assert_eq!(work_notif.target_route, "/settings/agents/pa_main?view=work");
    }
}
