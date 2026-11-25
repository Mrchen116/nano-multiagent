use crate::config::{home_dir, write_private_json, DesktopPaths};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

const MACOS_PLIST_LABEL: &str = "work.crewden.desktop";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TestAutostartMarker {
    enabled: bool,
    executable: String,
    args: Vec<String>,
}

fn macos_plist_path(paths: &DesktopPaths) -> Option<PathBuf> {
    if let Some(ref test_dir) = paths.test_autostart_dir {
        return Some(test_dir.join(format!("{}.plist", MACOS_PLIST_LABEL)));
    }
    home_dir().map(|h| {
        h.join("Library")
            .join("LaunchAgents")
            .join(format!("{}.plist", MACOS_PLIST_LABEL))
    })
}

fn xml_escape(input: &str) -> String {
    input
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

/// Configure or remove the Crewden Desktop `--background` login item without interrupting live tasks.
pub fn set_desktop_login_autostart(
    paths: &DesktopPaths,
    exe_path: &Path,
    enabled: bool,
) -> Result<(), String> {
    if let Some(ref test_dir) = paths.test_autostart_dir {
        let marker_path = test_dir.join("desktop-login-autostart.json");
        if enabled {
            write_private_json(
                &marker_path,
                &TestAutostartMarker {
                    enabled: true,
                    executable: exe_path.to_string_lossy().to_string(),
                    args: vec!["--background".to_string()],
                },
            )?;
        } else {
            let _ = fs::remove_file(&marker_path);
        }
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        let plist_path =
            macos_plist_path(paths).ok_or_else(|| "Cannot resolve LaunchAgents path".to_string())?;
        if enabled {
            if let Some(parent) = plist_path.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            let plist = format!(
                r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{exe}</string>
    <string>--background</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>
"#,
                label = MACOS_PLIST_LABEL,
                exe = xml_escape(&exe_path.to_string_lossy()),
            );
            fs::write(&plist_path, plist).map_err(|e| e.to_string())?;
        } else {
            let _ = fs::remove_file(&plist_path);
        }
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        use winreg::enums::*;
        use winreg::RegKey;
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);
        let (run_key, _) = hkcu
            .create_subkey(r"Software\Microsoft\Windows\CurrentVersion\Run")
            .map_err(|e| e.to_string())?;
        if enabled {
            let cmd = format!("\"{}\" --background", exe_path.to_string_lossy());
            run_key
                .set_value("CrewdenDesktop", &cmd)
                .map_err(|e| e.to_string())?;
        } else {
            let _ = run_key.delete_value("CrewdenDesktop");
        }
        return Ok(());
    }

    #[allow(unreachable_code)]
    Ok(())
}

/// Read whether Crewden Desktop `--background` login autostart is currently registered.
pub fn get_desktop_login_autostart(paths: &DesktopPaths) -> bool {
    if let Some(ref test_dir) = paths.test_autostart_dir {
        return test_dir.join("desktop-login-autostart.json").is_file();
    }

    #[cfg(target_os = "macos")]
    {
        return macos_plist_path(paths)
            .map(|p| p.is_file())
            .unwrap_or(false);
    }

    #[cfg(target_os = "windows")]
    {
        use winreg::enums::*;
        use winreg::RegKey;
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);
        if let Ok(run_key) = hkcu.open_subkey(r"Software\Microsoft\Windows\CurrentVersion\Run") {
            let val: Result<String, _> = run_key.get_value("CrewdenDesktop");
            return val.is_ok();
        }
        return false;
    }

    #[allow(unreachable_code)]
    false
}
