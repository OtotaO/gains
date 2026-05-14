# GAINS plug-in API

GAINS exposes its event bus (ZeroMQ JSON) so plug-ins can subscribe,
transform text, and publish new events. Plug-ins run as their own
processes; the runner (`gains-plugins` / `services/plugins/runner.py`)
discovers each `plugins/<name>/plugin.py` and supervises it.

## Bus wiring

* **Subscribe** on `tcp://localhost:5555` (the XPUB side of the bus).
* **Publish** on `tcp://localhost:5556` (the XSUB side of the bus).

Filter by `event` in Python rather than via SUB topic prefixes — payloads
are JSON-encoded objects, so prefix filtering doesn't match cleanly.

## Directory layout

```
plugins/
└── my_plugin/
    ├── __init__.py  (optional, empty is fine)
    └── plugin.py    (REQUIRED — entry point with a `main()` function)
```

## Template

```python
# plugins/my_plugin/plugin.py
"""Capitalises any standalone 'todo' to 'TODO'."""
from __future__ import annotations

import logging
import re
import time

import zmq

log = logging.getLogger("gains.plugin.my_plugin")
TODO_RE = re.compile(r"\btodo\b", re.IGNORECASE)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://localhost:5555")
    sub.setsockopt_string(zmq.SUBSCRIBE, "")
    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://localhost:5556")

    log.info("my_plugin ready")
    try:
        while True:
            msg = sub.recv_json()
            if msg.get("event") != "text.committed":
                continue
            text = msg.get("text", "")
            rewritten = TODO_RE.sub("TODO", text)
            if rewritten != text:
                pub.send_json({
                    "event": "plugin.rewrite",
                    "text": rewritten,
                    "orig_ts": msg.get("ts"),
                    "plugin": "my_plugin",
                    "ts": time.time(),
                })
    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        pub.close()
        ctx.term()


if __name__ == "__main__":
    main()
```

Run with:

```bash
gains-plugins        # supervises every plugins/<name>/plugin.py
# …or single-plugin:
python plugins/my_plugin/plugin.py
```

## Event reference

| Topic            | Payload                                          | Notes                                    |
|------------------|--------------------------------------------------|------------------------------------------|
| `text.committed` | `{text, ts}`                                     | Emitted by the Tauri shell on nod        |
| `plugin.rewrite` | `{text, orig_ts, plugin, ts}`                    | Note exporter splices this into the session |

Plug-ins **should** stamp their `plugin` field so consumers can attribute
the rewrite. The note exporter replaces the most recent speech entry's
text with the rewrite.

## Built-in plug-ins

* `grammar_guard` — OpenAI v1 client, default model `gpt-4o-mini`. Idle if
  `OPENAI_API_KEY` is unset.
* `sample_rewriter` — trivial TODO capitaliser; demo only.
