"""Note exporter: builds note sessions from ASR + nod events, writes txt/md/json.

Listens on the bus for ``asr.partial`` (text) + ``gesture.nod`` (commit) and
``plugin.rewrite`` (rewrites from plug-ins). Flushes a session to disk every
N commits or every M seconds.

Bug fixes vs. previous version:
* Interactive ``input("output dir: ")`` at startup removed — a service
  must start non-interactively. Output dir is now a CLI arg / env var.
* Subscriber connects to the XPUB side (5555) of the bus as expected.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import zmq

log = logging.getLogger("gains.notes")

DEFAULT_OUTPUT_DIR = Path(os.getenv("GAINS_NOTES_DIR", "notes"))
COMMIT_FLUSH_AFTER = 5
TIME_FLUSH_AFTER_SEC = 30.0


class NoteExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: list[dict[str, Any]] = []
        self.session_start: float | None = None
        self.ctx = zmq.Context.instance()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect("tcp://localhost:5555")
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        log.info("note exporter ready, output=%s", self.output_dir)

    def run(self) -> None:
        try:
            while True:
                msg = self.sub.recv_json()
                self._handle(msg)
        except KeyboardInterrupt:
            pass
        finally:
            if self.current_session:
                self._flush()
            self.sub.close()
            self.ctx.term()

    def _handle(self, msg: dict[str, Any]) -> None:
        event = msg.get("event")
        ts = msg.get("ts", time.time())
        if event == "asr.partial":
            text = (msg.get("text") or "").strip()
            if not text:
                return
            if self.session_start is None:
                self.session_start = ts
            self.current_session.append({
                "type": "speech",
                "text": text,
                "ts": ts,
                "confidence": msg.get("confidence"),
                "start": msg.get("start"),
                "end": msg.get("end"),
            })
        elif event == "plugin.rewrite":
            # Replace the most-recent speech entry's text with the rewrite.
            for entry in reversed(self.current_session):
                if entry["type"] == "speech":
                    entry["original"] = entry["text"]
                    entry["text"] = msg.get("text", entry["text"])
                    entry["rewritten_by"] = msg.get("plugin")
                    break
        elif event == "gesture.nod" or event == "text.committed":
            if not self.current_session:
                return
            for entry in reversed(self.current_session):
                if entry["type"] == "speech" and not entry.get("committed"):
                    entry["committed"] = True
                    entry["commit_ts"] = ts
                    log.info("committed: %s", entry["text"][:60])
                    break
            if self._should_flush():
                self._flush()

    def _should_flush(self) -> bool:
        committed = sum(1 for e in self.current_session if e.get("committed"))
        elapsed = (time.time() - self.session_start) if self.session_start else 0.0
        return committed >= COMMIT_FLUSH_AFTER or elapsed > TIME_FLUSH_AFTER_SEC

    def _flush(self) -> None:
        if not self.current_session:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session = {
            "session_id": stamp,
            "start_time": self.session_start,
            "end_time": time.time(),
            "entries": self.current_session,
            "total_entries": len(self.current_session),
            "committed_entries": sum(1 for e in self.current_session if e.get("committed")),
        }
        self._write_txt(session, self.output_dir / f"gains_notes_{stamp}.txt")
        self._write_md(session, self.output_dir / f"gains_notes_{stamp}.md")
        self._write_json(session, self.output_dir / f"gains_notes_{stamp}.json")
        log.info("flushed session: %d committed / %d total",
                 session["committed_entries"], session["total_entries"])
        self.current_session = []
        self.session_start = None

    @staticmethod
    def _write_txt(session: dict[str, Any], path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            f.write(f"GAINS Notes — Session {session['session_id']}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 50 + "\n\n")
            for entry in session["entries"]:
                if entry.get("committed"):
                    f.write(f"{entry['text']}\n\n")

    @staticmethod
    def _write_md(session: dict[str, Any], path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            f.write(f"# GAINS Notes — Session {session['session_id']}\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n")
            duration = (session["end_time"] - (session["start_time"] or session["end_time"]))
            f.write(f"**Duration:** {duration:.1f}s\n")
            f.write(f"**Entries:** {session['committed_entries']}/{session['total_entries']}\n\n")
            f.write("---\n\n")
            for entry in session["entries"]:
                if entry.get("committed"):
                    f.write(f"{entry['text']}\n\n")

    @staticmethod
    def _write_json(session: dict[str, Any], path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    NoteExporter(args.output_dir).run()


if __name__ == "__main__":
    main()
