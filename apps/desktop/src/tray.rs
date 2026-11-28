use crate::autostart::get_desktop_login_autostart;
use crate::config::{
    append_host_log, random_hex_token, show_error_dialog, show_fatal_startup_dialog_async,
    DesktopPaths,
};
use crate::host_server::{register_login, set_managed_login, HostSharedState};
use crate::local_node::{
    open_external_url, reconcile_webview_ui_cache, resolve_active_bundle, run_local_admin_sync,
};
use crate::notifications::{DesktopUiBridge, WindowAttentionState};
use serde_json::json;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use tauri::image::Image;
use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent};
use tauri::webview::NewWindowResponse;
use tauri::{
    AppHandle, Manager, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder, WindowEvent,
};

const MAIN_WINDOW_LABEL: &str = "main";
const TRAY_TEMPLATE_PNG: &[u8] = include_bytes!("../icons/tray.png");
const TRAY_COLOR_PNG: &[u8] = include_bytes!("../icons/128x128.png");

#[derive(Clone)]
struct TrayMenuItems {
    open_main: MenuItem<tauri::Wry>,
    open_nodes: MenuItem<tauri::Wry>,
    start_node: MenuItem<tauri::Wry>,
    restart_node: MenuItem<tauri::Wry>,
    stop_node: MenuItem<tauri::Wry>,
    autostart: CheckMenuItem<tauri::Wry>,
    quit: MenuItem<tauri::Wry>,
}

pub struct TauriUiCoordinator {
    app_handle: Mutex<Option<AppHandle>>,
    bootstrap_base: Mutex<Option<(u16, String)>>,
    attention: RwLock<WindowAttentionState>,
    pending_route: Mutex<Option<String>>,
    pub explicit_quit: AtomicBool,
    tray_unread: Mutex<u64>,
    locale: Mutex<String>,
    tray_icon: Mutex<Option<TrayIcon>>,
    status_item: Mutex<Option<MenuItem<tauri::Wry>>>,
    autostart_item: Mutex<Option<CheckMenuItem<tauri::Wry>>>,
    menu_items: Mutex<Option<TrayMenuItems>>,
}

impl Default for TauriUiCoordinator {
    fn default() -> Self {
        Self {
            app_handle: Mutex::new(None),
            bootstrap_base: Mutex::new(None),
            attention: RwLock::new(WindowAttentionState {
                visible_and_focused: false,
                current_route: "/chat".to_string(),
            }),
            pending_route: Mutex::new(None),
            explicit_quit: AtomicBool::new(false),
            tray_unread: Mutex::new(0),
            locale: Mutex::new("zh".to_string()),
            tray_icon: Mutex::new(None),
            status_item: Mutex::new(None),
            autostart_item: Mutex::new(None),
            menu_items: Mutex::new(None),
        }
    }
}

fn format_status_label(zh: bool, total_unread: u64) -> String {
    if zh {
        if total_unread > 0 {
            format!("Crewden 常驻在线（{} 条未读）", total_unread)
        } else {
            "Crewden 常驻在线".to_string()
        }
    } else if total_unread > 0 {
        format!("Crewden Online ({} unread)", total_unread)
    } else {
        "Crewden Online".to_string()
    }
}

fn format_tray_tooltip(zh: bool, total_unread: u64) -> String {
    if total_unread == 0 {
        return "Crewden Desktop".to_string();
    }
    if zh {
        format!("Crewden Desktop（{} 条未读）", total_unread)
    } else {
        format!("Crewden Desktop ({} unread)", total_unread)
    }
}

fn is_loopback_host_url(url: &url::Url, expected_port: Option<u16>) -> bool {
    url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && expected_port.map(|port| url.port() == Some(port)).unwrap_or(true)
}

impl TauriUiCoordinator {
    pub fn bind_app(&self, handle: AppHandle, port: u16, boot_nonce: String) {
        *self.app_handle.lock().unwrap() = Some(handle);
        *self.bootstrap_base.lock().unwrap() = Some((port, boot_nonce));
    }

    pub fn set_window_focused(&self, visible_and_focused: bool) {
        self.attention.write().unwrap().visible_and_focused = visible_and_focused;
    }

