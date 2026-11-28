use crate::config::{
    append_host_log, classify_im_origin, current_desktop_platform_id, random_hex_token,
    write_private_json, DesktopDefaultsFile, DesktopPaths, DesktopUiActiveFile,
    DesktopUiOriginPointer, ImOriginSecurity, UpdaterPrefsFile,
};
use crate::host_server::{refresh_stored_session_serialized, HostSharedState};
use crate::local_node::{
    configure_hidden_command, extract_tar_gz, file_sha256, launch_verified_installer,
    publish_seed_directory, resolve_active_bundle, resolve_active_ui_bundle,
    standalone_node_rel_path, verify_ready_ui_version_root,
};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::watch;
use url::Url;

pub const CURRENT_DESKTOP_SHELL_PROTOCOL: u64 = 2;
pub const CURRENT_UPDATER_PROTOCOL: u64 = 1;
pub const CURRENT_DATA_EPOCH: u64 = 1;
const GITHUB_RELEASE_PREFIX: &str = "https://github.com/Mrchen116/nano-multiagent/releases/download/";
const MAX_HTTPS_REDIRECTS: usize = 10;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VerifiedPlatformInstaller {
    pub download_url: String,
    pub sha256: String,
    pub size: u64,
    pub filename: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VerifiedDesktopManifest {
    pub version: String,
    pub source_commit: String,
    pub sha256: String,
    pub download_url: String,
    pub release_base_url: Option<String>,
    pub package: String,
    pub platform: String,
    pub size: u64,
    pub updater_protocol: u64,
    pub data_epoch: u64,
    pub shell_protocol: u64,
    pub macos_distribution: Option<String>,
    pub release_notes: Option<String>,
    pub installer: VerifiedPlatformInstaller,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum UpdaterMode {
    HotBundle,
    Installer,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UpdaterProgress {
    pub downloaded_bytes: u64,
    pub total_bytes: Option<u64>,
    pub stage: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DesktopUpdaterTargetInfo {
    pub version: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub release_notes: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub macos_distribution: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DesktopUpdaterSnapshot {
    pub current_version: String,
    pub platform: String,
    pub auto_update: bool,
    pub phase: String,
    pub mode: Option<UpdaterMode>,
    pub target: Option<DesktopUpdaterTargetInfo>,
    pub progress: Option<UpdaterProgress>,
    pub active_tasks: u64,
    pub just_updated_version: Option<String>,
    pub capsule_dismissed: bool,
    pub active_ui_sha256: Option<String>,
    pub reload_generation: u64,
    pub error_code: Option<String>,
    pub last_checked_at: Option<String>,
}

#[derive(Debug, Clone)]
pub struct StartupPromotionBackup {
    pub im_origin: String,
    pub promoted_sha256: String,
    pub prev_ui_ptr: Option<DesktopUiOriginPointer>,
    pub prev_node_ptr: Option<Value>,
}

#[derive(Default)]
struct OriginUpdaterRuntime {
    phase: String,
    mode: Option<UpdaterMode>,
    target: Option<VerifiedDesktopManifest>,
    progress: Option<UpdaterProgress>,
    active_tasks: u64,
    error_code: Option<String>,
    last_checked_at: Option<String>,
    dismissed_version: Option<String>,
    installer_path: Option<PathBuf>,
    node_operation_id: Option<String>,
    node_id: Option<String>,
    cancel_tx: Option<watch::Sender<bool>>,
}

pub struct DesktopUpdaterController {
    by_origin: Mutex<HashMap<String, OriginUpdaterRuntime>>,
    task_lock: tokio::sync::Mutex<()>,
    pub reload_generation: AtomicU64,
    startup_backups: Mutex<HashMap<String, StartupPromotionBackup>>,
}

impl Default for DesktopUpdaterController {
    fn default() -> Self {
        Self {
            by_origin: Mutex::new(HashMap::new()),
            task_lock: tokio::sync::Mutex::new(()),
            reload_generation: AtomicU64::new(1),
            startup_backups: Mutex::new(HashMap::new()),
        }
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn now_iso_string() -> String {
    format!("{}", now_secs())
}

pub fn read_updater_prefs(paths: &DesktopPaths) -> UpdaterPrefsFile {
    fs::read_to_string(paths.updater_prefs_path())
        .ok()
        .and_then(|raw| serde_json::from_str::<UpdaterPrefsFile>(&raw).ok())
        .unwrap_or_default()
}

pub fn write_updater_prefs(paths: &DesktopPaths, prefs: &UpdaterPrefsFile) -> Result<(), String> {
    write_private_json(&paths.updater_prefs_path(), prefs)
}

pub fn read_ui_active_file(paths: &DesktopPaths) -> DesktopUiActiveFile {
    fs::read_to_string(paths.desktop_ui_active_path())
        .ok()
        .and_then(|raw| serde_json::from_str::<DesktopUiActiveFile>(&raw).ok())
        .unwrap_or_default()
}

pub fn write_ui_active_file(paths: &DesktopPaths, data: &DesktopUiActiveFile) -> Result<(), String> {
    write_private_json(&paths.desktop_ui_active_path(), data)
}

fn is_hex_len(s: &str, expected: usize) -> bool {
    s.len() == expected && s.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

pub fn parse_strict_semver(v: &str) -> Option<(u64, u64, u64)> {
    let parts: Vec<&str> = v.split('.').collect();
    if parts.len() != 3 {
        return None;
    }
    let parse_seg = |seg: &str| -> Option<u64> {
        if seg.is_empty() || (seg.len() > 1 && seg.starts_with('0')) || !seg.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        seg.parse::<u64>().ok()
    };
    Some((parse_seg(parts[0])?, parse_seg(parts[1])?, parse_seg(parts[2])?))
}

fn normalize_release_base_url(raw: &str, allow_private_http: bool) -> Option<String> {
    let parsed = Url::parse(raw.trim()).ok()?;
    if !parsed.username().is_empty() || parsed.password().is_some() || parsed.query().is_some() || parsed.fragment().is_some() {
        return None;
    }
    let port_suffix = parsed.port().map(|p| format!(":{}", p)).unwrap_or_default();
    let origin_candidate = format!("{}://{}{}", parsed.scheme(), parsed.host_str()?, port_suffix);
    let (norm_origin, security) = classify_im_origin(&origin_candidate).ok()?;
    let allowed = matches!(security, ImOriginSecurity::Https | ImOriginSecurity::LoopbackHttp)
        || (allow_private_http && security == ImOriginSecurity::PrivateHttp);
    if !allowed {
        return None;
    }
    let clean_path = parsed.path().trim_end_matches('/');
    Some(format!("{}{}/", norm_origin, clean_path))
}

#[derive(Debug, Clone, Default)]
pub struct TrustedReleaseConfig {
    pub trusted_bases: Vec<String>,
    pub allow_private_http: bool,
}

pub fn load_trusted_release_config(paths: &DesktopPaths, active_version_root: Option<&Path>) -> TrustedReleaseConfig {
    let mut trusted_bases = Vec::new();
    let mut allow_private_http = false;

    if let Some(root) = active_version_root {
        if let Ok(raw) = fs::read_to_string(root.join(".nano-release.json")) {
            if let Ok(val) = serde_json::from_str::<Value>(&raw) {
                if val["allow_private_http_release_base"].as_bool() == Some(true) {
                    allow_private_http = true;
                }
                if let Some(u) = val["trusted_release_base_url"].as_str().or_else(|| val["release_base_url"].as_str()) {
                    trusted_bases.push(u.to_string());
                }
            }
        }
    }

    if let Ok(raw) = fs::read_to_string(paths.desktop_defaults_path()) {
        if let Ok(defaults) = serde_json::from_str::<DesktopDefaultsFile>(&raw) {
            if defaults.allow_private_http_release_base == Some(true) {
                allow_private_http = true;
            }
            if let Some(u) = defaults.trusted_release_base_url {
                trusted_bases.push(u);
            }
        }
    }

    if let Ok(loopback) = std::env::var("NANO_LOOPBACK_RELEASE_ORIGIN") {
        let trimmed = loopback.trim();
        if !trimmed.is_empty() {
            trusted_bases.push(trimmed.to_string());
        }
    }

    TrustedReleaseConfig {
        trusted_bases,
        allow_private_http,
    }
}

/// Parse and verify a Desktop release manifest identically to `@nano/product-contracts` `parseReleaseManifest`.
pub fn parse_desktop_release_manifest(
    input: &Value,
    expected_desktop_platform: &str,
    trusted: &TrustedReleaseConfig,
) -> Option<VerifiedDesktopManifest> {
    let obj = input.as_object()?;
    let version = obj.get("version")?.as_str()?;
    let sha256 = obj.get("sha256")?.as_str()?;
    if !is_hex_len(sha256, 64) {
        return None;
    }
    let source_commit = obj.get("source_commit")?.as_str()?;
    if !is_hex_len(source_commit, 40) {
        return None;
    }
    let tag = if is_hex_len(version, 40) {
        if source_commit != version {
            return None;
        }
        format!("node-{}", version)
    } else if parse_strict_semver(version).is_some() {
        format!("v{}", version)
    } else {
        return None;
    };

    if obj.get("node_major")?.as_u64() != Some(24) || obj.get("pnpm_version")?.as_str() != Some("11.7.0") {
        return None;
    }
    let updater_protocol = obj.get("updater_protocol")?.as_u64().filter(|&n| n >= 1)?;
    let data_epoch = obj.get("data_epoch")?.as_u64().filter(|&n| n >= 1)?;
    let shell_protocol = obj.get("shell_protocol")?.as_u64().filter(|&n| n >= 1)?;
    let size = obj.get("size")?.as_u64().filter(|&n| n >= 1)?;

    let release_notes = match obj.get("release_notes") {
        None | Some(Value::Null) => None,
        Some(v) => {
            let s = v.as_str()?;
            if s.encode_utf16().count() > 2000 {
                return None;
            }
            Some(s.to_string())
        }
    };

    let (expected_pkg, expected_installer) = match expected_desktop_platform {
        "desktop-darwin-arm64" => ("desktop-darwin-arm64.json", "Crewden-Desktop-arm64.dmg"),
        "desktop-win32-x64" => ("desktop-win32-x64.json", "Crewden-Desktop-Setup-x64.exe"),
        _ => return None,
    };

    let package = obj.get("package")?.as_str()?;
    let platform = obj.get("platform")?.as_str()?;
    if package != expected_pkg || platform != expected_desktop_platform {
        return None;
    }

    let macos_distribution = match obj.get("macos_distribution") {
        None | Some(Value::Null) => None,
        Some(v) => {
            if expected_desktop_platform != "desktop-darwin-arm64" {
                return None;
            }
            let s = v.as_str()?;
            if !matches!(s, "unsigned-test" | "unnotarized" | "developer-id-notarized") {
                return None;
            }
            Some(s.to_string())
        }
    };

    let mut base = format!("{}{}/", GITHUB_RELEASE_PREFIX, tag);
    let mut normalized_release_base_url = None;
    if let Some(raw_base_val) = obj.get("release_base_url") {
        if !raw_base_val.is_null() {
            let raw_base = raw_base_val.as_str()?;
            let candidate = normalize_release_base_url(raw_base, trusted.allow_private_http)?;
            let matched = trusted
                .trusted_bases
                .iter()
                .filter_map(|item| normalize_release_base_url(item, trusted.allow_private_http))
                .any(|t| candidate == t || candidate == format!("{}{}/", t, tag));
            if !matched {
                return None;
            }
            base = candidate.clone();
            normalized_release_base_url = Some(candidate);
        }
    }

    let download_url = obj.get("download_url")?.as_str()?;
    if download_url != format!("{}{}", base, expected_pkg) {
        return None;
    }

    let inst_obj = obj.get("installer")?.as_object()?;
    let inst_url = inst_obj.get("download_url")?.as_str()?;
    let inst_sha = inst_obj.get("sha256")?.as_str()?;
    let inst_size = inst_obj.get("size")?.as_u64().filter(|&n| n >= 1)?;
    if inst_url != format!("{}{}", base, expected_installer) || !is_hex_len(inst_sha, 64) {
        return None;
    }

    Some(VerifiedDesktopManifest {
        version: version.to_string(),
        source_commit: source_commit.to_string(),
        sha256: sha256.to_string(),
        download_url: download_url.to_string(),
        release_base_url: normalized_release_base_url,
        package: package.to_string(),
        platform: platform.to_string(),
        size,
        updater_protocol,
        data_epoch,
        shell_protocol,
        macos_distribution,
        release_notes,
        installer: VerifiedPlatformInstaller {
            download_url: inst_url.to_string(),
            sha256: inst_sha.to_string(),
            size: inst_size,
            filename: expected_installer.to_string(),
        },
    })
}

/// Classify whether a verified target manifest is already current, eligible for `hot_bundle`, or requires `installer`.
pub fn classify_target_release(
    current_version: &str,
    current_sha256: Option<&str>,
    target: &VerifiedDesktopManifest,
) -> Option<UpdaterMode> {
    if target.shell_protocol < CURRENT_DESKTOP_SHELL_PROTOCOL
        || target.updater_protocol < CURRENT_UPDATER_PROTOCOL
        || target.data_epoch < CURRENT_DATA_EPOCH
    {
        return None;
    }
    if let (Some(cur_sem), Some(tgt_sem)) = (parse_strict_semver(current_version), parse_strict_semver(&target.version)) {
        if tgt_sem < cur_sem {
            return None;
        }
    }
    if current_sha256 == Some(target.sha256.as_str())
        && current_version == target.version
        && target.shell_protocol == CURRENT_DESKTOP_SHELL_PROTOCOL
        && target.updater_protocol == CURRENT_UPDATER_PROTOCOL
        && target.data_epoch == CURRENT_DATA_EPOCH
    {
        return None;
    }
    if target.shell_protocol == CURRENT_DESKTOP_SHELL_PROTOCOL
        && target.updater_protocol == CURRENT_UPDATER_PROTOCOL
        && target.data_epoch == CURRENT_DATA_EPOCH
    {
        Some(UpdaterMode::HotBundle)
    } else {
        Some(UpdaterMode::Installer)
    }
}

fn resolve_effective_download_url(url: &str) -> String {
    if let Ok(override_origin) = std::env::var("NANO_LOOPBACK_RELEASE_ORIGIN") {
        let trimmed = override_origin.trim().trim_end_matches('/');
        if !trimmed.is_empty() && url.starts_with(GITHUB_RELEASE_PREFIX) {
            if let Ok(parsed) = Url::parse(trimmed) {
                if parsed.scheme() == "http"
                    && matches!(parsed.host_str(), Some("127.0.0.1") | Some("localhost"))
                {
                    return format!("{}/{}", trimmed, &url[GITHUB_RELEASE_PREFIX.len()..]);
                }
            }
        }
    }
    url.to_string()
}

/// Pure validation helper for HTTPS CDN redirect hops (e.g. GitHub Releases -> `objects.githubusercontent.com`).
pub fn validate_https_redirect_hop(next_url: &Url, hop_count: usize) -> Result<(), &'static str> {
    if hop_count >= MAX_HTTPS_REDIRECTS {
        return Err("Too many redirects");
    }
    if next_url.scheme() != "https" {
        return Err("Refusing protocol downgrade redirect from https:// to non-https");
    }
    if !next_url.username().is_empty() || next_url.password().is_some() {
        return Err("Refusing redirect URL with embedded credentials");
    }
    Ok(())
}

pub fn build_download_http_client(effective_url: &str) -> Result<reqwest::Client, String> {
    let parsed = Url::parse(effective_url).map_err(|_| "Invalid download URL".to_string())?;
    let policy = if parsed.scheme() == "https" {
        reqwest::redirect::Policy::custom(|attempt| {
            match validate_https_redirect_hop(attempt.url(), attempt.previous().len()) {
                Ok(()) => attempt.follow(),
                Err(reason) => attempt.error(reason),
            }
        })
    } else {
        // Cleartext trusted LAN / loopback sources strictly forbid redirects.
        reqwest::redirect::Policy::none()
    };
    reqwest::Client::builder()
        .redirect(policy)
        .connect_timeout(Duration::from_secs(20))
        .timeout(Duration::from_secs(600))
        .build()
        .map_err(|e| e.to_string())
}

fn notify_ui_updater_changed(state: &HostSharedState, im_origin: &str) {
    let prefs = read_updater_prefs(&state.paths);
    let (phase, target_ver) = {
        let map = state.updater.by_origin.lock().unwrap();
        let entry = map.get(im_origin);
        (
            entry.map(|e| e.phase.clone()).filter(|p| !p.is_empty()).unwrap_or_else(|| "idle".to_string()),
            entry.and_then(|e| e.target.as_ref().map(|t| t.version.clone())),
        )
    };
    state
        .ui_bridge
        .updater_state_changed(&phase, target_ver.as_deref(), prefs.auto_update);
}

/// Cancel any in-flight check/download task for `im_origin` (used on cancel, auto_update=false, or server switch).
pub fn cancel_origin_tasks(state: &HostSharedState, im_origin: &str) {
    let tx = {
        let mut map = state.updater.by_origin.lock().unwrap();
        map.get_mut(im_origin).and_then(|rt| rt.cancel_tx.take())
    };
    if let Some(tx) = tx {
        let _ = tx.send(true);
    }
}

pub fn on_server_switched(state: &Arc<HostSharedState>, previous_origin: &str, next_origin: &str) {
    if previous_origin != next_origin {
        cancel_origin_tasks(state, previous_origin);
        state.updater.by_origin.lock().unwrap().remove(previous_origin);
    }
    let state_clone = state.clone();
    tokio::spawn(async move {
        let _ = check_for_updates(state_clone, false).await;
    });
}

pub fn build_updater_snapshot(state: &HostSharedState) -> DesktopUpdaterSnapshot {
    let cfg = state.host_config.read().unwrap().clone();
    let prefs = read_updater_prefs(&state.paths);
    let ui_active = read_ui_active_file(&state.paths);
    let bundle = resolve_active_ui_bundle(&state.paths, &cfg.im_origin, state.dev_repo_root.as_deref()).ok();
    let current_version = bundle
        .as_ref()
        .map(|b| b.version.clone())
        .unwrap_or_else(|| "0.1.0".to_string());
    let active_ui_sha256 = bundle.as_ref().and_then(|b| b.sha256.clone());
    let is_source = current_version == "source" && state.seed_archives_dir.is_none();

    let map = state.updater.by_origin.lock().unwrap();
    let rt = map.get(&cfg.im_origin);

    let mut phase = rt
        .map(|r| r.phase.as_str())
        .filter(|p| !p.is_empty())
        .unwrap_or(if is_source { "source_mode" } else { "idle" })
        .to_string();
    let mut mode = rt.and_then(|r| r.mode);
    let mut target_info = rt.and_then(|r| {
        r.target.as_ref().map(|t| DesktopUpdaterTargetInfo {
            version: t.version.clone(),
            release_notes: t.release_notes.clone(),
            size_bytes: Some(if r.mode == Some(UpdaterMode::Installer) {
                t.installer.size
            } else {
                t.size
            }),
            macos_distribution: t.macos_distribution.clone(),
        })
    });

    // If our active bundle has already caught up to the target sha256, clear stale ready/available state.
    if let (Some(cur_sha), Some(tgt_sha)) = (
        active_ui_sha256.as_deref(),
        rt.and_then(|r| r.target.as_ref().map(|t| t.sha256.as_str())),
    ) {
        if cur_sha == tgt_sha && matches!(phase.as_str(), "available" | "preparing" | "ready_to_switch" | "switching") {
            phase = "up_to_date".to_string();
            mode = None;
            target_info = None;
        }
    }

    if ui_active.previous_ui.contains_key(&cfg.im_origin) { phase = "switching".into(); }

    let capsule_dismissed = match (rt.and_then(|r| r.dismissed_version.as_deref()), target_info.as_ref()) {
        (Some(d), Some(t)) => d == t.version,
        _ => false,
    };

    DesktopUpdaterSnapshot {
        current_version,
        platform: current_desktop_platform_id().to_string(),
        auto_update: prefs.auto_update,
        phase,
        mode,
        target: target_info,
        progress: rt.and_then(|r| r.progress.clone()),
        active_tasks: rt.map(|r| r.active_tasks).unwrap_or(0),
        just_updated_version: ui_active.just_updated.get(&cfg.im_origin).cloned(),
        capsule_dismissed,
        active_ui_sha256,
        reload_generation: state.updater.reload_generation.load(Ordering::SeqCst),
        error_code: rt.and_then(|r| r.error_code.clone()),
        last_checked_at: rt.and_then(|r| r.last_checked_at.clone()),
    }
}

async fn download_verified_file(
    raw_url: &str,
    dest_path: &Path,
    expected_sha256: &str,
    expected_size: Option<u64>,
    mut cancel_rx: watch::Receiver<bool>,
    state: &HostSharedState,
    expected_origin: &str,
    expected_epoch: u64,
    on_progress: impl Fn(u64, Option<u64>),
) -> Result<bool, (String, &'static str)> {
    if dest_path.is_file() {
        if let Ok(existing_sha) = file_sha256(dest_path) {
            if existing_sha == expected_sha256 {
                let len = fs::metadata(dest_path).map(|m| m.len()).ok();
                if expected_size.map(|exp| len == Some(exp)).unwrap_or(true) {
                    return Ok(true);
                }
            }
        }
    }
    if let Some(parent) = dest_path.parent() {
        fs::create_dir_all(parent).map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?;
    }
    let effective_url = resolve_effective_download_url(raw_url);
    let client = build_download_http_client(&effective_url).map_err(|e| (e, "network_unreachable"))?;
    let res = client
        .get(&effective_url)
        .send()
        .await
        .map_err(|e| (format!("Download request failed: {e}"), "network_unreachable"))?;
    if !res.status().is_success() {
        return Err((format!("Download HTTP {}", res.status()), "network_unreachable"));
    }
    let total = expected_size.or_else(|| res.content_length());
    let part_path = dest_path.with_extension(format!("part-{}-{}", std::process::id(), random_hex_token(4)));

    let mut file = fs::File::create(&part_path).map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?;
    let mut hasher = Sha256::new();
    let mut downloaded: u64 = 0;
    let mut stream = res.bytes_stream();

    let stream_res: Result<(), (String, &'static str)> = async {
        loop {
            tokio::select! {
                _ = cancel_rx.changed() => {
                    if *cancel_rx.borrow() {
                        return Err(("Cancelled".to_string(), "cancelled"));
                    }
                }
                chunk_opt = stream.next() => {
                    let Some(chunk_res) = chunk_opt else { break; };
                    let cfg = state.host_config.read().unwrap().clone();
                    if cfg.im_origin != expected_origin || cfg.context_epoch != expected_epoch {
                        return Err(("Server switched".to_string(), "cancelled"));
                    }
                    let chunk = chunk_res.map_err(|e| (e.to_string(), "network_unreachable"))?;
                    downloaded += chunk.len() as u64;
                    if let Some(max_sz) = expected_size {
                        if downloaded > max_sz {
                            return Err(("Downloaded size exceeded manifest size".to_string(), "verification_failed"));
                        }
                    }
                    hasher.update(&chunk);
                    file.write_all(&chunk).map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?;
                    on_progress(downloaded, total);
                }
            }
        }
        file.flush().map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?;
        Ok(())
    }
    .await;

    drop(file);
    if let Err(err) = stream_res {
        let _ = fs::remove_file(&part_path);
        return Err(err);
    }

    if let Some(exp_sz) = expected_size {
        if downloaded != exp_sz {
            let _ = fs::remove_file(&part_path);
            return Err(("Incomplete download length".to_string(), "verification_failed"));
        }
    }
    let digest = format!("{:x}", hasher.finalize());
    if digest != expected_sha256 {
        let _ = fs::remove_file(&part_path);
        return Err(("SHA-256 verification mismatch".to_string(), "verification_failed"));
    }
    fs::rename(&part_path, dest_path).map_err(|e| {
        let _ = fs::remove_file(&part_path);
        (e.to_string(), "disk_or_unpack_failed")
    })?;
    Ok(false)
}

fn unpack_staged_hot_bundle_blocking(
    paths: &DesktopPaths,
    target: &VerifiedDesktopManifest,
    cached_rt: &Path,
    runtime_sha: &str,
    cached_app: &Path,
) -> Result<PathBuf, String> {
    let runtimes_dir = paths.desktop_home.join("runtimes");
    let versions_dir = paths.desktop_home.join("versions");
    fs::create_dir_all(&runtimes_dir).map_err(|e| e.to_string())?;
    fs::create_dir_all(&versions_dir).map_err(|e| e.to_string())?;

    let final_version_root = versions_dir.join(&target.sha256);
    if verify_ready_ui_version_root(&final_version_root) {
        return Ok(final_version_root);
    }

    let final_runtime_root = runtimes_dir.join(runtime_sha);
    if !final_runtime_root.join(".ready").is_file() {
        let backing = tempfile::Builder::new()
            .prefix("ota-rt-")
            .tempdir_in(&runtimes_dir)
            .map_err(|e| e.to_string())?;
        let stage = backing.path();
        extract_tar_gz(cached_rt, stage)?;
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
                .map_err(|e| e.to_string())?;
            if !out.status.success() {
                return Err(format!("runtime layout.mjs failed: {}", String::from_utf8_lossy(&out.stderr)));
            }
        }
        fs::write(stage.join(".ready"), b"").map_err(|e| e.to_string())?;
        if !final_runtime_root.join(".ready").is_file() {
            #[cfg(windows)]
            {
                crate::local_node::publish_seed_runtime(stage, &final_runtime_root)?;
                let _ = backing.keep();
            }
            #[cfg(not(windows))]
            publish_seed_directory(stage, &final_runtime_root)?;
        }
    }

    let node_bin = final_runtime_root.join(standalone_node_rel_path());
    let layout = final_runtime_root.join("layout.mjs");
    let token = random_hex_token(6);
    let app_extract = versions_dir.join(format!(".ota-app-extract-{}", token));
    let version_stage = versions_dir.join(format!(".ota-ver-stage-{}", token));
    fs::create_dir_all(&app_extract).map_err(|e| e.to_string())?;
    fs::create_dir_all(&version_stage).map_err(|e| e.to_string())?;

    let unpack_res = (|| -> Result<(), String> {
        extract_tar_gz(cached_app, &app_extract)?;
        if layout.is_file() {
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
                .map_err(|e| e.to_string())?;
            if !out.status.success() {
                return Err(format!("version layout.mjs failed: {}", String::from_utf8_lossy(&out.stderr)));
            }
        } else {
            let _ = fs::remove_dir_all(&version_stage);
            fs::rename(&app_extract, &version_stage).map_err(|e| e.to_string())?;
        }
        let mut manifest_json = json!({
            "version": target.version,
            "source_commit": target.source_commit,
            "sha256": target.sha256,
            "download_url": target.download_url,
            "node_major": 24,
            "pnpm_version": "11.7.0",
            "package": target.package,
            "platform": target.platform,
            "size": target.size,
            "updater_protocol": target.updater_protocol,
            "data_epoch": target.data_epoch,
            "shell_protocol": target.shell_protocol,
            "installer": {
                "download_url": target.installer.download_url,
                "sha256": target.installer.sha256,
                "size": target.installer.size,
            },
            "release_notes": target.release_notes,
            "macos_distribution": target.macos_distribution,
            "release_base_url": target.release_base_url,
        });
        // Node's release parser distinguishes an absent optional field from JSON null.
        manifest_json.as_object_mut().unwrap().retain(|_, value| !value.is_null());
        write_private_json(&version_stage.join(".release-manifest.json"), &manifest_json)?;
        if !version_stage.join(crate::local_node::node_rel_path()).is_file()
            || !version_stage.join("ui/frontend/index.html").is_file()
        {
            return Err("Staged version bundle is missing ui/frontend/index.html or runtime".to_string());
        }
        if !final_version_root.exists() {
            publish_seed_directory(&version_stage, &final_version_root)?;
        }
        if !final_version_root.join(".ready").is_file() {
            if layout.is_file() && final_version_root.join("workspaces.json").is_file() {
                let mut verify_cmd = Command::new(&node_bin);
                configure_hidden_command(&mut verify_cmd);
                let out = verify_cmd
                    .arg(&layout)
                    .arg("verify")
                    .arg(&final_version_root)
                    .output()
                    .map_err(|e| {
                        let _ = fs::remove_dir_all(&final_version_root);
                        e.to_string()
                    })?;
                if !out.status.success() {
                    let _ = fs::remove_dir_all(&final_version_root);
                    return Err("layout.mjs verify failed".to_string());
                }
            }
            if let Err(err) = fs::write(final_version_root.join(".ready"), format!("{}\n", target.sha256)) {
                let _ = fs::remove_dir_all(&final_version_root);
                return Err(err.to_string());
            }
        }
        if !verify_ready_ui_version_root(&final_version_root) {
            let _ = fs::remove_dir_all(&final_version_root);
            return Err("Verified version bundle failed final readiness check".to_string());
        }
        Ok(())
    })();

    let _ = fs::remove_dir_all(&app_extract);
    let _ = fs::remove_dir_all(&version_stage);
    unpack_res?;
    Ok(final_version_root)
}

async fn stage_hot_bundle(
    state: Arc<HostSharedState>,
    im_origin: String,
    context_epoch: u64,
    target: VerifiedDesktopManifest,
    cancel_rx: watch::Receiver<bool>,
) -> Result<PathBuf, (String, &'static str)> {
    let final_version_root = state.paths.desktop_home.join("versions").join(&target.sha256);
    if verify_ready_ui_version_root(&final_version_root) {
        return Ok(final_version_root);
    }

    let cache_dir = state.paths.desktop_home.join("cache");
    fs::create_dir_all(&cache_dir).map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?;

    let desc_path = cache_dir.join(format!("descriptor-{}.json", target.sha256));
    download_verified_file(
        &target.download_url,
        &desc_path,
        &target.sha256,
        Some(target.size),
        cancel_rx.clone(),
        &state,
        &im_origin,
        context_epoch,
        |_, _| {},
    )
    .await?;

    let desc_raw = fs::read_to_string(&desc_path).map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?;
    let desc: Value = serde_json::from_str(&desc_raw).map_err(|e| (e.to_string(), "verification_failed"))?;
    let base = match target.download_url.rfind('/') {
        Some(idx) => &target.download_url[..=idx],
        None => return Err(("Invalid descriptor download_url".to_string(), "verification_failed")),
    };

    let rt_name = desc["runtime"]["name"].as_str().unwrap_or("");
    let rt_sha = desc["runtime"]["sha256"].as_str().unwrap_or("");
    let rt_url = desc["runtime"]["download_url"].as_str().unwrap_or("");
    let rt_size = desc["runtime"]["size"].as_u64();
    let app_name = desc["app"]["name"].as_str().unwrap_or("");
    let app_sha = desc["app"]["sha256"].as_str().unwrap_or("");
    let app_url = desc["app"]["download_url"].as_str().unwrap_or("");
    let app_size = desc["app"]["size"].as_u64();

    if desc["version"].as_str() != Some(target.version.as_str())
        || desc["source_commit"].as_str() != Some(target.source_commit.as_str())
        || desc["updater_protocol"].as_u64() != Some(CURRENT_UPDATER_PROTOCOL)
        || desc["data_epoch"].as_u64() != Some(CURRENT_DATA_EPOCH)
        || desc["shell_protocol"].as_u64() != Some(CURRENT_DESKTOP_SHELL_PROTOCOL)
        || rt_name.is_empty()
        || rt_name.contains('/')
        || rt_name.contains('\\')
        || !is_hex_len(rt_sha, 64)
        || rt_url != format!("{}{}", base, rt_name)
        || app_name.is_empty()
        || app_name.contains('/')
        || app_name.contains('\\')
        || !is_hex_len(app_sha, 64)
        || app_url != format!("{}{}", base, app_name)
    {
        return Err(("Invalid desktop descriptor metadata".to_string(), "verification_failed"));
    }

    let final_rt_root = state.paths.desktop_home.join("runtimes").join(rt_sha);
    let cached_rt = cache_dir.join(format!("{}-{}", rt_sha, rt_name));
    if !final_rt_root.join(".ready").is_file() {
        let state_p = state.clone();
        let origin_p = im_origin.clone();
        download_verified_file(
            rt_url,
            &cached_rt,
            rt_sha,
            rt_size,
            cancel_rx.clone(),
            &state,
            &im_origin,
            context_epoch,
            move |dl, tot| {
                if let Some(rt) = state_p.updater.by_origin.lock().unwrap().get_mut(&origin_p) {
                    rt.progress = Some(UpdaterProgress {
                        downloaded_bytes: dl,
                        total_bytes: tot,
                        stage: "downloading".to_string(),
                    });
                }
            },
        )
        .await?;
    }

    let cached_app = cache_dir.join(format!("{}-{}", app_sha, app_name));
    {
        let state_p = state.clone();
        let origin_p = im_origin.clone();
        download_verified_file(
            app_url,
            &cached_app,
            app_sha,
            app_size,
            cancel_rx.clone(),
            &state,
            &im_origin,
            context_epoch,
            move |dl, tot| {
                if let Some(rt) = state_p.updater.by_origin.lock().unwrap().get_mut(&origin_p) {
                    rt.progress = Some(UpdaterProgress {
                        downloaded_bytes: dl,
                        total_bytes: tot,
                        stage: "downloading".to_string(),
                    });
                }
            },
        )
        .await?;
    }

    if *cancel_rx.borrow() {
        return Err(("Cancelled".to_string(), "cancelled"));
    }
    {
        if let Some(rt) = state.updater.by_origin.lock().unwrap().get_mut(&im_origin) {
            rt.progress = Some(UpdaterProgress {
                downloaded_bytes: 0,
                total_bytes: None,
                stage: "unpacking".to_string(),
            });
        }
    }

    let paths = state.paths.clone();
    let rt_sha_owned = rt_sha.to_string();
    let target_clone = target.clone();
    tokio::task::spawn_blocking(move || {
        unpack_staged_hot_bundle_blocking(&paths, &target_clone, &cached_rt, &rt_sha_owned, &cached_app)
    })
    .await
    .map_err(|e| (e.to_string(), "disk_or_unpack_failed"))?
    .map_err(|e| (e, "disk_or_unpack_failed"))
}

/// Conservatively remove unreferenced archives from `<desktop_home>/cache/` and `cache/installers/`.
pub fn prune_stale_update_cache(paths: &DesktopPaths, extra_keep_shas: &[String]) {
    let mut keep_shas: HashSet<String> = extra_keep_shas.iter().cloned().collect();

    if let Ok(raw) = fs::read_to_string(paths.seed_marker_path()) {
        if let Ok(val) = serde_json::from_str::<Value>(&raw) {
            if let Some(s) = val["sha256"].as_str() {
                keep_shas.insert(s.to_string());
            }
            if let Some(s) = val["runtime_sha256"].as_str() {
                keep_shas.insert(s.to_string());
            }
        }
    }

    let ui_active = read_ui_active_file(paths);
    for ptr in ui_active.origins.values() {
        keep_shas.insert(ptr.sha256.clone());
    }

    if let Ok(entries) = fs::read_dir(paths.nano_install_root.join("connections")) {
        for entry in entries.flatten() {
            let dir = entry.path();
            for fname in [".desktop-active.json", ".desktop-switch.json"] {
                if let Ok(raw) = fs::read_to_string(dir.join(fname)) {
                    if let Ok(val) = serde_json::from_str::<Value>(&raw) {
                        for key in ["sha256", "previous_sha256", "target_sha256"] {
                            if let Some(s) = val[key].as_str() {
                                keep_shas.insert(s.to_string());
                            }
                        }
                    }
                }
            }
        }
    }

    // Expand kept descriptor files so their referenced `runtime` & `app` archive shas are also retained.
    let cache_dir = paths.desktop_home.join("cache");
    let current_shas: Vec<String> = keep_shas.iter().cloned().collect();
    for sha in current_shas {
        if let Ok(raw) = fs::read_to_string(cache_dir.join(format!("descriptor-{}.json", sha))) {
            if let Ok(desc) = serde_json::from_str::<Value>(&raw) {
                if let Some(rt_sha) = desc["runtime"]["sha256"].as_str() {
                    keep_shas.insert(rt_sha.to_string());
                }
                if let Some(app_sha) = desc["app"]["sha256"].as_str() {
                    keep_shas.insert(app_sha.to_string());
                }
            }
        }
    }

    for sub in [&cache_dir, &cache_dir.join("installers")] {
        let Ok(entries) = fs::read_dir(sub) else { continue; };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let Some(name) = path.file_name().and_then(|n| n.to_str()) else { continue; };
            if name.contains(".part-") || name.ends_with(".seed-part") {
                continue;
            }
            let referenced = keep_shas.iter().any(|sha| !sha.is_empty() && name.contains(sha));
            if !referenced {
                let _ = fs::remove_file(&path);
            }
        }
    }
}

/// Trigger background auto-switch when the window is hidden (`!window_visible && !has_unsaved_form`) and an update is ready.
pub fn maybe_auto_apply_when_hidden(state: &Arc<HostSharedState>) {
    let attn = state.ui_bridge.window_attention();
    if attn.window_visible || attn.has_unsaved_form {
        return;
    }
    let prefs = read_updater_prefs(&state.paths);
    if !prefs.auto_update {
        return;
    }
    let cfg = state.host_config.read().unwrap().clone();
    let ui_active = read_ui_active_file(&state.paths);
    let should_apply = {
        let map = state.updater.by_origin.lock().unwrap();
        map.get(&cfg.im_origin)
            .filter(|rt| rt.phase == "ready_to_switch" && rt.mode == Some(UpdaterMode::HotBundle))
            .and_then(|rt| rt.target.as_ref())
            .map(|t| ui_active.rollback_blocked.get(&cfg.im_origin) != Some(&t.sha256) && ui_active.deferred_auto.get(&cfg.im_origin) != Some(&t.sha256))
            .unwrap_or(false)
    };
    if should_apply {
        let state_clone = state.clone();
        tauri::async_runtime::spawn(async move {
            let _ = apply_desktop_update_internal(state_clone, None, true).await;
        });
    }
}

/// Extract `node.user_id` from a real multi-line `js-yaml` `config.yaml` (or JSON fallback).
pub(crate) fn parse_node_owner_id_from_config(raw: &str) -> Option<String> {
    let trimmed_all = raw.trim();
    if trimmed_all.is_empty() {
        return None;
    }
    if let Ok(val) = serde_json::from_str::<Value>(trimmed_all) {
        return val["node"]["user_id"]
            .as_str()
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string);
    }

    let mut in_node_block = false;
    let mut node_child_indent: Option<usize> = None;
    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') || trimmed == "---" || trimmed == "..." {
            continue;
        }
        let indent = line.len() - line.trim_start_matches(' ').len();
        if indent == 0 {
            if let Some(rest) = trimmed.strip_prefix("node:") {
                let rest_trim = rest.trim();
                if rest_trim.is_empty() || rest_trim.starts_with('#') {
                    in_node_block = true;
                    node_child_indent = None;
                    continue;
                }
                if let Ok(inline_val) = serde_json::from_str::<Value>(rest_trim) {
                    if let Some(uid) = inline_val["user_id"].as_str().map(str::trim).filter(|s| !s.is_empty()) {
                        return Some(uid.to_string());
                    }
                }
            }
            in_node_block = false;
            node_child_indent = None;
            continue;
        }
        if !in_node_block {
            continue;
        }
        let expected_indent = *node_child_indent.get_or_insert(indent);
        if indent != expected_indent {
            continue;
        }
        let Some(raw_val) = trimmed.strip_prefix("user_id:") else {
            continue;
        };
        let v = raw_val.trim();
        if v.is_empty() || v == "~" || v == "null" {
            return None;
        }
        let unquoted = if v.starts_with('\'') && v.len() >= 2 {
            // Single-quoted YAML scalar: find closing single quote ('' escapes a literal ').
            let bytes = v.as_bytes();
            let mut idx = 1;
            let mut out = String::new();
            while idx < bytes.len() {
                if bytes[idx] == b'\'' {
                    if idx + 1 < bytes.len() && bytes[idx + 1] == b'\'' {
                        out.push('\'');
                        idx += 2;
                        continue;
                    }
                    break;
                }
                if let Some(ch) = v[idx..].chars().next() {
                    out.push(ch);
                    idx += ch.len_utf8();
                } else {
                    break;
                }
            }
            out
        } else if v.starts_with('"') {
            serde_json::from_str::<String>(v)
                .ok()
                .or_else(|| v.strip_prefix('"')?.split('"').next().map(str::to_string))?
        } else {
            let without_comment = match v.find(" #") {
                Some(pos) => &v[..pos],
                None => v,
            };
            without_comment.trim().to_string()
        };
        let cleaned = unquoted.trim();
        return if cleaned.is_empty() { None } else { Some(cleaned.to_string()) };
    }
    None
}

fn advertised_manifest_path(paths: &DesktopPaths, origin: &str) -> PathBuf {
    paths.desktop_home.join("update-offers").join(crate::config::sha256_hex(origin.as_bytes()))
}

fn previous_ui_pointer(bundle: &crate::local_node::ActiveBundlePaths) -> Option<DesktopUiOriginPointer> {
    Some(DesktopUiOriginPointer {
        version: bundle.version.clone(),
        sha256: bundle.sha256.clone()?,
        version_root: bundle.version_root.to_string_lossy().into_owned(),
        updated_at_epoch: now_secs(),
    })
}

/// Keep the last served bundle as the fallback for updates initiated remotely by a node.
pub fn remember_served_ui(paths: &DesktopPaths, origin: &str, bundle: &crate::local_node::ActiveBundlePaths) {
    let mut ui = read_ui_active_file(paths);
    if !ui.origins.contains_key(origin) {
        if let Some(pointer) = previous_ui_pointer(bundle) {
            ui.origins.insert(origin.to_string(), pointer);
            let _ = write_ui_active_file(paths, &ui);
        }
    }
}

/// Finish a provisional WebView switch only if this document still belongs to that switch.
pub fn finish_ui_boot(state: &HostSharedState, origin: &str, sha: &str, loaded: bool) {
    let cfg = state.host_config.read().unwrap();
    if cfg.im_origin != origin { return; }
    let mut ui = read_ui_active_file(&state.paths);
    let Some(active) = ui.origins.get(origin) else { return; };
    if active.sha256 != sha { return; }
    let version = active.version.clone();
    let Some(previous) = ui.previous_ui.remove(origin) else { return; };
    if loaded {
        ui.just_updated.insert(origin.to_string(), version);
    } else {
        ui.origins.insert(origin.to_string(), previous);
        ui.just_updated.remove(origin);
        ui.rollback_blocked.insert(origin.to_string(), sha.to_string());
    }
    if write_ui_active_file(&state.paths, &ui).is_err() { return; }
    drop(cfg);
    if !loaded {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(origin.to_string()).or_default();
        rt.phase = "failed".into();
        rt.error_code = Some("switch_rolled_back".into());
        drop(map);
        state.updater.reload_generation.fetch_add(1, Ordering::SeqCst);
        state.ui_bridge.reload_webview(None);
    }
    notify_ui_updater_changed(state, origin);
}

/// Safely promote an already-staged `.ready` hot update on startup ONLY when the local node is NOT already online,
/// saving a rollback backup in case `supervise_node`'s initial `start` fails.
pub fn try_promote_staged_update_on_startup(state: &HostSharedState, im_origin: &str, owner_id: Option<&str>) {
    let prefs = read_updater_prefs(&state.paths);
    if !prefs.auto_update {
        return;
    }
    let Ok(current_bundle) = resolve_active_ui_bundle(&state.paths, im_origin, state.dev_repo_root.as_deref()) else {
        return;
    };
    if current_bundle.version == "source" {
        return;
    }
    let ui_active = read_ui_active_file(&state.paths);
    let trusted = load_trusted_release_config(&state.paths, Some(&current_bundle.version_root));
    let expected_platform = format!("desktop-{}", current_desktop_platform_id());

    // Content-addressed bundles are shared. Only this service's last verified offer
    // authorizes a startup switch, including when multiple IMs use the official CDN.
    let Ok(raw) = fs::read(advertised_manifest_path(&state.paths, im_origin)) else { return; };
    let Ok(offer) = serde_json::from_slice(&raw) else { return; };
    let Some(target) = parse_desktop_release_manifest(&offer, &expected_platform, &trusted) else { return; };
    let target_root = state.paths.desktop_home.join("versions").join(&target.sha256);
    if ui_active.rollback_blocked.get(im_origin) == Some(&target.sha256) || ui_active.deferred_auto.get(im_origin) == Some(&target.sha256)
        || classify_target_release(&current_bundle.version, current_bundle.sha256.as_deref(), &target) != Some(UpdaterMode::HotBundle)
        || !verify_ready_ui_version_root(&target_root)
    {
        return;
    }

    // Inspect local connection state: NEVER overwrite `.desktop-active.json` if a live node is already running or foreign-owned!
    let mut prev_node_ptr: Option<Value> = None;
    let mut update_node_ptr_path: Option<PathBuf> = None;
    if let Ok(conn_dir) = state.paths.connection_dir(im_origin) {
        if conn_dir.join(".gateway-state.json").is_file() {
            // A node may already be alive; let normal runtime `NodeUpdates` coordinate task-draining switch instead.
            return;
        }
        let active_path = conn_dir.join(".desktop-active.json");
        let cfg_path = conn_dir.join("config.yaml");
        if active_path.is_file() && cfg_path.is_file() {
            let same_owner = owner_id.and_then(|oid| {
                let raw_cfg = fs::read_to_string(&cfg_path).ok()?;
                let cfg_owner = parse_node_owner_id_from_config(&raw_cfg)?;
                Some(cfg_owner == oid)
            }) == Some(true);
            if same_owner {
                if let Ok(raw_ptr) = fs::read_to_string(&active_path) {
                    prev_node_ptr = serde_json::from_str::<Value>(&raw_ptr).ok();
                    update_node_ptr_path = Some(active_path);
                }
            }
        }
    }

    let mut next_ui = ui_active;
    let prev_ui_ptr = next_ui.origins.get(im_origin).cloned();
    let root_str = target_root.to_string_lossy().to_string();
    next_ui.origins.insert(
        im_origin.to_string(),
        DesktopUiOriginPointer {
            version: target.version.clone(),
            sha256: target.sha256.clone(),
            version_root: root_str.clone(),
            updated_at_epoch: now_secs(),
        },
    );
    if let Some(previous) = previous_ui_pointer(&current_bundle) { next_ui.previous_ui.insert(im_origin.to_string(), previous); }
    next_ui.just_updated.remove(im_origin);
    if write_ui_active_file(&state.paths, &next_ui).is_err() {
        return;
    }

    if let (Some(path), Some(mut node_ptr)) = (update_node_ptr_path, prev_node_ptr.clone()) {
        if let Some(obj) = node_ptr.as_object_mut() {
            obj.insert("sha256".to_string(), json!(target.sha256));
            obj.insert("version".to_string(), json!(target.version));
            obj.insert("version_root".to_string(), json!(root_str));
            obj.insert("ui_root".to_string(), json!(target_root.join("ui").to_string_lossy()));
            obj.insert("updated_at_epoch".to_string(), json!(now_secs()));
            let _ = write_private_json(&path, &node_ptr);
        }
    }

    state.updater.startup_backups.lock().unwrap().insert(
        im_origin.to_string(),
        StartupPromotionBackup {
            im_origin: im_origin.to_string(),
            promoted_sha256: target.sha256,
            prev_ui_ptr,
            prev_node_ptr,
        },
    );
}

pub fn clear_startup_promotion_backup(state: &HostSharedState, im_origin: &str) {
    state.updater.startup_backups.lock().unwrap().remove(im_origin);
}

/// Roll back startup-promoted pointers if `supervise_node`'s initial `start` fails, restoring the previous working bundle.
pub fn rollback_startup_promotion_if_needed(state: &HostSharedState, im_origin: &str) -> bool {
    let Some(backup) = state.updater.startup_backups.lock().unwrap().remove(im_origin) else {
        return false;
    };
    let mut ui_active = read_ui_active_file(&state.paths);
    if let Some(prev_ui) = backup.prev_ui_ptr {
        ui_active.origins.insert(im_origin.to_string(), prev_ui);
    } else {
        ui_active.origins.remove(im_origin);
    }
    ui_active.just_updated.remove(im_origin);
    ui_active.previous_ui.remove(im_origin);
    ui_active.rollback_blocked.insert(im_origin.to_string(), backup.promoted_sha256.clone());
    let _ = write_ui_active_file(&state.paths, &ui_active);

    if let (Ok(active_path), Some(prev_node)) = (state.paths.desktop_active_path(im_origin), backup.prev_node_ptr) {
        let _ = write_private_json(&active_path, &prev_node);
    }

    {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.to_string()).or_default();
        rt.phase = "failed".to_string();
        rt.error_code = Some("switch_rolled_back".to_string());
    }
    let _ = crate::local_node::reconcile_webview_ui_cache(
        &state.paths,
        im_origin,
        state.dev_repo_root.as_deref(),
        state.seed_archives_dir.as_deref(),
    );
    state.updater.reload_generation.fetch_add(1, Ordering::SeqCst);
    state.ui_bridge.reload_webview(None);
    notify_ui_updater_changed(state, im_origin);
    append_host_log(
        Some(&state.paths),
        "WARN",
        &format!("Rolled back failed startup promotion {} for {}", backup.promoted_sha256, im_origin),
    );
    true
}

/// Synchronize `desktop-ui-active.json` when `update-worker.ts` completes or rolls back and hits `/desktop/internal/reload-assets`.
pub fn on_internal_reload_assets(state: &HostSharedState, expected_origin: Option<&str>) {
    let context = state.host_config.read().unwrap();
    let im_origin = context.im_origin.clone();
    if expected_origin.is_some_and(|origin| origin != im_origin) { return; }
    let stored_owner = state
        .sessions
        .read()
        .unwrap()
        .by_origin
        .get(&im_origin)
        .map(|s| s.owner_id.clone());

    if let (Some(owner_id), Ok(conn_dir)) = (stored_owner, state.paths.connection_dir(&im_origin)) {
        let cfg_path = conn_dir.join("config.yaml");
        let active_path = conn_dir.join(".desktop-active.json");
        let same_owner = fs::read_to_string(&cfg_path)
            .ok()
            .and_then(|raw| parse_node_owner_id_from_config(&raw))
            .map(|uid| uid == owner_id)
            .unwrap_or(false);

        if same_owner && active_path.is_file() {
            if let Ok(raw_ptr) = fs::read_to_string(&active_path) {
                if let Ok(ptr_val) = serde_json::from_str::<Value>(&raw_ptr) {
                    if let (Some(ver), Some(sha), Some(vroot)) = (
                        ptr_val["version"].as_str(),
                        ptr_val["sha256"].as_str(),
                        ptr_val["version_root"].as_str(),
                    ) {
                        if verify_ready_ui_version_root(Path::new(vroot)) {
                            let mut ui_active = read_ui_active_file(&state.paths);
                            let prev_ptr = ui_active.origins.get(&im_origin).cloned();
                            let prev_sha = prev_ptr.as_ref().map(|p| p.sha256.clone());
                            let is_forward_upgrade = match prev_ptr.as_ref() {
                                Some(prev) => match (parse_strict_semver(ver), parse_strict_semver(&prev.version)) {
                                    (Some(next_v), Some(prev_v)) => next_v > prev_v,
                                    _ => prev.sha256 != sha,
                                },
                                None => true,
                            };
                            ui_active.origins.insert(
                                im_origin.clone(),
                                DesktopUiOriginPointer {
                                    version: ver.to_string(),
                                    sha256: sha.to_string(),
                                    version_root: vroot.to_string(),
                                    updated_at_epoch: now_secs(),
                                },
                            );
                            if prev_sha.as_deref() != Some(sha) {
                                ui_active.just_updated.remove(&im_origin);
                                if let Some(previous) = prev_ptr.filter(|_| is_forward_upgrade) {
                                    ui_active.previous_ui.insert(im_origin.clone(), previous);
                                } else {
                                    ui_active.previous_ui.remove(&im_origin);
                                }
                            }
                            let _ = write_ui_active_file(&state.paths, &ui_active);
                            prune_stale_update_cache(&state.paths, &[sha.to_string()]);
                        }
                    }
                }
            }
        }
    }

    let _ = crate::local_node::reconcile_webview_ui_cache(
        &state.paths,
        &im_origin,
        state.dev_repo_root.as_deref(),
        state.seed_archives_dir.as_deref(),
    );
    state.updater.reload_generation.fetch_add(1, Ordering::SeqCst);
    state.ui_bridge.reload_webview(None);
    notify_ui_updater_changed(state, &im_origin);
}

pub async fn check_for_updates(state: Arc<HostSharedState>, manual: bool) -> DesktopUpdaterSnapshot {
    if !state.is_seed_ready() || !manual && !read_updater_prefs(&state.paths).auto_update {
        return build_updater_snapshot(&state);
    }
    let cfg = state.host_config.read().unwrap().clone();
    let im_origin = cfg.im_origin.clone();
    let context_epoch = cfg.context_epoch;

    let Ok(current_bundle) = resolve_active_ui_bundle(&state.paths, &im_origin, state.dev_repo_root.as_deref()) else {
        return build_updater_snapshot(&state);
    };
    if current_bundle.version == "source" && state.seed_archives_dir.is_none() {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        rt.phase = "source_mode".to_string();
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    }

    // Avoid clobbering an active download/switch unless user explicitly clicked Retry on a failed state.
    {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        if matches!(
            rt.phase.as_str(),
            "checking" | "preparing" | "downloading_installer" | "waiting_for_tasks" | "switching"
        ) {
            drop(map);
            return build_updater_snapshot(&state);
        }
        rt.phase = "checking".to_string();
        rt.error_code = None;
    }
    if manual {
        notify_ui_updater_changed(&state, &im_origin);
    }

    let expected_platform = format!("desktop-{}", current_desktop_platform_id());
    let manifest_url = format!("{}/install/manifest.{}.json", im_origin, expected_platform);
    let res = state.http_client.get(&manifest_url).send().await;

    // Ensure server did not switch while fetching manifest.
    {
        let latest_cfg = state.host_config.read().unwrap().clone();
        if latest_cfg.im_origin != im_origin || latest_cfg.context_epoch != context_epoch {
            return build_updater_snapshot(&state);
        }
    }

    let response = match res {
        Ok(r) => r,
        Err(err) => {
            append_host_log(Some(&state.paths), "WARN", &format!("Update check failed ({}): {}", manifest_url, err));
            let mut map = state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            if manual || rt.phase.is_empty() || rt.phase == "checking" {
                rt.phase = "failed".to_string();
                rt.error_code = Some("network_unreachable".to_string());
            }
            rt.last_checked_at = Some(now_iso_string());
            drop(map);
            notify_ui_updater_changed(&state, &im_origin);
            return build_updater_snapshot(&state);
        }
    };

    let status_code = response.status().as_u16();
    if status_code == 404 {
        let _ = fs::remove_file(advertised_manifest_path(&state.paths, &im_origin));
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        rt.phase = "unpublished".to_string();
        rt.mode = None;
        rt.target = None;
        rt.progress = None;
        rt.error_code = None;
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    }

    if status_code == 503 {
        let body_text = response.text().await.unwrap_or_default();
        if body_text.to_ascii_lowercase().contains("not published") {
            let _ = fs::remove_file(advertised_manifest_path(&state.paths, &im_origin));
            let mut map = state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            rt.phase = "unpublished".to_string();
            rt.mode = None;
            rt.target = None;
            rt.progress = None;
            rt.error_code = None;
            rt.last_checked_at = Some(now_iso_string());
            drop(map);
            notify_ui_updater_changed(&state, &im_origin);
            return build_updater_snapshot(&state);
        }
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        if manual || rt.phase.is_empty() || rt.phase == "checking" {
            rt.phase = "failed".to_string();
            rt.error_code = Some("network_unreachable".to_string());
        }
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    }

    if !response.status().is_success() {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        if manual || rt.phase == "checking" {
            rt.phase = "failed".to_string();
            rt.error_code = Some("network_unreachable".to_string());
        }
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    }

    let Ok(raw_json) = response.json::<Value>().await else {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        rt.phase = "failed".to_string();
        rt.error_code = Some("verification_failed".to_string());
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    };

    let trusted = load_trusted_release_config(&state.paths, Some(&current_bundle.version_root));
    let Some(manifest) = parse_desktop_release_manifest(&raw_json, &expected_platform, &trusted) else {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        rt.phase = "failed".to_string();
        rt.error_code = Some("verification_failed".to_string());
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    };

    let _ = write_private_json(&advertised_manifest_path(&state.paths, &im_origin), &raw_json);
    let Some(mode) = classify_target_release(&current_bundle.version, current_bundle.sha256.as_deref(), &manifest) else {
        let mut map = state.updater.by_origin.lock().unwrap();
        let rt = map.entry(im_origin.clone()).or_default();
        rt.phase = "up_to_date".to_string();
        rt.mode = None;
        rt.target = None;
        rt.progress = None;
        rt.error_code = None;
        rt.last_checked_at = Some(now_iso_string());
        drop(map);
        notify_ui_updater_changed(&state, &im_origin);
        return build_updater_snapshot(&state);
    };

    let prefs = read_updater_prefs(&state.paths);
    if mode == UpdaterMode::HotBundle {
        let ready_root = state.paths.desktop_home.join("versions").join(&manifest.sha256);
        let already_staged = verify_ready_ui_version_root(&ready_root);
        let mut spawn_bg_stage = false;
        let mut cancel_rx_opt = None;
        {
            let mut map = state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            rt.mode = Some(UpdaterMode::HotBundle);
            rt.target = Some(manifest.clone());
            rt.error_code = None;
            rt.last_checked_at = Some(now_iso_string());
            if manual {
                rt.dismissed_version = None;
            }
            if !manual && read_ui_active_file(&state.paths).rollback_blocked.get(&im_origin) == Some(&manifest.sha256) {
                rt.phase = "failed".to_string();
                rt.error_code = Some("switch_rolled_back".to_string());
            } else if already_staged {
                rt.phase = "ready_to_switch".to_string();
                rt.progress = None;
            } else if prefs.auto_update {
                rt.phase = "preparing".to_string();
                rt.progress = Some(UpdaterProgress {
                    downloaded_bytes: 0,
                    total_bytes: Some(manifest.size),
                    stage: "downloading".to_string(),
                });
                let (tx, rx) = watch::channel(false);
                rt.cancel_tx = Some(tx);
                cancel_rx_opt = Some(rx);
                spawn_bg_stage = true;
            } else {
                rt.phase = "available".to_string();
                rt.progress = None;
            }
        }
        notify_ui_updater_changed(&state, &im_origin);

        if already_staged {
            maybe_auto_apply_when_hidden(&state);
        } else if spawn_bg_stage {
            if let Some(cancel_rx) = cancel_rx_opt {
                let state_bg = state.clone();
                let origin_bg = im_origin.clone();
                let manifest_bg = manifest.clone();
                tokio::spawn(async move {
                    let _guard = state_bg.updater.task_lock.lock().await;
                    match stage_hot_bundle(state_bg.clone(), origin_bg.clone(), context_epoch, manifest_bg, cancel_rx).await {
                        Ok(_) => {
                            {
                                let mut map = state_bg.updater.by_origin.lock().unwrap();
                                if let Some(rt) = map.get_mut(&origin_bg) {
                                    rt.phase = "ready_to_switch".to_string();
                                    rt.progress = None;
                                    rt.cancel_tx = None;
                                }
                            }
                            notify_ui_updater_changed(&state_bg, &origin_bg);
                            maybe_auto_apply_when_hidden(&state_bg);
                        }
                        Err((_, "cancelled")) => {
                            {
                                let mut map = state_bg.updater.by_origin.lock().unwrap();
                                if let Some(rt) = map.get_mut(&origin_bg) {
                                    rt.phase = "available".to_string();
                                    rt.progress = None;
                                    rt.cancel_tx = None;
                                }
                            }
                            notify_ui_updater_changed(&state_bg, &origin_bg);
                        }
                        Err((detail, code)) => {
                            append_host_log(Some(&state_bg.paths), "WARN", &format!("Background stage failed: {}", detail));
                            {
                                let mut map = state_bg.updater.by_origin.lock().unwrap();
                                if let Some(rt) = map.get_mut(&origin_bg) {
                                    rt.phase = "failed".to_string();
                                    rt.error_code = Some(code.to_string());
                                    rt.progress = None;
                                    rt.cancel_tx = None;
                                }
                            }
                            notify_ui_updater_changed(&state_bg, &origin_bg);
                        }
                    }
                });
            }
        }
    } else {
        // Outer Tauri shell / installer upgrade
        let installer_file = state
            .paths
            .desktop_home
            .join("cache/installers")
            .join(format!("{}-{}", manifest.installer.sha256, manifest.installer.filename));
        let installer_verified = installer_file.is_file()
            && file_sha256(&installer_file).ok().as_deref() == Some(manifest.installer.sha256.as_str());
        {
            let mut map = state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            rt.mode = Some(UpdaterMode::Installer);
            rt.target = Some(manifest.clone());
            rt.error_code = None;
            rt.progress = None;
            rt.last_checked_at = Some(now_iso_string());
            if manual {
                rt.dismissed_version = None;
            }
            if installer_verified {
                rt.phase = "installer_ready".to_string();
                rt.installer_path = Some(installer_file);
            } else {
                rt.phase = "available".to_string();
                rt.installer_path = None;
            }
        }
        notify_ui_updater_changed(&state, &im_origin);
    }

    build_updater_snapshot(&state)
}

pub async fn set_auto_update_preference(state: Arc<HostSharedState>, auto_update: bool) -> Result<DesktopUpdaterSnapshot, String> {
    write_updater_prefs(&state.paths, &UpdaterPrefsFile { auto_update })?;
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    if !auto_update {
        let should_cancel = {
            let map = state.updater.by_origin.lock().unwrap();
            map.get(&im_origin).map(|rt| rt.phase == "preparing").unwrap_or(false)
        };
        if should_cancel {
            cancel_origin_tasks(&state, &im_origin);
        }
        notify_ui_updater_changed(&state, &im_origin);
        return Ok(build_updater_snapshot(&state));
    }

    notify_ui_updater_changed(&state, &im_origin);
    // When re-enabling auto_update, kick off background check/preparation immediately.
    let state_clone = state.clone();
    tokio::spawn(async move {
        let _ = check_for_updates(state_clone, false).await;
    });
    Ok(build_updater_snapshot(&state))
}

pub fn dismiss_updater_notice(state: &HostSharedState, kind: &str) -> DesktopUpdaterSnapshot {
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    if kind == "just_updated" {
        let mut ui_active = read_ui_active_file(&state.paths);
        ui_active.just_updated.remove(&im_origin);
        let _ = write_ui_active_file(&state.paths, &ui_active);
    } else if kind == "capsule" {
        let mut map = state.updater.by_origin.lock().unwrap();
        if let Some(rt) = map.get_mut(&im_origin) {
            rt.dismissed_version = rt.target.as_ref().map(|t| t.version.clone());
        }
    } else if kind == "reopen_capsule" {
        let mut map = state.updater.by_origin.lock().unwrap();
        if let Some(rt) = map.get_mut(&im_origin) {
            rt.dismissed_version = None;
        }
    }
    notify_ui_updater_changed(state, &im_origin);
    build_updater_snapshot(state)
}

async fn obtain_im_access_token(state: &HostSharedState, im_origin: &str, bearer_override: Option<String>) -> Option<(String, String)> {
    if let Some(token) = bearer_override {
        let me_url = format!("{}/im/v1/auth/me", im_origin);
        if let Ok(res) = state.http_client.get(&me_url).bearer_auth(&token).send().await {
            if res.status().is_success() {
                if let Ok(user) = res.json::<Value>().await {
                    let uid = user["id"].as_str().unwrap_or("");
                    let owner = user["owner_id"].as_str().unwrap_or(uid).to_string();
                    if !owner.is_empty() {
                        return Some((token, owner));
                    }
                }
            }
        }
    }
    if let Ok(refreshed) = refresh_stored_session_serialized(state, im_origin).await {
        let token = refreshed["access_token"].as_str().unwrap_or("").to_string();
        let uid = refreshed["user"]["id"].as_str().unwrap_or("");
        let owner = refreshed["user"]["owner_id"].as_str().unwrap_or(uid).to_string();
        if !token.is_empty() && !owner.is_empty() {
            return Some((token, owner));
        }
    }
    None
}

pub async fn apply_desktop_update(
    state: Arc<HostSharedState>,
    bearer_override: Option<String>,
) -> Result<DesktopUpdaterSnapshot, String> {
    apply_desktop_update_internal(state, bearer_override, false).await
}

async fn apply_desktop_update_internal(
    state: Arc<HostSharedState>,
    bearer_override: Option<String>,
    silent_auto: bool,
) -> Result<DesktopUpdaterSnapshot, String> {
    let cfg = state.host_config.read().unwrap().clone();
    let im_origin = cfg.im_origin.clone();
    let context_epoch = cfg.context_epoch;

    let (mode, target_opt, current_phase) = {
        let map = state.updater.by_origin.lock().unwrap();
        let rt = map.get(&im_origin);
        (
            rt.and_then(|r| r.mode),
            rt.and_then(|r| r.target.clone()),
            rt.map(|r| r.phase.clone()).unwrap_or_default(),
        )
    };

    let (Some(mode), Some(target)) = (mode, target_opt) else {
        return Ok(check_for_updates(state, !silent_auto).await);
    };

    if mode == UpdaterMode::Installer {
        if current_phase == "downloading_installer" || current_phase == "installer_ready" {
            return Ok(build_updater_snapshot(&state));
        }
        let dest = state
            .paths
            .desktop_home
            .join("cache/installers")
            .join(format!("{}-{}", target.installer.sha256, target.installer.filename));
        let (tx, rx) = watch::channel(false);
        {
            let mut map = state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            rt.phase = "downloading_installer".to_string();
            rt.error_code = None;
            rt.progress = Some(UpdaterProgress {
                downloaded_bytes: 0,
                total_bytes: Some(target.installer.size),
                stage: "downloading".to_string(),
            });
            rt.cancel_tx = Some(tx);
        }
        notify_ui_updater_changed(&state, &im_origin);

        let state_bg = state.clone();
        let origin_bg = im_origin.clone();
        let target_bg = target.clone();
        tokio::spawn(async move {
            let state_p = state_bg.clone();
            let origin_p = origin_bg.clone();
            let res = download_verified_file(
                &target_bg.installer.download_url,
                &dest,
                &target_bg.installer.sha256,
                Some(target_bg.installer.size),
                rx,
                &state_bg,
                &origin_bg,
                context_epoch,
                move |dl, tot| {
                    if let Some(rt) = state_p.updater.by_origin.lock().unwrap().get_mut(&origin_p) {
                        rt.progress = Some(UpdaterProgress {
                            downloaded_bytes: dl,
                            total_bytes: tot,
                            stage: "downloading".to_string(),
                        });
                    }
                },
            )
            .await;

            match res {
                Ok(_) => {
                    {
                        let mut map = state_bg.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&origin_bg) {
                            rt.phase = "installer_ready".to_string();
                            rt.installer_path = Some(dest);
                            rt.progress = None;
                            rt.cancel_tx = None;
                        }
                    }
                    prune_stale_update_cache(&state_bg.paths, &[target_bg.installer.sha256]);
                    notify_ui_updater_changed(&state_bg, &origin_bg);
                }
                Err((_, "cancelled")) => {
                    {
                        let mut map = state_bg.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&origin_bg) {
                            rt.phase = "available".to_string();
                            rt.progress = None;
                            rt.cancel_tx = None;
                        }
                    }
                    notify_ui_updater_changed(&state_bg, &origin_bg);
                }
                Err((detail, code)) => {
                    append_host_log(Some(&state_bg.paths), "WARN", &format!("Installer download failed: {}", detail));
                    {
                        let mut map = state_bg.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&origin_bg) {
                            rt.phase = "failed".to_string();
                            rt.error_code = Some(code.to_string());
                            rt.progress = None;
                            rt.cancel_tx = None;
                        }
                    }
                    notify_ui_updater_changed(&state_bg, &origin_bg);
                }
            }
        });
        return Ok(build_updater_snapshot(&state));
    }

    // `mode == HotBundle`
    let ready_root = state.paths.desktop_home.join("versions").join(&target.sha256);
    if !verify_ready_ui_version_root(&ready_root) {
        if current_phase == "preparing" {
            return Ok(build_updater_snapshot(&state));
        }
        let (tx, rx) = watch::channel(false);
        {
            let mut map = state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            rt.phase = "preparing".to_string();
            rt.error_code = None;
            rt.progress = Some(UpdaterProgress {
                downloaded_bytes: 0,
                total_bytes: Some(target.size),
                stage: "downloading".to_string(),
            });
            rt.cancel_tx = Some(tx);
        }
        notify_ui_updater_changed(&state, &im_origin);
        let _guard = state.updater.task_lock.lock().await;
        if let Err((detail, code)) = stage_hot_bundle(state.clone(), im_origin.clone(), context_epoch, target.clone(), rx).await {
            if code == "cancelled" {
                let mut map = state.updater.by_origin.lock().unwrap();
                if let Some(rt) = map.get_mut(&im_origin) {
                    rt.phase = "available".to_string();
                    rt.progress = None;
                    rt.cancel_tx = None;
                }
            } else {
                append_host_log(Some(&state.paths), "WARN", &format!("On-demand stage failed: {}", detail));
                let mut map = state.updater.by_origin.lock().unwrap();
                if let Some(rt) = map.get_mut(&im_origin) {
                    rt.phase = "failed".to_string();
                    rt.error_code = Some(code.to_string());
                    rt.progress = None;
                    rt.cancel_tx = None;
                }
            }
            notify_ui_updater_changed(&state, &im_origin);
            return Ok(build_updater_snapshot(&state));
        }
        {
            let mut map = state.updater.by_origin.lock().unwrap();
            if let Some(rt) = map.get_mut(&im_origin) {
                rt.phase = "ready_to_switch".to_string();
                rt.progress = None;
                rt.cancel_tx = None;
            }
        }
        notify_ui_updater_changed(&state, &im_origin);
    }

    // Re-verify server did not switch during staging.
    {
        let latest_cfg = state.host_config.read().unwrap().clone();
        if latest_cfg.im_origin != im_origin || latest_cfg.context_epoch != context_epoch {
            return Ok(build_updater_snapshot(&state));
        }
    }

    // Determine local node ownership for `im_origin`.
    let auth_pair = obtain_im_access_token(&state, &im_origin, bearer_override).await;
    let session_owner = auth_pair
        .as_ref()
        .map(|(_, o)| o.clone())
        .or_else(|| {
            state
                .sessions
                .read()
                .unwrap()
                .by_origin
                .get(&im_origin)
                .map(|s| s.owner_id.clone())
        });

    let mut ownership = "unbound".to_string();
    let mut local_node_id: Option<String> = None;
    let mut node_at_target = false;
    let mut local_active_tasks: u64 = 0;

    if let (Some(owner_id), Ok(bundle)) = (
        session_owner.clone(),
        resolve_active_bundle(&state.paths, &im_origin, state.dev_repo_root.as_deref()),
    ) {
        node_at_target = bundle.sha256.as_ref() == Some(&target.sha256);
        let paths_cl = state.paths.clone();
        let origin_cl = im_origin.clone();
        if let Ok(Ok(inspected)) = tokio::task::spawn_blocking(move || {
            crate::local_node::run_local_admin_sync(
                &paths_cl,
                &bundle,
                &origin_cl,
                "inspect",
                Some(&owner_id),
                None,
                None,
            )
        })
        .await
        {
            if inspected.ok {
                ownership = inspected.body["ownership"].as_str().unwrap_or("unbound").to_string();
                local_node_id = inspected.body["node_id"].as_str().map(str::to_string);
                local_active_tasks = inspected.body["active_tasks"].as_u64().unwrap_or(0);
            }
        }
    }

    let current = state.host_config.read().unwrap().clone();
    let attention = state.ui_bridge.window_attention();
    if current.im_origin != im_origin || current.context_epoch != context_epoch
        || silent_auto && (attention.window_visible || attention.has_unsaved_form || !read_updater_prefs(&state.paths).auto_update)
    {
        return Ok(build_updater_snapshot(&state));
    }

    if ownership == "managed_online" && !node_at_target {
        if silent_auto && local_active_tasks > 0 {
            // In silent background auto-mode, never gate new incoming messages while tasks are still running.
            return Ok(build_updater_snapshot(&state));
        }
        let Some((access_token, _)) = auth_pair else {
            return Err("Authentication required to coordinate online computer update".to_string());
        };
        let Some(node_id) = local_node_id else {
            return Err("Local computer node_id missing".to_string());
        };
        let update_url = format!("{}/im/v1/nodes/{}/update", im_origin, node_id);
        let req_id = format!("desktop-upd-{}", random_hex_token(8));
        let res = state
            .http_client
            .post(&update_url)
            .bearer_auth(&access_token)
            .json(&json!({
                "request_id": req_id,
                "version": target.version,
                "sha256": target.sha256,
            }))
            .send()
            .await
            .map_err(|e| format!("Failed to request node update: {e}"))?;

        if !res.status().is_success() {
            let detail = res.text().await.unwrap_or_default();
            return Err(format!("Node update rejected: {}", detail));
        }
        let op: Value = res.json().await.map_err(|e| e.to_string())?;
        let op_id = op["id"].as_str().unwrap_or("").to_string();
        let op_state = op["state"].as_str().unwrap_or("requested");

        {
            let mut map = state.updater.by_origin.lock().unwrap();
            if let Some(rt) = map.get_mut(&im_origin) {
                rt.node_id = Some(node_id.clone());
                rt.node_operation_id = if op_id.is_empty() { None } else { Some(op_id.clone()) };
                rt.active_tasks = local_active_tasks;
                rt.phase = if local_active_tasks > 0 || op_state == "waiting" {
                    "waiting_for_tasks".to_string()
                } else {
                    "switching".to_string()
                };
            }
        }
        notify_ui_updater_changed(&state, &im_origin);
        spawn_online_node_update_poller(state.clone(), im_origin, context_epoch, node_id, op_id, target, access_token);
        return Ok(build_updater_snapshot(&state));
    }

    // Instant local pointer switch (`unbound`, `managed_stopped`, `takeover_available`, or `foreign_owner`).
    let root_str = ready_root.to_string_lossy().to_string();
    let mut ui_active = read_ui_active_file(&state.paths);
    let previous = resolve_active_ui_bundle(&state.paths, &im_origin, state.dev_repo_root.as_deref())?;
    if let Some(pointer) = previous_ui_pointer(&previous) { ui_active.previous_ui.insert(im_origin.clone(), pointer); }
    ui_active.origins.insert(
        im_origin.clone(),
        DesktopUiOriginPointer {
            version: target.version.clone(),
            sha256: target.sha256.clone(),
            version_root: root_str.clone(),
            updated_at_epoch: now_secs(),
        },
    );
    ui_active.just_updated.remove(&im_origin);
    ui_active.rollback_blocked.remove(&im_origin);
    write_ui_active_file(&state.paths, &ui_active)?;

    // ONLY update `.desktop-active.json` when `managed_stopped` for the SAME owner (never touch `foreign_owner`).
    if ownership == "managed_stopped" {
        if let Ok(active_path) = state.paths.desktop_active_path(&im_origin) {
            if let Ok(raw) = fs::read_to_string(&active_path) {
                if let Ok(mut val) = serde_json::from_str::<Value>(&raw) {
                    if let Some(obj) = val.as_object_mut() {
                        obj.insert("sha256".to_string(), json!(target.sha256));
                        obj.insert("version".to_string(), json!(target.version));
                        obj.insert("version_root".to_string(), json!(root_str));
                        obj.insert("ui_root".to_string(), json!(ready_root.join("ui").to_string_lossy()));
                        obj.insert("updated_at_epoch".to_string(), json!(now_secs()));
                        let _ = write_private_json(&active_path, &val);
                    }
                }
            }
        }
    }

    {
        let mut map = state.updater.by_origin.lock().unwrap();
        if let Some(rt) = map.get_mut(&im_origin) {
            rt.phase = "up_to_date".to_string();
            rt.mode = None;
            rt.target = None;
            rt.progress = None;
            rt.error_code = None;
        }
    }
    prune_stale_update_cache(&state.paths, &[target.sha256]);
    let _ = crate::local_node::reconcile_webview_ui_cache(
        &state.paths,
        &im_origin,
        state.dev_repo_root.as_deref(),
        state.seed_archives_dir.as_deref(),
    );
    state.updater.reload_generation.fetch_add(1, Ordering::SeqCst);
    state.ui_bridge.reload_webview(None);
    notify_ui_updater_changed(&state, &im_origin);
    Ok(build_updater_snapshot(&state))
}

