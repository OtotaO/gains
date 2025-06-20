# GAINS Plug-in API

GAINS exposes its event bus (ZeroMQ topic‐prefixed JSON) so Python plug-ins can subscribe, transform text, and publish new events.

## Directory layout

plugins/
my_plugin/
init.py      # optional
plugin.py        # REQUIRED (entry point)

## Starter template

```python
# plugins/my_plugin/plugin.py
import zmq, re, time

ctx = zmq.Context()
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://localhost:5555")
sub.setsockopt_string(zmq.SUBSCRIBE, "text.committed")

pub = ctx.socket(zmq.PUB)
pub.connect("tcp://localhost:5555")

print("[my_plugin] loaded")

while True:
    msg = sub.recv_json()
    original = msg["text"]

    # Example: capitalise 'todo'
    rewritten = re.sub(r"\btodo\b", "TODO", original, flags=re.I)

    if rewritten != original:
        pub.send_json(
            {
                "event": "plugin.rewrite",
                "text": rewritten,
                "orig_ts": msg["ts"],
                "plugin": "my_plugin",
                "ts": time.time(),
            }
        )
```

Run all plug-ins with:

python services/plugins/runner.py

Core events

Topic	Payload fields	Notes
text.committed	text, ts	Emitted by UI when user nods "commit"
plugin.rewrite	text, orig_ts, plugin, ts	Any plug-in can publish a rewrite

The note-export service listens for plugin.rewrite and writes the rewritten version instead of the original.

Happy hacking! 🎉 