    pub fn set_current_route(&self, route: String) {
        self.attention.write().unwrap().current_route = route;
    }

    fn build_bootstrap_url(&self, next_route: &str) -> Option<url::Url> {
        self.build_bootstrap_url_with_cache_bust(next_route, None)
    }

    pub(crate) fn build_bootstrap_url_with_cache_bust(
        &self,
        next_route: &str,
        cache_bust: Option<&str>,
    ) -> Option<url::Url> {
        let (port, ref nonce) = (*self.bootstrap_base.lock().unwrap()).clone()?;
        let mut u = url::Url::parse(&format!("http://127.0.0.1:{}/desktop/bootstrap", port)).ok()?;
        {
            let mut pairs = u.query_pairs_mut();
            pairs.append_pair("nonce", nonce).append_pair(
                "next",
                if next_route.starts_with('/') {
                    next_route
                } else {
                    "/chat"
                },
            );
            if let Some(cb) = cache_bust.filter(|s| !s.is_empty()) {
                pairs.append_pair("_cb", cb);
            }
        }
        Some(u)
    }

    pub fn ensure_main_window(
        &self,
        app: &AppHandle,
        target_route: Option<&str>,
    ) -> Result<WebviewWindow, String> {
        #[cfg(target_os = "macos")]
        {
            let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);
        }

        let effective_route = self
            .pending_route
            .lock()
            .unwrap()
            .clone()
            .or_else(|| target_route.map(str::to_string));

        if let Some(win) = app.get_webview_window(MAIN_WINDOW_LABEL) {
            let _ = win.show();
            if win.is_minimized().unwrap_or(false) {
                let _ = win.unminimize();
            }
            let _ = win.set_focus();
            if let Some(ref route) = effective_route {
                self.set_current_route(route.clone());
                if let Ok(encoded) = serde_json::to_string(route) {
                    let js = format!(
                        "if (window.__CREWDEN_SHELL_READY__) {{ window.dispatchEvent(new CustomEvent('crewden:navigate', {{ detail: {0} }})); }} else if (window.location.origin.startsWith('http://127.0.0.1:')) {{ window.location.assign({0}); }}",
                        encoded
                    );
                    let _ = win.eval(&js);
                }
            }
            self.set_window_focused(true);
            return Ok(win);
        }

        if let Some(host_state) = app.try_state::<Arc<HostSharedState>>() {
            let im_origin = host_state.host_config.read().unwrap().im_origin.clone();
            let _ = reconcile_webview_ui_cache(
                &host_state.paths,
                &im_origin,
                host_state.dev_repo_root.as_deref(),
                host_state.seed_archives_dir.as_deref(),
            );
        }

        let initial_route = effective_route.as_deref().unwrap_or("/chat");
        let url = self
            .build_bootstrap_url(initial_route)
            .ok_or_else(|| "桌面本地回环引导地址尚未初始化".to_string())?;
        self.set_current_route(initial_route.to_string());
        let expected_port = self.bootstrap_base.lock().unwrap().as_ref().map(|(p, _)| *p);
        let paths_for_nav = app.try_state::<Arc<HostSharedState>>().map(|s| s.paths.clone());
        let paths_for_log = paths_for_nav.clone();
        let paths_for_new_win = paths_for_nav.clone();
        let coord_for_new_win = app.state::<Arc<TauriUiCoordinator>>().inner().clone();

        let win = WebviewWindowBuilder::new(app, MAIN_WINDOW_LABEL, WebviewUrl::External(url))
            .title("Crewden")
            .inner_size(1280.0, 840.0)
            .min_inner_size(380.0, 560.0)
            .visible(true)
            .focused(true)
            .on_navigation(move |nav_url| {
                if matches!(nav_url.scheme(), "about" | "blob")
                    || is_loopback_host_url(nav_url, expected_port)
                {
                    return true;
                }
                if matches!(nav_url.scheme(), "http" | "https") {
                    if let Some(ref paths) = paths_for_nav {
                        let _ = open_external_url(paths, nav_url.as_str());
                    }
                }
                false
            })
            .on_new_window(move |win_url, _features| {
                if is_loopback_host_url(&win_url, expected_port) {
                    let route = match win_url.query() {
                        Some(q) if !q.is_empty() => format!("{}?{}", win_url.path(), q),
                        _ => win_url.path().to_string(),
                    };
                    if route.starts_with('/') {
                        coord_for_new_win.activate_route(&route);
                    }
                    return NewWindowResponse::Deny;
                }
                if matches!(win_url.scheme(), "http" | "https") {
                    if let Some(ref paths) = paths_for_new_win {
                        let _ = open_external_url(paths, win_url.as_str());
                    }
                }
                NewWindowResponse::Deny
            })
            .build()
            .map_err(|e| {
                let msg = format!("无法创建主窗口（WebView 初始化失败）：{}", e);
                append_host_log(paths_for_log.as_ref(), "ERROR", &msg);
                msg
            })?;

