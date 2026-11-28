use crate::config::{
    append_host_log, append_private_jsonl, sha256_hex, write_private_json, DesktopPaths,
    StoredSessionsFile,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::{self, Write};
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct WebviewUiCacheMarker {
    bundle_fingerprint: String,
    version: String,
    updated_at_epoch: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SeedErrorKind {
    DiskFull,
    PermissionOrLocked,
    CorruptArchive,
    Other,
}

/// Return concise, non-misleading user guidance matching a seed preparation failure category.
pub fn seed_error_guidance(err: &str) -> &'static str {
    match classify_seed_error(err) {
        SeedErrorKind::DiskFull => {
            "释放本机应用数据所在分区的可用磁盘空间后即可继续，已有账号与本地数据未受影响。"
        }
        SeedErrorKind::PermissionOrLocked => {
            "请确认当前系统账号对本机数据目录具有读写权限，或排查安全软件的文件占用与拦截。"
        }
        SeedErrorKind::CorruptArchive => {
            "内置运行环境归档校验未通过，建议重新下载官方安装包覆盖安装。"
        }
        SeedErrorKind::Other => {
            "请根据下方诊断详情排查，已有账号与本地数据未受影响。"
        }
    }
}

/// Classify a seed bundle preparation failure so the host and preparation page surface accurate remediation.
pub fn classify_seed_error(err: &str) -> SeedErrorKind {
    let lower = err.to_ascii_lowercase();
    if err.contains("磁盘可用空间不足")
        || err.contains("磁盘空间不足")
        || err.contains("磁盘空间已满")
        || lower.contains("no space left on device")
        || lower.contains("enospc")
        || lower.contains("disk full")
        || lower.contains("not enough space")
        || lower.contains("os error 112")
        || lower.contains("os error 39")
        || lower.contains("os error 28")
    {
        return SeedErrorKind::DiskFull;
    }
    if err.contains("目录访问被拒绝")
        || lower.contains("os error 5")
        || lower.contains("os error 32")
        || lower.contains("os error 13")
        || lower.contains("os error 1)")
        || lower.contains("access is denied")
        || lower.contains("permission denied")
        || lower.contains("operation not permitted")
        || lower.contains("eacces")
        || lower.contains("eperm")
    {
        return SeedErrorKind::PermissionOrLocked;
    }
    if lower.contains("sha-256 mismatch")
        || lower.contains("unrecognized archive")
        || lower.contains("unexpected end of file")
        || lower.contains("corrupt")
    {
        return SeedErrorKind::CorruptArchive;
    }
    SeedErrorKind::Other
}

fn annotate_seed_error(raw: String) -> String {
    match classify_seed_error(&raw) {
        SeedErrorKind::DiskFull if !raw.starts_with("磁盘") => {
            format!("解压写入时磁盘空间已满：{}", raw)
        }
        _ => raw,
    }
}

fn existing_ancestor(path: &Path) -> PathBuf {
    for ancestor in path.ancestors() {
        if ancestor.exists() {
            return ancestor.to_path_buf();
        }
    }
    std::env::temp_dir()
}

/// Query free bytes available to the current user on the filesystem backing `path`.
pub fn query_available_disk_bytes(path: &Path) -> Option<u64> {
    let target = existing_ancestor(path);
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        #[link(name = "kernel32")]
        extern "system" {
            fn GetDiskFreeSpaceExW(
                lp_directory_name: *const u16,
                lp_free_bytes_available_to_caller: *mut u64,
                lp_total_number_of_bytes: *mut u64,
                lp_total_number_of_free_bytes: *mut u64,
            ) -> i32;
        }
        let mut wide: Vec<u16> = target.as_os_str().encode_wide().collect();
        wide.push(0);
        let mut free_to_caller = 0u64;
        let mut total = 0u64;
        let mut total_free = 0u64;
        let ok = unsafe {
            GetDiskFreeSpaceExW(
                wide.as_ptr(),
                &mut free_to_caller,
                &mut total,
                &mut total_free,
            )
        };
        return if ok != 0 { Some(free_to_caller) } else { None };
    }
    #[cfg(unix)]
    {
        let out = Command::new("/bin/df")
            .args(["-Pk"])
            .arg(&target)
            .output()
            .ok()?;
        if !out.status.success() {
            return None;
        }
        let text = String::from_utf8_lossy(&out.stdout);
        let avail_kib: u64 = text
            .lines()
            .nth(1)?
            .split_whitespace()
            .nth(3)?
            .parse()
            .ok()?;
        return Some(avail_kib.saturating_mul(1024));
    }
    #[allow(unreachable_code)]
    None
}

