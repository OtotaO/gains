import zmq, re

ctx = zmq.Context.instance()
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://localhost:5555")
sub.setsockopt_string(zmq.SUBSCRIBE, "text.committed")

pub = ctx.socket(zmq.PUB)
pub.connect("tcp://localhost:5555")

print("[sample_rewriter] ready")

while True:
    msg = sub.recv_json()
    text = msg["text"]
    # trivial rewrite: capitalise TODO keywords
    text2 = re.sub(r"\btodo\b", "TODO", text, flags=re.IGNORECASE)
    if text2 != text:
        pub.send_json({"event": "plugin.rewrite", "text": text2, "orig_ts": msg["ts"]}) 