use crate::config::{append_private_jsonl, write_private_json, DesktopPaths, StoredSessionsFile};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone)]
pub struct ActiveBundlePaths {
    pub version_root: PathBuf,
    pub node_bin: PathBuf,
    pub cli_js: PathBuf,
    pub ui_frontend: PathBuf,
    pub ui_trajectory: PathBuf,
    pub version: String,
    pub sha256: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct SeedMarker {
    version: String,
    sha256: String,
    runtime_sha256: String,
    version_root: String,
}

#[derive(Debug, Clone, Deserialize)]
struct DesktopActivePointer {
    version_root: Option<String>,
    ui_root: Option<String>,
    version: Option<String>,
    sha256: Option<String>,
}

fn configure_hidden_command(cmd: &mut Command) {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let _ = cmd;
}

fn node_rel_path() -> &'static str {
    if cfg!(target_os = "windows") {
        "runtime/node.exe"
    } else {
        "runtime/bin/node"
    }
}

fn standalone_node_rel_path() -> &'static str {
    if cfg!(target_os = "windows") {
        "node.exe"
    } else {
        "bin/node"
    }
}

/// Locate bundled `seed-archives/` next to the packaged `.app` or Windows install root.
pub fn default_seed_archives_dir(explicit: Option<&Path>) -> Option<PathBuf> {
    if let Some(dir) = explicit {
        if dir.is_dir() {
            return Some(dir.to_path_buf());
        }
    }
    if let Ok(env_dir) = std::env::var("CREWDEN_SEED_ARCHIVES_DIR") {
        let p = PathBuf::from(env_dir);
        if p.is_dir() {
            return Some(p);
        }
    }
    let exe = std::env::current_exe().ok()?;
    // macOS: Crewden.app/Contents/MacOS/crewden-desktop -> Contents/Resources/seed-archives
    if let Some(contents) = exe.parent().and_then(|p| p.parent()) {
        let mac_seed = contents.join("Resources").join("seed-archives");
        if mac_seed.is_dir() {
            return Some(mac_seed);
        }
    }
    // Windows: <install>/CrewdenDesktop.exe -> <install>/seed-archives
    if let Some(dir) = exe.parent() {
        let win_seed = dir.join("seed-archives");
        if win_seed.is_dir() {
            return Some(win_seed);
        }
    }
    None
}

fn seed_manifest_filename() -> &'static str {
    if cfg!(target_os = "windows") {
        "manifest.desktop-win32-x64.json"
    } else {
        "manifest.desktop-darwin-arm64.json"
    }
}

/// Copy `seed-archives/desktop-defaults.json` (if bundled) into `<desktop_home>/desktop-defaults.json`
/// before loopback server initialization, or remove stale defaults when an official installer overwrites a private one.
pub fn sync_seed_desktop_defaults(paths: &DesktopPaths, seed_archives_dir: Option<&Path>) {
    let Some(seed_dir) = default_seed_archives_dir(seed_archives_dir) else {
        return;
    };
    let defaults_src = seed_dir.join("desktop-defaults.json");
    let dest = paths.desktop_defaults_path();
    if defaults_src.is_file() {
        if let Some(parent) = dest.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let _ = fs::copy(&defaults_src, &dest);
    } else {
        let _ = fs::remove_file(&dest);
    }
}

fn read_seed_marker(paths: &DesktopPaths) -> Option<SeedMarker> {
    fs::read_to_string(paths.seed_marker_path())
        .ok()
        .and_then(|raw| serde_json::from_str::<SeedMarker>(&raw).ok())
}