fn estimate_seed_required_bytes(
    rt_bytes: u64,
    app_bytes: u64,
    runtime_ready: bool,
    rt_cached: bool,
    app_cached: bool,
) -> u64 {
    let rt_cache_need = if runtime_ready || rt_cached { 0 } else { rt_bytes };
    let rt_unpack_need = if runtime_ready {
        0
    } else {
        rt_bytes.saturating_mul(5)
    };
    let app_cache_need = if app_cached { 0 } else { app_bytes };
    let app_unpack_need = app_bytes.saturating_mul(5);
    let headroom = if !runtime_ready && rt_bytes >= 32 * 1024 * 1024 {
        384 * 1024 * 1024
    } else if app_bytes >= 8 * 1024 * 1024 {
        64 * 1024 * 1024
    } else {
        4 * 1024 * 1024
    };
    rt_cache_need
        .saturating_add(rt_unpack_need)
        .saturating_add(app_cache_need)
        .saturating_add(app_unpack_need)
        .saturating_add(headroom)
}

fn format_insufficient_disk_space_error(required_bytes: u64, available_bytes: u64) -> String {
    const GIB: f64 = 1024.0 * 1024.0 * 1024.0;
    const MIB: f64 = 1024.0 * 1024.0;
    if required_bytes >= 100 * 1024 * 1024 {
        let mut req_gb = ((required_bytes as f64 / GIB) * 10.0).ceil() / 10.0;
        let avail_gb = ((available_bytes as f64 / GIB) * 10.0).round() / 10.0;
        if req_gb <= avail_gb {
            req_gb = avail_gb + 0.1;
        }
        format!(
            "磁盘可用空间不足：初始化运行环境需要约 {:.1} GB，当前仅剩 {:.1} GB。",
            req_gb, avail_gb
        )
    } else {
        let mut req_mb = ((required_bytes as f64 / MIB) * 10.0).ceil() / 10.0;
        let avail_mb = ((available_bytes as f64 / MIB) * 10.0).round() / 10.0;
        if req_mb <= avail_mb {
            req_mb = avail_mb + 0.1;
        }
        format!(
            "磁盘可用空间不足：初始化运行环境需要约 {:.1} MB，当前仅剩 {:.1} MB。",
            req_mb, avail_mb
        )
    }
}

/// Remove only WebView HTTP/code/GPU cache directories while preserving Cookies, Local Storage, and IndexedDB.
pub fn purge_webview_http_caches(webview_data_dir: &Path) -> usize {
    let mut removed = 0usize;
    let eb_roots = [webview_data_dir.join("EBWebView"), webview_data_dir.to_path_buf()];
    for root in &eb_roots {
        for rel in [
            "Default/Cache",
            "Default/Code Cache",
            "Default/GPUCache",
            "GrShaderCache",
            "GraphiteDawnCache",
            "ShaderCache",
        ] {
            let candidate = root.join(rel);
            if candidate.exists() && fs::remove_dir_all(&candidate).is_ok() {
                removed += 1;
            }
        }
    }
    for mac_rel in ["WebKit/NetworkCache", "WebKit/OfflineWebApplicationCache"] {
        let candidate = webview_data_dir.join(mac_rel);
        if candidate.exists() && fs::remove_dir_all(&candidate).is_ok() {
            removed += 1;
        }
    }
    removed
}

