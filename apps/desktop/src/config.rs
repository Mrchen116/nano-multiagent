use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use url::Url;

#[derive(Debug, Clone, Default)]
pub struct DesktopCliOptions {
    pub isolated_root: Option<PathBuf>,
    pub background: bool,
    pub stop: bool,
    pub headless_host: bool,
    pub prepare_seed: bool,
    pub im_origin: Option<String>,
    pub initial_route: Option<String>,
    pub deep_link_url: Option<String>,
    pub seed_archives_dir: Option<PathBuf>,
    pub dev_repo_root: Option<PathBuf>,
}

impl DesktopCliOptions {
    pub fn parse_from<I, S>(args: I) -> Result<Self, String>
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        let mut opts = DesktopCliOptions::default();
        let vec: Vec<String> = args.into_iter().map(Into::into).collect();
        let mut idx = 1;
        while idx < vec.len() {
            let arg = &vec[idx];
            match arg.as_str() {
                "--isolated-root" => {
                    idx += 1;
                    let val = vec
                        .get(idx)
                        .ok_or_else(|| "--isolated-root requires a directory path".to_string())?;
                    opts.isolated_root = Some(PathBuf::from(val));
                }
                "--background" => {
                    opts.background = true;
                }
                "--stop" => {
                    opts.stop = true;
                }
                "--prepare-seed" => opts.prepare_seed = true,
                "--headless-host" => {
                    opts.headless_host = true;
                }
                "--im-origin" => {
                    idx += 1;
                    let val = vec
                        .get(idx)
                        .ok_or_else(|| "--im-origin requires an HTTP(S) URL".to_string())?;
                    opts.im_origin = Some(normalize_im_origin(val)?);
                }
                "--seed-archives-dir" => {
                    idx += 1;
                    let val = vec
                        .get(idx)
                        .ok_or_else(|| "--seed-archives-dir requires a path".to_string())?;
                    opts.seed_archives_dir = Some(PathBuf::from(val));
                }
                "--dev-repo-root" => {
                    idx += 1;
                    let val = vec
                        .get(idx)
                        .ok_or_else(|| "--dev-repo-root requires a path".to_string())?;
                    opts.dev_repo_root = Some(PathBuf::from(val));
                }
                other if other.starts_with("crewden-desktop://") => {
                    opts.deep_link_url = Some(other.to_string());
                    if let Ok(Some(route)) = parse_deep_link_route(other) {
                        opts.initial_route = Some(route);
                    }
                }
                _ => {}
            }
            idx += 1;
        }
        Ok(opts)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImOriginSecurity {
    Https,
    LoopbackHttp,
    PrivateHttp,
    RejectedPublicHttp,
}

impl ImOriginSecurity {
    pub fn is_cleartext_http(self) -> bool {
        matches!(self, Self::LoopbackHttp | Self::PrivateHttp | Self::RejectedPublicHttp)
    }
}

/// Classify an IM server origin using strict IPv4/IPv6 literal parsing and reserved-domain rules.
///
/// Official `crewden.work` / `*.crewden.work` and public hosts always reject cleartext `http://`.
pub fn classify_im_origin(raw: &str) -> Result<(String, ImOriginSecurity), String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("IM server URL cannot be empty".to_string());
    }
    // Reject non-standard leading-zero IPv4 octets before `Url::parse` normalizes them as octal.
    if let Some(after_scheme) = trimmed
        .strip_prefix("http://")
        .or_else(|| trimmed.strip_prefix("https://"))
    {
        let authority = after_scheme.split(['/', '?', '#']).next().unwrap_or("");
        let host_part = authority.split(':').next().unwrap_or("");
        if !host_part.is_empty()
            && host_part.split('.').count() == 4
            && host_part.bytes().all(|b| b.is_ascii_digit() || b == b'.')
            && host_part
                .split('.')
                .any(|seg| seg.len() > 1 && seg.starts_with('0'))
        {
            return Err("IPv4 octets must not use leading zeros".to_string());
        }
    }
    let parsed = Url::parse(trimmed).map_err(|_| "Invalid IM server URL".to_string())?;
    if parsed.scheme() != "https" && parsed.scheme() != "http" {
        return Err("Only http:// and https:// IM server URLs are supported".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("IM server URL must not embed credentials".to_string());
    }
    if parsed.query().is_some()
        || parsed.fragment().is_some()
        || (parsed.path() != "/" && !parsed.path().is_empty())
    {
        return Err("IM server URL must not include a subpath, query, or fragment".to_string());
    }
    let host_str = parsed
        .host_str()
        .ok_or_else(|| "IM server URL must include a host".to_string())?;
    let lower_host = host_str.to_ascii_lowercase();
    let mut origin = format!("{}://{}", parsed.scheme(), lower_host);
    if let Some(port) = parsed.port() {
        origin.push_str(&format!(":{}", port));
    }

    if parsed.scheme() == "https" {
        return Ok((origin, ImOriginSecurity::Https));
    }
    if lower_host == "crewden.work" || lower_host.ends_with(".crewden.work") {
        return Ok((origin, ImOriginSecurity::RejectedPublicHttp));
    }

    match parsed.host() {
        Some(url::Host::Ipv4(ipv4)) => {
            if ipv4.is_loopback() {
                Ok((origin, ImOriginSecurity::LoopbackHttp))
            } else if ipv4.is_private() {
                Ok((origin, ImOriginSecurity::PrivateHttp))
            } else {
                Ok((origin, ImOriginSecurity::RejectedPublicHttp))
            }
        }
        Some(url::Host::Ipv6(ipv6)) => {
            if ipv6.is_loopback() {
                Ok((origin, ImOriginSecurity::LoopbackHttp))
            } else {
                let seg0 = ipv6.segments()[0];
                if (seg0 & 0xfe00) == 0xfc00 || (seg0 & 0xffc0) == 0xfe80 {
                    Ok((origin, ImOriginSecurity::PrivateHttp))
                } else {
                    Ok((origin, ImOriginSecurity::RejectedPublicHttp))
                }
            }
        }
        Some(url::Host::Domain(domain)) => {
            let d = domain.to_ascii_lowercase();
            if d == "localhost" {
                Ok((origin, ImOriginSecurity::LoopbackHttp))
            } else if d.ends_with(".local") && d.len() > ".local".len() && !d.starts_with('.') {
                Ok((origin, ImOriginSecurity::PrivateHttp))
            } else {
                Ok((origin, ImOriginSecurity::RejectedPublicHttp))
            }
        }
        None => Err("IM server URL must include a host".to_string()),
    }
}

