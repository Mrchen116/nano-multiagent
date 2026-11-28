pub mod autostart;
pub mod config;
pub mod generated_contracts;
pub mod host_server;
pub mod local_node;
pub mod notifications;
pub mod tray;
pub mod updater;

use crate::config::{
    append_host_log, local_node_bridge_endpoint, write_private_json, DesktopCliOptions,
    DesktopPaths, HostRuntimeStateFile, InstanceLock,
};
#[cfg(any(target_os = "macos", target_os = "ios"))]
use crate::host_server::handle_deep_link_url;
use crate::host_server::{ping_local_bridge, start_host_server_full};
use crate::local_node::{resolve_active_bundle, run_local_admin_sync, stop_all_managed_local_nodes};
use crate::notifications::NoopUiBridge;
use crate::tray::{install_system_tray, TauriUiCoordinator};
use serde_json::json;
use std::fs;
use std::path::Path;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::Duration;
use tauri::RunEvent;

#[cfg(target_os = "windows")]
fn allow_foreground_activation(pid: u32) {
    #[link(name = "user32")]
    extern "system" {
        fn AllowSetForegroundWindow(dw_process_id: u32) -> i32;
    }
    if pid > 0 {
        unsafe {
            let _ = AllowSetForegroundWindow(pid);
        }
    }
}

fn is_os_pid_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    #[cfg(unix)]
    {
        extern "C" {
            fn kill(pid: std::os::raw::c_int, sig: std::os::raw::c_int) -> std::os::raw::c_int;
        }
        let Ok(c_pid) = std::os::raw::c_int::try_from(pid) else {
            return false;
        };
        let rc = unsafe { kill(c_pid, 0) };
        if rc == 0 {
            return true;
        }
        std::io::Error::last_os_error().raw_os_error() == Some(1)
    }
    #[cfg(windows)]
    {
        #[link(name = "kernel32")]
        extern "system" {
            fn OpenProcess(
                dw_desired_access: u32,
                b_inherit_handle: i32,
                dw_process_id: u32,
            ) -> *mut std::ffi::c_void;
            fn WaitForSingleObject(h_handle: *mut std::ffi::c_void, dw_milliseconds: u32) -> u32;
            fn CloseHandle(h_object: *mut std::ffi::c_void) -> i32;
        }
        const SYNCHRONIZE_AND_QUERY_LIMITED: u32 = 0x0010_1000;
        const WAIT_TIMEOUT: u32 = 258;
        unsafe {
            let handle = OpenProcess(SYNCHRONIZE_AND_QUERY_LIMITED, 0, pid);
            if handle.is_null() {
                return false;
            }
            let wait_rc = WaitForSingleObject(handle, 0);
            let _ = CloseHandle(handle);
            wait_rc == WAIT_TIMEOUT
        }
    }
}

fn lock_owner_metadata_dir(lock_dir: &Path) -> std::path::PathBuf {
    lock_dir
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join(".gateway-owner")
}

fn lock_owner_sidecar_path(lock_dir: &Path) -> std::path::PathBuf {
    let base = lock_dir
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or(".gateway-lifecycle.lock");
    lock_owner_metadata_dir(lock_dir).join(format!("{base}.json"))
}

fn lock_transition_guard_path(lock_dir: &Path) -> std::path::PathBuf {
    let base = lock_dir
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or(".gateway-lifecycle.lock");
    lock_owner_metadata_dir(lock_dir).join(format!("{base}.guard"))
}

