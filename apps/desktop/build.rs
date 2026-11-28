use std::env;
use std::fs;
use std::path::PathBuf;

const WINDOWS_COMMON_CONTROLS_V6_MANIFEST: &str = r#"<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
        type="win32"
        name="Microsoft.Windows.Common-Controls"
        version="6.0.0.0"
        processorArchitecture="*"
        publicKeyToken="6595b64144ccf1df"
        language="*"
      />
    </dependentAssembly>
  </dependency>
</assembly>
"#;

fn main() {
    let is_windows_msvc = env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows")
        && env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc");
    if is_windows_msvc {
        // `tauri-winres` links its `.rc` manifest via `cargo:rustc-link-arg-bins`, leaving
        // `--lib` unit-test binaries without `Common-Controls 6.0.0.0`. Tests touching
        // `TauriUiCoordinator` / `muda` then import `ComCtl32.dll` v6 symbols (`SetWindowSubclass`,
        // `DefSubclassProc`, `TaskDialogIndirect`) against legacy v5.82 and abort at load time
        // with `0xc0000139 (STATUS_ENTRYPOINT_NOT_FOUND)`. Omit the `.rc` manifest to avoid
        // duplicate `RT_MANIFEST` on `[[bin]]`, and embed `Common-Controls 6.0.0.0` via `link.exe`
        // across both `[[bin]]` and test targets.
        let attrs = tauri_build::Attributes::new()
            .windows_attributes(tauri_build::WindowsAttributes::new_without_app_manifest());
        tauri_build::try_build(attrs).expect("failed to run tauri-build");

        let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR missing"));
        let manifest_path = out_dir.join("windows-app-manifest.xml");
        fs::write(&manifest_path, WINDOWS_COMMON_CONTROLS_V6_MANIFEST)
            .expect("failed to write windows-app-manifest.xml");
        println!("cargo:rustc-link-arg=/MANIFEST:EMBED");
        println!(
            "cargo:rustc-link-arg=/MANIFESTINPUT:{}",
            manifest_path.display()
        );
    } else {
        tauri_build::build();
    }
}
