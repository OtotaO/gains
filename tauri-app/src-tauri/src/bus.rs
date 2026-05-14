//! ZeroMQ bridge between the Python service mesh and the Tauri frontend.
//!
//! * SUB connects to the bus' XPUB side (5555) and forwards every JSON
//!   payload to the frontend via [`AppHandle::emit("bus-message", _)`].
//! * PUB connects to the bus' XSUB side (5556) and is used by Tauri
//!   commands (e.g. `commit_text`) that need to publish events.

use std::sync::Mutex;

use anyhow::{Context, Result};
use serde_json::Value;
use tauri::{AppHandle, Emitter};

const BUS_SUB_ENDPOINT: &str = "tcp://localhost:5555";
const BUS_PUB_ENDPOINT: &str = "tcp://localhost:5556";

/// PUB socket the rest of the app can use to publish events.
///
/// `zmq::Socket` is `Send + !Sync`, so we wrap it in a `Mutex` for
/// thread-safe access from Tauri command handlers.
pub struct BusPublisher {
    socket: Mutex<zmq::Socket>,
}

impl BusPublisher {
    pub fn new(ctx: &zmq::Context) -> Result<Self> {
        let socket = ctx.socket(zmq::PUB).context("create PUB socket")?;
        socket
            .connect(BUS_PUB_ENDPOINT)
            .context("connect PUB to bus")?;
        Ok(Self {
            socket: Mutex::new(socket),
        })
    }

    pub fn send(&self, value: &Value) -> Result<()> {
        let payload = serde_json::to_string(value)?;
        let socket = self.socket.lock().expect("bus PUB mutex poisoned");
        socket.send(payload.as_bytes(), 0)?;
        Ok(())
    }
}

/// Spawn a background thread that subscribes to the bus and forwards
/// messages to the frontend. Errors are logged and the thread exits.
pub fn spawn_subscriber(app: AppHandle, ctx: zmq::Context) {
    std::thread::Builder::new()
        .name("gains-bus-sub".into())
        .spawn(move || {
            if let Err(err) = run_subscriber(&app, &ctx) {
                tracing::error!(?err, "bus subscriber exited");
            }
        })
        .expect("spawn bus subscriber");
}

fn run_subscriber(app: &AppHandle, ctx: &zmq::Context) -> Result<()> {
    let sub = ctx.socket(zmq::SUB).context("create SUB socket")?;
    sub.connect(BUS_SUB_ENDPOINT)
        .context("connect SUB to bus")?;
    sub.set_subscribe(b"").context("subscribe to all topics")?;
    tracing::info!(endpoint = BUS_SUB_ENDPOINT, "bus subscriber connected");

    loop {
        let raw = sub
            .recv_string(0)
            .context("recv from bus")?
            .map_err(|_| anyhow::anyhow!("non-utf8 bus message"))?;
        match serde_json::from_str::<Value>(&raw) {
            Ok(value) => {
                if let Err(e) = app.emit("bus-message", value) {
                    tracing::warn!(error = %e, "emit failed");
                }
            }
            Err(e) => tracing::warn!(error = %e, "drop malformed bus message"),
        }
    }
}
