pub mod autostart;
pub mod config;
pub mod host_server;
pub mod local_node;
pub mod notifications;
pub mod tray;

use crate::config::{append_host_log, DesktopCliOptions, DesktopPaths, HostRuntimeStateFile, InstanceLock};
use crate::host_server::{handle_deep_link_url, start_host_server_full};
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
    paths: DesktopPaths,
    dev_repo_root: Option<std::path::PathBuf>,
    host_state: Arc<crate::host_server::HostSharedState>,
) {
    std::thread::spawn(move || {
        let mut initial_boot_checked = false;
        loop {
            if host_state.shutdown_tx.lock().unwrap().is_none() {
                return;
            }
            if !host_state.is_seed_ready() {
                std::thread::sleep(Duration::from_millis(500));
                continue;
            }
            let im_origin = host_state.host_config.read().unwrap().im_origin.clone();
            let owner = host_state
                .sessions
                .read()
                .unwrap()
                .by_origin
                .get(&im_origin)
                .map(|s| s.owner_id.clone());

            if let Some(owner_id) = owner {
                let active_ptr_json = paths
                    .desktop_active_path(&im_origin)
                    .ok()
                    .and_then(|p| fs::read_to_string(p).ok())
                    .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok());
                if let Some(active_ptr) = active_ptr_json {
                    let user_stopped = active_ptr["user_stopped"].as_bool().unwrap_or(false);
                    let config_dir = paths
                        .connection_config_path(&im_origin)
                        .ok()
                        .and_then(|p| p.parent().map(|d| d.to_path_buf()));
                    let busy_with_switch_or_lock = config_dir
                        .as_ref()
                        .map(|d| {
                            d.join(".desktop-switch.json").exists()
                                || d.join(".gateway-lifecycle.lock").exists()
                        })
                        .unwrap_or(false);
                    let crash_marker_present = config_dir
                        .as_ref()
                        .map(|d| d.join(".gateway-state.json").is_file())
                        .unwrap_or(false);

                    let should_reconcile = !busy_with_switch_or_lock
                        && !user_stopped
                        && (!initial_boot_checked || crash_marker_present);

                    if should_reconcile {
                        if let Ok(bundle) =
                            resolve_active_bundle(&paths, &im_origin, dev_repo_root.as_deref())
                        {
                            if let Ok(inspect) = run_local_admin_sync(
                                &paths,
                                &bundle,
                                &im_origin,
                                "inspect",
                                Some(&owner_id),
                                None,
                                None,
                            ) {
                                let is_stopped =
                                    inspect.body["ownership"].as_str() == Some("managed_stopped");
                                let is_online =
                                    inspect.body["ownership"].as_str() == Some("managed_online");
                                let autostart_on =
                                    inspect.body["autostart"].as_bool() != Some(false);
                                let version_mismatch = !initial_boot_checked
                                    && is_online
                                    && bundle.version != "source"
                                    && inspect.body["version"].as_str()
                                        != Some(bundle.version.as_str());
                                if inspect.ok && version_mismatch {
                                    let _ = run_local_admin_sync(
                                        &paths,
                                        &bundle,
                                        &im_origin,
                                        "lifecycle",
                                        Some(&owner_id),
                                        None,
                                        Some(&json!({ "action": "restart" })),
                                    );
                                } else if inspect.ok
                                    && is_stopped
                                    && ((!initial_boot_checked && autostart_on)
                                        || crash_marker_present)
                                {
                                    let _ = run_local_admin_sync(
                                        &paths,
                                        &bundle,
                                        &im_origin,
                                        "lifecycle",
                                        Some(&owner_id),
                                        None,
                                        Some(&json!({ "action": "start" })),
                                    );
                                }
                            }
                        }
                        initial_boot_checked = true;
                    }
                }
            }
            std::thread::sleep(Duration::from_secs(3));
        }
    });
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
            spawn_managed_node_supervisor(paths, cli.dev_repo_root, running.state.clone());
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
    let dev_root_for_autostart = cli.dev_repo_root.clone();

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

            spawn_managed_node_supervisor(
                state_setup.paths.clone(),
                dev_root_for_autostart,
                state_setup.clone(),
            );

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