/// Advance existing `.desktop-active.json` pointers across connections when a new installer seed bundle lands.
fn advance_managed_active_pointers_to_seed(
    paths: &DesktopPaths,
    version: &str,
    target_sha: &str,
    final_version_root: &Path,
) {
    let connections_dir = paths.nano_install_root.join("connections");
    let Ok(entries) = fs::read_dir(&connections_dir) else {
        return;
    };
    let now_epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let root_str = final_version_root.to_string_lossy().to_string();
    let ui_str = final_version_root.join("ui").to_string_lossy().to_string();
    for entry in entries.flatten() {
        let active_path = entry.path().join(".desktop-active.json");
        if !active_path.is_file() {
            continue;
        }
        let Ok(raw) = fs::read_to_string(&active_path) else {
            continue;
        };
        let Ok(mut val) = serde_json::from_str::<Value>(&raw) else {
            continue;
        };
        let Some(obj) = val.as_object_mut() else {
            continue;
        };
        obj.insert("managed_by".to_string(), json!("crewden-desktop"));
        obj.insert("sha256".to_string(), json!(target_sha));
        obj.insert("version".to_string(), json!(version));
        obj.insert("version_root".to_string(), json!(root_str));
        obj.insert("ui_root".to_string(), json!(ui_str));
        obj.insert("updated_at_epoch".to_string(), json!(now_epoch));
        let _ = write_private_json(&active_path, &val);
    }
}

/// Reconcile `seed-current.json` and `.desktop-active.json` immediately when the bundled seed `.ready` already exists
/// and differs from `seed-current.json` (e.g. re-installing or switching installers while keeping OTA updates untouched).
pub fn reconcile_ready_seed_bundle(paths: &DesktopPaths, seed_archives_dir: Option<&Path>) {
    let Some(seed_dir) = default_seed_archives_dir(seed_archives_dir) else {
        return;
    };
    let manifest_path = seed_dir.join(seed_manifest_filename());
    let Ok(manifest_raw) = fs::read_to_string(&manifest_path) else {
        return;
    };
    let Ok(manifest) = serde_json::from_str::<Value>(&manifest_raw) else {
        return;
    };
    let Some(target_sha) = manifest["sha256"].as_str() else {
        return;
    };
    let version = manifest["version"].as_str().unwrap_or("0.1.0");
    let final_version_root = paths.desktop_home.join("versions").join(target_sha);
    if !final_version_root.join(".ready").is_file() {
        return;
    }
    let prev = read_seed_marker(paths);
    if prev.as_ref().map(|m| m.sha256.as_str()) == Some(target_sha) {
        return;
    }
    let runtime_sha = manifest["package"]
        .as_str()
        .and_then(|pkg| fs::read_to_string(seed_dir.join(pkg)).ok())
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .and_then(|d| d["runtime"]["sha256"].as_str().map(str::to_string))
        .or_else(|| prev.map(|m| m.runtime_sha256))
        .unwrap_or_default();
    let _ = write_private_json(
        &paths.seed_marker_path(),
        &SeedMarker {
            version: version.to_string(),
            sha256: target_sha.to_string(),
            runtime_sha256: runtime_sha,
            version_root: final_version_root.to_string_lossy().to_string(),
        },
    );
    advance_managed_active_pointers_to_seed(paths, version, target_sha, &final_version_root);
}

/// Gracefully stop all managed local node processes across saved Desktop sessions without setting `user_stopped`.
pub fn stop_all_managed_local_nodes(paths: &DesktopPaths, dev_repo_root: Option<&Path>) {
    let sessions = fs::read_to_string(paths.sessions_path())
        .ok()
        .and_then(|raw| serde_json::from_str::<StoredSessionsFile>(&raw).ok())
        .unwrap_or_default();
    for (im_origin, session) in sessions.by_origin {
        if let Ok(active_path) = paths.desktop_active_path(&im_origin) {
            if !active_path.is_file() {
                continue;
            }
        }
        if let Ok(bundle) = resolve_active_bundle(paths, &im_origin, dev_repo_root) {
            let _ = run_local_admin_sync(
                paths,
                &bundle,
                &im_origin,
                "lifecycle",
                Some(&session.owner_id),
                None,
                Some(&json!({ "action": "stop", "preserve_user_stopped": true })),
            );
        }
    }
}

