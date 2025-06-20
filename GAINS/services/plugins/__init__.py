import importlib, pkgutil, zmq

PUB = zmq.Context().socket(zmq.SUB)
PUB.connect("tcp://localhost:5555")
PUB.setsockopt_string(zmq.SUBSCRIBE, "plugin.request")

def load_plugins():
    for info in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f"plugins.{info.name}.plugin")
        print(f"[PLUG] Loaded {info.name}")

load_plugins() 