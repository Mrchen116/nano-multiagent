use crate::autostart::set_desktop_login_autostart;
use crate::config::{
    append_host_log, classify_deep_link_connect, current_desktop_platform_id,
    local_node_bridge_endpoint, normalize_im_origin, random_hex_token, resolve_default_im_origin,
    sha256_hex, write_private_json, DeepLinkConnectOutcome, DesktopPaths, HostRuntimeStateFile,
    PendingServerSwitch, PersistedHostConfig, StoredSessionEntry, StoredSessionsFile,
};
use crate::local_node::{
    ensure_seed_bundle_installed, has_pending_seed_bundle, open_external_url,
    open_or_reveal_workspace_path, reconcile_ready_seed_bundle, resolve_active_bundle,
    run_local_admin_sync, stop_all_managed_local_nodes, sync_seed_desktop_defaults,
};
use crate::notifications::{
    spawn_notification_daemon, ActiveDaemonSession, DesktopUiBridge, NotificationCenterState,
};
use axum::body::Body;
use axum::extract::ws::{Message as AxumWsMessage, WebSocket, WebSocketUpgrade};
use axum::extract::{DefaultBodyLimit, Path as AxumPath, Query, Request, State};
use axum::http::{HeaderMap, HeaderValue, Method, StatusCode, Uri};
use axum::response::{IntoResponse, Redirect, Response};
use axum::routing::{any, get, post, put};
use axum::{Json, Router};
use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs;
use std::net::SocketAddr;
use std::path::{Component, Path, PathBuf};
use std::pin::Pin;
use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncBufReadExt, AsyncRead, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::net::TcpListener;
use tokio::sync::{oneshot, watch};
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::Message as TungsteniteMsg;

const CAP_COOKIE_NAME: &str = "__crewden_desktop_cap";

#[derive(Clone)]
struct VerifiedAuthIdentity {
    owner_id: String,
    cached_at: Instant,
}

#[derive(Clone)]
struct LocalTrajectoryTicket {
    agent_id: String,
    session_id: String,
    owner_id: String,
    node_epoch: i64,
    access_token: String,
    im_origin: String,
    bridge_endpoint: String,
    expires_at: Instant,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SeedPreparationState {
    Ready,
    Preparing,
    Failed(String),
}

pub struct HostSharedState {
    pub paths: DesktopPaths,
    pub seed_archives_dir: Option<PathBuf>,
    pub dev_repo_root: Option<PathBuf>,
    pub port: u16,
    pub cap_token: String,
    pub boot_nonce: String,
    pub reload_token: String,
    pub host_config: RwLock<PersistedHostConfig>,
    pub sessions: RwLock<StoredSessionsFile>,
    pub seed_status: RwLock<SeedPreparationState>,
    pub pending_server_switch: Mutex<Option<PendingServerSwitch>>,
    pub deep_link_error: Mutex<Option<String>>,
    pub http_client: reqwest::Client,
    auth_cache: Mutex<HashMap<String, VerifiedAuthIdentity>>,
    trajectory_tickets: Mutex<HashMap<String, LocalTrajectoryTicket>>,
    pub session_tx: watch::Sender<Option<ActiveDaemonSession>>,
    pub session_epoch_tx: watch::Sender<u64>,
    pub notification_center: Arc<NotificationCenterState>,
    pub ui_bridge: Arc<dyn DesktopUiBridge>,
    pub shutdown_tx: Mutex<Option<oneshot::Sender<()>>>,
    pub refresh_lock: tokio::sync::Mutex<()>,
}

impl HostSharedState {
    pub fn is_seed_ready(&self) -> bool {
        matches!(*self.seed_status.read().unwrap(), SeedPreparationState::Ready)
    }

    pub fn seed_error(&self) -> Option<String> {
        match &*self.seed_status.read().unwrap() {
            SeedPreparationState::Failed(msg) => Some(msg.clone()),
            _ => None,
        }
    }
}

pub struct RunningHostServer {
    pub state: Arc<HostSharedState>,
    pub port: u16,
    pub bootstrap_url: String,
    shutdown_rx: Option<oneshot::Receiver<()>>,
}

impl RunningHostServer {
    pub fn bootstrap_url_for(&self, next_path: &str) -> String {
        let next = if next_path.starts_with('/') {
            next_path
        } else {
            "/chat"
        };
        let mut u = url::Url::parse(&format!("http://127.0.0.1:{}/desktop/bootstrap", self.port))
            .expect("valid loopback url");
        u.query_pairs_mut()
            .append_pair("nonce", &self.state.boot_nonce)
            .append_pair("next", next);
        u.to_string()
    }

