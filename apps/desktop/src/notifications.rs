use crate::config::{append_private_jsonl, random_hex_token, DesktopPaths, StoredSessionEntry};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{HashMap, VecDeque};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::watch;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::HeaderValue;
use tokio_tungstenite::tungstenite::Message as TungsteniteMsg;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DesktopNotificationRecord {
    pub id: String,
    pub kind: String,
    pub title: String,
    pub body: String,
    pub target_route: String,
    pub created_at: u64,
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
    fn reload_webview(&self, target_route: Option<&str>);
}

#[derive(Default)]
pub struct NoopUiBridge {
    pub badge_count: Mutex<u64>,
    pub activated_routes: Mutex<Vec<String>>,
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

    fn reload_webview(&self, _target_route: Option<&str>) {}
}

#[derive(Debug, Clone)]
pub struct ActiveDaemonSession {
    pub im_origin: String,
    pub session: StoredSessionEntry,
}

#[derive(Debug, Clone, Default)]
struct ConvSummaryEntry {
    unread: u64,
    muted: bool,
    title: String,
}

pub struct NotificationCenterState {
    recent: Mutex<VecDeque<DesktopNotificationRecord>>,
    unread_total: Mutex<u64>,
    conversations: Mutex<HashMap<String, ConvSummaryEntry>>,
    ws_connected: AtomicBool,
}

impl Default for NotificationCenterState {
    fn default() -> Self {
        Self {
            recent: Mutex::new(VecDeque::with_capacity(64)),
            unread_total: Mutex::new(0),
            conversations: Mutex::new(HashMap::new()),
            ws_connected: AtomicBool::new(false),
        }
    }
}

impl NotificationCenterState {
    pub fn record(&self, paths: &DesktopPaths, item: DesktopNotificationRecord) {
        append_private_jsonl(&paths.notifications_log_path(), &item);
        let mut guard = self.recent.lock().unwrap();
        if guard.len() >= 64 {
            guard.pop_front();
        }
        guard.push_back(item);
    }

    pub fn list(&self) -> Vec<DesktopNotificationRecord> {
        self.recent.lock().unwrap().iter().cloned().collect()
    }

