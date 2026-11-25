use crate::autostart::{get_desktop_login_autostart, set_desktop_login_autostart};
use crate::config::DesktopPaths;
use crate::host_server::HostSharedState;
use crate::local_node::{resolve_active_bundle, run_local_admin_sync};
use crate::notifications::{DesktopUiBridge, WindowAttentionState};
use serde_json::json;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use tauri::image::Image;
use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder, WindowEvent};

const MAIN_WINDOW_LABEL: &str = "main";
const TRAY_PNG: &[u8] = include_bytes!("../icons/tray.png");

pub struct TauriUiCoordinator {
    app_handle: Mutex<Option<AppHandle>>,
    bootstrap_base: Mutex<Option<(u16, String)>>,
    attention: RwLock<WindowAttentionState>,
    pending_route: Mutex<Option<String>>,
    pub explicit_quit: AtomicBool,
    tray_unread: Mutex<u64>,
    status_item: Mutex<Option<MenuItem<tauri::Wry>>>,
    autostart_item: Mutex<Option<CheckMenuItem<tauri::Wry>>>,
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
            status_item: Mutex::new(None),
            autostart_item: Mutex::new(None),
        }
    }
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
        let (port, ref nonce) = (*self.bootstrap_base.lock().unwrap()).clone()?;
        let mut u = url::Url::parse(&format!("http://127.0.0.1:{}/desktop/bootstrap", port)).ok()?;
        u.query_pairs_mut()
            .append_pair("nonce", nonce)
            .append_pair("next", if next_route.starts_with('/') { next_route } else { "/chat" });
        Some(u)
    }

    pub fn ensure_main_window(&self, app: &AppHandle, target_route: Option<&str>) -> Option<WebviewWindow> {
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
            let _ = win.unminimize();
            let _ = win.show();
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
            return Some(win);
        }

        let initial_route = effective_route.as_deref().unwrap_or("/chat");
        let url = self.build_bootstrap_url(initial_route)?;
        self.set_current_route(initial_route.to_string());

        let win = WebviewWindowBuilder::new(app, MAIN_WINDOW_LABEL, WebviewUrl::External(url))
            .title("Crewden")
            .inner_size(1280.0, 840.0)
            .min_inner_size(380.0, 560.0)
            .visible(true)
            .focused(true)
            .build()
            .ok()?;

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
        Some(win)
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
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let app_clone = app.clone();
        let status_item = self.status_item.lock().unwrap().clone();
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
                let label = if total_unread > 0 {
                    format!("Crewden 常驻在线（{} 条未读）", total_unread)
                } else {
                    "Crewden 常驻在线".to_string()
                };
                let _ = item.set_text(label);
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
        let route = target_route.to_string();
        let coord = app.state::<Arc<TauriUiCoordinator>>().inner().clone();
        let app_clone = app.clone();
        let _ = app.run_on_main_thread(move || {
            let _ = coord.ensure_main_window(&app_clone, Some(&route));
        });
    }

    fn reload_webview(&self, target_route: Option<&str>) {
        let Some(app) = self.app_handle.lock().unwrap().clone() else {
            return;
        };
        let next = target_route.map(str::to_string);
        let boot_url = self.build_bootstrap_url(next.as_deref().unwrap_or("/chat"));
        let app_clone = app.clone();
        let _ = app.run_on_main_thread(move || {
            if let Some(win) = app_clone.get_webview_window(MAIN_WINDOW_LABEL) {
                if let Some(url) = boot_url {
                    if let Ok(encoded) = serde_json::to_string(url.as_str()) {
                        let _ = win.eval(&format!("window.location.replace({});", encoded));
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

    let icon = Image::from_bytes(TRAY_PNG).map_err(|e| e.to_string())?;
    let coord_for_menu = coord.clone();
    let coord_for_click = coord.clone();
    let state_for_menu = host_state.clone();

    TrayIconBuilder::with_id("crewden-tray")
        .icon(icon)
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
                let _ = coord_for_click.ensure_main_window(tray.app_handle(), None);
            }
        })
        .on_menu_event(move |app_handle, event| {
            match event.id().as_ref() {
                "open_main" => {
                    let _ = coord_for_menu.ensure_main_window(app_handle, None);
                }
                "open_nodes" => {
                    let _ = coord_for_menu.ensure_main_window(app_handle, Some("/settings/nodes"));
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
                    );
                }
                "toggle_autostart" => {
                    let next_enabled = !get_desktop_login_autostart(&state_for_menu.paths);
                    if let Ok(exe) = std::env::current_exe() {
                        let _ = set_desktop_login_autostart(&state_for_menu.paths, &exe, next_enabled);
                    }
                    if let Some(ref item) = *coord_for_menu.autostart_item.lock().unwrap() {
                        let _ = item.set_checked(next_enabled);
                    }
                    let origin = state_for_menu.host_config.read().unwrap().im_origin.clone();
                    let owner = state_for_menu
                        .sessions
                        .read()
                        .unwrap()
                        .by_origin
                        .get(&origin)
                        .map(|s| s.owner_id.clone());
                    spawn_tray_lifecycle_action(
                        state_for_menu.paths.clone(),
                        state_for_menu.dev_repo_root.clone(),
                        origin,
                        owner,
                        if next_enabled {
                            "autostart-on"
                        } else {
                            "autostart-off"
                        },
                    );
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

    Ok(())
}

fn spawn_tray_lifecycle_action(
    paths: DesktopPaths,
    dev_repo_root: Option<PathBuf>,
    im_origin: String,
    owner_id: Option<String>,
    action: &'static str,
) {
    let Some(owner) = owner_id else {
        return;
    };
    std::thread::spawn(move || {
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
