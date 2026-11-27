use super::*;
use crate::config::{sha256_hex, DesktopCliOptions};
use crate::host_server::start_host_server_full;
use crate::notifications::NoopUiBridge;
use std::sync::Arc;
use std::time::Duration;

fn archive(seed: &Path, name: &str, contents: &Path) -> Value {
    let filename = format!("{name}.tar.gz");
    let archive = seed.join(&filename);
    assert!(Command::new("tar")
        .arg("-czf")
        .arg(&archive)
        .arg("-C")
        .arg(contents)
        .arg(".")
        .status()
        .unwrap()
        .success());
    json!({ "name": filename, "sha256": sha256_hex(&fs::read(archive).unwrap()) })
}

fn isolated_paths(root: &Path) -> DesktopPaths {
    DesktopPaths::resolve(&DesktopCliOptions {
        isolated_root: Some(root.to_path_buf()),
        ..Default::default()
    })
    .unwrap()
}

#[tokio::test]
async fn seed_retry_repairs_cached_archives_from_bundle() {
    let tmp = tempfile::tempdir().unwrap();
    let seed = tmp.path();
    let runtime = seed.join("runtime");
    let app = seed.join("app");
    let node = runtime.join(standalone_node_rel_path());
    fs::create_dir_all(node.parent().unwrap()).unwrap();
    // Homebrew's node depends on libraries relative to its installation directory.
    #[cfg(unix)]
    fs::write(&node, "#!/bin/sh\nexec node \"$@\"\n").unwrap();
    #[cfg(windows)]
    {
        let found = Command::new("node")
            .args(["-p", "process.execPath"])
            .output()
            .unwrap();
        assert!(found.status.success());
        fs::copy(String::from_utf8(found.stdout).unwrap().trim(), &node).unwrap();
    }
    fs::write(
        runtime.join("layout.mjs"),
        include_bytes!("../../../../packaging/desktop/layout.mjs"),
    )
    .unwrap();
    fs::write(runtime.join("dependencies.json"), "{}").unwrap();
    fs::create_dir(&app).unwrap();
    fs::write(app.join("workspaces.json"), "{}").unwrap();
    let descriptor = json!({
        "runtime": archive(seed, "runtime", &runtime),
        "app": archive(seed, "app", &app),
    });
    let raw = serde_json::to_vec(&descriptor).unwrap();
    let target = sha256_hex(&raw);
    fs::write(seed.join("descriptor.json"), &raw).unwrap();
    fs::write(
        seed.join(seed_manifest_filename()),
        json!({
            "package": "descriptor.json", "sha256": target, "version": "1.0.0"
        })
        .to_string(),
    )
    .unwrap();

    let clean = isolated_paths(&seed.join("first-install"));
    let installed = ensure_seed_bundle_installed(&clean, Some(seed))
        .unwrap()
        .unwrap();
    assert!(installed.join("runtime/layout.mjs").is_file());
    assert_eq!(fs::read(installed.join("workspaces.json")).unwrap(), b"{}");

    let paths = isolated_paths(&seed.join("retry"));
    let cache = paths.desktop_home.join("cache");
    fs::create_dir(&cache).unwrap();
    let cached_archive = |name: &str| {
        cache.join(format!(
            "{}-{name}.tar.gz",
            descriptor[name]["sha256"].as_str().unwrap()
        ))
    };
    fs::write(cached_archive("runtime"), b"partial").unwrap();
    let app_archive = seed.join("app.tar.gz");
    let app_bytes = fs::read(&app_archive).unwrap();
    fs::write(cached_archive("app"), vec![0; app_bytes.len()]).unwrap();
    let cached_desc = cache.join(format!("descriptor-{target}.json"));
    fs::write(&cached_desc, b"{").unwrap();
    let older = paths.desktop_home.join("versions/older");
    fs::create_dir_all(&older).unwrap();
    fs::write(older.join(".ready"), "older").unwrap();
    let session_bytes = br#"{"by_origin":{}}"#;
    fs::write(paths.sessions_path(), session_bytes).unwrap();
    let workspace_file = paths.nano_install_root.join("workspace-note.txt");
    fs::write(&workspace_file, "saved note").unwrap();
    fs::write(&app_archive, b"damaged installer").unwrap();

    let host = start_host_server_full(
        paths.clone(),
        None,
        Some(seed.to_owned()),
        None,
        None,
        Arc::new(NoopUiBridge::default()),
    )
    .await
    .unwrap();
    tokio::time::timeout(Duration::from_secs(60), async {
        while host.state.seed_error().is_none() {
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
    .await
    .unwrap();
    let error = host.state.seed_error().unwrap();
    assert!(
        error.contains("app.tar.gz") && error.contains("SHA-256 mismatch"),
        "{error}"
    );
    assert!(!paths.seed_marker_path().exists());
    assert!(!paths.desktop_home.join("versions").join(&target).exists());
    assert_eq!(fs::read(older.join(".ready")).unwrap(), b"older");

    fs::write(&app_archive, &app_bytes).unwrap();
    let client = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .unwrap();
    let bootstrap = client.get(&host.bootstrap_url).send().await.unwrap();
    let cookie = bootstrap.headers()["set-cookie"]
        .to_str()
        .unwrap()
        .split(';')
        .next()
        .unwrap();
    client
        .post(format!(
            "http://127.0.0.1:{}/desktop/v1/seed/retry",
            host.port
        ))
        .header("Cookie", cookie)
        .send()
        .await
        .unwrap()
        .error_for_status()
        .unwrap();
    tokio::time::timeout(Duration::from_secs(60), async {
        while !host.state.is_seed_ready() {
            assert!(
                host.state.seed_error().is_none(),
                "{:?}",
                host.state.seed_error()
            );
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
    .await
    .unwrap();
    let version = paths.desktop_home.join("versions").join(&target);
    assert!(version.join("runtime/layout.mjs").is_file());
    assert_eq!(fs::read(version.join("workspaces.json")).unwrap(), b"{}");
    assert_eq!(fs::read(cached_desc).unwrap(), raw);
    assert_eq!(fs::read(cached_archive("app")).unwrap(), app_bytes);
    assert_eq!(fs::read(older.join(".ready")).unwrap(), b"older");
    assert_eq!(fs::read(paths.sessions_path()).unwrap(), session_bytes);
    assert_eq!(fs::read(workspace_file).unwrap(), b"saved note");
}
