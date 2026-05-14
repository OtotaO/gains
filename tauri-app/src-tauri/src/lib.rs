mod bus;

use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::json;
use tauri::{Manager, State};

use crate::bus::BusPublisher;

/// Publish a ``text.committed`` event to the bus. Called by the frontend
/// when a nod is detected. Downstream plug-ins listen for this event.
#[tauri::command]
fn commit_text(text: String, bus: State<'_, BusPublisher>) -> Result<(), String> {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs_f64();
    let payload = json!({
        "event": "text.committed",
        "text": text,
        "ts": ts,
    });
    bus.send(&payload).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let ctx = zmq::Context::new();
            let publisher = BusPublisher::new(&ctx)?;
            app.manage(publisher);
            bus::spawn_subscriber(app.handle().clone(), ctx);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![commit_text])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
