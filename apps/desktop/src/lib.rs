pub mod autostart;
pub mod config;
pub mod generated_contracts;
pub mod host_server;
pub mod local_node;
pub mod notifications;
pub mod tray;

use crate::config::{append_host_log, local_node_bridge_endpoint, write_private_json, DesktopCliOptions, DesktopPaths, HostRuntimeStateFile, InstanceLock};
use crate::host_server::{handle_deep_link_url, ping_local_bridge, start_host_server_full};
use crate::local_node::{resolve_active_bundle, run_local_admin_sync, stop_all_managed_local_nodes};
use crate::notifications::NoopUiBridge;
use crate::tray::{install_system_tray, TauriUiCoordinator};
use serde_json::json;
use std::fs;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::Duration;
use tauri::RunEvent;

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

        let deep_url = format!(
            "http://127.0.0.1:{}/desktop/internal/deep-link",
            existing.port
        );
        let _ = client
            .post(&deep_url)
            .header("x-crewden-reload-token", &existing.reload_token)
            .json(&json!({
                "url": cli.deep_link_url,
                "route": cli.initial_route,
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
    let login_owner = state.sessions.read().unwrap().by_origin.get(&login_origin).map(|s| s.owner_id.clone());
    std::thread::spawn(move || {
        let mut first_check = true;
        while state.shutdown_tx.lock().unwrap().is_some() {
            if state.is_seed_ready() {
                let _guard = state.node_lifecycle.lock().unwrap();
                let origin = state.host_config.read().unwrap().im_origin.clone();
                let owner = state.sessions.read().unwrap().by_origin.get(&origin).map(|s| s.owner_id.clone());
                if let Some(owner) = owner {
                    let login = background_login && first_check && origin == login_origin && Some(&owner) == login_owner.as_ref();
                    match supervise_node(&state, &runtime, &origin, &owner, first_check, login) {
                        Ok(checked) => first_check &= !checked,
                        Err(error) => { append_host_log(Some(&state.paths), "WARN", &error); }
                    }
                }
            }
            std::thread::sleep(Duration::from_secs(3));
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
) -> Result<bool, String> {
    let paths = &state.paths;
    let dir = paths.connection_dir(origin)?;
    let pointer = dir.join(".desktop-active.json");
    if !pointer.is_file() || dir.join(".desktop-switch.json").exists() || dir.join(".gateway-lifecycle.lock").exists() {
        return Ok(false);
    }
    let mut active: serde_json::Value = serde_json::from_slice(&fs::read(&pointer).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    let stopped = active["user_stopped"].as_bool() == Some(true);
    let resume = login && autostart::get_desktop_login_autostart(paths);
    if stopped && !resume {
        return Ok(true);
    }
    let has_state = dir.join(".gateway-state.json").is_file();
    if !first_check {
        if !has_state {
            return Ok(true);
        }
        let config = dir.join("config.yaml");
        #[cfg(unix)]
        let config = config.canonicalize().unwrap_or(config);
        let endpoint = local_node_bridge_endpoint(&config);
        if runtime.block_on(ping_local_bridge(&endpoint)).is_some() {
            return Ok(true);
        }
    }
    let bundle = resolve_active_bundle(paths, origin, state.dev_repo_root.as_deref())?;
    let inspect = run_local_admin_sync(paths, &bundle, origin, "supervise", Some(owner), None, None)?;
    if !inspect.ok {
        return Err(inspect.body["detail"].to_string());
    }
    let enabled = inspect.body["autostart"].as_bool() == Some(true);
    let online = inspect.body["ownership"] == "managed_online";
    let offline = inspect.body["ownership"] == "managed_stopped";
    if stopped && (!enabled || !(online || offline)) {
        return Ok(true);
    }
    if stopped && online {
        // The Windows gateway logon task can beat the Desktop logon item.
        active["user_stopped"] = json!(false);
        write_private_json(&pointer, &active)?;
    }
    let action = if first_check && online && bundle.version != "source" && inspect.body["version"] != bundle.version {
        "restart"
    } else if offline && (has_state || (first_check && enabled)) {
        "start"
    } else {
        return Ok(true);
    };
    let result = run_local_admin_sync(paths, &bundle, origin, "lifecycle", Some(owner), None, Some(&json!({ "action": action })))?;
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
            let ui = Arc::new(NoopUiBridge::default());
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

    let coord = Arc::new(TauriUiCoordinator::default());
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
    let initial_open_route = cli.initial_route.clone();
    let coord_setup = coord.clone();
    let state_setup = host_state.clone();

    let app = tauri::Builder::default()
        .manage(coord.clone())
        .manage(host_state.clone())
        .setup(move |app| {
            let handle = app.handle().clone();
            coord_setup.bind_app(handle.clone(), port, boot_nonce);
            install_system_tray(&handle, coord_setup.clone(), state_setup.clone())
                .map_err(std::io::Error::other)?;

            #[cfg(target_os = "macos")]
            if start_in_background {
                let _ = app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            }

            if !start_in_background {
                let _ = coord_setup.ensure_main_window(
                    &handle,
                    Some(initial_open_route.as_deref().unwrap_or("/chat")),
                );
            }

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
    let state_run = host_state.clone();
    app.run(move |app_handle, event| match event {
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
                let _ = coord_run.ensure_main_window(app_handle, None);
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