/// Read-only check returning true only when `.gateway-lifecycle.lock` is actively transitioning
/// or held by a live process with a fresh heartbeat. Never mutates lock directories from Rust;
/// `apps/node` reaps dead locks atomically under `.gateway-owner/<lock>.guard`.
pub(crate) fn is_active_gateway_lifecycle_lock(lock_dir: &Path) -> bool {
    let guard_dir = lock_transition_guard_path(lock_dir);
    if let Ok(g_meta) = fs::metadata(&guard_dir) {
        let g_age = g_meta
            .modified()
            .ok()
            .and_then(|t| t.elapsed().ok())
            .unwrap_or(Duration::ZERO);
        if g_age <= Duration::from_secs(5) {
            return true;
        }
    }
    let Ok(meta) = fs::metadata(lock_dir) else {
        return false;
    };
    let age = meta
        .modified()
        .ok()
        .and_then(|t| t.elapsed().ok())
        .unwrap_or(Duration::ZERO);
    let owner_path = lock_owner_sidecar_path(lock_dir);
    if let Ok(raw) = fs::read_to_string(&owner_path) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
            if let Some(pid) = val["pid"]
                .as_u64()
                .and_then(|p| u32::try_from(p).ok())
                .filter(|p| *p > 0)
            {
                if !is_os_pid_alive(pid) {
                    return false;
                }
                // `proper-lockfile` refreshes directory mtime every 1s; if mtime stalled for >15s
                // (e.g. zombie or reassigned PID), let `manageGateway` verify `process_start` and reap.
                return age <= Duration::from_secs(15);
            }
        }
        return age <= Duration::from_secs(5);
    }
    age <= Duration::from_secs(5)
}

fn ensure_foreground_startup_window<T>(
    start_in_background: bool,
    host_state_path: &Path,
    open_window: impl FnOnce() -> Result<T, String>,
) -> Result<(), String> {
    if start_in_background {
        return Ok(());
    }
    if let Err(err) = open_window() {
        let _ = fs::remove_file(host_state_path);
        return Err(err);
    }
    Ok(())
}

fn try_read_live_host_state(paths: &DesktopPaths) -> Option<HostRuntimeStateFile> {
    let raw = fs::read_to_string(paths.host_state_path()).ok()?;
    serde_json::from_str::<HostRuntimeStateFile>(&raw).ok()
}

fn forward_to_running_instance(
    paths: &DesktopPaths,
    cli: &DesktopCliOptions,
) -> Result<bool, String> {
    let Some(existing) = try_read_live_host_state(paths) else {
        return Ok(false);
    };
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| e.to_string())?;

    rt.block_on(async move {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|e| e.to_string())?;

        if cli.stop {
            let url = format!("http://127.0.0.1:{}/desktop/internal/shutdown", existing.port);
            let _ = client
                .post(&url)
                .header("x-crewden-reload-token", &existing.reload_token)
                .send()
                .await;
            return Ok(true);
        }

        let status_url = format!("http://127.0.0.1:{}/desktop/internal/status", existing.port);
        let Ok(status_res) = client
            .get(&status_url)
            .header("x-crewden-reload-token", &existing.reload_token)
            .send()
            .await
        else {
            return Ok(false);
        };
        if !status_res.status().is_success() {
            return Ok(false);
        }
        let status_json = status_res.json::<serde_json::Value>().await.ok();
        let _live_pid = status_json
            .as_ref()
            .and_then(|v| v["pid"].as_u64())
            .and_then(|p| u32::try_from(p).ok())
            .unwrap_or(existing.pid);
        #[cfg(target_os = "windows")]
        allow_foreground_activation(_live_pid);

        let deep_url = format!(
            "http://127.0.0.1:{}/desktop/internal/deep-link",
            existing.port
        );
        let _ = client
            .post(&deep_url)
            .header("x-crewden-reload-token", &existing.reload_token)
            .json(&json!({
                "url": cli.deep_link_url,
            }))
            .send()
            .await;
        Ok(true)
    })
}

