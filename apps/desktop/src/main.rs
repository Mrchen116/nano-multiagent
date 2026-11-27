#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if let Err(err) = crewden_desktop::run_from_env() {
        let paths = crewden_desktop::config::DesktopCliOptions::parse_from(std::env::args())
            .ok()
            .and_then(|cli| crewden_desktop::config::DesktopPaths::resolve(&cli).ok());
        let log_path = crewden_desktop::config::append_host_log(paths.as_ref(), "FATAL", &err);
        crewden_desktop::config::show_fatal_startup_dialog(&err, &log_path);
        eprintln!("Crewden Desktop error: {} (log: {})", err, log_path.display());
        std::process::exit(1);
    }
}
