mod zmq_bridge;

use tauri::Manager;
use serde_json::Value;

#[tauri::command]
fn commit_text() -> Result<(), String> {
    println!("Text committed via Tauri command");
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            zmq_bridge::spawn_zmq(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![commit_text])
        .run(tauri::generate_context!())
        .expect("error while running tauri");
} 