fn spawn_online_node_update_poller(
    state: Arc<HostSharedState>,
    im_origin: String,
    context_epoch: u64,
    node_id: String,
    op_id: String,
    target: VerifiedDesktopManifest,
    mut token: String,
) {
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(Duration::from_secs(1)).await;
            let cfg = state.host_config.read().unwrap().clone();
            if cfg.im_origin != im_origin || cfg.context_epoch != context_epoch || state.shutdown_tx.lock().unwrap().is_none() {
                return;
            }
            if !op_id.is_empty() {
                let still_active_op = state
                    .updater
                    .by_origin
                    .lock()
                    .unwrap()
                    .get(&im_origin)
                    .and_then(|rt| rt.node_operation_id.as_deref())
                    == Some(op_id.as_str());
                if !still_active_op {
                    return;
                }
            }
            let nodes_url = format!("{}/im/v1/nodes", im_origin);
            let Ok(res) = state.http_client.get(&nodes_url).bearer_auth(&token).send().await else {
                continue;
            };
            if res.status() == reqwest::StatusCode::UNAUTHORIZED {
                if let Some((renewed, _)) = obtain_im_access_token(&state, &im_origin, None).await { token = renewed; }
                continue;
            }
            let Ok(rows) = res.json::<Value>().await else { continue; };
            let latest = state.host_config.read().unwrap().clone();
            if latest.im_origin != im_origin || latest.context_epoch != context_epoch { return; }
            let Some(arr) = rows.as_array() else { continue; };
            let Some(node_row) = arr.iter().find(|n| n["node_id"].as_str() == Some(node_id.as_str())) else {
                continue;
            };
            let op = &node_row["update"]["operation"];
            if !op_id.is_empty() && op["id"].as_str().is_some_and(|id| id != op_id) {
                continue;
            }
            let Some(op_state) = op["state"].as_str() else { continue; };
            match op_state {
                "requested" | "downloading" | "installing" | "waiting" => {
                    if op["cancel_requested"].as_bool() == Some(true) {
                        continue;
                    }
                    let mut map = state.updater.by_origin.lock().unwrap();
                    if let Some(rt) = map.get_mut(&im_origin) {
                        if op_id.is_empty() || rt.node_operation_id.as_deref() == Some(op_id.as_str()) {
                            rt.phase = "waiting_for_tasks".to_string();
                        }
                    }
                    drop(map);
                    notify_ui_updater_changed(&state, &im_origin);
                }
                "switching" | "verifying" | "rolling_back" => {
                    let mut map = state.updater.by_origin.lock().unwrap();
                    if let Some(rt) = map.get_mut(&im_origin) {
                        rt.phase = "switching".to_string();
                    }
                    drop(map);
                    notify_ui_updater_changed(&state, &im_origin);
                }
                "succeeded" => {
                    let ui = read_ui_active_file(&state.paths);
                    if ui.origins.get(&im_origin).map(|p| &p.sha256) != Some(&target.sha256)
                        && ui.rollback_blocked.get(&im_origin) != Some(&target.sha256) {
                        on_internal_reload_assets(&state, Some(&im_origin));
                    }
                    {
                        let mut map = state.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&im_origin) {
                            rt.phase = "up_to_date".to_string();
                            rt.mode = None;
                            rt.target = None;
                            rt.node_operation_id = None;
                        }
                    }
                    prune_stale_update_cache(&state.paths, &[target.sha256]);
                    notify_ui_updater_changed(&state, &im_origin);
                    return;
                }
                "cancelled" => {
                    let mut ui = read_ui_active_file(&state.paths);
                    ui.deferred_auto.insert(im_origin.clone(), target.sha256.clone());
                    let _ = write_ui_active_file(&state.paths, &ui);
                    {
                        let mut map = state.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&im_origin) {
                            rt.phase = "ready_to_switch".to_string();
                            rt.node_operation_id = None;
                        }
                    }
                    notify_ui_updater_changed(&state, &im_origin);
                    return;
                }
                "rolled_back" => {
                    let mut ui = read_ui_active_file(&state.paths);
                    ui.rollback_blocked.insert(im_origin.clone(), target.sha256.clone());
                    let _ = write_ui_active_file(&state.paths, &ui);
                    {
                        let mut map = state.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&im_origin) {
                            rt.phase = "failed".to_string();
                            rt.error_code = Some("switch_rolled_back".to_string());
                            rt.node_operation_id = None;
                        }
                    }
                    notify_ui_updater_changed(&state, &im_origin);
                    return;
                }
                "failed" | "interrupted" | "recovery_required" => {
                    {
                        let mut map = state.updater.by_origin.lock().unwrap();
                        if let Some(rt) = map.get_mut(&im_origin) {
                            rt.phase = "failed".to_string();
                            rt.error_code = Some("disk_or_unpack_failed".to_string());
                            rt.node_operation_id = None;
                        }
                    }
                    notify_ui_updater_changed(&state, &im_origin);
                    return;
                }
                _ => {}
            }
        }
    });
}