        // Apply any unread count accumulated while running silently in `--background` mode.
        let current_unread = *self.tray_unread.lock().unwrap();
        let _ = win.set_badge_count(if current_unread > 0 {
            Some(current_unread as i64)
        } else {
            None
        });

        let coord_clone = app.state::<Arc<TauriUiCoordinator>>().inner().clone();
        win.on_window_event(move |event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                if !coord_clone.explicit_quit.load(Ordering::SeqCst) {
                    api.prevent_close();
                    if let Some(ref handle) = *coord_clone.app_handle.lock().unwrap() {
                        if let Some(w) = handle.get_webview_window(MAIN_WINDOW_LABEL) {
                            let _ = w.hide();
                        }
                    }
                    coord_clone.set_window_focused(false);
                }
            }
            WindowEvent::Focused(focused) => {
                coord_clone.set_window_focused(*focused);
            }
            _ => {}
        });

        self.set_window_focused(true);
        Ok(win)
    }

    pub fn ensure_main_window_or_report(&self, app: &AppHandle, target_route: Option<&str>) {
        if let Err(err) = self.ensure_main_window(app, target_route) {
            let paths = app
                .try_state::<Arc<HostSharedState>>()
                .map(|s| s.paths.clone());
            let log_path = append_host_log(paths.as_ref(), "ERROR", &err);
            show_fatal_startup_dialog_async(err, log_path);
        }
    }
}

impl DesktopUiBridge for TauriUiCoordinator {
    fn window_attention(&self) -> WindowAttentionState {
        self.attention.read().unwrap().clone()
    }

    fn update_current_route(&self, route: &str) -> Option<String> {
        if !route.starts_with('/') {
            return None;
        }
        if let Some(target) = self.pending_route.lock().unwrap().take() {
            if target != route {
                self.set_current_route(target.clone());
                return Some(target);
            }
        }
        self.set_current_route(route.to_string());
        None
    }

    fn update_unread_badge(&self, total_unread: u64) {
        *self.tray_unread.lock().unwrap() = total_unread;
        let zh = self.locale.lock().unwrap().starts_with("zh");
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let app_clone = app.clone();
        let status_item = self.status_item.lock().unwrap().clone();
        let tray_icon = self.tray_icon.lock().unwrap().clone();
        let _ = app.run_on_main_thread(move || {
            if let Some(win) = app_clone.get_webview_window(MAIN_WINDOW_LABEL) {
                let badge = if total_unread > 0 {
                    Some(total_unread as i64)
                } else {
                    None
                };
                let _ = win.set_badge_count(badge);
            }
            if let Some(item) = status_item {
                let _ = item.set_text(format_status_label(zh, total_unread));
            }
            if let Some(tray) = tray_icon {
                let _ = tray.set_tooltip(Some(format_tray_tooltip(zh, total_unread)));
            }
        });
    }

    fn login_autostart_changed(&self, enabled: bool) {
        if let Some(item) = self.autostart_item.lock().unwrap().clone() {
            let _ = item.set_checked(enabled);
        }
        if let Some(win) = self.app_handle.lock().unwrap().as_ref().and_then(|app| app.get_webview_window(MAIN_WINDOW_LABEL)) {
            let _ = win.eval("window.dispatchEvent(new Event('crewden:login-autostart-changed'))");
        }
    }