fn spawn_managed_node_supervisor(
    state: Arc<crate::host_server::HostSharedState>,
    background_login: bool,
) {
    let runtime = tokio::runtime::Handle::current();
    let login_origin = state.host_config.read().unwrap().im_origin.clone();
    let login_owner = state
        .sessions
        .read()
        .unwrap()
        .by_origin
        .get(&login_origin)
        .map(|s| s.owner_id.clone());
    std::thread::spawn(move || {
        let mut first_check = true;
        let mut context = None;
        let mut expected_running = false;
        let mut login_pending = background_login;
        loop {
            let mut delay = Duration::from_secs(3);
            {
                let _guard = state.node_lifecycle.lock().unwrap();
                if state.shutdown_tx.lock().unwrap().is_none() {
                    return;
                }
                if state.is_seed_ready() {
                    let origin = state.host_config.read().unwrap().im_origin.clone();
                    let owner = state
                        .sessions
                        .read()
                        .unwrap()
                        .by_origin
                        .get(&origin)
                        .map(|s| s.owner_id.clone());
                    let next = (origin.clone(), owner.clone());
                    if context.as_ref() != Some(&next) {
                        if context.is_some() { login_pending = false; }
                        context = Some(next);
                        expected_running = false;
                        first_check = true;
                        state.ui_bridge.login_autostart_changed(autostart::get_desktop_login_autostart(&state.paths));
                    }
                    if let Some(owner) = owner {
                        let login = login_pending
                            && first_check
                            && origin == login_origin
                            && Some(&owner) == login_owner.as_ref();
                        match supervise_node(
                            &state,
                            &runtime,
                            &origin,
                            &owner,
                            first_check,
                            login,
                            &mut expected_running,
                        ) {
                            Ok(true) => {
                                crate::updater::clear_startup_promotion_backup(&state, &origin);
                                first_check = false;
                                login_pending = false;
                            }
                            Ok(false) => {}
                            Err(error) => {
                                append_host_log(Some(&state.paths), "WARN", &error);
                                if first_check && crate::updater::rollback_startup_promotion_if_needed(&state, &origin) {
                                    // Immediately retry starting the restored previous bundle without waiting 30s.
                                    delay = Duration::from_millis(200);
                                } else {
                                    delay = Duration::from_secs(30);
                                }
                            }
                        }
                    }
                }
            }
            std::thread::sleep(delay);
        }
    });
}