fn current_ui_bundle_fingerprint(
    paths: &DesktopPaths,
    im_origin: &str,
    dev_repo_root: Option<&Path>,
    seed_archives_dir: Option<&Path>,
) -> (String, String) {
    if let Ok(bundle) = resolve_active_bundle(paths, im_origin, dev_repo_root) {
        let index_sha = fs::read(bundle.ui_frontend.join("index.html"))
            .map(|bytes| sha256_hex(&bytes))
            .unwrap_or_else(|_| "missing-index".to_string());
        let raw = format!(
            "ready|{}|{}|{}|{}",
            bundle.version,
            bundle.sha256.as_deref().unwrap_or(""),
            bundle.ui_frontend.to_string_lossy(),
            index_sha
        );
        return (sha256_hex(raw.as_bytes()), bundle.version);
    }
    let pending_seed = default_seed_archives_dir(seed_archives_dir)
        .and_then(|dir| fs::read_to_string(dir.join(seed_manifest_filename())).ok())
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok());
    let sha = pending_seed
        .as_ref()
        .and_then(|v| v["sha256"].as_str())
        .unwrap_or("pending");
    let ver = pending_seed
        .as_ref()
        .and_then(|v| v["version"].as_str())
        .unwrap_or("preparing")
        .to_string();
    (format!("preparing:{sha}"), ver)
}

/// Purge stale WebView HTTP/code caches when first upgrading to cache-hygiene tracking or when the active UI bundle changes.
pub fn reconcile_webview_ui_cache(
    paths: &DesktopPaths,
    im_origin: &str,
    dev_repo_root: Option<&Path>,
    seed_archives_dir: Option<&Path>,
) -> bool {
    let (fingerprint, version) =
        current_ui_bundle_fingerprint(paths, im_origin, dev_repo_root, seed_archives_dir);
    let marker_path = paths.webview_ui_cache_marker_path();
    if let Ok(raw) = fs::read_to_string(&marker_path) {
        if let Ok(existing) = serde_json::from_str::<WebviewUiCacheMarker>(&raw) {
            if existing.bundle_fingerprint == fingerprint {
                return false;
            }
        }
    }
    let purged = purge_webview_http_caches(&paths.webview_data_dir);
    let now_epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let _ = write_private_json(
        &marker_path,
        &WebviewUiCacheMarker {
            bundle_fingerprint: fingerprint,
            version: version.clone(),
            updated_at_epoch: now_epoch,
        },
    );
    append_host_log(
        Some(paths),
        "INFO",
        &format!(
            "Reconciled WebView HTTP/code cache for UI bundle '{}' (purged {} cache directories)",
            version, purged
        ),
    );
    true
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
) -> Result<(), String> {
    let connections_dir = paths.nano_install_root.join("connections");
    let entries = match fs::read_dir(&connections_dir) {
        Ok(entries) => entries,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(()),
        Err(e) => return Err(e.to_string()),
    };
    let now_epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let root_str = final_version_root.to_string_lossy().to_string();
    let ui_str = final_version_root.join("ui").to_string_lossy().to_string();
    for entry in entries {
        let connection = entry.map_err(|e| e.to_string())?.path();
        if !connection.is_dir() {
            continue;
        }
        let active_path = connection.join(".desktop-active.json");
        let raw = match fs::read_to_string(&active_path) {
            Ok(raw) => raw,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
            Err(e) => return Err(e.to_string()),
        };
        let mut val: Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        if val["managed_by"] != "crewden-desktop" {
            continue;
        }
        let obj = val.as_object_mut().ok_or("Invalid desktop active pointer")?;
        obj.insert("sha256".to_string(), json!(target_sha));
        obj.insert("version".to_string(), json!(version));
        obj.insert("version_root".to_string(), json!(root_str));
        obj.insert("ui_root".to_string(), json!(ui_str));
        obj.insert("updated_at_epoch".to_string(), json!(now_epoch));
        write_private_json(&active_path, &val)?;
    }
    Ok(())
}

