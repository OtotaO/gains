"""Sample rewriter: trivial regex-based TODO capitaliser.

Demonstrates the plug-in contract: subscribe to ``text.committed`` and emit
``plugin.rewrite`` if you changed anything.
"""
from __future__ import annotations

import logging
import re
import time

import zmq

log = logging.getLogger("gains.plugin.sample_rewriter")
TODO_RE = re.compile(r"\btodo\b", flags=re.IGNORECASE)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://localhost:5555")
    sub.setsockopt_string(zmq.SUBSCRIBE, "")
    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://localhost:5556")

    log.info("sample_rewriter ready")
    try:
        while True:
            msg = sub.recv_json()
            if msg.get("event") != "text.committed":
                continue
            text = msg.get("text") or ""
            rewritten = TODO_RE.sub("TODO", text)
            if rewritten != text:
                pub.send_json({
                    "event": "plugin.rewrite",
                    "text": rewritten,
                    "orig_ts": msg.get("ts"),
                    "plugin": "sample_rewriter",
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
