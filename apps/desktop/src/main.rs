#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if let Err(err) = crewden_desktop::run_from_env() {
        let cli = crewden_desktop::config::DesktopCliOptions::parse_from(std::env::args()).ok();
        let paths = cli.as_ref().and_then(|opts| crewden_desktop::config::DesktopPaths::resolve(opts).ok());
        let log_path = crewden_desktop::config::append_host_log(paths.as_ref(), "FATAL", &err);
        if !cli.is_some_and(|opts| opts.prepare_seed) {
            crewden_desktop::config::show_fatal_startup_dialog(&err, &log_path);
        }
        eprintln!("Crewden Desktop error: {} (log: {})", err, log_path.display());
        std::process::exit(1);
    }
}