    pub fn find_route(&self, id: &str) -> Option<String> {
        self.recent
            .lock()
            .unwrap()
            .iter()
            .find(|item| item.id == id)
            .map(|item| item.target_route.clone())
    }

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
                let unread = item["unread_count"].as_u64().unwrap_or(0);
                let title = item["title"].as_str().unwrap_or("").to_string();
                next.insert(
                    cid.to_string(),
                    ConvSummaryEntry {
                        unread: if muted { 0 } else { unread },
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

fn now_epoch_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
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
    match event_type {
        "message.completed" => {
            if payload["delivery_status"].as_str() == Some("failed") {
                return None;
            }
            if payload["sender_type"].as_str() == Some("user") {
                return None;
            }
            if let Some(uid) = non_empty_str(&payload["sender_user_id"]) {
                if uid == self_user_id {
                    return None;
                }
            }
            let cid = payload["conversation_id"].as_str().unwrap_or("");
            if cid.is_empty() || muted_conversations.get(cid).copied().unwrap_or(false) {
                return None;
            }
            let target_route = format!("/chat/{}", cid);
            if attention.visible_and_focused && attention.current_route.starts_with(&target_route) {
                return None;
            }
            let msg_id = payload["message_id"].as_str().unwrap_or("");
            let sender = non_empty_str(&payload["sender"]["display_name"])
                .or_else(|| non_empty_str(&payload["sender_display_name"]))
                .or_else(|| non_empty_str(&payload["sender_name"]))
                .or_else(|| pending_agent_senders.get(msg_id).map(String::as_str))
                .or_else(|| conv_titles.get(cid).map(String::as_str))
                .unwrap_or("助手");
            let preview =
                strip_mention_xml(payload["content"].as_str().unwrap_or("已完成本轮回复"));
            let body: String = preview.chars().take(90).collect();
            Some(DesktopNotificationRecord {
                id: format!("notif-{}", random_hex_token(8)),
                kind: "message_completed".to_string(),
                title: format!("{} · 回复完成", sender),
                body: if body.is_empty() {
                    "已完成本轮回复".to_string()
                } else {
                    body
                },
                target_route,
                created_at: now_epoch_secs(),
            })
        }
        "message.created" => {
            let cid = payload["conversation_id"].as_str().unwrap_or("");
            if cid.is_empty() {
                return None;
            }
            let sender_type = non_empty_str(&payload["sender_type"])
                .or_else(|| non_empty_str(&payload["sender"]["type"]))
                .unwrap_or("");
            let sender_user_id = non_empty_str(&payload["sender_user_id"])
                .or_else(|| non_empty_str(&payload["sender"]["id"]))
                .unwrap_or("");
            if sender_type != "user" || sender_user_id.is_empty() || sender_user_id == self_user_id {
                return None;
            }
            let content = payload["content"].as_str().unwrap_or("");
            let is_mention = mentions_user(content, self_user_id);
            if !is_mention && muted_conversations.get(cid).copied().unwrap_or(false) {
                return None;
            }
            let target_route = format!("/chat/{}", cid);
            if attention.visible_and_focused && attention.current_route.starts_with(&target_route) {
                return None;
            }
            let sender_name = non_empty_str(&payload["sender_display_name"])
                .or_else(|| non_empty_str(&payload["sender"]["display_name"]))
                .or_else(|| non_empty_str(&payload["sender_name"]))
                .or_else(|| conv_titles.get(cid).map(String::as_str))
                .unwrap_or("新消息");
            let clean = strip_mention_xml(content);
            let body: String = clean.chars().take(90).collect();
            Some(DesktopNotificationRecord {
                id: format!("notif-{}", random_hex_token(8)),
                kind: if is_mention {
                    "mention".to_string()
                } else {
                    "human_message".to_string()
                },
                title: if is_mention {
                    format!("{} 在会话中 @提及了你", sender_name)
                } else {
                    sender_name.to_string()
                },
                body: if body.is_empty() {
                    "发来一条新消息".to_string()
                } else {
                    body
                },
                target_route,
                created_at: now_epoch_secs(),
            })
        }
        "permission.request" => {
            let req_obj = payload.get("permission_request").unwrap_or(payload);
            let status = req_obj["status"]
                .as_str()
                .or_else(|| payload["status"].as_str())
                .unwrap_or("pending");
            if status != "pending" {
                return None;
            }
            let cid = payload["conversation_id"]
                .as_str()
                .or_else(|| req_obj["conversation_id"].as_str())
                .unwrap_or("");
            if cid.is_empty() {
                return None;
            }
            let target_route = format!("/chat/{}", cid);
            if attention.visible_and_focused && attention.current_route.starts_with(&target_route) {
                return None;
            }
            let tool = non_empty_str(&req_obj["tool_name"])
                .or_else(|| non_empty_str(&req_obj["tool"]))
                .or_else(|| non_empty_str(&payload["tool_name"]))
                .or_else(|| non_empty_str(&payload["tool"]))
                .unwrap_or("工具执行");
            Some(DesktopNotificationRecord {
                id: format!("notif-{}", random_hex_token(8)),
                kind: "chat_permission".to_string(),
                title: "工具权限待确认".to_string(),
                body: format!("会话请求授权执行 {}", tool),
                target_route,
                created_at: now_epoch_secs(),
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
                id: format!("notif-{}", random_hex_token(8)),
                kind: "work_permission".to_string(),
                title: format!("{} · 等待工具授权", agent_name),
                body: "点击打开助手 Work 视图处理待决权限请求".to_string(),
                target_route,
                created_at: now_epoch_secs(),
            })
        }
        _ => None,
    }
}

fn deliver_os_notification(item: &DesktopNotificationRecord, ui: Arc<dyn DesktopUiBridge>) {
    if std::env::var("CREWDEN_SUPPRESS_OS_NOTIFICATIONS").as_deref() == Ok("1") {
        return;
    }

    #[cfg(target_os = "macos")]
    {
        let title = item.title.clone();
        let body = item.body.clone();
        let route = item.target_route.clone();
        std::thread::spawn(move || {
            let response = mac_notification_sys::Notification::new()
                .title(&title)
                .message(&body)
                .wait_for_click(true)
                .send();
            if let Ok(mac_notification_sys::NotificationResponse::Click)
            | Ok(mac_notification_sys::NotificationResponse::ActionButton(_)) = response
            {
                ui.activate_route(&route);
            }
        });
    }

    #[cfg(target_os = "windows")]
    {
        let title = item.title.clone();
        let body = item.body.clone();
        let route = item.target_route.clone();
        std::thread::spawn(move || {
            use tauri_winrt_notification::Toast;
            let _ = Toast::new(Toast::POWERSHELL_APP_ID)
                .title(&title)
                .text1(&body)
                .on_activated(move |_| {
                    ui.activate_route(&route);
                    Ok(())
                })
                .show();
        });
    }
}

struct SessionCursorTracker {
    im_origin: String,
    user_id: String,
    cursor: Option<u64>,
    notified_work_status: HashMap<String, String>,
    notified_completed_messages: VecDeque<String>,
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
                host_state
                    .notification_center
                    .clear_conversations(host_state.ui_bridge.as_ref());
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
                    cursor: None,
                    notified_work_status: HashMap::new(),
                    notified_completed_messages: VecDeque::with_capacity(64),
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
    http_client: &reqwest::Client,
    im_origin: &str,
    access_token: &str,
    center: &NotificationCenterState,
    ui: &dyn DesktopUiBridge,
) -> Option<u64> {
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
                    center.replace_conversations(items, ui);
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
                    center.replace_conversations(list, ui);
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

async fn run_single_session_stream(
    host_state: &crate::host_server::HostSharedState,
    active: &ActiveDaemonSession,
    tracker: &mut SessionCursorTracker,
) {
    let paths = &host_state.paths;
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

    // 2. Seed initial unread counts, mute preferences, and baseline max_event_id from GET /im/v1/sync
    let synced_max = sync_conversations_and_cursor(
        http_client,
        &active.im_origin,
        &access_token,
        center,
        ui.as_ref(),
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
    center.set_ws_connected(true);

    let mut pending_agent_senders: HashMap<String, String> = HashMap::new();
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
                            http_client,
                            &active.im_origin,
                            &access_token,
                            center,
                            ui.as_ref(),
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
                        center.upsert_conversation(&payload, ui.as_ref());
                    }
                    "conversation.membership_changed"
                    | "conversation.deleted"
                    | "message.receipts_changed" => {
                        let _ = sync_conversations_and_cursor(
                            http_client,
                            &active.im_origin,
                            &access_token,
                            center,
                            ui.as_ref(),
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
                            if let (Some(mid), Some(sname)) = (
                                non_empty_str(&payload["message_id"]).or_else(|| non_empty_str(&payload["id"])),
                                non_empty_str(&payload["sender"]["display_name"])
                                    .or_else(|| non_empty_str(&payload["sender_display_name"]))
                                    .or_else(|| non_empty_str(&payload["sender_name"])),
                            ) {
                                if pending_agent_senders.len() >= 128 {
                                    pending_agent_senders.clear();
                                }
                                pending_agent_senders.insert(mid.to_string(), sname.to_string());
                            }
                        }
                        center.on_message_created(
                            cid,
                            sender_uid == self_user_id,
                            payload["unread_count"].as_u64(),
                            ui.as_ref(),
                        );
                    }
                    _ => {}
                }

                if event_type == "message.completed" {
                    if let Some(mid) = non_empty_str(&payload["message_id"]) {
                        if tracker.notified_completed_messages.iter().any(|x| x == mid) {
                            continue;
                        }
                        if tracker.notified_completed_messages.len() >= 64 {
                            tracker.notified_completed_messages.pop_front();
                        }
                        tracker.notified_completed_messages.push_back(mid.to_string());
                    }
                }

                // Enrich & deduplicate agent.work.updated waiting_permission transitions
                if event_type == "agent.work.updated" {
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
                if let Some(notif) = classify_user_stream_event_with_senders(
                    &event_type,
                    &payload,
                    &self_user_id,
                    &muted_by_conv,
                    &titles_by_conv,
                    &pending_agent_senders,
                    &attention,
                ) {
                    center.record(paths, notif.clone());
                    deliver_os_notification(&notif, ui.clone());
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
    }
}