    fn set_locale(&self, locale: &str) {
        let normalized = if locale.trim().to_ascii_lowercase().starts_with("en") {
            "en".to_string()
        } else {
            "zh".to_string()
        };
        *self.locale.lock().unwrap() = normalized.clone();
        let zh = normalized == "zh";
        let total_unread = *self.tray_unread.lock().unwrap();
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let status_item = self.status_item.lock().unwrap().clone();
        let tray_icon = self.tray_icon.lock().unwrap().clone();
        let items = self.menu_items.lock().unwrap().clone();
        let _ = app.run_on_main_thread(move || {
            if let Some(status) = status_item {
                let _ = status.set_text(format_status_label(zh, total_unread));
            }
            if let Some(tray) = tray_icon {
                let _ = tray.set_tooltip(Some(format_tray_tooltip(zh, total_unread)));
            }
            if let Some(m) = items {
                let _ = m.open_main.set_text(if zh { "打开主窗口" } else { "Open Crewden" });
                let _ = m.open_nodes.set_text(if zh { "电脑与运行设置…" } else { "Computers & local settings…" });
                let _ = m.start_node.set_text(if zh { "启动本机后台节点" } else { "Start local node" });
                let _ = m.restart_node.set_text(if zh { "重启本机后台节点" } else { "Restart local node" });
                let _ = m.stop_node.set_text(if zh { "停止本机后台节点" } else { "Stop local node" });
                let _ = m.autostart.set_text(if zh { "开机登录自启" } else { "Start at login" });
                let _ = m.quit.set_text(if zh { "退出 Crewden" } else { "Quit Crewden" });
            }
        });
    }

    fn activate_route(&self, target_route: &str) {
        if target_route.starts_with('/') {
            *self.pending_route.lock().unwrap() = Some(target_route.to_string());
            self.set_current_route(target_route.to_string());
        }
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };

        let coord = app.state::<Arc<TauriUiCoordinator>>().inner().clone();
        let app_clone = app.clone();
        let _ = app.run_on_main_thread(move || {
            coord.ensure_main_window_or_report(&app_clone, None);
        });
    }

    fn clear_session_navigation(&self) {
        self.pending_route.lock().unwrap().take();
        self.attention.write().unwrap().current_route.clear();
    }

    fn focus_window(&self) {
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let coord = app.state::<Arc<TauriUiCoordinator>>().inner().clone();
        let app_clone = app.clone();
        let _ = app.run_on_main_thread(move || {
            coord.ensure_main_window_or_report(&app_clone, None);
        });
    }

    fn notify_host_context_updated(&self) {
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let app_clone = app.clone();
        let _ = app.run_on_main_thread(move || {
            if let Some(win) = app_clone.get_webview_window(MAIN_WINDOW_LABEL) {
                let _ = win.eval(
                    "window.dispatchEvent(new CustomEvent('crewden:host-context-updated'));",
                );
            }
        });
    }

    fn reload_webview(&self, target_route: Option<&str>) {
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let current_route = self.attention.read().unwrap().current_route.clone();
        let desired_route = target_route
            .filter(|r| r.starts_with('/'))
            .map(str::to_string)
            .or_else(|| {
                if current_route.starts_with('/') {
                    Some(current_route)
                } else {
                    None
                }
            })
            .unwrap_or_else(|| "/chat".to_string());
        let bust = random_hex_token(8);
        let boot_url = self.build_bootstrap_url_with_cache_bust(&desired_route, Some(&bust));
        let app_clone = app.clone();
        let _ = app.run_on_main_thread(move || {
            if let Some(win) = app_clone.get_webview_window(MAIN_WINDOW_LABEL) {
                if let Some(url) = boot_url {
                    if win.navigate(url.clone()).is_err() {
                        if let Ok(encoded) = serde_json::to_string(url.as_str()) {
                            let _ = win.eval(&format!("window.location.replace({});", encoded));
                        }
                    }
                } else {
                    let _ = win.eval("window.location.reload();");
                }
            }
        });
    }
}