/// Normalize and validate an IM server origin (`https://...`, loopback `http://...`, or RFC1918/RFC4193/`.local` private `http://...`).
pub fn normalize_im_origin(raw: &str) -> Result<String, String> {
    let (origin, security) = classify_im_origin(raw)?;
    if security == ImOriginSecurity::RejectedPublicHttp {
        return Err(
            "官方与公网 IM 服务必须使用 https:// 加密连接（仅本机回环或局域网私有地址允许 http://）"
                .to_string(),
        );
    }
    Ok(origin)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DeepLinkConnectOutcome {
    NotConnectUrl,
    Valid {
        origin: String,
        is_cleartext_http: bool,
    },
    RejectedPublicHttp {
        attempted_origin: String,
    },
    Invalid(String),
}

/// Classify `crewden-desktop://connect?origin=<encoded>` without mutating saved configuration.
pub fn classify_deep_link_connect(raw: &str) -> DeepLinkConnectOutcome {
    let Ok(parsed) = Url::parse(raw.trim()) else {
        return DeepLinkConnectOutcome::Invalid("Malformed crewden-desktop:// URL".to_string());
    };
    if parsed.scheme() != "crewden-desktop" {
        return DeepLinkConnectOutcome::NotConnectUrl;
    }
    let action = parsed.host_str().unwrap_or("");
    if action != "connect" && parsed.path().trim_matches('/') != "connect" {
        return DeepLinkConnectOutcome::NotConnectUrl;
    }
    for (k, v) in parsed.query_pairs() {
        if k == "origin" {
            return match classify_im_origin(&v) {
                Ok((origin, ImOriginSecurity::RejectedPublicHttp)) => {
                    DeepLinkConnectOutcome::RejectedPublicHttp {
                        attempted_origin: origin,
                    }
                }
                Ok((origin, security)) => DeepLinkConnectOutcome::Valid {
                    origin,
                    is_cleartext_http: security.is_cleartext_http(),
                },
                Err(reason) => DeepLinkConnectOutcome::Invalid(reason),
            };
        }
    }
    DeepLinkConnectOutcome::Invalid("Missing origin parameter".to_string())
}

/// Parse `crewden-desktop://connect?origin=<encoded>` safely, rejecting public cleartext HTTP or bad schemes.
pub fn parse_deep_link_origin(raw: &str) -> Result<Option<String>, String> {
    match classify_deep_link_connect(raw) {
        DeepLinkConnectOutcome::NotConnectUrl => Ok(None),
        DeepLinkConnectOutcome::Valid { origin, .. } => Ok(Some(origin)),
        DeepLinkConnectOutcome::RejectedPublicHttp { attempted_origin } => Err(format!(
            "Deep-link origin {} must use https://",
            attempted_origin
        )),
        DeepLinkConnectOutcome::Invalid(reason) => Err(reason),
    }
}

/// Parse `crewden-desktop://open?route=<encoded>` safely for OS notification click routing.
pub fn parse_deep_link_route(raw: &str) -> Result<Option<String>, String> {
    let parsed = Url::parse(raw.trim()).map_err(|_| "Malformed crewden-desktop:// URL".to_string())?;
    if parsed.scheme() != "crewden-desktop" {
        return Ok(None);
    }
    let action = parsed.host_str().unwrap_or("");
    if action != "open" && parsed.path().trim_matches('/') != "open" {
        return Ok(None);
    }
    for (k, v) in parsed.query_pairs() {
        if k == "route" {
            let trimmed = v.trim();
            if !trimmed.starts_with('/') || trimmed.starts_with("//") || trimmed.chars().any(|c| c.is_control()) {
                return Err("Deep-link route must be a safe app-relative path".to_string());
            }
            return Ok(Some(trimmed.to_string()));
        }
    }
    Ok(None)
}

pub fn current_desktop_platform_id() -> &'static str {
    if cfg!(target_os = "windows") {
        "win32-x64"
    } else {
        "darwin-arm64"
    }
}