// Check the bundle version once. Afterwards the gateway's own IPC response suffices;
// only a missing bridge needs the CLI's PID/birth and ownership verification.
fn supervise_node(
    state: &crate::host_server::HostSharedState,
    runtime: &tokio::runtime::Handle,
    origin: &str,
    owner: &str,
    first_check: bool,
    login: bool,
    expected_running: &mut bool,
) -> Result<bool, String> {
    let paths = &state.paths;
    let dir = paths.connection_dir(origin)?;
    let pointer = dir.join(".desktop-active.json");
    if !pointer.is_file()
        || dir.join(".desktop-switch.json").exists()
        || is_active_gateway_lifecycle_lock(&dir.join(".gateway-lifecycle.lock"))
    {
        return Ok(false);
    }
    let mut active: serde_json::Value =
        serde_json::from_slice(&fs::read(&pointer).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    let stopped = active["user_stopped"].as_bool() == Some(true);
    if stopped && !first_check {
        *expected_running = false;
        return Ok(true);
    }
    let has_state = dir.join(".gateway-state.json").is_file();
    if !first_check {
        if !has_state && !*expected_running {
            return Ok(true);
        }
        let config = dir.join("config.yaml");
        #[cfg(unix)]
        let config = config.canonicalize().unwrap_or(config);
        let endpoint = local_node_bridge_endpoint(&config);
        if let Some(ping) = runtime.block_on(ping_local_bridge(&endpoint)) {
            *expected_running = ping["owner_id"] == owner;
            return Ok(true);
        }
    }
    let bundle = resolve_active_bundle(paths, origin, state.dev_repo_root.as_deref())?;
    let inspect =
        run_local_admin_sync(paths, &bundle, origin, "supervise", Some(owner), None, None)?;
    if !inspect.ok {
        return Err(inspect.body["detail"].to_string());
    }
    let enabled = inspect.body["autostart"].as_bool() == Some(true);
    let online = inspect.body["ownership"] == "managed_online";
    let offline = inspect.body["ownership"] == "managed_stopped";
    if first_check && (online || offline) {
        state.ui_bridge.login_autostart_changed(enabled);
    }
    if stopped && (!login || !enabled || !(online || offline)) {
        *expected_running = false;
        return Ok(true);
    }
    if stopped && online {
        // The Windows gateway logon task can beat the Desktop logon item.
        active["user_stopped"] = json!(false);
        write_private_json(&pointer, &active)?;
    }
    let start = offline && (*expected_running || (enabled && (has_state || first_check)));
    if online || start {
        *expected_running = true;
    }
    let action = if first_check
        && online
        && bundle.version != "source"
        && inspect.body["version"] != bundle.version
    {
        "restart"
    } else if start {
        "start"
    } else {
        return Ok(true);
    };
    let result = run_local_admin_sync(
        paths,
        &bundle,
        origin,
        "lifecycle",
        Some(owner),
        None,
        Some(&json!({ "action": action })),
    )?;
    if !result.ok {
        return Err(result.body["detail"].to_string());
    }
    Ok(true)
}

/// Acquire single-instance OS lock or forward wakeup to a concurrently starting instance.
fn acquire_instance_or_forward(
    paths: &DesktopPaths,
    cli: &DesktopCliOptions,
) -> Result<Option<InstanceLock>, String> {
    if cli.stop {
        let _ = forward_to_running_instance(paths, cli);
        for _ in 0..50 {
            if let Ok(Some(lock)) = InstanceLock::try_acquire(&paths.instance_lock_path()) {
                stop_all_managed_local_nodes(paths, cli.dev_repo_root.as_deref());
                drop(lock);
                return Ok(None);
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        stop_all_managed_local_nodes(paths, cli.dev_repo_root.as_deref());
        return Ok(None);
    }
    if forward_to_running_instance(paths, cli)? {
        return Ok(None);
    }
    if let Some(lock) = InstanceLock::try_acquire(&paths.instance_lock_path())? {
        return Ok(Some(lock));
    }
    // Another instance holds `instance.lock` (e.g. launched milliseconds ago before writing host-state.json).
    for _ in 0..50 {
        std::thread::sleep(Duration::from_millis(100));
        if forward_to_running_instance(paths, cli)? {
            return Ok(None);
        }
        if let Some(lock) = InstanceLock::try_acquire(&paths.instance_lock_path())? {
            return Ok(Some(lock));
        }
    }
    Err("另一个 Crewden Desktop 实例正在启动中，请稍候片刻重试。".to_string())
}

/// Entrypoint for Crewden Desktop (`crewden-desktop`).
pub fn run_from_env() -> Result<(), String> {
    let cli = DesktopCliOptions::parse_from(std::env::args())?;
    let paths = DesktopPaths::resolve(&cli)?;

    if cli.prepare_seed {
        local_node::ensure_seed_bundle_installed(&paths, cli.seed_archives_dir.as_deref())?
            .ok_or_else(|| "Installer seed bundle missing".to_string())?;
        return Ok(());
    }
    let Some(_instance_lock) = acquire_instance_or_forward(&paths, &cli)? else {
        return Ok(());
    };
    append_host_log(Some(&paths), "INFO", "Starting Crewden Desktop host");

    if cli.headless_host {
        let rt = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .map_err(|e| e.to_string())?;
        return rt.block_on(async move {
            let ui = Arc::new(NoopUiBridge::with_window_visible(!cli.background));
            let mut running = start_host_server_full(
                paths.clone(),
                cli.im_origin.as_deref(),
                cli.seed_archives_dir.clone(),
                cli.dev_repo_root.clone(),
                cli.deep_link_url.as_deref(),
                ui,
            )
            .await?;
            spawn_managed_node_supervisor(running.state.clone(), cli.background);
            if let Some(rx) = running.take_shutdown_receiver() {
                let _ = rx.await;
            }
            Ok(())
        });
    }

    let coord = Arc::new(TauriUiCoordinator::with_window_visible(!cli.background));
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|e| e.to_string())?;
    let _guard = rt.enter();

    let mut running = rt.block_on(start_host_server_full(
        paths.clone(),
        cli.im_origin.as_deref(),
        cli.seed_archives_dir.clone(),
        cli.dev_repo_root.clone(),
        cli.deep_link_url.as_deref(),
        coord.clone(),
    ))?;

    let host_state = running.state.clone();
    let port = running.port;
    let boot_nonce = host_state.boot_nonce.clone();
    let shutdown_rx = running.take_shutdown_receiver();

    let start_in_background = cli.background;
    let coord_setup = coord.clone();
    let state_setup = host_state.clone();

    let app = tauri::Builder::default()
        .manage(coord.clone())
        .manage(host_state.clone())
        .setup(move |app| {
            let handle = app.handle().clone();
            coord_setup.bind_app(handle.clone(), port, boot_nonce);
            if let Err(err) =
                install_system_tray(&handle, coord_setup.clone(), state_setup.clone())
            {
                let _ = fs::remove_file(state_setup.paths.host_state_path());
                return Err(std::io::Error::other(err).into());
            }

            #[cfg(target_os = "macos")]
            if start_in_background {
                let _ = app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            }

            ensure_foreground_startup_window(
                start_in_background,
                &state_setup.paths.host_state_path(),
                || coord_setup.ensure_main_window(&handle, Some("/chat")),
            )
            .map_err(std::io::Error::other)?;

            spawn_managed_node_supervisor(state_setup.clone(), start_in_background);

            if let Some(rx) = shutdown_rx {
                let exit_handle = handle.clone();
                let exit_coord = coord_setup.clone();
                tokio::spawn(async move {
                    if rx.await.is_ok() {
                        exit_coord.explicit_quit.store(true, Ordering::SeqCst);
                        exit_handle.exit(0);
                    }
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .map_err(|e| format!("Failed to build Tauri application: {}", e))?;

    let coord_run = coord.clone();
    #[cfg(any(target_os = "macos", target_os = "ios"))]
    let state_run = host_state.clone();
    app.run(move |_app_handle, event| match event {
        RunEvent::ExitRequested { api, .. } => {
            if !coord_run.explicit_quit.load(Ordering::SeqCst) {
                api.prevent_exit();
            }
        }
        #[cfg(target_os = "macos")]
        RunEvent::Reopen {
            has_visible_windows,
            ..
        } => {
            if !has_visible_windows {
                coord_run.ensure_main_window_or_report(_app_handle, None);
            }
        }
        #[cfg(any(target_os = "macos", target_os = "ios"))]
        RunEvent::Opened { urls } => {
            for url in urls {
                handle_deep_link_url(&state_run, url.as_str());
            }
        }
        _ => {}
    });

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reaps_dead_gateway_lifecycle_lock_while_respecting_live_owner() {
        let tmp = tempfile::tempdir().unwrap();
        let lock_dir = tmp.path().join(".gateway-lifecycle.lock");
        let owner_dir = tmp.path().join(".gateway-owner");
        let owner_sidecar = owner_dir.join(".gateway-lifecycle.lock.json");
        fs::create_dir_all(&lock_dir).unwrap();
        fs::create_dir_all(&owner_dir).unwrap();
        fs::write(
            &owner_sidecar,
            serde_json::to_vec(&json!({
                "pid": std::process::id(),
                "process_start": "current",
                "acquired_at": 1,
            }))
            .unwrap(),
        )
        .unwrap();
        assert!(
            is_active_gateway_lifecycle_lock(&lock_dir),
            "Live current process holding fresh lifecycle lock must be respected"
        );

        // Dead owner PID is immediately recognized as inactive without mutating files from Rust.
        fs::write(
            &owner_sidecar,
            serde_json::to_vec(&json!({
                "pid": 999_999_991u32,
                "process_start": "dead",
                "acquired_at": 1,
            }))
            .unwrap(),
        )
        .unwrap();
        assert!(!is_active_gateway_lifecycle_lock(&lock_dir));
        assert!(
            lock_dir.exists() && owner_sidecar.exists(),
            "Rust check must remain read-only so Node reaps atomically under its transition guard"
        );
    }

    #[test]
    fn foreground_window_creation_failure_aborts_startup_and_cleans_host_state() {
        let tmp = tempfile::tempdir().unwrap();
        let host_state = tmp.path().join("host-state.json");
        fs::write(&host_state, b"{\"ready\":true}").unwrap();

        // `--background` skips opening main window and keeps host-state.json intact.
        ensure_foreground_startup_window::<()>(true, &host_state, || {
            panic!("background mode must not open main window on cold start")
        })
        .unwrap();
        assert!(host_state.is_file());

        // Foreground startup MUST propagate window creation errors and clean up host-state.json.
        let err = ensure_foreground_startup_window::<()>(false, &host_state, || {
            Err("无法创建主窗口（WebView 初始化失败）：WebView2 runtime error".to_string())
        })
        .unwrap_err();
        assert!(err.contains("无法创建主窗口"));
        assert!(!host_state.exists());
    }
}
