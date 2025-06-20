import os, zmq, time, openai, re
openai.api_key = os.getenv("OPENAI_API_KEY")

ctx = zmq.Context()
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://localhost:5555")
sub.setsockopt_string(zmq.SUBSCRIBE, "text.committed")

pub = ctx.socket(zmq.PUB)
pub.connect("tcp://localhost:5555")

PROMPT = "Rewrite the text with correct grammar but keep the meaning identical."

while True:
    msg = sub.recv_json()
    draft = msg["text"]

    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": PROMPT},
                  {"role": "user", "content": draft}]
    )
    fixed = res.choices[0].message.content.strip()

    if fixed != draft:
        pub.send_json({
            "event": "plugin.rewrite",
            "text": fixed,
            "orig_ts": msg["ts"],
            "plugin": "grammar_guard",
            "ts": time.time()
        }) 