/// Return true when bundled seed archives exist and have not yet unpacked their target `.ready` marker.
pub fn has_pending_seed_bundle(paths: &DesktopPaths, seed_archives_dir: Option<&Path>) -> bool {
    let Some(seed_dir) = default_seed_archives_dir(seed_archives_dir) else {
        return false;
    };
    let manifest_path = seed_dir.join(seed_manifest_filename());
    if !manifest_path.is_file() {
        return false;
    }
    let Ok(raw) = fs::read_to_string(&manifest_path) else {
        return true;
    };
    let Ok(manifest) = serde_json::from_str::<Value>(&raw) else {
        return true;
    };
    let Some(target_sha) = manifest["sha256"].as_str() else {
        return true;
    };
    !paths
        .desktop_home
        .join("versions")
        .join(target_sha)
        .join(".ready")
        .is_file()
}

/// Unpack first-install seed archives into `<desktop_home>/{cache,runtimes,versions}` so
/// managed Node 24.22.1 works with zero global PATH tools and future updates reuse `runtime`.
pub fn ensure_seed_bundle_installed(
    paths: &DesktopPaths,
    seed_archives_dir: Option<&Path>,
) -> Result<Option<PathBuf>, String> {
    sync_seed_desktop_defaults(paths, seed_archives_dir);
    let Some(seed_dir) = default_seed_archives_dir(seed_archives_dir) else {
        return Ok(None);
    };
    let manifest_name = seed_manifest_filename();
    let manifest_path = seed_dir.join(manifest_name);
    if !manifest_path.is_file() {
        return Ok(None);
    }
    let manifest_raw = fs::read_to_string(&manifest_path).map_err(|e| e.to_string())?;
    let manifest: Value = serde_json::from_str(&manifest_raw).map_err(|e| e.to_string())?;
    let pkg_name = manifest["package"]
        .as_str()
        .ok_or_else(|| "Seed manifest missing package".to_string())?;
    let target_sha = manifest["sha256"]
        .as_str()
        .ok_or_else(|| "Seed manifest missing sha256".to_string())?;
    let version = manifest["version"].as_str().unwrap_or("0.1.0").to_string();

    let final_version_root = paths.desktop_home.join("versions").join(target_sha);
    if final_version_root.join(".ready").is_file() {
        reconcile_ready_seed_bundle(paths, Some(&seed_dir));
        return Ok(Some(final_version_root));
    }

    let descriptor_src = seed_dir.join(pkg_name);
    let descriptor_raw = fs::read_to_string(&descriptor_src).map_err(|e| e.to_string())?;
    let descriptor: Value = serde_json::from_str(&descriptor_raw).map_err(|e| e.to_string())?;
    let runtime_name = descriptor["runtime"]["name"]
        .as_str()
        .ok_or_else(|| "Seed descriptor missing runtime.name".to_string())?;
    let runtime_sha = descriptor["runtime"]["sha256"]
        .as_str()
        .ok_or_else(|| "Seed descriptor missing runtime.sha256".to_string())?;
    let app_name = descriptor["app"]["name"]
        .as_str()
        .ok_or_else(|| "Seed descriptor missing app.name".to_string())?;
    let app_sha = descriptor["app"]["sha256"]
        .as_str()
        .ok_or_else(|| "Seed descriptor missing app.sha256".to_string())?;

    let cache_dir = paths.desktop_home.join("cache");
    let runtimes_dir = paths.desktop_home.join("runtimes");
    let versions_dir = paths.desktop_home.join("versions");
    fs::create_dir_all(&cache_dir).map_err(|e| e.to_string())?;
    fs::create_dir_all(&runtimes_dir).map_err(|e| e.to_string())?;
    fs::create_dir_all(&versions_dir).map_err(|e| e.to_string())?;

    // Populate cache/ so update-worker.ts sees verified cached runtime & descriptor archives.
    let cached_desc = cache_dir.join(format!("descriptor-{}.json", target_sha));
    let cached_rt = cache_dir.join(format!("{}-{}", runtime_sha, runtime_name));
    let cached_app = cache_dir.join(format!("{}-{}", app_sha, app_name));
    if !cached_desc.is_file() {
        let _ = fs::copy(&descriptor_src, &cached_desc);
    }
    if !cached_rt.is_file() {
        fs::copy(seed_dir.join(runtime_name), &cached_rt).map_err(|e| e.to_string())?;
    }
    if !cached_app.is_file() {
        fs::copy(seed_dir.join(app_name), &cached_app).map_err(|e| e.to_string())?;
    }

    let final_runtime_root = runtimes_dir.join(runtime_sha);
    if !final_runtime_root.join(".ready").is_file() {
        let stage = runtimes_dir.join(format!(".seed-rt-{}", std::process::id()));
        let _ = fs::remove_dir_all(&stage);
        fs::create_dir_all(&stage).map_err(|e| e.to_string())?;
        extract_tar_gz(&cached_rt, &stage)?;
        let node_bin = stage.join(standalone_node_rel_path());
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if node_bin.is_file() {
                let _ = fs::set_permissions(&node_bin, fs::Permissions::from_mode(0o755));
            }
        }
        let layout = stage.join("layout.mjs");
        if layout.is_file() {
            let mut cmd = Command::new(&node_bin);
            configure_hidden_command(&mut cmd);
            let out = cmd
                .arg(&layout)
                .arg("runtime")
                .arg(&stage)
                .arg(&final_runtime_root)
                .output()
                .map_err(|e| format!("Failed to run runtime layout.mjs: {}", e))?;
            if !out.status.success() {
                let _ = fs::remove_dir_all(&stage);
                return Err(format!(
                    "runtime layout.mjs failed: {}",
                    String::from_utf8_lossy(&out.stderr)
                ));
            }
        }
        fs::write(stage.join(".ready"), b"").map_err(|e| e.to_string())?;
        if final_runtime_root.exists() {
            let _ = fs::remove_dir_all(&stage);
        } else {
            fs::rename(&stage, &final_runtime_root).map_err(|e| e.to_string())?;
        }
    }

    let node_bin = final_runtime_root.join(standalone_node_rel_path());
    let layout = final_runtime_root.join("layout.mjs");
    let app_extract = versions_dir.join(format!(".seed-app-extract-{}", std::process::id()));
    let version_stage = versions_dir.join(format!(".seed-ver-stage-{}", std::process::id()));
    let _ = fs::remove_dir_all(&app_extract);
    let _ = fs::remove_dir_all(&version_stage);
    fs::create_dir_all(&app_extract).map_err(|e| e.to_string())?;
    fs::create_dir_all(&version_stage).map_err(|e| e.to_string())?;

    extract_tar_gz(&cached_app, &app_extract)?;
    let mut cmd = Command::new(&node_bin);
    configure_hidden_command(&mut cmd);
    let out = cmd
        .arg(&layout)
        .arg("version")
        .arg(&version_stage)
        .arg(&final_version_root)
        .arg(&final_runtime_root)
        .arg(&app_extract)
        .output()
        .map_err(|e| format!("Failed to run version layout.mjs: {}", e))?;
    let _ = fs::remove_dir_all(&app_extract);
    if !out.status.success() {
        let _ = fs::remove_dir_all(&version_stage);
        return Err(format!(
            "version layout.mjs failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }

    write_private_json(&version_stage.join(".release-manifest.json"), &manifest)?;
    fs::write(version_stage.join(".ready"), format!("{}\n", target_sha)).map_err(|e| e.to_string())?;
    if !final_version_root.exists() {
        fs::rename(&version_stage, &final_version_root).map_err(|e| e.to_string())?;
    } else {
        let _ = fs::remove_dir_all(&version_stage);
    }

    let seed_changed = read_seed_marker(paths)
        .map(|m| m.sha256 != target_sha)
        .unwrap_or(true);
    write_private_json(
        &paths.seed_marker_path(),
        &SeedMarker {
            version: version.clone(),
            sha256: target_sha.to_string(),
            runtime_sha256: runtime_sha.to_string(),
            version_root: final_version_root.to_string_lossy().to_string(),
        },
    )?;
    if seed_changed {
        advance_managed_active_pointers_to_seed(paths, &version, target_sha, &final_version_root);
    }
    Ok(Some(final_version_root))
}

fn extract_tar_gz(archive: &Path, dest: &Path) -> Result<(), String> {
    let tar_bin = if cfg!(target_os = "windows") {
        PathBuf::from(r"C:\Windows\System32\tar.exe")
    } else {
        PathBuf::from("/usr/bin/tar")
    };
    let program = if tar_bin.is_file() {
        tar_bin
    } else {
        PathBuf::from("tar")
    };
    let mut cmd = Command::new(program);
    configure_hidden_command(&mut cmd);
    let out = cmd
        .arg("-xzf")
        .arg(archive)
        .arg("-C")
        .arg(dest)
        .output()
        .map_err(|e| format!("Failed to invoke tar: {}", e))?;
    if !out.status.success() {
        return Err(format!(
            "tar extraction failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    Ok(())
}

/// Resolve the active version bundle (UI + Node 24.22.1 + `apps/node/lib/cli.js`) for `im_origin`.
pub fn resolve_active_bundle(
    paths: &DesktopPaths,
    im_origin: &str,
    dev_repo_root: Option<&Path>,
) -> Result<ActiveBundlePaths, String> {
    // 1. Connection-scoped `.desktop-active.json` written by connect or update-worker
    if let Ok(active_path) = paths.desktop_active_path(im_origin) {
        if let Ok(raw) = fs::read_to_string(&active_path) {
            if let Ok(ptr) = serde_json::from_str::<DesktopActivePointer>(&raw) {
                if let Some(ref vr) = ptr.version_root {
                    let root = PathBuf::from(vr);
                    if root.join(".ready").is_file() && root.join(node_rel_path()).is_file() {
                        let ui_base = ptr
                            .ui_root
                            .map(PathBuf::from)
                            .unwrap_or_else(|| root.join("ui"));
                        return Ok(ActiveBundlePaths {
                            node_bin: root.join(node_rel_path()),
                            cli_js: root.join("apps/node/lib/cli.js"),
                            ui_frontend: ui_base.join("frontend"),
                            ui_trajectory: ui_base.join("trajectory"),
                            version: ptr.version.unwrap_or_else(|| "managed".to_string()),
                            sha256: ptr.sha256,
                            version_root: root,
                        });
                    }
                }
            }
        }
    }

    // 2. Installed seed version in `<desktop_home>/seed-current.json`
    if let Ok(raw) = fs::read_to_string(paths.seed_marker_path()) {
        if let Ok(seed) = serde_json::from_str::<SeedMarker>(&raw) {
            let root = PathBuf::from(&seed.version_root);
            if root.join(".ready").is_file() && root.join(node_rel_path()).is_file() {
                return Ok(ActiveBundlePaths {
                    node_bin: root.join(node_rel_path()),
                    cli_js: root.join("apps/node/lib/cli.js"),
                    ui_frontend: root.join("ui/frontend"),
                    ui_trajectory: root.join("ui/trajectory"),
                    version: seed.version,
                    sha256: Some(seed.sha256),
                    version_root: root,
                });
            }
        }
    }

    // 3. Development / test repository fallback (blocked when packaged seed-archives exist without explicit dev_repo_root)
    let explicit_dev = dev_repo_root.map(Path::to_path_buf).or_else(|| {
        std::env::var("CREWDEN_DEV_REPO_ROOT")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .map(PathBuf::from)
    });
    if explicit_dev.is_none() && default_seed_archives_dir(None).is_some() {
        return Err("Seed runtime bundle is still preparing".to_string());
    }
    let repo_root = explicit_dev
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."));
    let repo_root = fs::canonicalize(&repo_root).unwrap_or(repo_root);
    let node_bin = resolve_dev_node_binary(&repo_root)?;
    Ok(ActiveBundlePaths {
        node_bin,
        cli_js: repo_root.join("apps/node/lib/cli.js"),
        ui_frontend: repo_root.join("src/IM/frontend/dist"),
        ui_trajectory: repo_root.join("packages/dsh-trajectory-viewer/dist"),
        version: "source".to_string(),
        sha256: None,
        version_root: repo_root,
    })
}

fn resolve_dev_node_binary(repo_root: &Path) -> Result<PathBuf, String> {
    if let Ok(explicit) = std::env::var("CREWDEN_NODE_BIN") {
        let p = PathBuf::from(explicit);
        if p.is_file() {
            return Ok(p);
        }
    }
    let cached_mac = repo_root
        .join(".cache/desktop-archives/node-v24.22.1-darwin-arm64/bin/node");
    if cached_mac.is_file() {
        return Ok(cached_mac);
    }
    let cached_win = repo_root.join(".cache/desktop-archives/node-v24.22.1-win-x64/node.exe");
    if cached_win.is_file() {
        return Ok(cached_win);
    }
    for candidate in ["/opt/homebrew/bin/node", "/usr/local/bin/node", "node"] {
        let p = PathBuf::from(candidate);
        if p.is_file() || candidate == "node" {
            return Ok(p);
        }
    }
    Err("No Node.js runtime found".to_string())
}

#[derive(Debug)]
pub struct LocalAdminResult {
    pub status: u16,
    pub ok: bool,
    pub body: Value,
}

/// Invoke `apps/node/lib/cli.js local-admin <subcommand>` using the active managed Node binary.
pub fn run_local_admin_sync(
    paths: &DesktopPaths,
    bundle: &ActiveBundlePaths,
    im_origin: &str,
    subcommand: &str,
    owner_id: Option<&str>,
    log_query: Option<&str>,
    stdin_payload: Option<&Value>,
) -> Result<LocalAdminResult, String> {
    let mut cmd = Command::new(&bundle.node_bin);
    configure_hidden_command(&mut cmd);
    cmd.arg(&bundle.cli_js)
        .arg("local-admin")
        .arg(subcommand)
        .arg("--origin")
        .arg(im_origin);
    if let Some(owner) = owner_id {
        if !owner.is_empty() {
            cmd.arg("--owner-id").arg(owner);
        }
    }
    if let Some(q) = log_query {
        if !q.trim().is_empty() {
            cmd.arg("--log-query").arg(q);
        }
    }
    cmd.env("CREWDEN_DESKTOP_HOME", &paths.desktop_home)
        .env("NANO_INSTALL_ROOT", &paths.nano_install_root)
        .env("CREWDEN_DESKTOP_MANAGED", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(ref test_auto) = paths.test_autostart_dir {
        cmd.env("NANO_TEST_AUTOSTART_DIR", test_auto);
    } else {
        cmd.env_remove("NANO_TEST_AUTOSTART_DIR");
    }
    if let Ok(loopback_http) = std::env::var("NANO_ALLOW_LOOPBACK_UPDATE_HTTP") {
        cmd.env("NANO_ALLOW_LOOPBACK_UPDATE_HTTP", loopback_http);
    }
    if let Ok(loopback_origin) = std::env::var("NANO_LOOPBACK_RELEASE_ORIGIN") {
        cmd.env("NANO_LOOPBACK_RELEASE_ORIGIN", loopback_origin);
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn local-admin ({}): {}", bundle.node_bin.display(), e))?;
    if let Some(mut stdin) = child.stdin.take() {
        let bytes = match stdin_payload {
            Some(v) => serde_json::to_vec(v).unwrap_or_else(|_| b"{}".to_vec()),
            None => b"{}".to_vec(),
        };
        let _ = stdin.write_all(&bytes);
    }
    let output = child
        .wait_with_output()
        .map_err(|e| format!("Failed waiting for local-admin: {}", e))?;
    let stdout_str = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr_str = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if let Some(last_line) = stdout_str.lines().rev().find(|l| l.trim_start().starts_with('{')) {
        if let Ok(parsed) = serde_json::from_str::<Value>(last_line) {
            let ok = parsed["ok"].as_bool().unwrap_or(false);
            let status = parsed["status"].as_u64().unwrap_or(if ok { 200 } else { 500 }) as u16;
            if ok {
                return Ok(LocalAdminResult {
                    status,
                    ok: true,
                    body: parsed["data"].clone(),
                });
            }
            let message = parsed["message"]
                .as_str()
                .unwrap_or("Local node operation failed")
                .to_string();
            let code = parsed["error_code"].as_str().unwrap_or("local_admin_error");
            return Ok(LocalAdminResult {
                status,
                ok: false,
                body: json!({
                    "code": code,
                    "detail": message,
                }),
            });
        }
    }

    Err(if !stderr_str.is_empty() {
        stderr_str
    } else {
        format!("local-admin exited with status {}", output.status)
    })
}

/// Safely open or reveal a verified local path in Finder / Explorer without shell interpolation.
pub fn open_or_reveal_workspace_path(
    paths: &DesktopPaths,
    resolved_path: &Path,
    reveal: bool,
) -> Result<(), String> {
    append_private_jsonl(
        &paths.open_actions_log_path(),
        &json!({
            "action": if reveal { "reveal" } else { "open" },
            "path": resolved_path.to_string_lossy(),
        }),
    );
    if std::env::var("CREWDEN_SUPPRESS_OS_OPEN").as_deref() == Ok("1") {
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        let mut cmd = Command::new("/usr/bin/open");
        if reveal {
            cmd.arg("-R");
        }
        cmd.arg(resolved_path);
        cmd.status().map_err(|e| e.to_string())?;
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        let mut cmd = Command::new("explorer.exe");
        if reveal {
            cmd.arg(format!("/select,{}", resolved_path.to_string_lossy()));
        } else {
            cmd.arg(resolved_path);
        }
        cmd.spawn().map_err(|e| e.to_string())?;
        return Ok(());
    }

    #[allow(unreachable_code)]
    Ok(())
}

/// Safely open an external `http(s)://` link in the OS default browser with zero IM credentials.
pub fn open_external_url(paths: &DesktopPaths, raw_url: &str) -> Result<(), String> {
    let parsed = url::Url::parse(raw_url.trim()).map_err(|_| "Invalid external URL".to_string())?;
    if parsed.scheme() != "https" && parsed.scheme() != "http" {
        return Err("Only http:// and https:// URLs may be opened externally".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() || parsed.host_str().is_none() {
        return Err("External URL must include a valid host without embedded credentials".to_string());
    }
    let clean = parsed.as_str().to_string();
    append_private_jsonl(
        &paths.open_actions_log_path(),
        &json!({
            "action": "external_url",
            "url": &clean,
        }),
    );
    if std::env::var("CREWDEN_SUPPRESS_OS_OPEN").as_deref() == Ok("1") {
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("/usr/bin/open")
            .arg(&clean)
            .status()
            .map_err(|e| e.to_string())?;
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        let mut cmd = Command::new("powershell.exe");
        configure_hidden_command(&mut cmd);
        cmd.args([
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-Command",
            "Start-Process -FilePath $env:CREWDEN_EXTERNAL_URL",
        ])
        .env("CREWDEN_EXTERNAL_URL", &clean)
        .spawn()
        .map_err(|e| e.to_string())?;
        return Ok(());
    }

    #[allow(unreachable_code)]
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn advances_active_pointers_on_new_installer_seed_while_preserving_ota_updates_and_clearing_stale_defaults() {
        use crate::config::DesktopCliOptions;
        let tmp = tempdir().unwrap();
        let paths = DesktopPaths::resolve(&DesktopCliOptions {
            isolated_root: Some(tmp.path().to_path_buf()),
            ..Default::default()
        })
        .unwrap();
        let origin = "https://im.crewden.work";

        // 1. Seed v1 with private defaults -> sync copies desktop-defaults.json; official seed without it removes it.
        let seed_v1 = tmp.path().join("seed-v1");
        fs::create_dir_all(&seed_v1).unwrap();
        fs::write(
            seed_v1.join("desktop-defaults.json"),
            r#"{"default_im_origin":"http://10.0.0.8:8011","allow_private_http_release_base":true}"#,
        )
        .unwrap();
        sync_seed_desktop_defaults(&paths, Some(&seed_v1));
        assert!(paths.desktop_defaults_path().is_file());

        let seed_official = tmp.path().join("seed-official");
        fs::create_dir_all(&seed_official).unwrap();
        sync_seed_desktop_defaults(&paths, Some(&seed_official));
        assert!(!paths.desktop_defaults_path().exists());

        // 2. Prepare ready versions sha_v1, sha_ota, sha_v2
        let make_ready_version = |sha: &str| {
            let root = paths.desktop_home.join("versions").join(sha);
            let node_path = root.join(node_rel_path());
            fs::create_dir_all(node_path.parent().unwrap()).unwrap();
            fs::create_dir_all(root.join("ui/frontend")).unwrap();
            fs::write(&node_path, b"node").unwrap();
            fs::write(root.join(".ready"), format!("{}\n", sha)).unwrap();
            root
        };
        let root_v1 = make_ready_version("sha_v1");
        let root_ota = make_ready_version("sha_ota");
        let root_v2 = make_ready_version("sha_v2");

        // Initial seed v1 reconciled and connection bound
        let manifest_name = seed_manifest_filename();
        fs::write(
            seed_official.join(manifest_name),
            json!({ "package": "pkg.json", "version": "1.0.0", "sha256": "sha_v1" }).to_string(),
        )
        .unwrap();
        reconcile_ready_seed_bundle(&paths, Some(&seed_official));

        let active_path = paths.desktop_active_path(origin).unwrap();
        write_private_json(
            &active_path,
            &json!({
                "managed_by": "crewden-desktop",
                "sha256": "sha_v1",
                "version": "1.0.0",
                "version_root": root_v1.to_string_lossy(),
                "ui_root": root_v1.join("ui").to_string_lossy(),
                "user_stopped": true,
            }),
        )
        .unwrap();

        // Simulate OTA update moving `.desktop-active.json` to `sha_ota` while installer `seed-archives` is still `sha_v1`
        write_private_json(
            &active_path,
            &json!({
                "managed_by": "crewden-desktop",
                "sha256": "sha_ota",
                "version": "1.0.5",
                "version_root": root_ota.to_string_lossy(),
                "ui_root": root_ota.join("ui").to_string_lossy(),
                "user_stopped": true,
            }),
        )
        .unwrap();
        reconcile_ready_seed_bundle(&paths, Some(&seed_official));
        let resolved_ota = resolve_active_bundle(&paths, origin, None).unwrap();
        assert_eq!(resolved_ota.version, "1.0.5");
        assert_eq!(resolved_ota.sha256.as_deref(), Some("sha_ota"));

        // Now simulate over-installing new installer v2.0.0 (`sha_v2`) -> `.desktop-active.json` advances to `sha_v2` & keeps `user_stopped: true`!
        fs::write(
            seed_official.join(manifest_name),
            json!({ "package": "pkg.json", "version": "2.0.0", "sha256": "sha_v2" }).to_string(),
        )
        .unwrap();
        reconcile_ready_seed_bundle(&paths, Some(&seed_official));
        let resolved_v2 = resolve_active_bundle(&paths, origin, None).unwrap();
        assert_eq!(resolved_v2.version, "2.0.0");
        assert_eq!(resolved_v2.sha256.as_deref(), Some("sha_v2"));
        assert_eq!(resolved_v2.version_root, root_v2);
        let updated_ptr: Value =
            serde_json::from_str(&fs::read_to_string(&active_path).unwrap()).unwrap();
        assert_eq!(updated_ptr["user_stopped"], json!(true));
    }
}
