"""Central event bus: XSUB/XPUB proxy + heartbeat.

Publishers connect to tcp://*:5556 (XSUB-bound).
Subscribers connect to tcp://*:5555 (XPUB-bound).

This replaces the previous broken design where every service connected its
PUB socket to a PUB-bound hub on 5555 (PUB→PUB transmits nothing, so the
Tauri SUB bridge only ever saw heartbeats).
"""
from __future__ import annotations

import logging
import threading
import time

import zmq

log = logging.getLogger("gains.bus")

SUB_ENDPOINT = "tcp://*:5556"  # publishers connect here
PUB_ENDPOINT = "tcp://*:5555"  # subscribers connect here


def heartbeat() -> None:
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.connect("tcp://localhost:5556")
    try:
        while True:
            sock.send_json({"event": "heartbeat", "ts": time.time()})
            time.sleep(1)
    finally:
        sock.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ctx = zmq.Context.instance()
    xsub = ctx.socket(zmq.XSUB)
    xsub.bind(SUB_ENDPOINT)
    xpub = ctx.socket(zmq.XPUB)
    xpub.bind(PUB_ENDPOINT)

    threading.Thread(target=heartbeat, daemon=True).start()
    log.info("bus proxy: publishers→%s, subscribers→%s", SUB_ENDPOINT, PUB_ENDPOINT)
    try:
        zmq.proxy(xsub, xpub)
    except KeyboardInterrupt:
        pass
    finally:
        xsub.close()
        xpub.close()
        ctx.term()


if __name__ == "__main__":
    main()