/// Reconcile `seed-current.json` and `.desktop-active.json` immediately when the bundled seed `.ready` already exists
/// and differs from `seed-current.json` (e.g. re-installing or switching installers while keeping OTA updates untouched).
pub fn reconcile_ready_seed_bundle(paths: &DesktopPaths, seed_archives_dir: Option<&Path>) -> Result<(), String> {
    let Some(seed_dir) = default_seed_archives_dir(seed_archives_dir) else {
        return Ok(());
    };
    let manifest_path = seed_dir.join(seed_manifest_filename());
    let Ok(manifest_raw) = fs::read_to_string(&manifest_path) else {
        return Ok(());
    };
    let Ok(manifest) = serde_json::from_str::<Value>(&manifest_raw) else {
        return Ok(());
    };
    let Some(target_sha) = manifest["sha256"].as_str() else {
        return Ok(());
    };
    let version = manifest["version"].as_str().unwrap_or("0.1.0");
    let final_version_root = paths.desktop_home.join("versions").join(target_sha);
    if !final_version_root.join(".ready").is_file() {
        return Ok(());
    }
    let prev = read_seed_marker(paths);
    if prev.as_ref().map(|m| m.sha256.as_str()) == Some(target_sha) {
        return Ok(());
    }
    let runtime_sha = manifest["package"]
        .as_str()
        .and_then(|pkg| fs::read_to_string(seed_dir.join(pkg)).ok())
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .and_then(|d| d["runtime"]["sha256"].as_str().map(str::to_string))
        .or_else(|| prev.map(|m| m.runtime_sha256))
        .unwrap_or_default();
    advance_managed_active_pointers_to_seed(paths, version, target_sha, &final_version_root)?;
    write_private_json(
        &paths.seed_marker_path(),
        &SeedMarker {
            version: version.to_string(),
            sha256: target_sha.to_string(),
            runtime_sha256: runtime_sha,
            version_root: final_version_root.to_string_lossy().to_string(),
        },
    )
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

fn file_sha256(path: &Path) -> io::Result<String> {
    let mut hasher = Sha256::new();
    io::copy(&mut fs::File::open(path)?, &mut hasher)?;
    Ok(format!("{:x}", hasher.finalize()))
}

fn cache_seed_asset(source: &Path, cached: &Path, expected_sha: &str) -> Result<(), String> {
    if file_sha256(cached).is_ok_and(|sha| sha == expected_sha) {
        return Ok(());
    }

    // The single seed worker reuses this sibling after interruption. OTA readers
    // only see the final name once all bytes have passed verification.
    let stage = cached.with_added_extension("seed-part");
    let replace = || -> Result<(), String> {
        let mut input = fs::File::open(source)
            .map_err(|e| format!("Open bundled seed {}: {e}", source.display()))?;
        let mut output = fs::File::create(&stage)
            .map_err(|e| format!("Create seed cache staging file {}: {e}", stage.display()))?;
        io::copy(&mut input, &mut output)
            .map_err(|e| format!("Copy {} to {}: {e}", source.display(), stage.display()))?;
        drop(output);
        let digest = file_sha256(&stage)
            .map_err(|e| format!("Verify seed cache {}: {e}", stage.display()))?;
        if digest != expected_sha {
            return Err(format!("Bundled seed {}: SHA-256 mismatch", source.display()));
        }
        fs::rename(&stage, cached)
            .map_err(|e| format!("Rename {} to {}: {e}", stage.display(), cached.display()))
    };
    let result = replace();
    if result.is_err() {
        let _ = fs::remove_file(&stage);
    }
    result
}

fn create_seed_directory(path: &Path) -> Result<(), String> {
    fs::create_dir_all(path).map_err(|e| format!("Create seed directory {}: {e}", path.display()))
}

fn mark_seed_ready(root: &Path, contents: &[u8]) -> Result<(), String> {
    let path = root.join(".ready");
    fs::write(&path, contents).map_err(|e| format!("Write seed marker {}: {e}", path.display()))
}

fn publish_seed_directory(stage: &Path, target: &Path) -> Result<(), String> {
    let mut result = fs::rename(stage, target);
    if cfg!(windows) {
        // NTFS also reports access denied while a child of the staged directory is open.
        for delay_ms in [25, 50, 100, 200, 400, 800] {
            if !matches!(&result, Err(e) if e.raw_os_error() == Some(5)) {
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(delay_ms));
            result = fs::rename(stage, target);
        }
    }
    result.map_err(|e| {
        format!("Rename seed directory {} to {}: {e}", stage.display(), target.display())
    })
}

#[cfg(windows)]
fn publish_seed_runtime(stage: &Path, target: &Path) -> Result<(), String> {
    // Move only a junction into the content-addressed slot. Open files in the
    // backing directory (including the Node used for layout) can stay open.
    let link = stage.with_added_extension("junction");
    let node = stage.join(standalone_node_rel_path());
    let mut cmd = Command::new(&node);
    configure_hidden_command(&mut cmd);
    let output = cmd
        .args(["-e", "require('node:fs').symlinkSync(process.argv[1], process.argv[2], 'junction')", "--"])
        .arg(stage)
        .arg(&link)
        .output()
        .map_err(|e| format!("Run {} to create runtime junction {}: {e}", node.display(), link.display()))?;
    if !output.status.success() {
        return Err(format!("Create runtime junction {} to {}: {}",
            link.display(), stage.display(), String::from_utf8_lossy(&output.stderr)));
    }
    let result = publish_seed_directory(&link, target);
    if result.is_err() {
        let _ = fs::remove_dir(&link);
    }
    result
}

/// Unpack first-install seed archives into `<desktop_home>/{cache,runtimes,versions}` so
/// managed Node 24.22.1 works with zero global PATH tools and future updates reuse `runtime`.
pub fn ensure_seed_bundle_installed(
    paths: &DesktopPaths,
    seed_archives_dir: Option<&Path>,
) -> Result<Option<PathBuf>, String> {
    ensure_seed_bundle_installed_with_available_bytes(paths, seed_archives_dir, None)
}

pub(crate) fn ensure_seed_bundle_installed_with_available_bytes(
    paths: &DesktopPaths,
    seed_archives_dir: Option<&Path>,
    override_available_bytes: Option<u64>,
) -> Result<Option<PathBuf>, String> {
    ensure_seed_bundle_installed_inner(paths, seed_archives_dir, override_available_bytes)
        .map_err(annotate_seed_error)
}

fn ensure_seed_bundle_installed_inner(
    paths: &DesktopPaths,
    seed_archives_dir: Option<&Path>,
    override_available_bytes: Option<u64>,
) -> Result<Option<PathBuf>, String> {
    let Some(seed_dir) = default_seed_archives_dir(seed_archives_dir) else {
        return Ok(None);
    };
    let manifest_name = seed_manifest_filename();
    let manifest_path = seed_dir.join(manifest_name);
    if !manifest_path.is_file() {
        return Ok(None);
    }
    let manifest_raw = fs::read_to_string(&manifest_path)
        .map_err(|e| format!("Read seed {}: {e}", manifest_path.display()))?;
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
        reconcile_ready_seed_bundle(paths, Some(&seed_dir))?;
        return Ok(Some(final_version_root));
    }

    // Preflight available disk space against archive + extraction peak before copying or extracting bytes.
    if let Ok(src_desc_raw) = fs::read_to_string(seed_dir.join(pkg_name)) {
        if let Ok(src_desc) = serde_json::from_str::<Value>(&src_desc_raw) {
            let rt_name = src_desc["runtime"]["name"].as_str().unwrap_or("");
            let rt_sha = src_desc["runtime"]["sha256"].as_str().unwrap_or("");
            let app_name = src_desc["app"]["name"].as_str().unwrap_or("");
            let app_sha = src_desc["app"]["sha256"].as_str().unwrap_or("");
            let rt_bytes = src_desc["runtime"]["size"]
                .as_u64()
                .unwrap_or(0)
                .max(fs::metadata(seed_dir.join(rt_name)).map(|m| m.len()).unwrap_or(0));
            let app_bytes = src_desc["app"]["size"]
                .as_u64()
                .unwrap_or(0)
                .max(fs::metadata(seed_dir.join(app_name)).map(|m| m.len()).unwrap_or(0));
            let runtime_ready = !rt_sha.is_empty()
                && paths
                    .desktop_home
                    .join("runtimes")
                    .join(rt_sha)
                    .join(".ready")
                    .is_file();
            let cache_dir_probe = paths.desktop_home.join("cache");
            let rt_cached = !rt_sha.is_empty()
                && fs::metadata(cache_dir_probe.join(format!("{rt_sha}-{rt_name}")))
                    .map(|m| rt_bytes > 0 && m.len() == rt_bytes)
                    .unwrap_or(false);
            let app_cached = !app_sha.is_empty()
                && fs::metadata(cache_dir_probe.join(format!("{app_sha}-{app_name}")))
                    .map(|m| app_bytes > 0 && m.len() == app_bytes)
                    .unwrap_or(false);
            let required = estimate_seed_required_bytes(
                rt_bytes,
                app_bytes,
                runtime_ready,
                rt_cached,
                app_cached,
            );
            if let Some(avail) =
                override_available_bytes.or_else(|| query_available_disk_bytes(&paths.desktop_home))
            {
                if avail < required {
                    return Err(format_insufficient_disk_space_error(required, avail));
                }
            }
        }
    }

    let cache_dir = paths.desktop_home.join("cache");
    create_seed_directory(&cache_dir)?;
    let cached_desc = cache_dir.join(format!("descriptor-{}.json", target_sha));
    cache_seed_asset(&seed_dir.join(pkg_name), &cached_desc, target_sha)?;
    let descriptor_raw = fs::read_to_string(&cached_desc)
        .map_err(|e| format!("Read seed {}: {e}", cached_desc.display()))?;
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

    let runtimes_dir = paths.desktop_home.join("runtimes");
    let versions_dir = paths.desktop_home.join("versions");
    create_seed_directory(&runtimes_dir)?;
    create_seed_directory(&versions_dir)?;

    let cached_rt = cache_dir.join(format!("{}-{}", runtime_sha, runtime_name));
    let cached_app = cache_dir.join(format!("{}-{}", app_sha, app_name));
    cache_seed_asset(&seed_dir.join(runtime_name), &cached_rt, runtime_sha)?;
    cache_seed_asset(&seed_dir.join(app_name), &cached_app, app_sha)?;

    let final_runtime_root = runtimes_dir.join(runtime_sha);
    if !final_runtime_root.join(".ready").is_file() {
        // A published Windows junction owns this backing directory for the life of
        // the runtime. A later install must never recycle it, even after PID reuse.
        let backing = tempfile::Builder::new()
            .prefix("seed-content-")
            .tempdir_in(&runtimes_dir)
            .map_err(|e| format!("Create runtime directory in {}: {e}", runtimes_dir.display()))?;
        let stage = backing.path();
        extract_tar_gz(&cached_rt, stage)?;
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
                .arg(stage)
                .arg(&final_runtime_root)
                .output()
                .map_err(|e| format!("Run {} with {}: {e}", layout.display(), node_bin.display()))?;
            if !out.status.success() {
                return Err(format!(
                    "runtime layout.mjs failed: {}",
                    String::from_utf8_lossy(&out.stderr)
                ));
            }
        }
        mark_seed_ready(stage, b"")?;
        if !final_runtime_root.join(".ready").is_file() {
            #[cfg(windows)]
            {
                publish_seed_runtime(stage, &final_runtime_root)?;
                let _ = backing.keep();
            }
            #[cfg(not(windows))]
            publish_seed_directory(stage, &final_runtime_root)?;
        }
    }

    let node_bin = final_runtime_root.join(standalone_node_rel_path());
    let layout = final_runtime_root.join("layout.mjs");
    let app_extract = versions_dir.join(format!(".seed-app-extract-{}", std::process::id()));
    let version_stage = versions_dir.join(format!(".seed-ver-stage-{}", std::process::id()));
    let _ = fs::remove_dir_all(&app_extract);
    let _ = fs::remove_dir_all(&version_stage);
    create_seed_directory(&app_extract)?;
    create_seed_directory(&version_stage)?;

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
        .map_err(|e| format!("Run {} with {}: {e}", layout.display(), node_bin.display()))?;
    let _ = fs::remove_dir_all(&app_extract);
    if !out.status.success() {
        let _ = fs::remove_dir_all(&version_stage);
        return Err(format!(
            "version layout.mjs failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }

    write_private_json(&version_stage.join(".release-manifest.json"), &manifest)?;
    mark_seed_ready(&version_stage, format!("{target_sha}\n").as_bytes())?;
    if !final_version_root.exists() {
        publish_seed_directory(&version_stage, &final_version_root)?;
    } else {
        let _ = fs::remove_dir_all(&version_stage);
    }

    let seed_changed = read_seed_marker(paths)
        .map(|m| m.sha256 != target_sha)
        .unwrap_or(true);
    if seed_changed {
        advance_managed_active_pointers_to_seed(paths, &version, target_sha, &final_version_root)?;
    }
    write_private_json(
        &paths.seed_marker_path(),
        &SeedMarker {
            version: version.clone(),
            sha256: target_sha.to_string(),
            runtime_sha256: runtime_sha.to_string(),
            version_root: final_version_root.to_string_lossy().to_string(),
        },
    )?;
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
        .map_err(|e| format!("Extract {} to {}: {e}", archive.display(), dest.display()))?;
    if !out.status.success() {
        return Err(format!(
            "Extract {} to {}: tar extraction failed: {}",
            archive.display(), dest.display(),
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
    cmd.arg(&bundle.cli_js).arg("local-admin");
    if subcommand == "supervise" {
        // Earlier active bundles accept inspect and ignore the extra positional.
        cmd.args(["inspect", "supervision"]);
    } else {
        cmd.arg(subcommand);
    }
    cmd.arg("--origin").arg(im_origin);
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
                let mut body = parsed["data"].clone();
                if matches!(subcommand, "inspect" | "supervise") && matches!(body["ownership"].as_str(), Some("managed_online" | "managed_stopped")) {
                    let task = body.as_object_mut().and_then(|obj| obj.remove("scheduled_at_login"));
                    let enabled = task.as_ref().and_then(Value::as_bool) == Some(true)
                        || (body["autostart"] == true && crate::autostart::get_desktop_login_autostart(paths));
                    body["autostart"] = json!(enabled);
                }
                return Ok(LocalAdminResult { status, ok: true, body });
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
        reconcile_ready_seed_bundle(&paths, Some(&seed_official)).unwrap();

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
        reconcile_ready_seed_bundle(&paths, Some(&seed_official)).unwrap();
        let resolved_ota = resolve_active_bundle(&paths, origin, None).unwrap();
        assert_eq!(resolved_ota.version, "1.0.5");
        assert_eq!(resolved_ota.sha256.as_deref(), Some("sha_ota"));

        // Now simulate over-installing new installer v2.0.0 (`sha_v2`) -> `.desktop-active.json` advances to `sha_v2` & keeps `user_stopped: true`!
        fs::write(
            seed_official.join(manifest_name),
            json!({ "package": "pkg.json", "version": "2.0.0", "sha256": "sha_v2" }).to_string(),
        )
        .unwrap();
        reconcile_ready_seed_bundle(&paths, Some(&seed_official)).unwrap();
        let resolved_v2 = resolve_active_bundle(&paths, origin, None).unwrap();
        assert_eq!(resolved_v2.version, "2.0.0");
        assert_eq!(resolved_v2.sha256.as_deref(), Some("sha_v2"));
        assert_eq!(resolved_v2.version_root, root_v2);
        let updated_ptr: Value =
            serde_json::from_str(&fs::read_to_string(&active_path).unwrap()).unwrap();
        assert_eq!(updated_ptr["user_stopped"], json!(true));
    }
}

#[cfg(test)]
mod seed_tests;
