#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if let Err(err) = crewden_desktop::run_from_env() {
        eprintln!("Crewden Desktop error: {}", err);
        std::process::exit(1);
    }
}
