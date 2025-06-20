import zmq, time, json
ctx = zmq.Context()
sock = ctx.socket(zmq.PUB)
sock.bind("tcp://*:5555")          # central bus

while True:
    sock.send_json({"event":"heartbeat","ts":time.time()})
    time.sleep(1) 