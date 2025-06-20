use tauri::Manager;
use zmq::Context;
use serde_json::Value;

pub fn spawn_zmq(app_handle: tauri::AppHandle) {
    std::thread::spawn(move || {
        let ctx = Context::new();
        let sub = ctx.socket(zmq::SUB).unwrap();
        sub.connect("tcp://localhost:5555").unwrap();
        sub.set_subscribe(b"").unwrap();

        loop {
            match sub.recv_string(0) {
                Ok(Ok(msg)) => {
                    // Parse the JSON message
                    if let Ok(json_value) = serde_json::from_str::<Value>(&msg) {
                        // Emit the message to the frontend
                        if let Err(e) = app_handle.emit_all("bus-message", json_value) {
                            eprintln!("Failed to emit bus message: {}", e);
                        }
                    }
                }
                Ok(Err(e)) => {
                    eprintln!("Failed to receive ZMQ message: {}", e);
                }
                Err(e) => {
                    eprintln!("ZMQ receive error: {}", e);
                }
            }
        }
    });
} 