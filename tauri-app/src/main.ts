// Simple GAINS frontend - connects to ZeroMQ bus
// Note: In a real implementation, you'd use WebSocket or HTTP for browser communication

import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/tauri";

const overlay = document.getElementById("overlay") as HTMLElement;
const micButton = document.getElementById("micButton") as HTMLButtonElement;

// Listen for real ZMQ messages from the Rust bridge
listen("bus-message", ({ payload }) => {
    const msg = payload as any;
    
    if (msg.event === "asr.partial") {
        overlay.textContent = msg.text;
    }
    if (msg.event === "gesture.nod") {
        overlay.textContent += " ✓";
        invoke("commit_text");
        console.log("Nod detected - committing text");
    }
    if (msg.event === "heartbeat") {
        // Optional: handle heartbeat for connection status
        console.log("ZMQ heartbeat received");
    }
});

// Mic button click handler - emit asr.toggle event
micButton.addEventListener("click", () => {
    overlay.textContent = "Listening...";
    console.log("Mic button clicked - starting ASR");
    
    // Emit asr.toggle event to the ZMQ bus
    // In a real implementation, this would be sent via the Rust bridge
    const toggleEvent = {
        event: "asr.toggle",
        action: "start",
        ts: Date.now()
    };
    
    // For now, simulate the toggle event
    setTimeout(() => {
        // Simulate ASR result for demo
        const mockEvent = {
            event: "asr.partial",
            text: "Hello, this is a test message from the mic button",
            ts: Date.now()
        };
        
        // Dispatch a custom event that the ZMQ bridge would normally send
        window.dispatchEvent(new CustomEvent("bus-message", { 
            detail: mockEvent 
        }));
    }, 2000);
});

async function openSettings() {
  // Fetch current settings from Rust
  const cfg: any = await invoke("get_settings");

  // ── Silence-timeout prompt ──
  const timeout = prompt(
    "Silence timeout (seconds)",
    String(cfg.silence_timeout_sec ?? 8)
  );
  if (timeout === null) return;
  cfg.silence_timeout_sec = Number(timeout);

  // ── ASR language prompt ──
  const lang = prompt(
    "ASR language (ISO-639-1 code: en, es, fr, de, …)",
    cfg.asr_language ?? "en"
  );
  if (lang === null) return;
  cfg.asr_language = lang.trim();

  // Save back to YAML via Rust command
  await invoke("save_settings", { cfg });

  alert(
    "Settings saved ✔︎\n\nRestart the ASR service to load the new model/language."
  );
}

console.log("GAINS frontend loaded - listening for ZMQ messages"); 