pub fn random_hex_token(bytes_len: usize) -> String {
    let mut buf = vec![0u8; bytes_len];
    rand::thread_rng().fill_bytes(&mut buf);
    hex_encode(&buf)
}

pub fn hex_encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

pub fn sha256_hex(input: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input);
    hex_encode(&hasher.finalize())
}

#[derive(Debug, Clone)]
pub struct DesktopPaths {
    pub desktop_home: PathBuf,
    pub nano_install_root: PathBuf,
    pub test_autostart_dir: Option<PathBuf>,
}

impl DesktopPaths {
    pub fn resolve(cli: &DesktopCliOptions) -> Result<Self, String> {
        if let Some(ref root) = cli.isolated_root {
            let abs = if root.is_absolute() {
                root.clone()
            } else {
                std::env::current_dir()
                    .map_err(|e| e.to_string())?
                    .join(root)
            };
            let desktop_home = abs.join("desktop");
            let nano_install_root = abs.join("nano");
            let autostart_dir = abs.join("autostart");
            fs::create_dir_all(&desktop_home).map_err(|e| e.to_string())?;
            fs::create_dir_all(&nano_install_root).map_err(|e| e.to_string())?;
            fs::create_dir_all(&autostart_dir).map_err(|e| e.to_string())?;
            return Ok(Self {
                desktop_home,
                nano_install_root,
                test_autostart_dir: Some(autostart_dir),
            });
        }

        let home = home_dir().ok_or_else(|| "Cannot determine user home directory".to_string())?;
        let desktop_home = if let Ok(env_home) = std::env::var("CREWDEN_DESKTOP_HOME") {
            PathBuf::from(env_home)
        } else if cfg!(target_os = "windows") {
            let local_app_data = std::env::var("LOCALAPPDATA")
                .map(PathBuf::from)
                .unwrap_or_else(|_| home.join("AppData").join("Local"));
            local_app_data.join("CrewdenDesktop")
        } else {
            home.join("Library")
                .join("Application Support")
                .join("CrewdenDesktop")
        };

        let nano_install_root = std::env::var("NANO_INSTALL_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|_| home.join(".nanoassistant"));

        let test_autostart_dir = std::env::var("NANO_TEST_AUTOSTART_DIR")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .map(PathBuf::from);

        fs::create_dir_all(&desktop_home).map_err(|e| e.to_string())?;
        if let Some(ref d) = test_autostart_dir {
            fs::create_dir_all(d).map_err(|e| e.to_string())?;
        }
        Ok(Self {
            desktop_home,
            nano_install_root,
            test_autostart_dir,
        })
    }

    pub fn host_config_path(&self) -> PathBuf {
        self.desktop_home.join("host-config.json")
    }

    pub fn host_state_path(&self) -> PathBuf {
        self.desktop_home.join("host-state.json")
    }

    pub fn sessions_path(&self) -> PathBuf {
        self.desktop_home.join("sessions.json")
    }

    pub fn open_actions_log_path(&self) -> PathBuf {
        self.desktop_home.join("open-actions.jsonl")
    }

    pub fn notifications_log_path(&self) -> PathBuf {
        self.desktop_home.join("notifications.jsonl")
    }

    pub fn seed_marker_path(&self) -> PathBuf {
        self.desktop_home.join("seed-current.json")
    }

    pub fn desktop_defaults_path(&self) -> PathBuf {
        self.desktop_home.join("desktop-defaults.json")
    }

    pub fn instance_lock_path(&self) -> PathBuf {
        self.desktop_home.join("instance.lock")
    }

    pub fn host_log_path(&self) -> PathBuf {
        self.desktop_home.join("desktop-host.log")
    }

    pub fn is_isolated_autostart(&self) -> bool {
        self.test_autostart_dir.is_some()
    }

    pub fn connection_dir(&self, im_origin: &str) -> Result<PathBuf, String> {
        let normalized = normalize_im_origin(im_origin)?;
        let hash = &sha256_hex(normalized.as_bytes())[..16];
        Ok(self.nano_install_root.join("connections").join(hash))
    }

    pub fn connection_config_path(&self, im_origin: &str) -> Result<PathBuf, String> {
        Ok(self.connection_dir(im_origin)?.join("config.yaml"))
    }

    pub fn desktop_active_path(&self, im_origin: &str) -> Result<PathBuf, String> {
        Ok(self.connection_dir(im_origin)?.join(".desktop-active.json"))
    }
}

/// Platform-parameterized local IPC endpoint resolver verified against `src/IM/shared/local-ipc-endpoint-test-cases.json`.
pub fn local_node_bridge_endpoint_for_platform(
    config_str: &str,
    is_windows: bool,
    tmpdir: &str,
) -> String {
    if is_windows {
        let digest = &sha256_hex(config_str.to_lowercase().as_bytes())[..24];
        return format!(r"\\.\pipe\crewden-desktop-node-{}", digest);
    }
    let digest = &sha256_hex(config_str.as_bytes())[..20];
    let parent = config_str
        .rsplit_once('/')
        .map(|(dir, _)| if dir.is_empty() { "/" } else { dir })
        .unwrap_or("/tmp");
    let candidate = if parent == "/" {
        "/.desktop-node.sock".to_string()
    } else {
        format!("{}/.desktop-node.sock", parent)
    };
    if candidate.as_bytes().len() <= 96 {
        return candidate;
    }
    format!(
        "{}/crewden-node-{}.sock",
        tmpdir.trim_end_matches('/'),
        digest
    )
}

/// Exact counterpart to `localNodeBridgeEndpoint` in `apps/node/src/platform-io.ts`.
pub fn local_node_bridge_endpoint(config_path: &Path) -> String {
    let config_str = config_path.to_string_lossy();
    let tmp = std::env::var("TMPDIR").unwrap_or_else(|_| "/tmp".to_string());
    local_node_bridge_endpoint_for_platform(&config_str, cfg!(target_os = "windows"), &tmp)
}

pub fn home_dir() -> Option<PathBuf> {
    if cfg!(target_os = "windows") {
        std::env::var("USERPROFILE").ok().map(PathBuf::from)
    } else {
        std::env::var("HOME").ok().map(PathBuf::from)
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DesktopDefaultsFile {
    #[serde(default)]
    pub default_im_origin: Option<String>,
    #[serde(default)]
    pub trusted_release_base_url: Option<String>,
    #[serde(default)]
    pub allow_private_http_release_base: Option<bool>,
}

/// Resolve the default IM origin from `<desktop_home>/desktop-defaults.json`,
/// bundled `seed-archives/desktop-defaults.json`, `CREWDEN_DEFAULT_IM_ORIGIN`, or `https://im.crewden.work`.
pub fn resolve_default_im_origin(paths: &DesktopPaths, seed_dir: Option<&Path>) -> String {
    let mut candidate_paths = vec![paths.desktop_defaults_path()];
    if let Some(dir) = seed_dir {
        candidate_paths.push(dir.join("desktop-defaults.json"));
    }
    for p in candidate_paths {
        if let Ok(raw) = fs::read_to_string(&p) {
            if let Ok(defaults) = serde_json::from_str::<DesktopDefaultsFile>(&raw) {
                if let Some(ref origin) = defaults.default_im_origin {
                    if let Ok(normalized) = normalize_im_origin(origin) {
                        return normalized;
                    }
                }
            }
        }
    }
    std::env::var("CREWDEN_DEFAULT_IM_ORIGIN")
        .ok()
        .and_then(|v| normalize_im_origin(&v).ok())
        .unwrap_or_else(|| "https://im.crewden.work".to_string())
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PendingServerSwitch {
    pub target_origin: String,
    pub is_cleartext_http: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersistedHostConfig {
    pub persisted_port: u16,
    pub im_origin: String,
    pub context_epoch: u64,
}

impl Default for PersistedHostConfig {
    fn default() -> Self {
        let default_origin = std::env::var("CREWDEN_DEFAULT_IM_ORIGIN")
            .ok()
            .and_then(|v| normalize_im_origin(&v).ok())
            .unwrap_or_else(|| "https://im.crewden.work".to_string());
        Self {
            persisted_port: 0,
            im_origin: default_origin,
            context_epoch: 1,
        }
    }
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HostRuntimeStateFile {
    pub pid: u32,
    pub port: u16,
    pub ready: bool,
    #[serde(default = "default_true")]
    pub host_ready: bool,
    #[serde(default = "default_true")]
    pub seed_ready: bool,
    pub im_origin: String,
    pub reload_token: String,
    pub boot_nonce: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredSessionEntry {
    pub user_id: String,
    pub owner_id: String,
    pub username: String,
    pub refresh_token: String,
    pub updated_at: u64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct StoredSessionsFile {
    pub by_origin: HashMap<String, StoredSessionEntry>,
}

pub fn write_private_json<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("Create directory {}: {e}", parent.display()))?;
    }
    let bytes = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
    let tmp = path.with_extension(format!("tmp-{}-{}", std::process::id(), random_hex_token(4)));
    fs::write(&tmp, &bytes).map_err(|e| format!("Write {}: {e}", tmp.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&tmp, fs::Permissions::from_mode(0o600));
    }
    fs::rename(&tmp, path).map_err(|e| format!("Rename {} to {}: {e}", tmp.display(), path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(path, fs::Permissions::from_mode(0o600));
    }
    Ok(())
}

pub fn append_private_jsonl<T: Serialize>(path: &Path, value: &T) {
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(mut line) = serde_json::to_vec(value) {
        line.push(b'\n');
        use std::io::Write;
        if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(path) {
            let _ = file.write_all(&line);
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = fs::set_permissions(path, fs::Permissions::from_mode(0o600));
        }
    }
}

pub fn append_host_log(paths: Option<&DesktopPaths>, level: &str, message: &str) -> PathBuf {
    let target = paths
        .map(|p| p.host_log_path())
        .unwrap_or_else(|| std::env::temp_dir().join("crewden-desktop-host.log"));
    if let Some(parent) = target.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let line = format!(
        "[{}] [{}] [pid={}] {}\n",
        ts,
        level,
        std::process::id(),
        message.replace('\n', " ")
    );
    use std::io::Write;
    if let Ok(mut file) = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&target)
    {
        let _ = file.write_all(line.as_bytes());
    }
    target
}

/// Show a native OS alert dialog when `windows_subsystem = "windows"` hides stderr on fatal startup errors.
pub fn show_fatal_startup_dialog(message: &str, log_path: &Path) {
    if std::env::var("CREWDEN_SUPPRESS_OS_OPEN").as_deref() == Ok("1") {
        return;
    }
    let full_msg = format!(
        "Crewden Desktop 启动失败：{}\n\n诊断日志已写入：\n{}",
        message,
        log_path.display()
    );
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let _ = std::process::Command::new("powershell.exe")
            .creation_flags(CREATE_NO_WINDOW)
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($env:CREWDEN_FATAL_MSG, 'Crewden Desktop', 'OK', 'Error') | Out-Null",
            ])
            .env("CREWDEN_FATAL_MSG", &full_msg)
            .status();
    }
    #[cfg(target_os = "macos")]
    {
        let _ = std::process::Command::new("/usr/bin/osascript")
            .args([
                "-e",
                "on run argv",
                "-e",
                "display alert \"Crewden Desktop 启动失败\" message (item 1 of argv) as critical",
                "-e",
                "end run",
                "--",
                &full_msg,
            ])
            .status();
    }
}

/// Non-blocking OS-exclusive single-instance lock (`flock(LOCK_EX|LOCK_NB)` on Unix, `share_mode(0)` on Windows).
pub struct InstanceLock {
    _file: fs::File,
}

impl InstanceLock {
    pub fn try_acquire(lock_path: &Path) -> Result<Option<Self>, String> {
        if let Some(parent) = lock_path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        #[cfg(unix)]
        {
            use std::os::unix::io::AsRawFd;
            extern "C" {
                fn flock(fd: std::os::raw::c_int, operation: std::os::raw::c_int) -> std::os::raw::c_int;
            }
            const LOCK_EX: std::os::raw::c_int = 2;
            const LOCK_NB: std::os::raw::c_int = 4;
            let file = fs::OpenOptions::new()
                .create(true)
                .read(true)
                .write(true)
                .truncate(false)
                .open(lock_path)
                .map_err(|e| format!("Cannot open instance lock {}: {}", lock_path.display(), e))?;
            let rc = unsafe { flock(file.as_raw_fd(), LOCK_EX | LOCK_NB) };
            if rc == 0 {
                return Ok(Some(Self { _file: file }));
            }
            let err = std::io::Error::last_os_error();
            if err.kind() == std::io::ErrorKind::WouldBlock
                || matches!(err.raw_os_error(), Some(35) | Some(11))
            {
                return Ok(None);
            }
            Err(format!("Failed to lock {}: {}", lock_path.display(), err))
        }
        #[cfg(windows)]
        {
            use std::os::windows::fs::OpenOptionsExt;
            match fs::OpenOptions::new()
                .create(true)
                .read(true)
                .write(true)
                .share_mode(0)
                .open(lock_path)
            {
                Ok(file) => Ok(Some(Self { _file: file })),
                Err(err) if matches!(err.raw_os_error(), Some(32) | Some(33)) => Ok(None),
                Err(err) => Err(format!("Failed to lock {}: {}", lock_path.display(), err)),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_deep_link_and_enforces_strict_origin_security() {
        let ok = parse_deep_link_origin(
            "crewden-desktop://connect?origin=https%3A%2F%2Fim.crewden.work%2F",
        )
        .unwrap();
        assert_eq!(ok.as_deref(), Some("https://im.crewden.work"));

        let loopback = parse_deep_link_origin(
            "crewden-desktop://connect?origin=http%3A%2F%2F127.0.0.1%3A18080",
        )
        .unwrap();
        assert_eq!(loopback.as_deref(), Some("http://127.0.0.1:18080"));

        // Private RFC1918 LAN HTTP is allowed as cleartext HTTP with confirmation.
        assert_eq!(
            classify_deep_link_connect(
                "crewden-desktop://connect?origin=http%3A%2F%2F10.24.8.15%3A8011"
            ),
            DeepLinkConnectOutcome::Valid {
                origin: "http://10.24.8.15:8011".to_string(),
                is_cleartext_http: true,
            }
        );

        // Public domains, official *.crewden.work, 10.evil.com, and CGNAT 100.64.x MUST reject cleartext HTTP!
        for bad in [
            "http://im.crewden.work",
            "http://sub.crewden.work:8080",
            "http://10.evil.com",
            "http://192.168.evil.com",
            "http://100.64.0.1:8011",
            "http://evil.example",
        ] {
            assert!(
                normalize_im_origin(bad).is_err(),
                "Expected {} to be rejected",
                bad
            );
            let dl = format!(
                "crewden-desktop://connect?origin={}",
                url::form_urlencoded::byte_serialize(bad.as_bytes()).collect::<String>()
            );
            assert!(matches!(
                classify_deep_link_connect(&dl),
                DeepLinkConnectOutcome::RejectedPublicHttp { .. }
            ));
        }

        // CLI parse_from must preserve deep_link_url without overwriting opts.im_origin or crashing on rejected HTTP!
        let cli = DesktopCliOptions::parse_from([
            "crewden-desktop",
            "crewden-desktop://connect?origin=http%3A%2F%2Fim.crewden.work",
        ])
        .unwrap();
        assert!(cli.im_origin.is_none());
        assert_eq!(
            cli.deep_link_url.as_deref(),
            Some("crewden-desktop://connect?origin=http%3A%2F%2Fim.crewden.work")
        );

        assert!(parse_deep_link_origin(
            "crewden-desktop://connect?origin=https%3A%2F%2Fuser%3Apass%40im.example"
        )
        .is_err());

        let route = parse_deep_link_route(
            "crewden-desktop://open?route=%2Fsettings%2Fagents%2Feng-1%3Fview%3Dwork",
        )
        .unwrap();
        assert_eq!(route.as_deref(), Some("/settings/agents/eng-1?view=work"));
        assert!(parse_deep_link_route("crewden-desktop://open?route=%2F%2Fevil.example").is_err());
        assert!(parse_deep_link_route("crewden-desktop://open?route=https%3A%2F%2Fevil.example").is_err());
    }

    #[test]
    fn matches_shared_local_ipc_endpoint_golden_vectors() {
        #[derive(Deserialize)]
        struct VectorFile {
            cases: Vec<VectorCase>,
        }
        #[derive(Deserialize)]
        struct VectorCase {
            id: String,
            platform: String,
            config_path: String,
            tmpdir: String,
            expected_endpoint: String,
        }
        let raw = include_str!("../../../src/IM/shared/local-ipc-endpoint-test-cases.json");
        let parsed: VectorFile = serde_json::from_str(raw).expect("valid ipc vector json");
        assert!(parsed.cases.len() >= 6);
        for case in parsed.cases {
            let actual = local_node_bridge_endpoint_for_platform(
                &case.config_path,
                case.platform == "win32",
                &case.tmpdir,
            );
            assert_eq!(actual, case.expected_endpoint, "case {}", case.id);
        }
    }
}