    pub fn take_shutdown_receiver(&mut self) -> Option<oneshot::Receiver<()>> {
        self.shutdown_rx.take()
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn load_or_init_host_config(
    paths: &DesktopPaths,
    seed_archives_dir: Option<&Path>,
    override_origin: Option<&str>,
) -> PersistedHostConfig {
    let fallback_origin = resolve_default_im_origin(paths, seed_archives_dir);
    let mut cfg = match fs::read_to_string(paths.host_config_path())
        .ok()
        .and_then(|raw| serde_json::from_str::<PersistedHostConfig>(&raw).ok())
    {
        Some(mut disk_cfg) => {
            match normalize_im_origin(&disk_cfg.im_origin) {
                Ok(valid) => disk_cfg.im_origin = valid,
                Err(reason) => {
                    append_host_log(
                        Some(paths),
                        "WARN",
                        &format!(
                            "Resetting invalid persisted im_origin '{}' to '{}': {}",
                            disk_cfg.im_origin, fallback_origin, reason
                        ),
                    );
                    disk_cfg.im_origin = fallback_origin;
                    disk_cfg.context_epoch = disk_cfg.context_epoch.saturating_add(1);
                }
            }
            disk_cfg
        }
        None => PersistedHostConfig {
            persisted_port: 0,
            im_origin: fallback_origin,
            context_epoch: 1,
        },
    };
    if let Some(origin) = override_origin {
        if let Ok(norm) = normalize_im_origin(origin) {
            if cfg.im_origin != norm {
                cfg.im_origin = norm;
                cfg.context_epoch += 1;
            }
        }
    }
    if cfg.context_epoch == 0 {
        cfg.context_epoch = 1;
    }
    cfg
}

pub fn write_host_state_snapshot(state: &HostSharedState) -> Result<(), String> {
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let seed_ready = state.is_seed_ready();
    write_private_json(
        &state.paths.host_state_path(),
        &HostRuntimeStateFile {
            pid: std::process::id(),
            port: state.port,
            ready: seed_ready,
            host_ready: true,
            seed_ready,
            im_origin,
            reload_token: state.reload_token.clone(),
            boot_nonce: state.boot_nonce.clone(),
        },
    )
}

pub fn spawn_seed_unpack_worker(state: Arc<HostSharedState>) {
    std::thread::spawn(move || {
        match ensure_seed_bundle_installed(&state.paths, state.seed_archives_dir.as_deref()) {
            Ok(_) => {
                *state.seed_status.write().unwrap() = SeedPreparationState::Ready;
                let _ = write_host_state_snapshot(&state);
                state.ui_bridge.reload_webview(None);
            }
            Err(err) => {
                append_host_log(
                    Some(&state.paths),
                    "ERROR",
                    &format!("Seed bundle preparation failed: {}", err),
                );
                *state.seed_status.write().unwrap() = SeedPreparationState::Failed(err);
            }
        }
    });
}

/// Evaluate a `crewden-desktop://...` deep link uniformly across cold start, Windows forward, and macOS `Opened`.
pub fn handle_deep_link_url(state: &HostSharedState, raw_url: &str) {
    match classify_deep_link_connect(raw_url) {
        DeepLinkConnectOutcome::Valid {
            origin,
            is_cleartext_http,
        } => {
            *state.deep_link_error.lock().unwrap() = None;
            let current_origin = state.host_config.read().unwrap().im_origin.clone();
            if origin != current_origin {
                *state.pending_server_switch.lock().unwrap() = Some(PendingServerSwitch {
                    target_origin: origin,
                    is_cleartext_http,
                });
                state.ui_bridge.focus_window();
                state.ui_bridge.notify_host_context_updated();
            } else {
                *state.pending_server_switch.lock().unwrap() = None;
                state.ui_bridge.focus_window();
            }
        }
        DeepLinkConnectOutcome::RejectedPublicHttp { attempted_origin } => {
            *state.pending_server_switch.lock().unwrap() = None;
            let msg = format!(
                "已拦截不安全的明文连接请求（{}）。官方与公网 IM 服务必须使用 https:// 加密连接，当前服务保持不变。",
                attempted_origin
            );
            append_host_log(Some(&state.paths), "WARN", &msg);
            *state.deep_link_error.lock().unwrap() = Some(msg);
            state.ui_bridge.focus_window();
            state.ui_bridge.notify_host_context_updated();
        }
        DeepLinkConnectOutcome::Invalid(reason) => {
            let msg = format!("无法识别的服务连接请求：{}", reason);
            append_host_log(Some(&state.paths), "WARN", &msg);
            *state.deep_link_error.lock().unwrap() = Some(msg);
            state.ui_bridge.focus_window();
            state.ui_bridge.notify_host_context_updated();
        }
        DeepLinkConnectOutcome::NotConnectUrl => {
            if let Ok(Some(route)) = crate::config::parse_deep_link_route(raw_url) {
                state.ui_bridge.activate_route(&route);
            } else {
                state.ui_bridge.focus_window();
            }
        }
    }
}

fn load_sessions(paths: &DesktopPaths) -> StoredSessionsFile {
    fs::read_to_string(paths.sessions_path())
        .ok()
        .and_then(|raw| serde_json::from_str::<StoredSessionsFile>(&raw).ok())
        .unwrap_or_default()
}

async fn bind_persisted_loopback(preferred_port: u16) -> Result<(TcpListener, u16), String> {
    if preferred_port > 0 {
        if let Ok(listener) = TcpListener::bind(("127.0.0.1", preferred_port)).await {
            let port = listener.local_addr().map_err(|e| e.to_string())?.port();
            return Ok((listener, port));
        }
    }
    let listener = TcpListener::bind(("127.0.0.1", 0))
        .await
        .map_err(|e| format!("Failed to bind loopback server: {}", e))?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    Ok((listener, port))
}

/// Start the resident loopback server (`127.0.0.1:<persisted_port>`) and background notification daemon.
pub async fn start_host_server(
    paths: DesktopPaths,
    override_origin: Option<&str>,
    dev_repo_root: Option<PathBuf>,
    ui_bridge: Arc<dyn DesktopUiBridge>,
) -> Result<RunningHostServer, String> {
    start_host_server_full(paths, override_origin, None, dev_repo_root, None, ui_bridge).await
}

/// Start the resident loopback server with optional seed preparation and cold-start deep-link evaluation.
pub async fn start_host_server_full(
    paths: DesktopPaths,
    override_origin: Option<&str>,
    seed_archives_dir: Option<PathBuf>,
    dev_repo_root: Option<PathBuf>,
    initial_deep_link: Option<&str>,
    ui_bridge: Arc<dyn DesktopUiBridge>,
) -> Result<RunningHostServer, String> {
    sync_seed_desktop_defaults(&paths, seed_archives_dir.as_deref());
    reconcile_ready_seed_bundle(&paths, seed_archives_dir.as_deref())?;
    let mut host_cfg = load_or_init_host_config(&paths, seed_archives_dir.as_deref(), override_origin);
    let (listener, port) = bind_persisted_loopback(host_cfg.persisted_port).await?;
    host_cfg.persisted_port = port;
    write_private_json(&paths.host_config_path(), &host_cfg)?;

    let sessions = load_sessions(&paths);
    let initial_daemon_session = sessions
        .by_origin
        .get(&host_cfg.im_origin)
        .cloned()
        .map(|s| ActiveDaemonSession {
            im_origin: host_cfg.im_origin.clone(),
            session: s,
        });

    let (session_tx, session_rx) = watch::channel(initial_daemon_session);
    let (session_epoch_tx, _) = watch::channel(host_cfg.context_epoch);
    let (shutdown_tx, shutdown_rx) = oneshot::channel();

    let cap_token = random_hex_token(32);
    let boot_nonce = random_hex_token(24);
    let reload_token = random_hex_token(24);

    // Must exceed Windows cold inspection & creation RPC budgets (130s).
    let http_client = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(150))
        .build()
        .map_err(|e| e.to_string())?;

    let notification_center = Arc::new(NotificationCenterState::default());
    let needs_seed_unpack = dev_repo_root.is_none()
        && std::env::var("CREWDEN_DEV_REPO_ROOT")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .is_none()
        && has_pending_seed_bundle(&paths, seed_archives_dir.as_deref());
    let initial_seed_state = if needs_seed_unpack {
        SeedPreparationState::Preparing
    } else {
        SeedPreparationState::Ready
    };

    let state = Arc::new(HostSharedState {
        paths: paths.clone(),
        seed_archives_dir,
        dev_repo_root,
        port,
        cap_token,
        boot_nonce: boot_nonce.clone(),
        reload_token: reload_token.clone(),
        host_config: RwLock::new(host_cfg.clone()),
        sessions: RwLock::new(sessions),
        seed_status: RwLock::new(initial_seed_state),
        pending_server_switch: Mutex::new(None),
        deep_link_error: Mutex::new(None),
        http_client: http_client.clone(),
        auth_cache: Mutex::new(HashMap::new()),
        trajectory_tickets: Mutex::new(HashMap::new()),
        session_tx,
        session_epoch_tx,
        notification_center: notification_center.clone(),
        ui_bridge: ui_bridge.clone(),
        shutdown_tx: Mutex::new(Some(shutdown_tx)),
        refresh_lock: tokio::sync::Mutex::new(()),
    });

    if let Some(dl) = initial_deep_link {
        handle_deep_link_url(&state, dl);
    }

    write_host_state_snapshot(&state)?;

    if needs_seed_unpack {
        spawn_seed_unpack_worker(state.clone());
    }

    spawn_notification_daemon(state.clone(), session_rx);

    let router = build_router(state.clone());
    tokio::spawn(async move {
        let _ = axum::serve(listener, router).await;
    });

    let bootstrap_url = format!(
        "http://127.0.0.1:{}/desktop/bootstrap?nonce={}&next=%2Fchat",
        port, boot_nonce
    );
    Ok(RunningHostServer {
        state,
        port,
        bootstrap_url,
        shutdown_rx: Some(shutdown_rx),
    })
}

fn build_router(state: Arc<HostSharedState>) -> Router {
    Router::new()
        .route("/desktop/bootstrap", get(handle_bootstrap))
        .route("/desktop/internal/status", get(handle_internal_status))
        .route("/desktop/internal/reload-assets", post(handle_internal_reload))
        .route("/desktop/internal/notifications", get(handle_internal_notifications))
        .route(
            "/desktop/internal/activate-notification",
            post(handle_internal_activate_notification),
        )
        .route("/desktop/internal/deep-link", post(handle_internal_deep_link))
        .route("/desktop/internal/popup-banner", get(handle_internal_popup_banner))
        .route("/desktop/internal/popup-action", post(handle_internal_popup_action))
        .route("/desktop/internal/window-attention", post(handle_internal_attention))
        .route("/desktop/internal/shutdown", post(handle_internal_shutdown))
        .route("/desktop/v1/context", get(handle_get_context))
        .route("/desktop/v1/attention", post(handle_v1_attention))
        .route("/desktop/v1/server", put(handle_put_server))
        .route(
            "/desktop/v1/server/pending/dismiss",
            post(handle_dismiss_pending_server),
        )
        .route("/desktop/v1/seed/retry", post(handle_seed_retry))
        .route("/desktop/v1/open-external", post(handle_open_external))
        .route("/desktop/v1/local-node/inspect", get(handle_local_inspect))
        .route(
            "/desktop/v1/local-node/probe-workers",
            post(handle_local_probe_workers),
        )
        .route("/desktop/v1/local-node/browser", post(handle_local_browser))
        .route("/desktop/v1/local-node/connect", post(handle_local_connect))
        .route("/desktop/v1/local-node/lifecycle", post(handle_local_lifecycle))
        .route("/desktop/v1/local-node/config", put(handle_local_config))
        .route("/desktop/v1/workspace/open", post(handle_workspace_open))
        .route(
            "/desktop/v1/trajectory/prepare",
            post(handle_local_trajectory_prepare),
        )
        .route("/desktop/ws/trajectory", get(handle_local_trajectory_ws))
        .route("/im/v1/auth/login", post(handle_im_auth_login))
        .route("/im/v1/auth/register", post(handle_im_auth_register))
        .route("/im/v1/auth/refresh", post(handle_im_auth_refresh))
        .route("/im/v1/auth/logout", post(handle_im_auth_logout))
        .route("/im/ws/*path", get(handle_im_ws_proxy))
        .route("/im/*path", any(handle_im_http_proxy))
        .fallback(get(handle_static_or_spa))
        .layer(DefaultBodyLimit::max(64 * 1024 * 1024))
        .with_state(state)
}

fn json_error(status: StatusCode, detail: impl Into<String>) -> Response {
    (status, Json(json!({ "detail": detail.into() }))).into_response()
}

fn verify_reload_token(state: &HostSharedState, headers: &HeaderMap) -> Result<(), Response> {
    let provided = headers
        .get("x-crewden-reload-token")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if provided.is_empty() || provided != state.reload_token {
        return Err(json_error(StatusCode::FORBIDDEN, "Invalid internal reload token"));
    }
    Ok(())
}

fn verify_capability_guard(state: &HostSharedState, headers: &HeaderMap) -> Result<(), Response> {
    let expected_origin = format!("http://127.0.0.1:{}", state.port);
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        if origin != expected_origin {
            return Err(json_error(
                StatusCode::FORBIDDEN,
                "Cross-origin access to Crewden loopback host is forbidden",
            ));
        }
    }
    let cookie_hdr = headers
        .get("cookie")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let has_cap = cookie_hdr.split(';').any(|part| {
        let trimmed = part.trim();
        if let Some((k, v)) = trimmed.split_once('=') {
            k.trim() == CAP_COOKIE_NAME && v.trim() == state.cap_token
        } else {
            false
        }
    });
    if !has_cap {
        return Err(json_error(
            StatusCode::FORBIDDEN,
            "Missing Crewden Desktop capability cookie",
        ));
    }
    Ok(())
}

fn extract_bearer_token(headers: &HeaderMap) -> Option<String> {
    let auth = headers.get("authorization")?.to_str().ok()?;
    let rest = auth.strip_prefix("Bearer ").or_else(|| auth.strip_prefix("bearer "))?;
    let trimmed = rest.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

async fn authenticate_caller(
    state: &HostSharedState,
    headers: &HeaderMap,
) -> Result<(String, VerifiedAuthIdentity), Response> {
    let token = extract_bearer_token(headers)
        .ok_or_else(|| json_error(StatusCode::UNAUTHORIZED, "Missing Bearer access token"))?;
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let cache_key = format!("{}::{}", im_origin, sha256_hex(token.as_bytes()));
    {
        let cache = state.auth_cache.lock().unwrap();
        if let Some(hit) = cache.get(&cache_key) {
            if hit.cached_at.elapsed() < Duration::from_secs(5) {
                return Ok((token, hit.clone()));
            }
        }
    }

    let me_url = format!("{}/im/v1/auth/me", im_origin);
    let res = state
        .http_client
        .get(&me_url)
        .bearer_auth(&token)
        .send()
        .await
        .map_err(|_| json_error(StatusCode::SERVICE_UNAVAILABLE, "Upstream IM unavailable"))?;
    if res.status() == reqwest::StatusCode::UNAUTHORIZED
        || res.status() == reqwest::StatusCode::FORBIDDEN
    {
        return Err(json_error(StatusCode::UNAUTHORIZED, "Invalid or expired session"));
    }
    if !res.status().is_success() {
        return Err(json_error(
            StatusCode::BAD_GATEWAY,
            "Could not verify account identity",
        ));
    }
    let user: Value = res
        .json()
        .await
        .map_err(|_| json_error(StatusCode::BAD_GATEWAY, "Malformed user profile"))?;
    let user_id = user["id"].as_str().unwrap_or("").to_string();
    let owner_id = user["owner_id"]
        .as_str()
        .unwrap_or(&user_id)
        .to_string();
    if user_id.is_empty() || owner_id.is_empty() {
        return Err(json_error(StatusCode::UNAUTHORIZED, "Incomplete account identity"));
    }
    let verified = VerifiedAuthIdentity {
        owner_id,
        cached_at: Instant::now(),
    };
    state
        .auth_cache
        .lock()
        .unwrap()
        .insert(cache_key, verified.clone());
    Ok((token, verified))
}

#[derive(Deserialize)]
struct BootstrapQuery {
    nonce: Option<String>,
    next: Option<String>,
}

async fn handle_bootstrap(
    State(state): State<Arc<HostSharedState>>,
    Query(query): Query<BootstrapQuery>,
) -> Response {
    if query.nonce.as_deref() != Some(state.boot_nonce.as_str()) {
        return json_error(StatusCode::FORBIDDEN, "Invalid bootstrap nonce");
    }
    let next = query
        .next
        .as_deref()
        .filter(|p| p.starts_with('/') && !p.starts_with("//"))
        .unwrap_or("/chat");
    let cookie = format!(
        "{}={}; HttpOnly; SameSite=Strict; Path=/",
        CAP_COOKIE_NAME, state.cap_token
    );
    let mut res = Redirect::temporary(next).into_response();
    if let Ok(val) = HeaderValue::from_str(&cookie) {
        res.headers_mut().insert(axum::http::header::SET_COOKIE, val);
    }
    res
}

async fn handle_internal_status(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    let cfg = state.host_config.read().unwrap().clone();
    let seed_ready = state.is_seed_ready();
    let bundle = if seed_ready {
        resolve_active_bundle(&state.paths, &cfg.im_origin, state.dev_repo_root.as_deref()).ok()
    } else {
        None
    };
    let attn = state.ui_bridge.window_attention();
    Json(json!({
        "ready": seed_ready,
        "host_ready": true,
        "seed_ready": seed_ready,
        "seed_error": state.seed_error(),
        "pid": std::process::id(),
        "port": state.port,
        "im_origin": cfg.im_origin,
        "context_epoch": cfg.context_epoch,
        "pending_server_switch": state.pending_server_switch.lock().unwrap().clone(),
        "deep_link_error": state.deep_link_error.lock().unwrap().clone(),
        "ws_connected": state.notification_center.is_ws_connected(),
        "unread_total": state.notification_center.unread(),
        "popup_count": state.ui_bridge.popup_count(),
        "window_focused": attn.visible_and_focused,
        "current_route": attn.current_route,
        "active_ui_version": bundle.as_ref().map(|b| &b.version),
        "active_node_bin": bundle.as_ref().map(|b| b.node_bin.to_string_lossy()),
    }))
    .into_response()
}

async fn handle_internal_reload(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    state.ui_bridge.reload_webview(None);
    Json(json!({ "ok": true })).into_response()
}

async fn handle_internal_notifications(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    Json(json!({
        "unread_total": state.notification_center.unread(),
        "items": state.notification_center.list(),
    }))
    .into_response()
}

#[derive(Deserialize)]
struct ActivateNotifBody {
    id: Option<String>,
    route: Option<String>,
}

async fn handle_internal_activate_notification(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<ActivateNotifBody>,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    let route = body
        .route
        .or_else(|| body.id.as_deref().and_then(|id| state.notification_center.find_route(id)));
    let Some(target) = route else {
        return json_error(StatusCode::NOT_FOUND, "Notification target not found");
    };
    state.ui_bridge.activate_route(&target);
    Json(json!({ "ok": true, "activated_route": target })).into_response()
}

#[derive(Deserialize)]
struct DeepLinkBody {
    url: Option<String>,
    route: Option<String>,
}

async fn handle_internal_deep_link(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<DeepLinkBody>,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    if let Some(ref raw_url) = body.url {
        handle_deep_link_url(&state, raw_url);
        return Json(json!({
            "ok": true,
            "im_origin": state.host_config.read().unwrap().im_origin,
            "pending_server_switch": state.pending_server_switch.lock().unwrap().clone(),
            "deep_link_error": state.deep_link_error.lock().unwrap().clone(),
        }))
        .into_response();
    }
    if let Some(ref target) = body.route {
        if !target.trim().is_empty() {
            state.ui_bridge.activate_route(target);
            return Json(json!({ "ok": true, "route": target })).into_response();
        }
    }
    state.ui_bridge.focus_window();
    Json(json!({ "ok": true })).into_response()
}

#[derive(Deserialize)]
struct PopupBannerQuery {
    nonce: Option<String>,
}

const POPUP_BANNER_CSP: &str =
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; connect-src 'self'";

const POPUP_BANNER_HTML: &str = r##"<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<style>
  * { box-sizing: border-box; user-select: none; -webkit-user-select: none; }
  html, body {
    margin: 0; width: 100%; height: 100%; overflow: hidden;
    background: transparent !important;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI", sans-serif;
    color: #231836;
  }
  body {
    padding: 8px 14px 20px 14px;
  }
  @keyframes popupEnter {
    from { opacity: 0; transform: translateY(-5px) scale(0.985); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  .card {
    width: 100%; height: 100%; padding: 12px 15px;
    display: flex; align-items: center; gap: 12px;
    background: rgba(255, 255, 255, 0.97);
    border: 1px solid rgba(48, 32, 73, 0.07);
    border-radius: 22px;
    box-shadow: 0 10px 24px -6px rgba(35, 24, 54, 0.16), 0 2px 6px rgba(35, 24, 54, 0.05);
    cursor: pointer;
    position: relative;
    animation: popupEnter 180ms cubic-bezier(0.22, 1, 0.36, 1);
    transition: background 140ms ease, transform 140ms ease;
  }
  .card:hover { background: #FFFFFF; }
  .card:active { transform: scale(0.992); }
  .avatar {
    width: 42px; height: 42px; flex-shrink: 0; border-radius: 13px;
    background: #FFF0B5;
    color: #6B43D8;
    display: grid; place-items: center;
  }
  .avatar svg { width: 24px; height: 24px; }
  .main { flex: 1; min-width: 0; padding-right: 18px; }
  .meta { display: flex; align-items: center; gap: 5px; margin-bottom: 2px; }
  .brand { font-size: 11px; font-weight: 700; color: #6B43D8; letter-spacing: -0.15px; }
  .sep, .time { font-size: 11px; color: #968FA6; font-weight: 500; }
  .title {
    font-size: 13.5px; font-weight: 650; line-height: 1.28; color: #231836;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px;
  }
  .body {
    font-size: 12px; line-height: 1.36; color: #665E78;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }
  .close {
    position: absolute; top: 10px; right: 11px; width: 22px; height: 22px;
    border: 0; border-radius: 999px; background: transparent; color: #968FA6;
    font-size: 15px; line-height: 1; cursor: pointer; display: grid; place-items: center;
    opacity: 0.65; transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
  }
  .card:hover .close { opacity: 1; }
  .close:hover { background: #F1EEF8; color: #231836; }
</style>
</head>
<body>
  <div class="card" id="card" role="button" tabindex="0">
    <div class="avatar" aria-hidden="true">
      <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <g transform="translate(51 49) rotate(-9) translate(-50 -50)">
          <path fill="#6B43D8" d="M 33,12 H 67 C 82.5,12 91,20.5 91,36 V 52 C 91,67.5 82.5,76 67,76 H 44 L 23.5,90.5 C 20.6,92.5 17,90.4 17,86.9 V 73.2 C 11.2,68.8 9,61.5 9,52 V 36 C 9,20.5 17.5,12 33,12 Z"/>
          <rect x="32.5" y="33" width="12" height="19" rx="6" fill="#FFF0B5"/>
          <path d="M 55.5,44.5 Q 63,34.5 70.5,44.5" fill="none" stroke="#FFF0B5" stroke-width="8.5" stroke-linecap="round"/>
        </g>
      </svg>
    </div>
    <div class="main">
      <div class="meta">
        <span class="brand">crewden</span>
        <span class="sep" aria-hidden="true">·</span>
        <span class="time" id="time">现在</span>
      </div>
      <div class="title" id="title"></div>
      <div class="body" id="body"></div>
    </div>
    <button type="button" class="close" id="close" aria-label="关闭通知">×</button>
  </div>
<script>
  const params = new URLSearchParams(window.location.search);
  const state = {
    nonce: params.get("nonce") || "",
    title: params.get("title") || "",
    body: params.get("body") || "",
    kind: params.get("kind") || "human_message",
    route: params.get("route") || "/chat",
    locale: params.get("locale") || "zh",
  };
  function cleanPreviewText(raw) {
    return String(raw || "").replace(/`([^`]+)`/g, "$1").trim();
  }
  function render(next) {
    Object.assign(state, next);
    const isEn = String(state.locale || "").toLowerCase().startsWith("en");
    document.documentElement.lang = isEn ? "en" : "zh-CN";
    document.getElementById("time").textContent = isEn ? "Now" : "现在";
    document.getElementById("close").setAttribute("aria-label", isEn ? "Dismiss" : "关闭通知");
    document.getElementById("title").textContent = cleanPreviewText(state.title) || "Crewden";
    document.getElementById("body").textContent = cleanPreviewText(state.body);
  }
  window.__updateCrewdenPopup = render;
  render(state);

  document.getElementById("close").addEventListener("click", (e) => {
    e.stopPropagation();
    fetch("/desktop/internal/popup-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nonce: state.nonce, action: "dismiss" }),
    });
  });
  document.getElementById("card").addEventListener("click", () => {
    fetch("/desktop/internal/popup-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nonce: state.nonce, action: "open", route: state.route }),
    });
  });
</script>
</body>
</html>"##;

async fn handle_internal_popup_banner(
    State(state): State<Arc<HostSharedState>>,
    Query(query): Query<PopupBannerQuery>,
) -> Response {
    if query.nonce.as_deref() != Some(state.boot_nonce.as_str()) {
        return json_error(StatusCode::FORBIDDEN, "Invalid popup nonce");
    }
    Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "text/html; charset=utf-8")
        .header("content-security-policy", POPUP_BANNER_CSP)
        .header("cache-control", "no-store")
        .body(Body::from(POPUP_BANNER_HTML))
        .unwrap()
}

#[derive(Deserialize)]
struct PopupActionBody {
    nonce: String,
    action: String,
    route: Option<String>,
}

async fn handle_internal_popup_action(
    State(state): State<Arc<HostSharedState>>,
    Json(body): Json<PopupActionBody>,
) -> Response {
    if body.nonce != state.boot_nonce {
        return json_error(StatusCode::FORBIDDEN, "Invalid popup nonce");
    }
    state.ui_bridge.dismiss_notification_popup();
    if body.action == "open" {
        let target = body
            .route
            .as_deref()
            .filter(|r| r.starts_with('/') && !r.starts_with("//"))
            .unwrap_or("/chat");
        state.ui_bridge.activate_route(target);
    }
    Json(json!({ "ok": true })).into_response()
}

#[derive(Deserialize)]
struct AttentionBody {
    #[serde(default)]
    current_route: String,
}

async fn handle_internal_attention(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<AttentionBody>,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    let redirect = state.ui_bridge.update_current_route(&body.current_route);
    Json(json!({ "ok": true, "route": redirect.as_deref().unwrap_or(&body.current_route), "navigate_to": redirect })).into_response()
}

async fn handle_v1_attention(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<AttentionBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let redirect = state.ui_bridge.update_current_route(&body.current_route);
    Json(json!({ "ok": true, "route": redirect.as_deref().unwrap_or(&body.current_route), "navigate_to": redirect })).into_response()
}

async fn handle_internal_shutdown(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_reload_token(&state, &headers) {
        return err;
    }
    let paths = state.paths.clone();
    let dev = state.dev_repo_root.clone();
    let _ = tokio::task::spawn_blocking(move || {
        stop_all_managed_local_nodes(&paths, dev.as_deref());
    })
    .await;
    let _ = fs::remove_file(state.paths.host_state_path());
    if let Some(tx) = state.shutdown_tx.lock().unwrap().take() {
        let _ = tx.send(());
    }
    Json(json!({ "ok": true })).into_response()
}

fn build_context_payload(state: &HostSharedState) -> Value {
    let cfg = state.host_config.read().unwrap().clone();
    json!({
        "im_origin": cfg.im_origin,
        "context_epoch": cfg.context_epoch,
        "platform": current_desktop_platform_id(),
        "seed_ready": state.is_seed_ready(),
        "seed_error": state.seed_error(),
        "host_log_path": state.paths.host_log_path().to_string_lossy(),
        "pending_server_switch": state.pending_server_switch.lock().unwrap().clone(),
        "deep_link_error": state.deep_link_error.lock().unwrap().clone(),
    })
}

async fn handle_get_context(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    Json(build_context_payload(&state)).into_response()
}

#[derive(Deserialize)]
struct SwitchServerBody {
    im_origin: String,
}

pub fn apply_server_switch(
    state: &HostSharedState,
    raw_origin: &str,
) -> Result<PersistedHostConfig, String> {
    let normalized = normalize_im_origin(raw_origin)?;
    let next_cfg = {
        let mut guard = state.host_config.write().unwrap();
        if guard.im_origin != normalized {
            guard.im_origin = normalized.clone();
            guard.context_epoch += 1;
        }
        guard.clone()
    };
    *state.pending_server_switch.lock().unwrap() = None;
    *state.deep_link_error.lock().unwrap() = None;
    write_private_json(&state.paths.host_config_path(), &next_cfg)?;
    let _ = write_host_state_snapshot(state);
    state.auth_cache.lock().unwrap().clear();
    state.trajectory_tickets.lock().unwrap().clear();
    let _ = state.session_epoch_tx.send(next_cfg.context_epoch);

    let daemon_session = state
        .sessions
        .read()
        .unwrap()
        .by_origin
        .get(&next_cfg.im_origin)
        .cloned()
        .map(|session| ActiveDaemonSession {
            im_origin: next_cfg.im_origin.clone(),
            session,
        });
    let _ = state.session_tx.send(daemon_session);
    Ok(next_cfg)
}

async fn handle_put_server(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<SwitchServerBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    match apply_server_switch(&state, &body.im_origin) {
        Ok(_cfg) => Json(build_context_payload(&state)).into_response(),
        Err(msg) => json_error(StatusCode::BAD_REQUEST, msg),
    }
}

async fn handle_dismiss_pending_server(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    *state.pending_server_switch.lock().unwrap() = None;
    *state.deep_link_error.lock().unwrap() = None;
    Json(json!({ "ok": true })).into_response()
}

async fn handle_seed_retry(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let should_spawn = {
        let mut guard = state.seed_status.write().unwrap();
        if matches!(*guard, SeedPreparationState::Failed(_)) {
            *guard = SeedPreparationState::Preparing;
            true
        } else {
            false
        }
    };
    if should_spawn {
        spawn_seed_unpack_worker(state.clone());
    }
    Json(build_context_payload(&state)).into_response()
}

#[derive(Deserialize)]
struct OpenExternalBody {
    url: String,
}

async fn handle_open_external(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<OpenExternalBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    match open_external_url(&state.paths, &body.url) {
        Ok(()) => Json(json!({ "ok": true })).into_response(),
        Err(msg) => json_error(StatusCode::BAD_REQUEST, msg),
    }
}

#[derive(Deserialize)]
struct InspectQuery {
    log_query: Option<String>,
}

fn require_seed_ready(state: &HostSharedState) -> Result<(), Response> {
    if !state.is_seed_ready() {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "code": "seed_preparing",
                "detail": state.seed_error().unwrap_or_else(|| "本机运行环境正在初始化，请稍候片刻".to_string()),
            })),
        )
            .into_response());
    }
    Ok(())
}

async fn invoke_local_admin(
    state: Arc<HostSharedState>,
    subcommand: &'static str,
    owner_id: Option<String>,
    log_query: Option<String>,
    stdin_payload: Option<Value>,
) -> Response {
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let paths = state.paths.clone();
    let dev_root = state.dev_repo_root.clone();
    let res = tokio::task::spawn_blocking(move || {
        let bundle = resolve_active_bundle(&paths, &im_origin, dev_root.as_deref())?;
        run_local_admin_sync(
            &paths,
            &bundle,
            &im_origin,
            subcommand,
            owner_id.as_deref(),
            log_query.as_deref(),
            stdin_payload.as_ref(),
        )
    })
    .await;

    match res {
        Ok(Ok(out)) => {
            let status = StatusCode::from_u16(out.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
            (status, Json(out.body)).into_response()
        }
        Ok(Err(err)) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err),
        Err(err) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err.to_string()),
    }
}

async fn handle_local_inspect(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Query(query): Query<InspectQuery>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let (_, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    invoke_local_admin(
        state,
        "inspect",
        Some(caller.owner_id),
        query.log_query,
        None,
    )
    .await
}

#[derive(Deserialize)]
struct ProbeWorkersBody {
    extra_path: Option<String>,
    path: Option<String>,
}

async fn handle_local_probe_workers(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<ProbeWorkersBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let (_, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    let candidate = body.extra_path.or(body.path).unwrap_or_default();
    invoke_local_admin(
        state,
        "probe-workers",
        Some(caller.owner_id),
        None,
        Some(json!({ "path": candidate })),
    )
    .await
}

async fn handle_local_browser(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let (_, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    invoke_local_admin(state, "browser", Some(caller.owner_id), None, Some(body)).await
}

#[derive(Deserialize)]
struct ConnectBody {
    confirm_transfer: Option<bool>,
}

async fn handle_local_connect(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<ConnectBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let (access_token, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let paths = state.paths.clone();
    let dev_root = state.dev_repo_root.clone();
    let confirm = body.confirm_transfer.unwrap_or(false);
    let owner_id = caller.owner_id.clone();

    let res = tokio::task::spawn_blocking(move || {
        let bundle = resolve_active_bundle(&paths, &im_origin, dev_root.as_deref())?;
        let active_meta = json!({
            "version": bundle.version,
            "sha256": bundle.sha256,
            "version_root": bundle.version_root.to_string_lossy(),
            "ui_root": bundle.version_root.join("ui").to_string_lossy(),
        });
        let connect_out = run_local_admin_sync(
            &paths,
            &bundle,
            &im_origin,
            "connect",
            Some(&owner_id),
            None,
            Some(&json!({
                "access_token": access_token,
                "confirm_transfer": confirm,
                "active_metadata": active_meta,
            })),
        )?;
        if connect_out.ok {
            let desired_autostart = connect_out.body["autostart"].as_bool().unwrap_or(true);
            if let Ok(exe) = std::env::current_exe() {
                let _ = set_desktop_login_autostart(&paths, &exe, desired_autostart);
            }
        }
        Ok::<_, String>(connect_out)
    })
    .await;

    match res {
        Ok(Ok(mut out)) => {
            if out.ok {
                if let Some(obj) = out.body.as_object_mut() {
                    obj.insert("ownership".to_string(), json!("managed_online"));
                }
            }
            let status = StatusCode::from_u16(out.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
            (status, Json(out.body)).into_response()
        }
        Ok(Err(err)) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err),
        Err(err) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err.to_string()),
    }
}

#[derive(Deserialize)]
struct LifecycleBody {
    action: String,
    enabled: Option<bool>,
}

async fn handle_local_lifecycle(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<LifecycleBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let (_, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };

    let cli_action = if body.action == "autostart" {
        if body.enabled.unwrap_or(true) {
            "autostart-on"
        } else {
            "autostart-off"
        }
    } else {
        body.action.as_str()
    }
    .to_string();
    let toggle_desktop_login = if body.action == "autostart" {
        Some(body.enabled.unwrap_or(true))
    } else {
        None
    };

    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let paths = state.paths.clone();
    let dev_root = state.dev_repo_root.clone();
    let owner_id = caller.owner_id.clone();

    let res = tokio::task::spawn_blocking(move || {
        let bundle = resolve_active_bundle(&paths, &im_origin, dev_root.as_deref())?;
        let life_res = run_local_admin_sync(
            &paths,
            &bundle,
            &im_origin,
            "lifecycle",
            Some(&owner_id),
            None,
            Some(&json!({ "action": cli_action })),
        )?;
        if !life_res.ok {
            return Ok(life_res);
        }
        if let Some(enable_login) = toggle_desktop_login {
            if let Ok(exe) = std::env::current_exe() {
                let _ = set_desktop_login_autostart(&paths, &exe, enable_login);
            }
        }
        run_local_admin_sync(&paths, &bundle, &im_origin, "inspect", Some(&owner_id), None, None)
    })
    .await;

    match res {
        Ok(Ok(out)) => {
            let status = StatusCode::from_u16(out.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
            (status, Json(out.body)).into_response()
        }
        Ok(Err(err)) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err),
        Err(err) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err.to_string()),
    }
}

async fn handle_local_config(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    if let Err(err) = require_seed_ready(&state) {
        return err;
    }
    let (_, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let paths = state.paths.clone();
    let dev_root = state.dev_repo_root.clone();
    let owner_id = caller.owner_id.clone();

    let res = tokio::task::spawn_blocking(move || {
        let bundle = resolve_active_bundle(&paths, &im_origin, dev_root.as_deref())?;
        let cfg_res = run_local_admin_sync(
            &paths,
            &bundle,
            &im_origin,
            "config",
            Some(&owner_id),
            None,
            Some(&body),
        )?;
        if !cfg_res.ok {
            return Ok(cfg_res);
        }
        run_local_admin_sync(&paths, &bundle, &im_origin, "inspect", Some(&owner_id), None, None)
    })
    .await;

    match res {
        Ok(Ok(out)) => {
            let status = StatusCode::from_u16(out.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
            (status, Json(out.body)).into_response()
        }
        Ok(Err(err)) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err),
        Err(err) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err.to_string()),
    }
}

#[derive(Deserialize)]
struct WorkspaceOpenBody {
    agent_id: String,
    path: String,
    action: String,
}

async fn handle_workspace_open(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<WorkspaceOpenBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let (access_token, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    let im_origin = state.host_config.read().unwrap().im_origin.clone();

    // Verify IM-level space / Personal Agent / deletion access for both `global` and `single_thread` Agents
    let auth_url = format!(
        "{}/im/v1/agents/{}/workspace/authorize",
        im_origin,
        urlencoding_segment(&body.agent_id)
    );
    if let Ok(auth_res) = state
        .http_client
        .post(&auth_url)
        .bearer_auth(&access_token)
        .json(&json!({}))
        .send()
        .await
    {
        if auth_res.status() == reqwest::StatusCode::GONE {
            let bytes = auth_res.bytes().await.unwrap_or_default();
            return Response::builder()
                .status(StatusCode::GONE)
                .header("content-type", "application/json")
                .body(Body::from(bytes))
                .unwrap();
        }
        if auth_res.status() == reqwest::StatusCode::UNAUTHORIZED
            || auth_res.status() == reqwest::StatusCode::FORBIDDEN
            || auth_res.status() == reqwest::StatusCode::NOT_FOUND
        {
            return json_error(StatusCode::FORBIDDEN, "Not authorized to access this Agent workspace");
        }
    }

    let mode = if body.action == "open" { "open" } else { "reveal" };
    let reveal = mode == "reveal";
    let paths = state.paths.clone();
    let dev_root = state.dev_repo_root.clone();
    let owner_id = caller.owner_id.clone();
    let agent_id = body.agent_id.clone();
    let target_path = body.path.clone();

    let res = tokio::task::spawn_blocking(move || {
        let bundle = resolve_active_bundle(&paths, &im_origin, dev_root.as_deref())?;
        let resolved = run_local_admin_sync(
            &paths,
            &bundle,
            &im_origin,
            "resolve-workspace",
            Some(&owner_id),
            None,
            Some(&json!({
                "agent_id": agent_id,
                "target_path": target_path,
                "mode": mode,
            })),
        )?;
        if !resolved.ok {
            return Ok::<_, String>(resolved);
        }
        let target_str = resolved.body["resolved_path"]
            .as_str()
            .ok_or_else(|| "Missing resolved_path".to_string())?;
        open_or_reveal_workspace_path(&paths, Path::new(target_str), reveal)?;
        Ok::<_, String>(resolved)
    })
    .await;

    match res {
        Ok(Ok(out)) => {
            let status = StatusCode::from_u16(out.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
            (status, Json(out.body)).into_response()
        }
        Ok(Err(err)) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err),
        Err(err) => json_error(StatusCode::INTERNAL_SERVER_ERROR, err.to_string()),
    }
}

fn urlencoding_segment(raw: &str) -> String {
    let mut u = url::Url::parse("http://localhost").unwrap();
    u.path_segments_mut().unwrap().push(raw);
    u.path().trim_start_matches('/').to_string()
}

#[derive(Deserialize)]
struct TrajectoryPrepareBody {
    agent_id: String,
    session_id: String,
}

async fn handle_local_trajectory_prepare(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Json(body): Json<TrajectoryPrepareBody>,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let (access_token, caller) = match authenticate_caller(&state, &headers).await {
        Ok(v) => v,
        Err(err) => return err,
    };
    let im_origin = state.host_config.read().unwrap().im_origin.clone();

    // Step 1: Verify IM Agent-level trajectory authorization first (rejects deleted executions 410 and unauthorized 403)
    let auth_url = format!(
        "{}/im/v1/agents/{}/trajectory/authorize",
        im_origin,
        urlencoding_segment(&body.agent_id)
    );
    let upstream = match state
        .http_client
        .post(&auth_url)
        .bearer_auth(&access_token)
        .json(&json!({ "session_id": body.session_id }))
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return Json(json!({ "mode": "remote" })).into_response(),
    };

    if upstream.status() == reqwest::StatusCode::GONE {
        let bytes = upstream.bytes().await.unwrap_or_default();
        return Response::builder()
            .status(StatusCode::GONE)
            .header("content-type", "application/json")
            .body(Body::from(bytes))
            .unwrap();
    }
    if upstream.status() == reqwest::StatusCode::FORBIDDEN
        || upstream.status() == reqwest::StatusCode::NOT_FOUND
    {
        let status = StatusCode::from_u16(upstream.status().as_u16()).unwrap_or(StatusCode::FORBIDDEN);
        let bytes = upstream.bytes().await.unwrap_or_default();
        return Response::builder()
            .status(status)
            .header("content-type", "application/json")
            .body(Body::from(bytes))
            .unwrap();
    }
    if !upstream.status().is_success() {
        return Json(json!({ "mode": "remote" })).into_response();
    }
    let auth_body: Value = match upstream.json().await {
        Ok(v) => v,
        Err(_) => return Json(json!({ "mode": "remote" })).into_response(),
    };
    let target_node_id = auth_body["node_id"].as_str().unwrap_or("").to_string();
    let target_owner_id = auth_body["owner_id"].as_str().unwrap_or("").to_string();
    let target_epoch = auth_body["node_epoch"].as_i64().unwrap_or(0);

    // Step 2 (R2-R1): Short-circuit to remote if local node does not belong to this caller or isn't target_node_id
    if target_owner_id != caller.owner_id {
        return Json(json!({ "mode": "remote" })).into_response();
    }
    let Ok(config_path) = state.paths.connection_config_path(&im_origin) else {
        return Json(json!({ "mode": "remote" })).into_response();
    };
    if !config_path.is_file() {
        return Json(json!({ "mode": "remote" })).into_response();
    }
    let endpoint = local_node_bridge_endpoint(&config_path);
    let Some(ping) = ping_local_bridge(&endpoint).await else {
        return Json(json!({ "mode": "remote" })).into_response();
    };
    let local_node_id = ping["node_id"].as_str().unwrap_or("");
    let local_owner_id = ping["owner_id"].as_str().unwrap_or("");
    let local_ready = ping["ready"].as_bool().unwrap_or(false);
    if !local_ready || local_node_id != target_node_id || local_owner_id != caller.owner_id {
        return Json(json!({ "mode": "remote" })).into_response();
    }

    let ticket = random_hex_token(24);
    {
        let mut tickets = state.trajectory_tickets.lock().unwrap();
        tickets.retain(|_, v| v.expires_at > Instant::now());
        tickets.insert(
            ticket.clone(),
            LocalTrajectoryTicket {
                agent_id: body.agent_id,
                session_id: body.session_id,
                owner_id: caller.owner_id,
                node_epoch: target_epoch,
                access_token,
                im_origin,
                bridge_endpoint: endpoint,
                expires_at: Instant::now() + Duration::from_secs(20),
            },
        );
    }
    Json(json!({ "mode": "local", "ticket": ticket })).into_response()
}

type BoxedIpcRead = Pin<Box<dyn AsyncRead + Send>>;
type BoxedIpcWrite = Pin<Box<dyn AsyncWrite + Send>>;

async fn connect_local_bridge_ipc(endpoint: &str) -> Result<(BoxedIpcRead, BoxedIpcWrite), String> {
    #[cfg(unix)]
    {
        let stream = tokio::net::UnixStream::connect(endpoint)
            .await
            .map_err(|e| e.to_string())?;
        let (r, w) = tokio::io::split(stream);
        return Ok((Box::pin(r), Box::pin(w)));
    }
    #[cfg(windows)]
    {
        let mut attempts = 0;
        let client = loop {
            match tokio::net::windows::named_pipe::ClientOptions::new().open(endpoint) {
                Ok(c) => break c,
                Err(e) if e.raw_os_error() == Some(231) && attempts < 20 => {
                    attempts += 1;
                    tokio::time::sleep(Duration::from_millis(25)).await;
                }
                Err(e) => return Err(e.to_string()),
            }
        };
        let (r, w) = tokio::io::split(client);
        return Ok((Box::pin(r), Box::pin(w)));
    }
    #[allow(unreachable_code)]
    Err("Unsupported platform".to_string())
}

async fn ping_local_bridge(endpoint: &str) -> Option<Value> {
    let Ok(Ok((reader, mut writer))) =
        tokio::time::timeout(Duration::from_millis(600), connect_local_bridge_ipc(endpoint)).await
    else {
        return None;
    };
    writer
        .write_all(b"{\"id\":\"ping\",\"method\":\"local.ping\"}\n")
        .await
        .ok()?;
    let mut lines = BufReader::new(reader).lines();
    let line = tokio::time::timeout(Duration::from_millis(600), lines.next_line())
        .await
        .ok()?
        .ok()??;
    let parsed: Value = serde_json::from_str(&line).ok()?;
    if parsed["ok"].as_bool() == Some(true) {
        Some(parsed["result"].clone())
    } else {
        None
    }
}

#[derive(Deserialize)]
struct TrajectoryWsQuery {
    ticket: String,
    agent_id: String,
    session_id: String,
}

async fn handle_local_trajectory_ws(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    Query(query): Query<TrajectoryWsQuery>,
    ws: WebSocketUpgrade,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let ticket_entry = {
        let mut guard = state.trajectory_tickets.lock().unwrap();
        guard.remove(&query.ticket)
    };
    let Some(entry) = ticket_entry else {
        return json_error(StatusCode::UNAUTHORIZED, "Invalid or expired trajectory ticket");
    };
    if entry.expires_at <= Instant::now()
        || entry.agent_id != query.agent_id
        || entry.session_id != query.session_id
    {
        return json_error(StatusCode::UNAUTHORIZED, "Trajectory ticket mismatch");
    }

    let epoch_rx = state.session_epoch_tx.subscribe();
    ws.on_upgrade(move |socket| run_local_trajectory_ws_bridge(state, socket, entry, epoch_rx))
}

async fn run_local_trajectory_ws_bridge(
    state: Arc<HostSharedState>,
    mut ws_socket: WebSocket,
    ticket: LocalTrajectoryTicket,
    mut epoch_rx: watch::Receiver<u64>,
) {
    let Ok((ipc_read, mut ipc_write)) = connect_local_bridge_ipc(&ticket.bridge_endpoint).await else {
        let _ = ws_socket
            .send(AxumWsMessage::Text(
                json!({ "type": "failed", "message": "无法连接本机节点 IPC 通道" }).to_string(),
            ))
            .await;
        let _ = ws_socket.close().await;
        return;
    };

    let observer_id = format!("desktop-obs-{}", random_hex_token(10));
    let prepare_cmd = json!({
        "id": "prep",
        "method": "local.trajectory.prepare",
        "observerId": observer_id,
        "agentId": ticket.agent_id,
        "sessionId": ticket.session_id,
        "ownerId": ticket.owner_id,
        "nodeEpoch": ticket.node_epoch,
    });
    if ipc_write
        .write_all(format!("{}\n", prepare_cmd).as_bytes())
        .await
        .is_err()
    {
        let _ = ws_socket.close().await;
        return;
    }

    let mut ipc_lines = BufReader::new(ipc_read).lines();
    let mut pending_attachments: HashMap<String, Value> = HashMap::new();
    let mut attachment_seq: u64 = 0;

    loop {
        tokio::select! {
            _ = epoch_rx.changed() => {
                let close_cmd = json!({ "method": "local.trajectory.close", "observerId": observer_id });
                let _ = ipc_write.write_all(format!("{}\n", close_cmd).as_bytes()).await;
                let _ = ws_socket.send(AxumWsMessage::Close(Some(axum::extract::ws::CloseFrame {
                    code: 1008,
                    reason: "会话已切换".into(),
                }))).await;
                break;
            }
            ipc_line = ipc_lines.next_line() => {
                match ipc_line {
                    Ok(Some(line)) => {
                        if line.trim().is_empty() {
                            continue;
                        }
                        if let Ok(parsed) = serde_json::from_str::<Value>(&line) {
                            if parsed["ok"].as_bool() == Some(false) && parsed["id"].as_str() == Some("prep") {
                                let msg = parsed["message"].as_str().unwrap_or("该执行不可访问");
                                let _ = ws_socket.send(AxumWsMessage::Text(json!({ "type": "failed", "message": msg }).to_string())).await;
                                break;
                            }
                            if let Some(rpc_id) = parsed["id"].as_str() {
                                if let Some(orig_req) = pending_attachments.remove(rpc_id) {
                                    let req_id = orig_req["requestId"].as_str().unwrap_or("").to_string();
                                    let sources = parsed["sources"].clone();
                                    let non_empty_sources = sources
                                        .as_array()
                                        .map(|arr| !arr.is_empty())
                                        .unwrap_or(false);
                                    let allowed = if parsed["ok"].as_bool() == Some(true) && non_empty_sources {
                                        authorize_chat_attachment(&state, &ticket, &sources).await
                                    } else {
                                        false
                                    };
                                    if allowed {
                                        let rpc = json!({
                                            "method": "local.trajectory.request",
                                            "observerId": observer_id,
                                            "hostAttachmentAuthorized": true,
                                            "request": orig_req,
                                        });
                                        if ipc_write.write_all(format!("{}\n", rpc).as_bytes()).await.is_err() {
                                            break;
                                        }
                                    } else {
                                        let err_frame = json!({
                                            "type": "error",
                                            "requestId": req_id,
                                            "code": "attachment_forbidden",
                                            "message": "无法验证附件访问权限",
                                        });
                                        if ws_socket.send(AxumWsMessage::Text(err_frame.to_string())).await.is_err() {
                                            break;
                                        }
                                    }
                                    continue;
                                }
                            }
                        }
                        if ws_socket.send(AxumWsMessage::Text(line)).await.is_err() {
                            break;
                        }
                    }
                    _ => break,
                }
            }
            ws_msg = ws_socket.recv() => {
                match ws_msg {
                    Some(Ok(AxumWsMessage::Text(text))) => {
                        let Ok(mut req_val) = serde_json::from_str::<Value>(&text) else {
                            continue;
                        };
                        if let Some(obj) = req_val.as_object_mut() {
                            obj.remove("attachmentAuthorized");
                        }
                        // Resolve authoritative attachment provenance from DSH (`trajectory/attachment-source`)
                        // and verify against IM server fail-closed; never trust client-supplied `params.sources`.
                        if req_val["method"].as_str() == Some("session/attachment") {
                            attachment_seq += 1;
                            let src_rpc_id = format!("att-src-{}", attachment_seq);
                            let src_rpc = json!({
                                "id": src_rpc_id,
                                "method": "local.trajectory.attachment_sources",
                                "observerId": observer_id,
                                "params": req_val["params"],
                            });
                            pending_attachments.insert(src_rpc_id, req_val);
                            if ipc_write.write_all(format!("{}\n", src_rpc).as_bytes()).await.is_err() {
                                break;
                            }
                            continue;
                        }
                        let rpc = json!({
                            "method": "local.trajectory.request",
                            "observerId": observer_id,
                            "request": req_val,
                        });
                        if ipc_write.write_all(format!("{}\n", rpc).as_bytes()).await.is_err() {
                            break;
                        }
                    }
                    Some(Ok(AxumWsMessage::Close(_))) | None => break,
                    _ => {}
                }
            }
        }
    }

    let close_cmd = json!({ "method": "local.trajectory.close", "observerId": observer_id });
    let _ = ipc_write
        .write_all(format!("{}\n", close_cmd).as_bytes())
        .await;
}

async fn authorize_chat_attachment(
    state: &HostSharedState,
    ticket: &LocalTrajectoryTicket,
    sources: &Value,
) -> bool {
    let url = format!(
        "{}/im/v1/agents/{}/trajectory/authorize-attachment",
        ticket.im_origin,
        urlencoding_segment(&ticket.agent_id)
    );
    let Ok(res) = state
        .http_client
        .post(&url)
        .bearer_auth(&ticket.access_token)
        .json(&json!({ "sources": sources }))
        .send()
        .await
    else {
        return false;
    };
    if !res.status().is_success() {
        return false;
    }
    res.json::<Value>()
        .await
        .ok()
        .and_then(|v| v["allowed"].as_bool())
        .unwrap_or(false)
}

fn persist_auth_session_from_im(
    state: &HostSharedState,
    im_origin: &str,
    upstream_json: &Value,
    force_daemon_restart: bool,
) -> Result<Value, String> {
    let access_token = upstream_json["access_token"]
        .as_str()
        .ok_or_else(|| "Upstream response missing access_token".to_string())?;
    let refresh_token = upstream_json["refresh_token"]
        .as_str()
        .ok_or_else(|| "Upstream response missing refresh_token".to_string())?;
    let user = &upstream_json["user"];
    let user_id = user["id"]
        .as_str()
        .ok_or_else(|| "Upstream response missing user.id".to_string())?
        .to_string();
    let owner_id = user["owner_id"]
        .as_str()
        .unwrap_or(&user_id)
        .to_string();
    let username = user["username"].as_str().unwrap_or("").to_string();

    let entry = StoredSessionEntry {
        user_id: user_id.clone(),
        owner_id,
        username,
        refresh_token: refresh_token.to_string(),
        updated_at: now_secs(),
    };

    let principal_changed = {
        let mut sessions = state.sessions.write().unwrap();
        let prev_user = sessions.by_origin.get(im_origin).map(|s| s.user_id.clone());
        sessions.by_origin.insert(im_origin.to_string(), entry.clone());
        write_private_json(&state.paths.sessions_path(), &*sessions)?;
        prev_user.as_deref() != Some(user_id.as_str())
    };

    let current_origin = state.host_config.read().unwrap().im_origin.clone();
    if current_origin == im_origin && (force_daemon_restart || principal_changed) {
        let _ = state.session_tx.send(Some(ActiveDaemonSession {
            im_origin: im_origin.to_string(),
            session: entry,
        }));
    }

    Ok(json!({
        "access_token": access_token,
        "user": user,
    }))
}

fn clear_auth_session_for_origin(state: &HostSharedState, im_origin: &str) {
    {
        let mut sessions = state.sessions.write().unwrap();
        sessions.by_origin.remove(im_origin);
        let _ = write_private_json(&state.paths.sessions_path(), &*sessions);
    }
    state.auth_cache.lock().unwrap().clear();
    state.trajectory_tickets.lock().unwrap().clear();
    let next_epoch = {
        let mut cfg = state.host_config.write().unwrap();
        cfg.context_epoch += 1;
        cfg.context_epoch
    };
    let _ = state.session_epoch_tx.send(next_epoch);
    let current_origin = state.host_config.read().unwrap().im_origin.clone();
    if current_origin == im_origin {
        let _ = state.session_tx.send(None);
    }
}

async fn forward_im_auth_establish(
    state: Arc<HostSharedState>,
    headers: HeaderMap,
    endpoint_suffix: &str,
    body_bytes: bytes::Bytes,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let target = format!("{}{}", im_origin, endpoint_suffix);
    // Deliberately omit X-IM-Session: browser so IM returns JSON { access_token, refresh_token, user }.
    let res = match state
        .http_client
        .post(&target)
        .header("content-type", "application/json")
        .body(body_bytes)
        .send()
        .await
    {
        Ok(r) => r,
        Err(err) => {
            return json_error(
                StatusCode::SERVICE_UNAVAILABLE,
                format!("Cannot reach IM service {}: {}", im_origin, err),
            )
        }
    };
    let status = StatusCode::from_u16(res.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let retry_after = res
        .headers()
        .get("retry-after")
        .and_then(|v| v.to_str().ok())
        .map(str::to_string);
    let bytes = res.bytes().await.unwrap_or_default();
    if !status.is_success() {
        let mut out = Response::builder()
            .status(status)
            .header("content-type", "application/json");
        if let Some(ra) = retry_after {
            out = out.header("retry-after", ra);
        }
        return out.body(Body::from(bytes)).unwrap();
    }
    let Ok(parsed) = serde_json::from_slice::<Value>(&bytes) else {
        return json_error(StatusCode::BAD_GATEWAY, "Invalid auth JSON from IM server");
    };
    match persist_auth_session_from_im(&state, &im_origin, &parsed, true) {
        Ok(sanitized) => (status, Json(sanitized)).into_response(),
        Err(msg) => json_error(StatusCode::BAD_GATEWAY, msg),
    }
}

async fn handle_im_auth_login(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    body: bytes::Bytes,
) -> Response {
    forward_im_auth_establish(state, headers, "/im/v1/auth/login", body).await
}

async fn handle_im_auth_register(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
    body: bytes::Bytes,
) -> Response {
    forward_im_auth_establish(state, headers, "/im/v1/auth/register", body).await
}

/// Serialized refresh_token exchange shared by both WebView `/im/v1/auth/refresh` and the
/// background notification daemon so concurrent callers never trigger replay revocation on JTI rotation.
pub async fn refresh_stored_session_serialized(
    state: &HostSharedState,
    im_origin: &str,
) -> Result<Value, (StatusCode, String)> {
    let _guard = state.refresh_lock.lock().await;
    let stored = state
        .sessions
        .read()
        .unwrap()
        .by_origin
        .get(im_origin)
        .cloned();
    let Some(entry) = stored else {
        return Err((StatusCode::UNAUTHORIZED, "Not signed in".to_string()));
    };
    let target = format!("{}/im/v1/auth/refresh", im_origin);
    let res = match state
        .http_client
        .post(&target)
        .json(&json!({ "refresh_token": entry.refresh_token }))
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => {
            return Err((
                StatusCode::SERVICE_UNAVAILABLE,
                "Upstream IM temporarily unreachable; session preserved".to_string(),
            ));
        }
    };

    let code = res.status().as_u16();
    if code == 401 || code == 403 {
        clear_auth_session_for_origin(state, im_origin);
        return Err((
            StatusCode::UNAUTHORIZED,
            "Session expired or revoked".to_string(),
        ));
    }
    if code >= 500 {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            "Upstream IM returned server error; session preserved".to_string(),
        ));
    }
    if !res.status().is_success() {
        let status = StatusCode::from_u16(code).unwrap_or(StatusCode::BAD_GATEWAY);
        let detail = res.text().await.unwrap_or_else(|_| "Refresh failed".to_string());
        return Err((status, detail));
    }

    let Ok(parsed) = res.json::<Value>().await else {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            "Malformed refresh payload".to_string(),
        ));
    };
    persist_auth_session_from_im(state, im_origin, &parsed, false)
        .map_err(|msg| (StatusCode::BAD_GATEWAY, msg))
}

async fn handle_im_auth_refresh(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    match refresh_stored_session_serialized(&state, &im_origin).await {
        Ok(sanitized) => Json(sanitized).into_response(),
        Err((status, detail)) => json_error(status, detail),
    }
}

async fn handle_im_auth_logout(
    State(state): State<Arc<HostSharedState>>,
    headers: HeaderMap,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let stored = state
        .sessions
        .read()
        .unwrap()
        .by_origin
        .get(&im_origin)
        .cloned();
    clear_auth_session_for_origin(&state, &im_origin);
    if let Some(entry) = stored {
        let target = format!("{}/im/v1/auth/logout", im_origin);
        let _ = state
            .http_client
            .post(&target)
            .json(&json!({ "refresh_token": entry.refresh_token }))
            .send()
            .await;
    }
    Json(json!({ "ok": true })).into_response()
}

async fn handle_im_http_proxy(
    State(state): State<Arc<HostSharedState>>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: bytes::Bytes,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let path_and_q = uri
        .path_and_query()
        .map(|pq| pq.as_str())
        .unwrap_or(uri.path());
    let target = format!("{}{}", im_origin, path_and_q);

    let req_method = reqwest::Method::from_bytes(method.as_str().as_bytes())
        .unwrap_or(reqwest::Method::GET);
    let mut builder = state.http_client.request(req_method, &target);

    for header_name in [
        "authorization",
        "content-type",
        "accept",
        "accept-language",
        "idempotency-key",
        "if-none-match",
    ] {
        if let Some(val) = headers.get(header_name) {
            if let Ok(s) = val.to_str() {
                builder = builder.header(header_name, s);
            }
        }
    }
    if !body.is_empty() {
        builder = builder.body(body);
    }

    let res = match builder.send().await {
        Ok(r) => r,
        Err(err) => {
            return json_error(
                StatusCode::SERVICE_UNAVAILABLE,
                format!("Upstream IM request failed: {}", err),
            )
        }
    };

    let status = StatusCode::from_u16(res.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let mut response_builder = Response::builder().status(status);
    for pass_hdr in [
        "content-type",
        "cache-control",
        "etag",
        "retry-after",
        "content-disposition",
        "content-length",
        "content-encoding",
    ] {
        if let Some(val) = res.headers().get(pass_hdr) {
            if let Ok(hv) = HeaderValue::from_bytes(val.as_bytes()) {
                response_builder = response_builder.header(pass_hdr, hv);
            }
        }
    }
    // Only conversation mutations need a complete body for the desktop notification cache.
    let body = if status.is_success()
        && (method == Method::POST || method == Method::PATCH)
        && uri.path().starts_with("/im/v1/conversations/")
    {
        let Ok(bytes) = res.bytes().await else {
            return json_error(StatusCode::BAD_GATEWAY, "Incomplete response from IM server");
        };
        if let Ok(parsed) = serde_json::from_slice::<Value>(&bytes) {
            state
                .notification_center
                .upsert_conversation(&parsed, state.ui_bridge.as_ref());
        }
        Body::from(bytes)
    } else {
        Body::from_stream(res.bytes_stream())
    };
    response_builder.body(body).unwrap()
}

async fn handle_im_ws_proxy(
    State(state): State<Arc<HostSharedState>>,
    AxumPath(subpath): AxumPath<String>,
    uri: Uri,
    headers: HeaderMap,
    ws: WebSocketUpgrade,
) -> Response {
    if let Err(err) = verify_capability_guard(&state, &headers) {
        return err;
    }
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let Ok(mut upstream_url) = url::Url::parse(&im_origin) else {
        return json_error(StatusCode::BAD_GATEWAY, "Invalid IM origin");
    };
    let ws_scheme = if upstream_url.scheme() == "https" {
        "wss"
    } else {
        "ws"
    };
    let _ = upstream_url.set_scheme(ws_scheme);
    upstream_url.set_path(&format!("/im/ws/{}", subpath.trim_start_matches('/')));
    upstream_url.set_query(uri.query());

    let epoch_rx = state.session_epoch_tx.subscribe();
    ws.on_upgrade(move |client_ws| {
        bridge_upstream_ws(client_ws, upstream_url.to_string(), im_origin, epoch_rx)
    })
}

async fn bridge_upstream_ws(
    mut client_ws: WebSocket,
    upstream_url: String,
    im_origin: String,
    mut epoch_rx: watch::Receiver<u64>,
) {
    let Ok(mut req) = upstream_url.into_client_request() else {
        let _ = client_ws.close().await;
        return;
    };
    if let Ok(hv) = tokio_tungstenite::tungstenite::http::HeaderValue::from_str(&im_origin) {
        req.headers_mut().insert("Origin", hv);
    }
    let Ok((mut upstream_ws, _)) = tokio_tungstenite::connect_async(req).await else {
        let _ = client_ws.close().await;
        return;
    };

    loop {
        tokio::select! {
            _ = epoch_rx.changed() => {
                let _ = upstream_ws.close(None).await;
                let _ = client_ws.close().await;
                break;
            }
            c_msg = client_ws.recv() => {
                match c_msg {
                    Some(Ok(AxumWsMessage::Text(t))) => {
                        if upstream_ws.send(TungsteniteMsg::Text(t)).await.is_err() { break; }
                    }
                    Some(Ok(AxumWsMessage::Binary(b))) => {
                        if upstream_ws.send(TungsteniteMsg::Binary(b)).await.is_err() { break; }
                    }
                    Some(Ok(AxumWsMessage::Ping(p))) => {
                        if upstream_ws.send(TungsteniteMsg::Ping(p)).await.is_err() { break; }
                    }
                    Some(Ok(AxumWsMessage::Pong(p))) => {
                        if upstream_ws.send(TungsteniteMsg::Pong(p)).await.is_err() { break; }
                    }
                    Some(Ok(AxumWsMessage::Close(_))) | Some(Err(_)) | None => {
                        let _ = upstream_ws.close(None).await;
                        break;
                    }
                }
            }
            u_msg = upstream_ws.next() => {
                match u_msg {
                    Some(Ok(TungsteniteMsg::Text(t))) => {
                        if client_ws.send(AxumWsMessage::Text(t)).await.is_err() { break; }
                    }
                    Some(Ok(TungsteniteMsg::Binary(b))) => {
                        if client_ws.send(AxumWsMessage::Binary(b)).await.is_err() { break; }
                    }
                    Some(Ok(TungsteniteMsg::Ping(p))) => {
                        if client_ws.send(AxumWsMessage::Ping(p)).await.is_err() { break; }
                    }
                    Some(Ok(TungsteniteMsg::Pong(p))) => {
                        if client_ws.send(AxumWsMessage::Pong(p)).await.is_err() { break; }
                    }
                    Some(Ok(TungsteniteMsg::Close(frame))) => {
                        let mapped = frame.map(|f| axum::extract::ws::CloseFrame {
                            code: f.code.into(),
                            reason: f.reason.to_string().into(),
                        });
                        let _ = client_ws.send(AxumWsMessage::Close(mapped)).await;
                        break;
                    }
                    _ => break,
                }
            }
        }
    }
}

fn sanitize_rel_path(raw: &str) -> Option<PathBuf> {
    let trimmed = raw.trim_start_matches('/');
    let mut clean = PathBuf::new();
    for comp in Path::new(trimmed).components() {
        match comp {
            Component::Normal(seg) => clean.push(seg),
            Component::CurDir => {}
            _ => return None,
        }
    }
    Some(clean)
}

fn mime_for_path(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase()
        .as_str()
    {
        "html" => "text/html; charset=utf-8",
        "js" | "mjs" => "application/javascript; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "json" => "application/json; charset=utf-8",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "webp" => "image/webp",
        "gif" => "image/gif",
        "ico" => "image/x-icon",
        "woff2" => "font/woff2",
        "woff" => "font/woff",
        "ttf" => "font/ttf",
        "wasm" => "application/wasm",
        "txt" => "text/plain; charset=utf-8",
        _ => "application/octet-stream",
    }
}

fn inject_desktop_boot_script(html: &str, state: &HostSharedState, cfg: &PersistedHostConfig) -> String {
    let payload = json!({
        "imOrigin": cfg.im_origin,
        "contextEpoch": cfg.context_epoch,
        "platform": current_desktop_platform_id(),
        "seedReady": state.is_seed_ready(),
        "seedError": state.seed_error(),
        "hostLogPath": state.paths.host_log_path().to_string_lossy(),
        "pendingServerSwitch": state.pending_server_switch.lock().unwrap().clone(),
        "deepLinkError": state.deep_link_error.lock().unwrap().clone(),
    });
    let tag = format!(
        "<script>window.__CREWDEN_DESKTOP__={};document.documentElement.dataset.crewdenDesktop='true';</script>",
        payload
    );
    if let Some(idx) = html.find("</head>") {
        let mut out = String::with_capacity(html.len() + tag.len() + 1);
        out.push_str(&html[..idx]);
        out.push_str(&tag);
        out.push_str(&html[idx..]);
        out
    } else {
        format!("{}{}", tag, html)
    }
}

fn render_seed_preparation_html(state: &HostSharedState) -> String {
    let init = json!({
        "seedError": state.seed_error(),
        "hostLogPath": state.paths.host_log_path().to_string_lossy(),
    });
    let template = r##"<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>Crewden Desktop</title>
<style>
  * { box-sizing: border-box; }
  html, body {
    margin: 0; width: 100%; height: 100%; overflow: hidden;
    background: #F6F5FA; color: #241C35;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Segoe UI", sans-serif;
    display: flex; align-items: center; justify-content: center;
  }
  .card {
    width: min(460px, calc(100vw - 48px));
    background: #FFFFFF;
    border: 1px solid rgba(36, 28, 53, 0.08);
    border-radius: 22px;
    padding: 32px 30px;
    box-shadow: 0 18px 44px -18px rgba(36, 28, 53, 0.14);
  }
  .brand { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
  .mark {
    width: 44px; height: 44px; border-radius: 14px; background: #FFF0B5;
    display: grid; place-items: center; flex-shrink: 0;
  }
  .mark svg { width: 26px; height: 26px; }
  .brand-name { font-size: 16px; font-weight: 700; color: #6B43D8; letter-spacing: -0.2px; }
  h1 { margin: 0 0 8px; font-size: 21px; font-weight: 700; line-height: 1.3; }
  p { margin: 0; font-size: 13.5px; line-height: 1.55; color: #655D77; }
  .bar-track {
    margin-top: 22px; height: 7px; border-radius: 999px;
    background: #EEEAF8; overflow: hidden; position: relative;
  }
  .bar-fill {
    position: absolute; inset: 0 auto 0 0; width: 42%; border-radius: 999px;
    background: linear-gradient(90deg, #6B43D8, #8D68F0);
    animation: slide 1.35s ease-in-out infinite;
  }
  @keyframes slide {
    0% { transform: translateX(-85%); }
    100% { transform: translateX(260%); }
  }
  .error-box {
    display: none; margin-top: 18px; padding: 12px 14px; border-radius: 12px;
    background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; font-size: 12.5px; line-height: 1.5;
  }
  .log-path {
    margin-top: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 11.5px; color: #655D77; word-break: break-all;
  }
  .actions { display: none; margin-top: 18px; gap: 10px; }
  button {
    border: 0; border-radius: 10px; padding: 9px 16px; font-size: 13px; font-weight: 600;
    background: #6B43D8; color: #FFFFFF; cursor: pointer;
  }
  button:hover { background: #5B35C5; }
</style>
</head>
<body>
  <main class="card">
    <div class="brand">
      <div class="mark" aria-hidden="true">
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <g transform="translate(51 49) rotate(-9) translate(-50 -50)">
            <path fill="#6B43D8" d="M 33,12 H 67 C 82.5,12 91,20.5 91,36 V 52 C 91,67.5 82.5,76 67,76 H 44 L 23.5,90.5 C 20.6,92.5 17,90.4 17,86.9 V 73.2 C 11.2,68.8 9,61.5 9,52 V 36 C 9,20.5 17.5,12 33,12 Z"/>
            <rect x="32.5" y="33" width="12" height="19" rx="6" fill="#FFF0B5"/>
            <path d="M 55.5,44.5 Q 63,34.5 70.5,44.5" fill="none" stroke="#FFF0B5" stroke-width="8.5" stroke-linecap="round"/>
          </g>
        </svg>
      </div>
      <span class="brand-name">crewden desktop</span>
    </div>
    <h1 id="heading">正在准备运行环境…</h1>
    <p id="desc">首次启动正在解压内置运行环境，无需打开命令行，准备完成后将自动进入工作台。</p>
    <div class="bar-track" id="progress"><div class="bar-fill"></div></div>
    <div class="error-box" id="error-box">
      <div id="error-text"></div>
      <div class="log-path" id="log-path"></div>
    </div>
    <div class="actions" id="actions">
      <button type="button" id="retry-btn">重试初始化</button>
    </div>
  </main>
<script>
  const INIT = __CREWDEN_SEED_INIT__;
  function applyState(err, logPath) {
    const progress = document.getElementById("progress");
    const errBox = document.getElementById("error-box");
    const actions = document.getElementById("actions");
    if (err) {
      document.getElementById("heading").textContent = "运行环境初始化未完成";
      document.getElementById("desc").textContent = "请检查本机磁盘空间或防病毒拦截情况后点击重试。";
      progress.style.display = "none";
      errBox.style.display = "block";
      actions.style.display = "flex";
      document.getElementById("error-text").textContent = err;
      document.getElementById("log-path").textContent = "日志文件：" + (logPath || "");
    } else {
      document.getElementById("heading").textContent = "正在准备运行环境…";
      document.getElementById("desc").textContent = "首次启动正在解压内置运行环境，无需打开命令行，准备完成后将自动进入工作台。";
      progress.style.display = "block";
      errBox.style.display = "none";
      actions.style.display = "none";
    }
  }
  applyState(INIT.seedError, INIT.hostLogPath);
  document.getElementById("retry-btn").addEventListener("click", async () => {
    applyState(null, INIT.hostLogPath);
    try { await fetch("/desktop/v1/seed/retry", { method: "POST" }); } catch {}
  });
  setInterval(async () => {
    try {
      const res = await fetch("/desktop/v1/context", { cache: "no-store" });
      if (!res.ok) return;
      const ctx = await res.json();
      if (ctx.seed_ready) {
        window.location.reload();
        return;
      }
      applyState(ctx.seed_error, ctx.host_log_path);
    } catch {}
  }, 600);
</script>
</body>
</html>"##;
    template.replace("__CREWDEN_SEED_INIT__", &init.to_string())
}

async fn handle_static_or_spa(
    State(state): State<Arc<HostSharedState>>,
    req: Request,
) -> Response {
    let req_path = req.uri().path();
    if !state.is_seed_ready() {
        return Response::builder()
            .status(StatusCode::OK)
            .header("content-type", "text/html; charset=utf-8")
            .header("cache-control", "no-store")
            .body(Body::from(render_seed_preparation_html(&state)))
            .unwrap();
    }
    let cfg = state.host_config.read().unwrap().clone();
    let Ok(bundle) = resolve_active_bundle(&state.paths, &cfg.im_origin, state.dev_repo_root.as_deref())
    else {
        return (StatusCode::SERVICE_UNAVAILABLE, "Desktop UI bundle unavailable").into_response();
    };

    // Serve isolated `/trajectory/*` viewer bundle without injecting main-window globals
    if req_path == "/trajectory" || req_path.starts_with("/trajectory/") {
        let sub = req_path.strip_prefix("/trajectory").unwrap_or("").trim_start_matches('/');
        let rel = if sub.is_empty() {
            PathBuf::from("index.html")
        } else {
            let Some(clean) = sanitize_rel_path(sub) else {
                return StatusCode::BAD_REQUEST.into_response();
            };
            clean
        };
        let target = bundle.ui_trajectory.join(&rel);
        let file_to_read = if target.is_file() {
            target
        } else {
            bundle.ui_trajectory.join("index.html")
        };
        if let Ok(bytes) = fs::read(&file_to_read) {
            return Response::builder()
                .status(StatusCode::OK)
                .header("content-type", mime_for_path(&file_to_read))
                .header("cache-control", "no-store")
                .header("access-control-allow-origin", "*")
                .header("x-frame-options", "SAMEORIGIN")
                .header("x-content-type-options", "nosniff")
                .body(Body::from(bytes))
                .unwrap();
        }
        return StatusCode::NOT_FOUND.into_response();
    }

    if let Some(rel) = sanitize_rel_path(req_path) {
        if !rel.as_os_str().is_empty() {
            let candidate = bundle.ui_frontend.join(&rel);
            if candidate.is_file() {
                if candidate.file_name().and_then(|n| n.to_str()) != Some("index.html") {
                    if let Ok(bytes) = fs::read(&candidate) {
                        return Response::builder()
                            .status(StatusCode::OK)
                            .header("content-type", mime_for_path(&candidate))
                            .body(Body::from(bytes))
                            .unwrap();
                    }
                }
            }
        }
    }

    // SPA route fallback -> index.html with injected window.__CREWDEN_DESKTOP__
    let index_path = bundle.ui_frontend.join("index.html");
    let Ok(raw_html) = fs::read_to_string(&index_path) else {
        return (StatusCode::NOT_FOUND, "Frontend index.html missing").into_response();
    };
    let injected = inject_desktop_boot_script(&raw_html, &state, &cfg);
    Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "text/html; charset=utf-8")
        .header("cache-control", "no-store")
        .body(Body::from(injected))
        .unwrap()
}

pub async fn wait_for_addr_ready(addr: SocketAddr) -> bool {
    for _ in 0..30 {
        if tokio::net::TcpStream::connect(addr).await.is_ok() {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::DesktopCliOptions;
    use crate::notifications::NoopUiBridge;

    async fn spawn_fake_im(fail_refresh_503: Arc<Mutex<bool>>, revoke_refresh_401: Arc<Mutex<bool>>) -> u16 {
        let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let app = Router::new()
            .route(
                "/im/v1/auth/login",
                post(|headers: HeaderMap| async move {
                    // Verify Desktop NEVER sends browser cookie session header!
                    assert!(headers.get("x-im-session").is_none());
                    Json(json!({
                        "access_token": "acc-1",
                        "refresh_token": "ref-1",
                        "user": {
                            "id": "u-1",
                            "owner_id": "u-1",
                            "username": "xiaolin",
                            "display_name": "小林",
                            "membership_status": "active",
                            "is_company_admin": false,
                            "locale": "zh",
                            "default_entry_node_id": null,
                            "owned_node_ids": [],
                            "created_at": "2026-11-25T00:00:00Z"
                        }
                    }))
                }),
            )
            .route(
                "/im/v1/auth/refresh",
                post({
                    let f503 = fail_refresh_503.clone();
                    let f401 = revoke_refresh_401.clone();
                    let expected_ref = Arc::new(Mutex::new(("ref-1".to_string(), 1u64)));
                    move |Json(body): Json<Value>| {
                        let f503 = f503.clone();
                        let f401 = f401.clone();
                        let expected_ref = expected_ref.clone();
                        async move {
                            if *f503.lock().unwrap() {
                                return (StatusCode::BAD_GATEWAY, Json(json!({ "detail": "down" }))).into_response();
                            }
                            let next_ref = {
                                let mut guard = expected_ref.lock().unwrap();
                                if *f401.lock().unwrap() || body["refresh_token"].as_str() != Some(guard.0.as_str()) {
                                    return (StatusCode::UNAUTHORIZED, Json(json!({ "detail": "revoked" }))).into_response();
                                }
                                guard.1 += 1;
                                guard.0 = format!("ref-{}", guard.1);
                                guard.0.clone()
                            };
                            Json(json!({
                                "access_token": "acc-2",
                                "refresh_token": next_ref,
                                "user": {
                                    "id": "u-1",
                                    "owner_id": "u-1",
                                    "username": "xiaolin",
                                    "display_name": "小林",
                                    "membership_status": "active",
                                    "is_company_admin": false,
                                    "locale": "zh",
                                    "default_entry_node_id": null,
                                    "owned_node_ids": [],
                                    "created_at": "2026-11-25T00:00:00Z"
                                }
                            }))
                            .into_response()
                        }
                    }
                }),
            );
        tokio::spawn(async move {
            let _ = axum::serve(listener, app).await;
        });
        port
    }

    #[tokio::test]
    async fn enforces_capability_cookie_origin_persists_port_preserves_503_and_hot_swaps_active_ui() {
        let tmp = tempfile::tempdir().unwrap();
        let fake_repo = tmp.path().join("repo");
        fs::create_dir_all(fake_repo.join("src/IM/frontend/dist")).unwrap();
        fs::create_dir_all(fake_repo.join("packages/dsh-trajectory-viewer/dist")).unwrap();
        fs::create_dir_all(fake_repo.join("apps/node/lib")).unwrap();
        fs::write(
            fake_repo.join("src/IM/frontend/dist/index.html"),
            "<!doctype html><html><head></head><body>seed-v1</body></html>",
        )
        .unwrap();
        fs::write(
            fake_repo.join("packages/dsh-trajectory-viewer/dist/index.html"),
            "<!doctype html><html><body>traj-v1</body></html>",
        )
        .unwrap();
        fs::write(fake_repo.join("apps/node/lib/cli.js"), "").unwrap();

        let fail_503 = Arc::new(Mutex::new(false));
        let revoke_401 = Arc::new(Mutex::new(false));
        let im_port = spawn_fake_im(fail_503.clone(), revoke_401.clone()).await;
        let im_origin = format!("http://127.0.0.1:{}", im_port);

        let cli = DesktopCliOptions {
            isolated_root: Some(tmp.path().join("iso")),
            im_origin: Some(im_origin.clone()),
            dev_repo_root: Some(fake_repo.clone()),
            ..Default::default()
        };
        let paths = DesktopPaths::resolve(&cli).unwrap();
        let ui = Arc::new(NoopUiBridge::default());
        let host = start_host_server(paths.clone(), Some(&im_origin), Some(fake_repo.clone()), ui).await.unwrap();
        let port = host.port;

        let persisted: PersistedHostConfig =
            serde_json::from_str(&fs::read_to_string(paths.host_config_path()).unwrap()).unwrap();
        assert_eq!(persisted.persisted_port, port);

        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .unwrap();

        // 1. Missing capability cookie -> 403
        let no_cookie = client
            .get(format!("http://127.0.0.1:{}/desktop/v1/context", port))
            .send()
            .await
            .unwrap();
        assert_eq!(no_cookie.status(), reqwest::StatusCode::FORBIDDEN);

        // 2. Bootstrap issues HttpOnly; SameSite=Strict capability cookie
        let boot_res = client.get(&host.bootstrap_url).send().await.unwrap();
        assert_eq!(boot_res.status(), reqwest::StatusCode::TEMPORARY_REDIRECT);
        let set_cookie = boot_res
            .headers()
            .get("set-cookie")
            .unwrap()
            .to_str()
            .unwrap()
            .to_string();
        assert!(set_cookie.contains("HttpOnly"));
        assert!(set_cookie.contains("SameSite=Strict"));
        let cap_pair = set_cookie.split(';').next().unwrap().to_string();

        // 3. Foreign Origin header is rejected even WITH valid capability cookie!
        let bad_origin = client
            .get(format!("http://127.0.0.1:{}/desktop/v1/context", port))
            .header("Cookie", &cap_pair)
            .header("Origin", "https://evil.example")
            .send()
            .await
            .unwrap();
        assert_eq!(bad_origin.status(), reqwest::StatusCode::FORBIDDEN);

        // 4. Valid same-origin request succeeds and index.html injects window.__CREWDEN_DESKTOP__
        let html = client
            .get(format!("http://127.0.0.1:{}/chat", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap()
            .text()
            .await
            .unwrap();
        assert!(html.contains("window.__CREWDEN_DESKTOP__="));
        assert!(html.contains("seed-v1"));

        // 5. Non-browser JSON login stores refresh_token on disk without leaking refresh_token to WebView
        let login_res = client
            .post(format!("http://127.0.0.1:{}/im/v1/auth/login", port))
            .header("Cookie", &cap_pair)
            .header("X-IM-Session", "browser")
            .json(&json!({ "username": "xiaolin", "password": "pw" }))
            .send()
            .await
            .unwrap();
        assert_eq!(login_res.status(), reqwest::StatusCode::OK);
        let login_body: Value = login_res.json().await.unwrap();
        assert_eq!(login_body["access_token"], "acc-1");
        assert!(login_body.get("refresh_token").is_none());

        // 6. Upstream 5xx / network failure returns 503 AND preserves stored refresh_token!
        *fail_503.lock().unwrap() = true;
        let transient = client
            .post(format!("http://127.0.0.1:{}/im/v1/auth/refresh", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap();
        assert_eq!(transient.status(), reqwest::StatusCode::SERVICE_UNAVAILABLE);

        *fail_503.lock().unwrap() = false;
        let recovered = client
            .post(format!("http://127.0.0.1:{}/im/v1/auth/refresh", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap();
        assert_eq!(recovered.status(), reqwest::StatusCode::OK);

        // 7. Explicit 401 revokes stored refresh_token
        *revoke_401.lock().unwrap() = true;
        let revoked = client
            .post(format!("http://127.0.0.1:{}/im/v1/auth/refresh", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap();
        assert_eq!(revoked.status(), reqwest::StatusCode::UNAUTHORIZED);
        *revoke_401.lock().unwrap() = false;
        let after_revoke = client
            .post(format!("http://127.0.0.1:{}/im/v1/auth/refresh", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap();
        assert_eq!(after_revoke.status(), reqwest::StatusCode::UNAUTHORIZED);

        // 8. Hot-switching `.desktop-active.json` immediately serves v2 UI assets without restarting host!
        let v2_root = paths.desktop_home.join("versions/v2sha");
        fs::create_dir_all(v2_root.join("runtime/bin")).unwrap();
        fs::create_dir_all(v2_root.join("ui/frontend")).unwrap();
        fs::create_dir_all(v2_root.join("ui/trajectory")).unwrap();
        let node_marker = if cfg!(target_os = "windows") {
            v2_root.join("runtime/node.exe")
        } else {
            v2_root.join("runtime/bin/node")
        };
        fs::create_dir_all(node_marker.parent().unwrap()).unwrap();
        fs::write(&node_marker, b"").unwrap();
        fs::write(v2_root.join(".ready"), b"").unwrap();
        fs::write(
            v2_root.join("ui/frontend/index.html"),
            "<!doctype html><html><head></head><body>upgraded-v2</body></html>",
        )
        .unwrap();
        write_private_json(
            &paths.desktop_active_path(&im_origin).unwrap(),
            &json!({
                "managed_by": "crewden-desktop",
                "version": "2.0.0",
                "sha256": "v2sha",
                "version_root": v2_root.to_string_lossy(),
                "ui_root": v2_root.join("ui").to_string_lossy(),
            }),
        )
        .unwrap();

        let html_v2 = client
            .get(format!("http://127.0.0.1:{}/chat", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap()
            .text()
            .await
            .unwrap();
        assert!(html_v2.contains("upgraded-v2"));

        // 9. Popup banner returns static CSP-protected HTML with zero server-side `<script>` interpolation!
        let xss_url = format!(
            "http://127.0.0.1:{}/desktop/internal/popup-banner?nonce={}&title=%3C%2Fscript%3E%3Cscript%3Eevil()%3C%2Fscript%3E&body=%3Cimg%20src%3Dx%20onerror%3D1%3E",
            port, host.state.boot_nonce
        );
        let popup_res = client.get(&xss_url).send().await.unwrap();
        assert_eq!(popup_res.status(), reqwest::StatusCode::OK);
        let csp = popup_res
            .headers()
            .get("content-security-policy")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");
        assert!(csp.contains("default-src 'none'"));
        let popup_html = popup_res.text().await.unwrap();
        assert!(!popup_html.contains("evil()"));
        assert!(!popup_html.contains("<img"));
    }

    #[tokio::test]
    async fn enforces_deep_link_confirmation_public_http_rejection_route_preservation_and_seed_preparation_gate() {
        let tmp = tempfile::tempdir().unwrap();
        let fake_repo = tmp.path().join("repo");
        fs::create_dir_all(fake_repo.join("src/IM/frontend/dist")).unwrap();
        fs::create_dir_all(fake_repo.join("packages/dsh-trajectory-viewer/dist")).unwrap();
        fs::create_dir_all(fake_repo.join("apps/node/lib")).unwrap();
        fs::write(
            fake_repo.join("src/IM/frontend/dist/index.html"),
            "<!doctype html><html><head></head><body>spa-ready</body></html>",
        )
        .unwrap();
        fs::write(
            fake_repo.join("packages/dsh-trajectory-viewer/dist/index.html"),
            "<!doctype html><html><body>traj</body></html>",
        )
        .unwrap();
        fs::write(fake_repo.join("apps/node/lib/cli.js"), "").unwrap();

        let cli = DesktopCliOptions {
            isolated_root: Some(tmp.path().join("iso")),
            dev_repo_root: Some(fake_repo.clone()),
            ..Default::default()
        };
        let paths = DesktopPaths::resolve(&cli).unwrap();

        // Write preset desktop-defaults.json AND a tampered persisted host-config.json with public cleartext HTTP:
        // Startup must reject `http://im.crewden.work` and fall back to preset `http://10.24.8.15:8011`!
        write_private_json(
            &paths.desktop_defaults_path(),
            &json!({
                "default_im_origin": "http://10.24.8.15:8011",
                "trusted_release_base_url": "http://10.24.8.15:9000/releases",
                "allow_private_http_release_base": true,
            }),
        )
        .unwrap();
        write_private_json(
            &paths.host_config_path(),
            &PersistedHostConfig {
                persisted_port: 0,
                im_origin: "http://im.crewden.work".to_string(),
                context_epoch: 2,
            },
        )
        .unwrap();

        let ui = Arc::new(NoopUiBridge::default());
        ui.update_current_route("/onboarding");

        // Cold-start with cross-origin deep link must stage `pending_server_switch` instead of silently switching!
        let host = start_host_server_full(
            paths.clone(),
            None,
            None,
            Some(fake_repo.clone()),
            Some("crewden-desktop://connect?origin=http%3A%2F%2F192.168.1.50%3A8011"),
            ui.clone(),
        )
        .await
        .unwrap();
        let port = host.port;

        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .unwrap();
        let boot_res = client.get(&host.bootstrap_url).send().await.unwrap();
        let cap_pair = boot_res
            .headers()
            .get("set-cookie")
            .unwrap()
            .to_str()
            .unwrap()
            .split(';')
            .next()
            .unwrap()
            .to_string();

        let ctx1: Value = client
            .get(format!("http://127.0.0.1:{}/desktop/v1/context", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(ctx1["im_origin"], "http://10.24.8.15:8011");
        assert_eq!(
            ctx1["pending_server_switch"],
            json!({
                "target_origin": "http://192.168.1.50:8011",
                "is_cleartext_http": true,
            })
        );

        // Dismiss pending switch -> keeps original server.
        let dismiss_res = client
            .post(format!(
                "http://127.0.0.1:{}/desktop/v1/server/pending/dismiss",
                port
            ))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap();
        assert_eq!(dismiss_res.status(), reqwest::StatusCode::OK);

        // Warm deep link with rejected public cleartext HTTP -> sets `deep_link_error` and keeps server unchanged!
        let bad_dl = client
            .post(format!("http://127.0.0.1:{}/desktop/internal/deep-link", port))
            .header("x-crewden-reload-token", &host.state.reload_token)
            .json(&json!({
                "url": "crewden-desktop://connect?origin=http%3A%2F%2Fim.crewden.work",
                "route": null,
            }))
            .send()
            .await
            .unwrap();
        assert_eq!(bad_dl.status(), reqwest::StatusCode::OK);
        let ctx2: Value = client
            .get(format!("http://127.0.0.1:{}/desktop/v1/context", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(ctx2["im_origin"], "http://10.24.8.15:8011");
        assert!(ctx2["pending_server_switch"].is_null());
        assert!(ctx2["deep_link_error"]
            .as_str()
            .unwrap_or("")
            .contains("https://"));

        // Plain shortcut re-launch (`url: null, route: null`) must focus window WITHOUT forcing `/chat`!
        let prev_focus = *ui.focus_count.lock().unwrap();
        let plain_wakeup = client
            .post(format!("http://127.0.0.1:{}/desktop/internal/deep-link", port))
            .header("x-crewden-reload-token", &host.state.reload_token)
            .json(&json!({ "url": null, "route": null }))
            .send()
            .await
            .unwrap();
        assert_eq!(plain_wakeup.status(), reqwest::StatusCode::OK);
        assert_eq!(*ui.focus_count.lock().unwrap(), prev_focus + 1);
        assert_eq!(ui.window_attention().current_route, "/onboarding");
        assert!(ui.activated_routes.lock().unwrap().is_empty());

        // Seed preparation state serves inline splash HTML and gates `/desktop/v1/local-node/*` with 503 `seed_preparing`.
        *host.state.seed_status.write().unwrap() = SeedPreparationState::Preparing;
        let prep_html = client
            .get(format!("http://127.0.0.1:{}/login", port))
            .header("Cookie", &cap_pair)
            .send()
            .await
            .unwrap()
            .text()
            .await
            .unwrap();
        assert!(prep_html.contains("正在准备运行环境"));
        assert!(!prep_html.contains("spa-ready"));

        let local_gate = client
            .post(format!(
                "http://127.0.0.1:{}/desktop/v1/local-node/connect",
                port
            ))
            .header("Cookie", &cap_pair)
            .json(&json!({}))
            .send()
            .await
            .unwrap();
        assert_eq!(local_gate.status(), reqwest::StatusCode::SERVICE_UNAVAILABLE);
        let gate_json: Value = local_gate.json().await.unwrap();
        assert_eq!(gate_json["code"], "seed_preparing");
    }
}