pub async fn cancel_desktop_update(
    state: Arc<HostSharedState>,
    bearer_override: Option<String>,
) -> Result<DesktopUpdaterSnapshot, String> {
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    cancel_origin_tasks(&state, &im_origin);

    let (node_id_opt, op_id_opt) = {
        let map = state.updater.by_origin.lock().unwrap();
        let rt = map.get(&im_origin);
        (
            rt.and_then(|r| r.node_id.clone()),
            rt.and_then(|r| r.node_operation_id.clone()),
        )
    };

    if let (Some(node_id), Some(op_id)) = (node_id_opt, op_id_opt) {
        let (token, _) = obtain_im_access_token(&state, &im_origin, bearer_override).await
            .ok_or_else(|| "Sign in to cancel the update".to_string())?;
        state.http_client.post(format!("{}/im/v1/nodes/{}/update/cancel", im_origin, node_id))
            .bearer_auth(token).json(&json!({ "operation_id": op_id }))
            .send().await.and_then(|response| response.error_for_status()).map_err(|e| e.to_string())?;
        // Keep tracking the operation until the node confirms cancellation or a competing switch.

    }

    notify_ui_updater_changed(&state, &im_origin);
    Ok(build_updater_snapshot(&state))
}

pub fn open_downloaded_installer(state: &HostSharedState) -> Result<DesktopUpdaterSnapshot, String> {
    let im_origin = state.host_config.read().unwrap().im_origin.clone();
    let (installer_path, expected_sha) = {
        let map = state.updater.by_origin.lock().unwrap();
        let rt = map.get(&im_origin).ok_or_else(|| "No installer ready".to_string())?;
        let target = rt.target.as_ref().ok_or_else(|| "No target manifest".to_string())?;
        let path = rt.installer_path.clone().unwrap_or_else(|| {
            state
                .paths
                .desktop_home
                .join("cache/installers")
                .join(format!("{}-{}", target.installer.sha256, target.installer.filename))
        });
        (path, target.installer.sha256.clone())
    };
    launch_verified_installer(&state.paths, &installer_path, &expected_sha)?;
    Ok(build_updater_snapshot(state))
}

