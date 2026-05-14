use leptos::prelude::*;
use leptos::task::spawn_local;
use serde::{Deserialize, Serialize};
use wasm_bindgen::prelude::*;

/// Tauri JS bindings. Tauri v2 exposes `window.__TAURI__.{core,event,updater}`
/// when ``withGlobalTauri`` is true in tauri.conf.json.
#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = ["window", "__TAURI__", "core"])]
    async fn invoke(cmd: &str, args: JsValue) -> JsValue;

    #[wasm_bindgen(js_namespace = ["window", "__TAURI__", "event"], catch)]
    async fn listen(event: &str, handler: &Closure<dyn FnMut(JsValue)>)
        -> Result<JsValue, JsValue>;

    #[wasm_bindgen(js_namespace = ["window", "__TAURI__", "updater"], catch)]
    async fn check() -> Result<JsValue, JsValue>;
}

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(tag = "event")]
enum BusMessage {
    #[serde(rename = "asr.partial")]
    AsrPartial { text: String },
    #[serde(rename = "gesture.nod")]
    GestureNod,
    #[serde(rename = "text.committed")]
    TextCommitted { text: String },
    #[serde(rename = "plugin.rewrite")]
    PluginRewrite {
        text: String,
        plugin: Option<String>,
    },
    #[serde(rename = "heartbeat")]
    Heartbeat,
    #[serde(other)]
    Unknown,
}

#[derive(Serialize)]
struct CommitArgs<'a> {
    text: &'a str,
}

#[component]
pub fn App() -> impl IntoView {
    let (caption, set_caption) = signal(String::from("Speak — nod to commit."));
    let (last_committed, set_last_committed) = signal(String::new());
    let (bus_status, set_bus_status) = signal(String::from("waiting for bus…"));

    // Bridge `bus-message` events from Rust into our signals.
    spawn_local(async move {
        // Wrap the handler in a Closure that JS will call.
        let handler: Closure<dyn FnMut(JsValue)> = Closure::new(move |payload: JsValue| {
            // The Tauri event payload is { event, id, payload, … }; we want `.payload`.
            let payload = js_sys::Reflect::get(&payload, &JsValue::from_str("payload"))
                .unwrap_or(JsValue::NULL);
            let Ok(msg) = serde_wasm_bindgen::from_value::<BusMessage>(payload) else {
                return;
            };
            match msg {
                BusMessage::AsrPartial { text } => {
                    let trimmed = text.trim().to_owned();
                    set_bus_status.set("listening".into());
                    set_caption.set(trimmed);
                }
                BusMessage::GestureNod => {
                    let current = caption.get_untracked();
                    set_last_committed.set(current.clone());
                    set_caption.set(format!("{current} ✓"));
                    // Tell Rust to publish text.committed for downstream plug-ins.
                    let current = current.clone();
                    spawn_local(async move {
                        let args = serde_wasm_bindgen::to_value(&CommitArgs { text: &current })
                            .unwrap_or(JsValue::NULL);
                        let _ = invoke("commit_text", args).await;
                    });
                }
                BusMessage::PluginRewrite { text, plugin } => {
                    let tag = plugin.unwrap_or_else(|| "plugin".into());
                    set_last_committed.set(format!("[{tag}] {text}"));
                }
                BusMessage::TextCommitted { .. } => {}
                BusMessage::Heartbeat => set_bus_status.set("connected".into()),
                BusMessage::Unknown => {}
            }
        });
        let _ = listen("bus-message", &handler).await;
        // Leak the closure so JS retains a callable reference for the
        // lifetime of the app — the listener never unsubscribes.
        handler.forget();
    });

    let check_update = move |_| {
        spawn_local(async move {
            match check().await {
                Ok(_) => set_bus_status.set("update check complete".into()),
                Err(_) => set_bus_status.set("update check failed".into()),
            }
        });
    };

    view! {
        <main class="container">
            <header class="header">
                <h1>"GAINS"</h1>
                <span class="bus-status">{ move || bus_status.get() }</span>
                <button class="update" on:click=check_update title="Check for updates">"⤴"</button>
            </header>

            <section class="captions">
                <div class="caption-live">{ move || caption.get() }</div>
                <div class="caption-committed">
                    <Show when=move || !last_committed.get().is_empty()>
                        <span class="label">"committed: "</span>
                        <span>{ move || last_committed.get() }</span>
                    </Show>
                </div>
            </section>

            <footer class="hint">
                "Tip: nod to commit the current caption."
            </footer>
        </main>
    }
}
