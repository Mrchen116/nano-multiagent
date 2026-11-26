pub mod autostart;
pub mod config;
pub mod host_server;
pub mod local_node;
pub mod notifications;
pub mod tray;

use crate::config::{DesktopCliOptions, DesktopPaths, HostRuntimeStateFile};
use crate::host_server::start_host_server;
use crate::local_node::{ensure_seed_bundle_installed, resolve_active_bundle, run_local_admin_sync};
use crate::notifications::{DesktopUiBridge, NoopUiBridge};
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
                "route": cli.initial_route.as_deref().unwrap_or("/chat"),
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
                                let autostart_on =
                                    inspect.body["autostart"].as_bool() != Some(false);
                                if inspect.ok
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

/// Entrypoint for Crewden Desktop (`crewden-desktop`).
pub fn run_from_env() -> Result<(), String> {
    let cli = DesktopCliOptions::parse_from(std::env::args())?;
    let paths = DesktopPaths::resolve(&cli)?;

    if forward_to_running_instance(&paths, &cli)? {
        return Ok(());
    }
    if cli.stop {
        return Ok(());
    }

    ensure_seed_bundle_installed(&paths, cli.seed_archives_dir.as_deref())?;

    if cli.headless_host {
        let rt = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .map_err(|e| e.to_string())?;
        return rt.block_on(async move {
            let ui = Arc::new(NoopUiBridge::default());
            let mut running = start_host_server(
                paths.clone(),
                cli.im_origin.as_deref(),
                cli.dev_repo_root.clone(),
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

    let mut running = rt.block_on(start_host_server(
        paths.clone(),
        cli.im_origin.as_deref(),
        cli.dev_repo_root.clone(),
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
                if let Ok(Some(new_origin)) = crate::config::parse_deep_link_origin(url.as_str()) {
                    let _ = crate::host_server::apply_server_switch(&state_run, &new_origin);
                    coord_run.reload_webview(Some("/chat"));
                    let _ = coord_run.ensure_main_window(app_handle, Some("/chat"));
                } else if let Ok(Some(route)) = crate::config::parse_deep_link_route(url.as_str()) {
                    coord_run.activate_route(&route);
                }
            }
        }
        _ => {}
    });

    Ok(())
}