pub fn install_system_tray(
    app: &AppHandle,
    coord: Arc<TauriUiCoordinator>,
    host_state: Arc<HostSharedState>,
) -> Result<(), String> {
    let status = MenuItem::with_id(app, "status", "Crewden 常驻在线", false, None::<&str>)
        .map_err(|e| e.to_string())?;
    let open_main = MenuItem::with_id(app, "open_main", "打开主窗口", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let open_nodes = MenuItem::with_id(app, "open_nodes", "电脑与运行设置…", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let sep1 = PredefinedMenuItem::separator(app).map_err(|e| e.to_string())?;
    let start_node = MenuItem::with_id(app, "node_start", "启动本机后台节点", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let restart_node = MenuItem::with_id(app, "node_restart", "重启本机后台节点", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let stop_node = MenuItem::with_id(app, "node_stop", "停止本机后台节点", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let initial_auto = get_desktop_login_autostart(&host_state.paths);
    let autostart = CheckMenuItem::with_id(
        app,
        "toggle_autostart",
        "开机登录自启",
        true,
        initial_auto,
        None::<&str>,
    )
    .map_err(|e| e.to_string())?;
    let sep2 = PredefinedMenuItem::separator(app).map_err(|e| e.to_string())?;
    let quit = MenuItem::with_id(app, "quit", "退出 Crewden", true, None::<&str>)
        .map_err(|e| e.to_string())?;

    *coord.status_item.lock().unwrap() = Some(status.clone());
    *coord.autostart_item.lock().unwrap() = Some(autostart.clone());
    *coord.menu_items.lock().unwrap() = Some(TrayMenuItems {
        open_main: open_main.clone(),
        open_nodes: open_nodes.clone(),
        start_node: start_node.clone(),
        restart_node: restart_node.clone(),
        stop_node: stop_node.clone(),
        autostart: autostart.clone(),
        quit: quit.clone(),
    });

    let menu = Menu::with_items(
        app,
        &[
            &status,
            &open_main,
            &open_nodes,
            &sep1,
            &start_node,
            &restart_node,
            &stop_node,
            &autostart,
            &sep2,
            &quit,
        ],
    )
    .map_err(|e| e.to_string())?;

    let (icon_bytes, use_template) = tray_icon_bytes_and_template(std::env::consts::OS);
    let icon = Image::from_bytes(icon_bytes).map_err(|e| e.to_string())?;
    let coord_for_menu = coord.clone();
    let coord_for_click = coord.clone();
    let state_for_menu = host_state.clone();

    let built_tray = TrayIconBuilder::with_id("crewden-tray")
        .icon(icon)
        .icon_as_template(use_template)
        .tooltip("Crewden Desktop")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_tray_icon_event(move |tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                coord_for_click.ensure_main_window_or_report(tray.app_handle(), None);
            }
        })
        .on_menu_event(move |app_handle, event| {
            match event.id().as_ref() {
                "open_main" => {
                    coord_for_menu.ensure_main_window_or_report(app_handle, None);
                }
                "open_nodes" => {
                    coord_for_menu.ensure_main_window_or_report(app_handle, Some("/settings/nodes"));
                }
                "node_start" | "node_restart" | "node_stop" => {
                    let action = match event.id().as_ref() {
                        "node_start" => "start",
                        "node_restart" => "restart",
                        _ => "stop",
                    };
                    spawn_tray_lifecycle_action(
                        state_for_menu.paths.clone(),
                        state_for_menu.dev_repo_root.clone(),
                        state_for_menu.host_config.read().unwrap().im_origin.clone(),
                        state_for_menu
                            .sessions
                            .read()
                            .unwrap()
                            .by_origin
                            .get(&state_for_menu.host_config.read().unwrap().im_origin)
                            .map(|s| s.owner_id.clone()),
                        action,
                        state_for_menu.node_lifecycle.clone(),
                    );
                }
                "toggle_autostart" => {
                    spawn_tray_login_toggle(state_for_menu.clone());
                }
                "quit" => {
                    coord_for_menu.explicit_quit.store(true, Ordering::SeqCst);
                    let _ = std::fs::remove_file(state_for_menu.paths.host_state_path());
                    app_handle.exit(0);
                }
                _ => {}
            }
        })
        .build(app)
        .map_err(|e| e.to_string())?;

    *coord.tray_icon.lock().unwrap() = Some(built_tray);
    Ok(())
}

fn spawn_tray_lifecycle_action(
    paths: DesktopPaths,
    dev_repo_root: Option<PathBuf>,
    im_origin: String,
    owner_id: Option<String>,
    action: &'static str,
    lock: Arc<Mutex<()>>,
) {
    let Some(owner) = owner_id else {
        return;
    };
    std::thread::spawn(move || {
        let _guard = lock.lock().unwrap();
        if let Ok(bundle) = resolve_active_bundle(&paths, &im_origin, dev_repo_root.as_deref()) {
            let _ = run_local_admin_sync(
                &paths,
                &bundle,
                &im_origin,
                "lifecycle",
                Some(&owner),
                None,
                Some(&json!({ "action": action })),
            );
        }
    });
}

fn spawn_tray_login_toggle(state: Arc<HostSharedState>) {
    let origin = state.host_config.read().unwrap().im_origin.clone();
    let owner = state
        .sessions
        .read()
        .unwrap()
        .by_origin
        .get(&origin)
        .map(|s| s.owner_id.clone());
    std::thread::spawn(move || {
        let result = {
            let _guard = state.node_lifecycle.lock().unwrap();
            let enabled = !get_desktop_login_autostart(&state.paths);
            (|| {
                if !state.paths.desktop_active_path(&origin)?.is_file() {
                    let result = register_login(&state, enabled);
                    state.ui_bridge.login_autostart_changed(get_desktop_login_autostart(&state.paths));
                    return result;
                }
                let Some(owner) = owner.as_deref() else {
                    state.ui_bridge.login_autostart_changed(!enabled);
                    return Err("请先登录本机节点所属账号".into());
                };
                let bundle =
                    resolve_active_bundle(&state.paths, &origin, state.dev_repo_root.as_deref())?;
                let out = set_managed_login(&state, &bundle, &origin, owner, None)?;
                if out.ok {
                    Ok(())
                } else {
                    Err(out.body["detail"]
                        .as_str()
                        .unwrap_or("本机设置失败")
                        .to_owned())
                }
            })()
        };
        if let Err(error) = result {
            show_error_dialog(&error);
        }
    });
}

pub(crate) fn tray_icon_bytes_and_template(target_os: &str) -> (&'static [u8], bool) {
    if target_os == "macos" {
        (TRAY_TEMPLATE_PNG, true)
    } else {
        (TRAY_COLOR_PNG, false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn windows_tray_icon_uses_colorful_brand_rgba_while_macos_keeps_template() {
        let (mac_bytes, mac_template) = tray_icon_bytes_and_template("macos");
        assert!(mac_template);
        let mac_img = Image::from_bytes(mac_bytes).unwrap();
        assert!(mac_img.width() > 0 && mac_img.height() > 0);

        let (win_bytes, win_template) = tray_icon_bytes_and_template("windows");
        assert!(!win_template);
        let win_img = Image::from_bytes(win_bytes).unwrap();
        let colorful_pixels = win_img
            .rgba()
            .chunks_exact(4)
            .filter(|px| px[3] > 32 && (px[0] != px[1] || px[1] != px[2]))
            .count();
        assert!(
            colorful_pixels > 100,
            "Windows tray icon must use colorful brand RGBA pixels instead of pure black monochrome silhouette, got {colorful_pixels} colorful pixels"
        );
    }

    #[test]
    fn bootstrap_url_supports_cache_bust_nonce_while_preserving_target_route() {
        let coord = TauriUiCoordinator::default();
        *coord.bootstrap_base.lock().unwrap() = Some((19876, "boot-nonce-1".to_string()));
        let normal = coord.build_bootstrap_url("/settings/nodes").unwrap();
        assert_eq!(
            normal.as_str(),
            "http://127.0.0.1:19876/desktop/bootstrap?nonce=boot-nonce-1&next=%2Fsettings%2Fnodes"
        );
        let busted = coord
            .build_bootstrap_url_with_cache_bust("/settings/nodes", Some("reload123"))
            .unwrap();
        assert!(busted.as_str().contains("_cb=reload123"), "{busted}");
        assert!(busted.as_str().contains("next=%2Fsettings%2Fnodes"), "{busted}");
    }
}
