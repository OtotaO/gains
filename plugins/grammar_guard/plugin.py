"""Grammar Guard plugin: rewrite committed text via OpenAI for grammar.

Listens for ``text.committed`` and emits ``plugin.rewrite`` with the
corrected text. Idle if ``OPENAI_API_KEY`` is unset.

Bug fixes vs. previous version:
* ``openai.ChatCompletion.create`` was removed in openai-python 1.0
  (Nov 2023). Uses the v1 client (``client.chat.completions.create``).
* Default model bumped from ``gpt-3.5-turbo`` to ``gpt-4o-mini``.
* Wire endpoints updated for the bus' XSUB side.
"""
from __future__ import annotations

import logging
import os
import time

import zmq
from openai import OpenAI

log = logging.getLogger("gains.plugin.grammar_guard")

MODEL = os.getenv("GRAMMAR_GUARD_MODEL", "gpt-4o-mini")
PROMPT = (
    "Rewrite the text with correct grammar but keep the meaning identical. "
    "Reply with the rewrite only, no commentary."
)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set; plugin will idle")
    client = OpenAI()

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://localhost:5555")
    sub.setsockopt_string(zmq.SUBSCRIBE, "")
    pub = ctx.socket(zmq.PUB)
    pub.connect("tcp://localhost:5556")

    log.info("grammar_guard ready, model=%s", MODEL)
    try:
        while True:
            msg = sub.recv_json()
            if msg.get("event") != "text.committed":
                continue
            draft = (msg.get("text") or "").strip()
            if not draft:
                continue
            try:
                res = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": PROMPT},
                        {"role": "user", "content": draft},
                    ],
                )
                fixed = (res.choices[0].message.content or "").strip()
            except Exception:
                log.exception("openai call failed")
                continue
            if fixed and fixed != draft:
                pub.send_json({
                    "event": "plugin.rewrite",
                    "text": fixed,
                    "orig_ts": msg.get("ts"),
                    "plugin": "grammar_guard",
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
