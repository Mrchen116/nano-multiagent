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
                    if let Some(origin) = parse_deep_link_origin(other)? {
                        opts.im_origin = Some(origin);
                        opts.deep_link_url = Some(other.to_string());
                    } else if let Some(route) = parse_deep_link_route(other)? {
                        opts.initial_route = Some(route);
                        opts.deep_link_url = Some(other.to_string());
                    }
                }
                _ => {}
            }
            idx += 1;
        }
        Ok(opts)
    }
}

/// Normalize and validate an IM server origin (`https://...` or loopback `http://...`).
pub fn normalize_im_origin(raw: &str) -> Result<String, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("IM server URL cannot be empty".to_string());
    }
    let parsed = Url::parse(trimmed).map_err(|_| "Invalid IM server URL".to_string())?;
    if parsed.scheme() != "https" && parsed.scheme() != "http" {
        return Err("Only http:// and https:// IM server URLs are supported".to_string());
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("IM server URL must not embed credentials".to_string());
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| "IM server URL must include a host".to_string())?;
    let mut origin = format!("{}://{}", parsed.scheme(), host);
    if let Some(port) = parsed.port() {
        origin.push_str(&format!(":{}", port));
    }
    Ok(origin)
}

/// Parse `crewden-desktop://connect?origin=<encoded>` safely, rejecting non-connect actions or bad schemes.
pub fn parse_deep_link_origin(raw: &str) -> Result<Option<String>, String> {
    let parsed = Url::parse(raw.trim()).map_err(|_| "Malformed crewden-desktop:// URL".to_string())?;
    if parsed.scheme() != "crewden-desktop" {
        return Ok(None);
    }
    let action = parsed.host_str().unwrap_or("");
    if action != "connect" && parsed.path().trim_matches('/') != "connect" {
        return Ok(None);
    }
    for (k, v) in parsed.query_pairs() {
        if k == "origin" {
            let origin = normalize_im_origin(&v)?;
            let origin_url = Url::parse(&origin).map_err(|_| "Invalid origin".to_string())?;
            let host = origin_url.host_str().unwrap_or("");
            let is_loopback = matches!(host, "127.0.0.1" | "localhost" | "[::1]" | "::1");
            if origin_url.scheme() != "https" && !(origin_url.scheme() == "http" && is_loopback) {
                return Err("Deep-link origin must use https:// (or loopback http://)".to_string());
            }
            return Ok(Some(origin));
        }
    }
    Ok(None)
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

/// Exact counterpart to `localNodeBridgeEndpoint` in `apps/node/src/local-bridge.ts`.
pub fn local_node_bridge_endpoint(config_path: &Path) -> String {
    let config_str = config_path.to_string_lossy().to_string();
    if cfg!(target_os = "windows") {
        let digest = &sha256_hex(config_str.to_lowercase().as_bytes())[..24];
        return format!(r"\\.\pipe\crewden-desktop-node-{}", digest);
    }
    let digest = &sha256_hex(config_str.as_bytes())[..20];
    let parent = config_path.parent().unwrap_or_else(|| Path::new("/tmp"));
    let candidate = parent.join(".desktop-node.sock");
    let candidate_str = candidate.to_string_lossy().to_string();
    if candidate_str.as_bytes().len() <= 96 {
        return candidate_str;
    }
    let tmp = std::env::var("TMPDIR").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(tmp)
        .join(format!("crewden-node-{}.sock", digest))
        .to_string_lossy()
        .to_string()
}

pub fn home_dir() -> Option<PathBuf> {
    if cfg!(target_os = "windows") {
        std::env::var("USERPROFILE").ok().map(PathBuf::from)
    } else {
        std::env::var("HOME").ok().map(PathBuf::from)
    }
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HostRuntimeStateFile {
    pub pid: u32,
    pub port: u16,
    pub ready: bool,
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
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let bytes = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
    let tmp = path.with_extension(format!("tmp-{}-{}", std::process::id(), random_hex_token(4)));
    fs::write(&tmp, &bytes).map_err(|e| e.to_string())?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&tmp, fs::Permissions::from_mode(0o600));
    }
    fs::rename(&tmp, path).map_err(|e| e.to_string())?;
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_deep_link_and_rejects_non_https_remote() {
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

        assert!(
            parse_deep_link_origin("crewden-desktop://connect?origin=http%3A%2F%2Fevil.example")
                .is_err()
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
}