pub fn spawn_updater_daemon(state: Arc<HostSharedState>) {
    tokio::spawn(async move {
        // Initial startup check shortly after boot / seed unpack.
        tokio::time::sleep(Duration::from_millis(1200)).await;
        loop {
            if state.shutdown_tx.lock().unwrap().is_none() {
                return;
            }
            if state.is_seed_ready() {
                let _ = check_for_updates(state.clone(), false).await;
            }
            tokio::time::sleep(Duration::from_secs(30 * 60)).await;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::DesktopCliOptions;
    use tempfile::tempdir;

    fn sample_manifest(platform: &str, pkg: &str, inst_name: &str, shell_protocol: u64) -> Value {
        let tag = "v1.4.0";
        let base = format!("https://github.com/Mrchen116/nano-multiagent/releases/download/{}/", tag);
        json!({
            "version": "1.4.0",
            "source_commit": "a".repeat(40),
            "sha256": "b".repeat(64),
            "download_url": format!("{}{}", base, pkg),
            "node_major": 24,
            "pnpm_version": "11.7.0",
            "package": pkg,
            "platform": platform,
            "size": 512,
            "updater_protocol": 1,
            "data_epoch": 1,
            "shell_protocol": shell_protocol,
            "release_notes": "Faster startup and seamless updates",
            "installer": {
                "download_url": format!("{}{}", base, inst_name),
                "sha256": "c".repeat(64),
                "size": 102400
            }
        })
    }

    #[test]
    fn validates_manifests_and_classifies_hot_bundle_vs_installer_across_platforms() {
        let trusted = TrustedReleaseConfig::default();
        let mac_v1 = sample_manifest("desktop-darwin-arm64", "desktop-darwin-arm64.json", "Crewden-Desktop-arm64.dmg", CURRENT_DESKTOP_SHELL_PROTOCOL);
        let parsed_v1 = parse_desktop_release_manifest(&mac_v1, "desktop-darwin-arm64", &trusted).expect("valid v1");
        assert_eq!(
            classify_target_release("1.3.2", Some(&"0".repeat(64)), &parsed_v1),
            Some(UpdaterMode::HotBundle)
        );
        // Same release -> None (`up_to_date`), semver downgrade -> None
        assert_eq!(classify_target_release("1.4.0", Some(&"b".repeat(64)), &parsed_v1), None);
        assert_eq!(classify_target_release("1.5.0", Some(&"9".repeat(64)), &parsed_v1), None);

        // shell_protocol = 2 -> valid manifest classified as `Installer`!
        let win_v2 = sample_manifest("desktop-win32-x64", "desktop-win32-x64.json", "Crewden-Desktop-Setup-x64.exe", CURRENT_DESKTOP_SHELL_PROTOCOL + 1);
        let parsed_v2 = parse_desktop_release_manifest(&win_v2, "desktop-win32-x64", &trusted).expect("valid shell_protocol=2");
        assert_eq!(
            classify_target_release("1.3.2", Some(&"0".repeat(64)), &parsed_v2),
            Some(UpdaterMode::Installer)
        );

        // Private self-hosted base rejected unless explicitly trusted + allow_private_http
        let mut private_manifest = mac_v1.clone();
        let priv_base = "http://10.24.8.15:9000/releases/v1.4.0/";
        private_manifest["release_base_url"] = json!(priv_base);
        private_manifest["download_url"] = json!(format!("{}desktop-darwin-arm64.json", priv_base));
        private_manifest["installer"]["download_url"] = json!(format!("{}Crewden-Desktop-arm64.dmg", priv_base));
        assert!(parse_desktop_release_manifest(&private_manifest, "desktop-darwin-arm64", &trusted).is_none());
        let trusted_priv = TrustedReleaseConfig {
            trusted_bases: vec!["http://10.24.8.15:9000/releases".to_string()],
            allow_private_http: true,
        };
        assert!(parse_desktop_release_manifest(&private_manifest, "desktop-darwin-arm64", &trusted_priv).is_some());
    }

    #[test]
    fn enforces_https_redirect_anti_downgrade_and_hop_limit() {
        let cdn = Url::parse("https://objects.githubusercontent.com/github-production-release-asset/file.dmg").unwrap();
        assert!(validate_https_redirect_hop(&cdn, 0).is_ok());
        assert!(validate_https_redirect_hop(&cdn, 9).is_ok());
        assert!(validate_https_redirect_hop(&cdn, 10).is_err());

        let downgrade = Url::parse("http://objects.githubusercontent.com/file.dmg").unwrap();
        assert!(validate_https_redirect_hop(&downgrade, 0).is_err());

        let creds = Url::parse("https://user:secret@objects.githubusercontent.com/file.dmg").unwrap();
        assert!(validate_https_redirect_hop(&creds, 0).is_err());
    }

    #[test]
    fn persists_prefs_isolates_ui_pointers_and_prunes_unreferenced_cache() {
        let tmp = tempdir().unwrap();
        let paths = DesktopPaths::resolve(&DesktopCliOptions {
            isolated_root: Some(tmp.path().to_path_buf()),
            ..Default::default()
        })
        .unwrap();

        assert!(read_updater_prefs(&paths).auto_update);
        write_updater_prefs(&paths, &UpdaterPrefsFile { auto_update: false }).unwrap();
        assert!(!read_updater_prefs(&paths).auto_update);

        let keep_sha = "1".repeat(64);
        let stale_sha = "2".repeat(64);
        let cache_dir = paths.desktop_home.join("cache");
        let inst_dir = cache_dir.join("installers");
        fs::create_dir_all(&inst_dir).unwrap();
        fs::write(cache_dir.join(format!("descriptor-{}.json", keep_sha)), b"{}").unwrap();
        fs::write(cache_dir.join(format!("descriptor-{}.json", stale_sha)), b"{}").unwrap();
        fs::write(inst_dir.join(format!("{}-Crewden.dmg", stale_sha)), b"old-dmg").unwrap();

        let mut ui_file = DesktopUiActiveFile::default();
        ui_file.origins.insert(
            "https://im.crewden.work".to_string(),
            DesktopUiOriginPointer {
                version: "1.4.0".to_string(),
                sha256: keep_sha.clone(),
                version_root: paths.desktop_home.join("versions").join(&keep_sha).to_string_lossy().to_string(),
                updated_at_epoch: 1,
            },
        );
        write_ui_active_file(&paths, &ui_file).unwrap();

        prune_stale_update_cache(&paths, &[]);
        assert!(cache_dir.join(format!("descriptor-{}.json", keep_sha)).is_file());
        assert!(!cache_dir.join(format!("descriptor-{}.json", stale_sha)).exists());
        assert!(!inst_dir.join(format!("{}-Crewden.dmg", stale_sha)).exists());
    }

    #[test]
    fn preserves_route_and_query_when_appending_reload_cache_buster() {
        let busted = crate::tray::append_reload_cache_buster("/chat/conv-42?thread=msg-9&_desktop_reload=1");
        assert!(busted.starts_with("/chat/conv-42?thread=msg-9&_desktop_reload="));
        assert!(!busted.ends_with("&_desktop_reload=1"));
        assert!(crate::tray::append_reload_cache_buster("invalid").starts_with("/chat?_desktop_reload="));
    }

    #[tokio::test]
    async fn executes_pure_chat_hot_switch_foreign_owner_isolation_installer_download_and_startup_rollback() {
        use crate::config::sha256_hex;
        use crate::host_server::start_host_server_full;
        use crate::notifications::NoopUiBridge;
        use axum::{routing::get, Json, Router};
        use tokio::net::TcpListener;

        let tmp = tempdir().unwrap();
        let paths = DesktopPaths::resolve(&DesktopCliOptions {
            isolated_root: Some(tmp.path().to_path_buf()),
            ..Default::default()
        })
        .unwrap();

        let make_ready_bundle = |sha: &str, ver: &str, commit: &str, release_base: &str| -> PathBuf {
            let root = paths.desktop_home.join("versions").join(sha);
            let node_path = root.join(crate::local_node::node_rel_path());
            fs::create_dir_all(node_path.parent().unwrap()).unwrap();
            fs::create_dir_all(root.join("ui/frontend")).unwrap();
            fs::create_dir_all(root.join("ui/trajectory")).unwrap();
            fs::write(&node_path, b"#!/bin/sh\necho '{\"ok\":true,\"status\":200,\"data\":{\"ownership\":\"foreign_owner\",\"node_name\":\"ForeignBox\"}}'\n").unwrap();
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let _ = fs::set_permissions(&node_path, fs::Permissions::from_mode(0o755));
            }
            fs::write(root.join("ui/frontend/index.html"), format!("<html><body>v{}</body></html>", ver)).unwrap();
            fs::write(root.join("ui/trajectory/index.html"), "<html></html>").unwrap();
            let plat = format!("desktop-{}", current_desktop_platform_id());
            let pkg = format!("{}.json", plat);
            let inst_name = if plat == "desktop-win32-x64" {
                "Crewden-Desktop-Setup-x64.exe"
            } else {
                "Crewden-Desktop-arm64.dmg"
            };
            write_private_json(
                &root.join(".release-manifest.json"),
                &json!({
                    "version": ver,
                    "source_commit": commit,
                    "sha256": sha,
                    "download_url": format!("{}{}", release_base, pkg),
                    "release_base_url": release_base,
                    "node_major": 24,
                    "pnpm_version": "11.7.0",
                    "package": pkg,
                    "platform": plat,
                    "size": 256,
                    "updater_protocol": 1,
                    "data_epoch": 1,
                    "shell_protocol": CURRENT_DESKTOP_SHELL_PROTOCOL,
                    "installer": {
                        "download_url": format!("{}{}", release_base, inst_name),
                        "sha256": "d".repeat(64),
                        "size": 128
                    }
                }),
            )
            .unwrap();
            fs::write(root.join(".ready"), format!("{}\n", sha)).unwrap();
            root
        };

        let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
        let im_port = listener.local_addr().unwrap().port();
        let im_origin = format!("http://127.0.0.1:{}", im_port);
        let release_base = format!("{}/releases/", im_origin);

        // Configure trusted self-hosted loopback release base in desktop-defaults.json
        write_private_json(
            &paths.desktop_defaults_path(),
            &json!({
                "default_im_origin": im_origin,
                "trusted_release_base_url": release_base,
                "allow_private_http_release_base": true
            }),
        )
        .unwrap();

        let sha_v1 = "1".repeat(64);
        let sha_v2 = "2".repeat(64);
        let root_v1 = make_ready_bundle(&sha_v1, "1.3.2", &"a".repeat(40), &release_base);
        let _root_v2 = make_ready_bundle(&sha_v2, "1.4.0", &"b".repeat(40), &release_base);

        // Seed marker at v1.3.2
        write_private_json(
            &paths.seed_marker_path(),
            &json!({
                "version": "1.3.2",
                "sha256": sha_v1,
                "runtime_sha256": "r".repeat(64),
                "version_root": root_v1.to_string_lossy()
            }),
        )
        .unwrap();

        // Plant a foreign-owner `.desktop-active.json` to ensure pure-chat update NEVER touches it!
        let foreign_conn = paths.connection_dir(&im_origin).unwrap();
        fs::create_dir_all(&foreign_conn).unwrap();
        fs::write(
            foreign_conn.join("config.yaml"),
            r#"{"node":{"node_id":"foreign-1","user_id":"other-user"}}"#,
        )
        .unwrap();
        let foreign_active_path = foreign_conn.join(".desktop-active.json");
        write_private_json(
            &foreign_active_path,
            &json!({
                "managed_by": "crewden-desktop",
                "version": "1.3.2",
                "sha256": sha_v1,
                "version_root": root_v1.to_string_lossy()
            }),
        )
        .unwrap();

        let plat = format!("desktop-{}", current_desktop_platform_id());
        let pkg = format!("{}.json", plat);
        let inst_name = if plat == "desktop-win32-x64" {
            "Crewden-Desktop-Setup-x64.exe"
        } else {
            "Crewden-Desktop-arm64.dmg"
        };
        let fake_installer_bytes = b"verified-installer-binary-payload-v200".to_vec();
        let fake_installer_sha = sha256_hex(&fake_installer_bytes);

        let manifest_state = Arc::new(Mutex::new(json!({
            "version": "1.4.0",
            "source_commit": "b".repeat(40),
            "sha256": sha_v2,
            "download_url": format!("{}{}", release_base, pkg),
            "release_base_url": release_base,
            "node_major": 24,
            "pnpm_version": "11.7.0",
            "package": pkg,
            "platform": plat,
            "size": 256,
            "updater_protocol": 1,
            "data_epoch": 1,
            "shell_protocol": CURRENT_DESKTOP_SHELL_PROTOCOL,
            "release_notes": "Hot switch note",
            "installer": {
                "download_url": format!("{}{}", release_base, inst_name),
                "sha256": fake_installer_sha,
                "size": fake_installer_bytes.len()
            }
        })));

        let ms_clone = manifest_state.clone();
        let inst_bytes_clone = fake_installer_bytes.clone();
        let manifest_route = format!("/install/manifest.{}.json", plat);
        let inst_route = format!("/releases/{}", inst_name);
        let app = Router::new()
            .route(
                &manifest_route,
                get(move || {
                    let val = ms_clone.lock().unwrap().clone();
                    async move { Json(val) }
                }),
            )
            .route(
                &inst_route,
                get(move || {
                    let b = inst_bytes_clone.clone();
                    async move { b }
                }),
            );
        tokio::spawn(async move {
            let _ = axum::serve(listener, app).await;
        });

        let ui = Arc::new(NoopUiBridge::default());
        ui.attention.write().unwrap().window_visible = true;
        ui.attention.write().unwrap().visible_and_focused = false;
        ui.attention.write().unwrap().current_route = "/chat/conv-9".to_string();

        // Temporarily disable auto_update before server boot so startup promotion can be tested deterministically too
        write_updater_prefs(&paths, &UpdaterPrefsFile { auto_update: true }).unwrap();
        // Keep window_visible=true -> unfocused visible window MUST NOT auto-reload, only reach `ready_to_switch`!
        let mut server = start_host_server_full(
            paths.clone(),
            Some(&im_origin),
            None,
            None,
            None,
            ui.clone(),
        )
        .await
        .unwrap();
        // Reset startup promotion to v1.3.2 to exercise online `check_for_updates` -> `apply_desktop_update`
        write_ui_active_file(&paths, &DesktopUiActiveFile::default()).unwrap();
        clear_startup_promotion_backup(&server.state, &im_origin);

        try_promote_staged_update_on_startup(&server.state, &im_origin, None);
        assert_eq!(resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version, "1.3.2");
        let snap1 = check_for_updates(server.state.clone(), true).await;
        assert_eq!(snap1.phase, "ready_to_switch");
        assert_eq!(snap1.current_version, "1.3.2");
        assert_eq!(snap1.target.as_ref().unwrap().version, "1.4.0");
        let gen_before = snap1.reload_generation;
        let hot_offer = fs::read(advertised_manifest_path(&paths, &im_origin)).unwrap();

        // Apply hot switch while foreign_owner node exists on disk -> switches UI to 1.4.0 WITHOUT touching foreign `.desktop-active.json`!
        let snap2 = apply_desktop_update(server.state.clone(), None).await.unwrap();
        assert_eq!(snap2.phase, "switching");
        finish_ui_boot(&server.state, &im_origin, &sha_v2, false);
        assert_eq!(resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version, "1.3.2");
        check_for_updates(server.state.clone(), true).await;
        apply_desktop_update(server.state.clone(), None).await.unwrap();
        finish_ui_boot(&server.state, &im_origin, &sha_v2, true);
        let snap2 = build_updater_snapshot(&server.state);
        assert_eq!(snap2.phase, "up_to_date");
        assert_eq!(snap2.current_version, "1.4.0");
        assert_eq!(snap2.just_updated_version.as_deref(), Some("1.4.0"));
        assert!(snap2.reload_generation > gen_before);
        let foreign_after: Value = serde_json::from_str(&fs::read_to_string(&foreign_active_path).unwrap()).unwrap();
        assert_eq!(foreign_after["version"], json!("1.3.2"), "Foreign node pointer must remain untouched");

        // Now publish shell_protocol=2 installer manifest -> seamless download, SHA-256 verify, and launch log!
        {
            let mut m = manifest_state.lock().unwrap();
            m["version"] = json!("2.0.0");
            m["sha256"] = json!("3".repeat(64));
            m["shell_protocol"] = json!(CURRENT_DESKTOP_SHELL_PROTOCOL + 1);
        }
        let snap3 = check_for_updates(server.state.clone(), true).await;
        assert_eq!(snap3.phase, "available");
        assert_eq!(snap3.mode, Some(UpdaterMode::Installer));

        let _ = apply_desktop_update(server.state.clone(), None).await.unwrap();
        for _ in 0..40 {
            if build_updater_snapshot(&server.state).phase == "installer_ready" {
                break;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        let snap4 = build_updater_snapshot(&server.state);
        assert_eq!(snap4.phase, "installer_ready");

        std::env::set_var("CREWDEN_SUPPRESS_OS_OPEN", "1");
        open_downloaded_installer(&server.state).unwrap();
        let actions_raw = fs::read_to_string(paths.open_actions_log_path()).unwrap();
        assert!(actions_raw.contains("launch_installer"));
        assert!(actions_raw.contains(&fake_installer_sha));

        // Verify startup promotion rollback restores previous bundle and blocks re-promotion of broken sha
        write_ui_active_file(&paths, &DesktopUiActiveFile::default()).unwrap();
        fs::remove_dir_all(&foreign_conn).unwrap();
        fs::write(advertised_manifest_path(&paths, &im_origin), hot_offer).unwrap();
        try_promote_staged_update_on_startup(&server.state, &im_origin, None);
        assert_eq!(
            resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version,
            "1.4.0"
        );
        assert!(rollback_startup_promotion_if_needed(&server.state, &im_origin));
        assert_eq!(
            resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version,
            "1.3.2"
        );
        assert_eq!(
            build_updater_snapshot(&server.state).error_code.as_deref(),
            Some("switch_rolled_back")
        );

        // Verify real multi-line `js-yaml` `config.yaml` startup promotion, rollback, and `on_internal_reload_assets` sync!
        assert_eq!(
            parse_node_owner_id_from_config(
                "agents:\n  - agent_id: a1\n    user_id: wrong-nested\nnode:\n  node_id: computer-1234\n  user_id: owner-alice # comment\n  node_name: Studio-Mac\n"
            ),
            Some("owner-alice".to_string())
        );
        assert_eq!(
            parse_node_owner_id_from_config("node:\n  user_id: 'owner''s-id'\n"),
            Some("owner's-id".to_string())
        );
        assert_eq!(
            parse_node_owner_id_from_config("node:\n  user_id: \"owner-quoted\"\n"),
            Some("owner-quoted".to_string())
        );
        assert_eq!(
            parse_node_owner_id_from_config("node:\n  user_id: ''\n"),
            None
        );

        // Clear rollback_blocked and plant a real YAML `config.yaml` owned by `owner-alice`
        write_ui_active_file(&paths, &DesktopUiActiveFile::default()).unwrap();
        server.state.sessions.write().unwrap().by_origin.insert(
            im_origin.clone(),
            crate::config::StoredSessionEntry {
                refresh_token: "rt-1".to_string(),
                user_id: "owner-alice".to_string(),
                owner_id: "owner-alice".to_string(),
                username: "alice".to_string(),
                updated_at: 1,
            },
        );
        let alice_conn = paths.connection_dir(&im_origin).unwrap();
        fs::create_dir_all(&alice_conn).unwrap();
        fs::write(
            alice_conn.join("config.yaml"),
            "node:\n  node_id: node-alice\n  user_id: owner-alice\n  node_name: Alice-Mac\nim_service:\n  url: http://127.0.0.1\n  token: tok\n",
        )
        .unwrap();
        let alice_active_path = alice_conn.join(".desktop-active.json");
        write_private_json(
            &alice_active_path,
            &json!({
                "managed_by": "crewden-desktop",
                "version": "1.3.2",
                "sha256": sha_v1,
                "version_root": root_v1.to_string_lossy()
            }),
        )
        .unwrap();

        try_promote_staged_update_on_startup(&server.state, &im_origin, Some("owner-alice"));
        assert_eq!(resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version, "1.4.0");
        assert_eq!(resolve_active_bundle(&paths, &im_origin, None).unwrap().version, "1.4.0");

        // Startup failure rolls back BOTH `desktop-ui-active.json` AND `.desktop-active.json`!
        assert!(rollback_startup_promotion_if_needed(&server.state, &im_origin));
        assert_eq!(resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version, "1.3.2");
        assert_eq!(resolve_active_bundle(&paths, &im_origin, None).unwrap().version, "1.3.2");

        // Remote upgrade via `.desktop-active.json` + `on_internal_reload_assets` advances UI to 1.4.0,
        // and subsequent worker rollback to 1.3.2 syncs UI back to 1.3.2 and clears `just_updated`!
        remember_served_ui(&paths, &im_origin, &resolve_active_ui_bundle(&paths, &im_origin, None).unwrap());
        let root_v2 = paths.desktop_home.join("versions").join(&sha_v2);
        write_private_json(
            &alice_active_path,
            &json!({
                "managed_by": "crewden-desktop",
                "version": "1.4.0",
                "sha256": sha_v2,
                "version_root": root_v2.to_string_lossy()
            }),
        )
        .unwrap();
        let generation = server.state.updater.reload_generation.load(Ordering::SeqCst);
        on_internal_reload_assets(&server.state, Some("https://previous.example"));
        assert_eq!(server.state.updater.reload_generation.load(Ordering::SeqCst), generation);
        on_internal_reload_assets(&server.state, Some(&im_origin));
        assert_eq!(resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version, "1.4.0");
        assert_eq!(build_updater_snapshot(&server.state).phase, "switching");
        finish_ui_boot(&server.state, &im_origin, &sha_v2, true);
        assert_eq!(build_updater_snapshot(&server.state).just_updated_version.as_deref(), Some("1.4.0"));

        write_private_json(
            &alice_active_path,
            &json!({
                "managed_by": "crewden-desktop",
                "version": "1.3.2",
                "sha256": sha_v1,
                "version_root": root_v1.to_string_lossy()
            }),
        )
        .unwrap();
        on_internal_reload_assets(&server.state, Some(&im_origin));
        assert_eq!(resolve_active_ui_bundle(&paths, &im_origin, None).unwrap().version, "1.3.2");
        assert_eq!(build_updater_snapshot(&server.state).just_updated_version, None);

        // Verify `capsule` dismiss + `reopen_capsule` host-synced roundtrip
        {
            let mut map = server.state.updater.by_origin.lock().unwrap();
            let rt = map.entry(im_origin.clone()).or_default();
            rt.phase = "ready_to_switch".to_string();
            rt.mode = Some(UpdaterMode::HotBundle);
            let parsed_m = serde_json::from_value::<Value>(manifest_state.lock().unwrap().clone()).unwrap();
            let mut m140 = parsed_m;
            m140["version"] = json!("1.4.0");
            m140["sha256"] = json!(sha_v2);
            m140["shell_protocol"] = json!(CURRENT_DESKTOP_SHELL_PROTOCOL);
            rt.target = parse_desktop_release_manifest(
                &m140,
                &plat,
                &TrustedReleaseConfig {
                    trusted_bases: vec![release_base.trim_end_matches('/').to_string()],
                    allow_private_http: true,
                },
            );
        }
        let dismissed = dismiss_updater_notice(&server.state, "capsule");
        assert!(dismissed.capsule_dismissed);
        let reopened = dismiss_updater_notice(&server.state, "reopen_capsule");
        assert!(!reopened.capsule_dismissed);

        let _ = server.take_shutdown_receiver();
    }
}
