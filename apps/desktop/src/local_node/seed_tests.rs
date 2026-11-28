use super::*;
use crate::config::{sha256_hex, DesktopCliOptions};
use crate::host_server::{start_host_server_full, RunningHostServer};
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

async fn wait_for_seed_error(host: &RunningHostServer) -> String {
    tokio::time::timeout(Duration::from_secs(60), async {
        loop {
            if let Some(error) = host.state.seed_error() {
                return error;
            }
            assert!(!host.state.is_seed_ready(), "seed unexpectedly ready");
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
    .await
    .expect("seed worker did not report a failure")
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
    copy_test_node(&node);
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
    let active = paths
        .desktop_active_path("https://im.crewden.work")
        .unwrap();
    let previous = json!({ "managed_by": "crewden-desktop", "version_root": older, "sha256": "older", "user_stopped": true });
    write_private_json(&active, &previous).unwrap();

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
    let error = wait_for_seed_error(&host).await;
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
    let retry = || async {
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
    };
    #[cfg(windows)]
    {
        let runtimes = paths.desktop_home.join("runtimes");
        // Deny only creation of a child directory so the GUI sees a deterministic
        // filesystem failure before tar starts. The rename ACL is tested separately.
        set_test_acl(&runtimes, "/deny", "*S-1-1-0:(AD)");
        retry().await;
        let error = wait_for_seed_error(&host).await;
        set_test_acl(&runtimes, "/remove:d", "*S-1-1-0");
        assert!(
            error.contains("Create runtime directory") && error.contains("os error 5"),
            "{error}"
        );
        assert_eq!(
            serde_json::from_slice::<Value>(&fs::read(&active).unwrap()).unwrap(),
            previous
        );
        let page = client
            .get(format!("http://127.0.0.1:{}/chat", host.port))
            .header("Cookie", cookie)
            .send()
            .await
            .unwrap()
            .text()
            .await
            .unwrap();
        assert!(page.contains("Create runtime directory"));
        assert!(!paths.seed_marker_path().exists());
        assert!(!paths.desktop_home.join("versions").join(&target).exists());
        assert_eq!(fs::read(older.join(".ready")).unwrap(), b"older");
        assert_eq!(fs::read(paths.sessions_path()).unwrap(), session_bytes);
        assert_eq!(fs::read(&workspace_file).unwrap(), b"saved note");
    }
    retry().await;
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
    let current: Value = serde_json::from_slice(&fs::read(active).unwrap()).unwrap();
    assert_eq!(current["sha256"], target);
    assert_eq!(current["user_stopped"], true);
    assert_eq!(fs::read(cached_desc).unwrap(), raw);
    assert_eq!(fs::read(cached_archive("app")).unwrap(), app_bytes);
    assert_eq!(fs::read(older.join(".ready")).unwrap(), b"older");
    assert_eq!(fs::read(paths.sessions_path()).unwrap(), session_bytes);
    assert_eq!(fs::read(workspace_file).unwrap(), b"saved note");
}

#[test]
fn seed_preflight_rejects_low_disk_space_before_unpacking() {
    let tmp = tempfile::tempdir().unwrap();
    let seed = tmp.path();
    let runtime = seed.join("runtime");
    let app = seed.join("app");
    let node = runtime.join(standalone_node_rel_path());
    fs::create_dir_all(node.parent().unwrap()).unwrap();
    #[cfg(unix)]
    fs::write(&node, "#!/bin/sh\nexec node \"$@\"\n").unwrap();
    #[cfg(windows)]
    copy_test_node(&node);
    fs::write(
        runtime.join("layout.mjs"),
        include_bytes!("../../../../packaging/desktop/layout.mjs"),
    )
    .unwrap();
    fs::write(runtime.join("dependencies.json"), "{}").unwrap();
    fs::create_dir(&app).unwrap();
    fs::write(app.join("workspaces.json"), "{}").unwrap();

    let mut rt_meta = archive(seed, "runtime", &runtime);
    let mut app_meta = archive(seed, "app", &app);
    // Simulate production archive metadata (~180 MiB runtime + ~25 MiB app) on a 1.1 GiB free drive.
    rt_meta["size"] = json!(180 * 1024 * 1024u64);
    app_meta["size"] = json!(25 * 1024 * 1024u64);
    let descriptor = json!({
        "runtime": rt_meta,
        "app": app_meta,
    });
    let raw = serde_json::to_vec(&descriptor).unwrap();
    let target = sha256_hex(&raw);
    fs::write(seed.join("descriptor.json"), &raw).unwrap();
    fs::write(
        seed.join(seed_manifest_filename()),
        json!({
            "package": "descriptor.json",
            "sha256": target,
            "version": "1.0.0"
        })
        .to_string(),
    )
    .unwrap();

    let paths = isolated_paths(&seed.join("low-disk"));
    let one_point_one_gib = 1_181_116_006u64; // 1.1 GiB
    let err = ensure_seed_bundle_installed_with_available_bytes(
        &paths,
        Some(seed),
        Some(one_point_one_gib),
    )
    .expect_err("Expected preflight disk space check to fail when only 1.1 GiB is free");
    assert!(err.contains("磁盘可用空间不足"), "unexpected error: {err}");
    assert!(err.contains("1.1 GB"), "expected available 1.1 GB in message: {err}");
    assert!(!paths.desktop_home.join("versions").join(&target).exists());
    assert!(
        query_available_disk_bytes(&paths.desktop_home).unwrap_or(0) > 0,
        "OS free disk space query should return positive available bytes"
    );
    assert_eq!(
        classify_seed_error("Extract app.tar.gz: tar extraction failed: Write failed: No space left on device"),
        SeedErrorKind::DiskFull
    );
    assert_eq!(
        classify_seed_error("Copy runtime.tar.gz: There is not enough space on the disk. (os error 112)"),
        SeedErrorKind::DiskFull
    );
    assert_eq!(
        classify_seed_error("Create runtime directory C:\\test: Access is denied. (os error 5)"),
        SeedErrorKind::PermissionOrLocked
    );
}

#[cfg(windows)]
fn copy_test_node(destination: &Path) {
    let found = Command::new("node")
        .args(["-p", "process.execPath"])
        .output()
        .unwrap();
    assert!(found.status.success());
    fs::copy(String::from_utf8(found.stdout).unwrap().trim(), destination).unwrap();
}

#[cfg(windows)]
#[test]
fn windows_publishes_ready_runtime_while_backing_file_remains_open() {
    use std::os::windows::fs::OpenOptionsExt;
    let tmp = tempfile::tempdir().unwrap();
    let stage = tmp.path().join("runtime backing");
    let target = tmp.path().join("published-runtime");
    fs::create_dir(&stage).unwrap();
    copy_test_node(&stage.join("node.exe"));
    fs::write(stage.join(".ready"), b"complete").unwrap();
    let held = fs::OpenOptions::new()
        .read(true)
        .share_mode(1)
        .open(stage.join(".ready"))
        .unwrap();
    assert_eq!(
        fs::rename(&stage, &target).unwrap_err().raw_os_error(),
        Some(5)
    );
    publish_seed_runtime(&stage, &target).unwrap();
    assert_eq!(fs::read(target.join(".ready")).unwrap(), b"complete");
    drop(held);
}

#[cfg(windows)]
#[test]
fn windows_seed_directory_rename_recovers_after_child_handle_closes() {
    use std::os::windows::fs::OpenOptionsExt;

    let tmp = tempfile::tempdir().unwrap();
    let stage = tmp.path().join(".seed-rt-stage");
    let target = tmp.path().join("installed-runtime");
    fs::create_dir(&stage).unwrap();
    let node = stage.join("node.exe");
    fs::write(&node, b"runtime fixture").unwrap();
    let held = fs::OpenOptions::new()
        .read(true)
        .share_mode(1) // FILE_SHARE_READ, as with a scanner reading the extracted file
        .open(node)
        .unwrap();
    assert_eq!(
        fs::rename(&stage, &target).unwrap_err().raw_os_error(),
        Some(5)
    );
    assert!(!target.exists());
    let release = std::thread::spawn(move || {
        std::thread::sleep(Duration::from_millis(100));
        drop(held);
    });
    publish_seed_directory(&stage, &target).unwrap();
    release.join().unwrap();
    assert_eq!(
        fs::read(target.join("node.exe")).unwrap(),
        b"runtime fixture"
    );
}

#[cfg(windows)]
fn set_test_acl(path: &Path, action: &str, ace: &str) {
    assert!(Command::new("icacls.exe")
        .arg(path)
        .args([action, ace])
        .status()
        .unwrap()
        .success());
}

#[cfg(windows)]
#[test]
fn windows_seed_directory_rename_reports_real_acl_denial() {
    let tmp = tempfile::tempdir().unwrap();
    let stage = tmp.path().join(".seed-ver-stage");
    let target = tmp.path().join("installed-version");
    fs::create_dir(&stage).unwrap();
    fs::write(stage.join(".ready"), "pending").unwrap();
    // NTFS grants rename through DELETE on the object or DELETE_CHILD on its parent.
    set_test_acl(tmp.path(), "/deny", "*S-1-1-0:(DC)");
    set_test_acl(&stage, "/deny", "*S-1-1-0:(D)");
    let result = publish_seed_directory(&stage, &target);
    set_test_acl(&stage, "/remove:d", "*S-1-1-0");
    set_test_acl(tmp.path(), "/remove:d", "*S-1-1-0");
    let error = result.unwrap_err();
    assert!(error.contains("os error 5"), "{error}");
    assert!(error.contains(&*stage.to_string_lossy()), "{error}");
    assert!(error.contains(&*target.to_string_lossy()), "{error}");
    assert!(stage.join(".ready").exists());
    assert!(!target.exists());
}
