import yaml
from pathlib import Path
import os
import time

try:
    from ctranslate2 import Generator as CT2
    HAS_CT2 = True
except ImportError:
    HAS_CT2 = False

def load_cfg():
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, 'r') as f:
        return yaml.safe_load(f)

cfg = load_cfg()
lang_code = cfg.get("asr_language", "en")
model_size = cfg.get("asr_model", "small")
model_name = f"{model_size}.{lang_code}"

cache = Path.home()/".gains_models"/model_name
if not cache.exists():
    # Download model on first run
    WhisperModel(model_name).download(cache_dir=cache)

if os.getenv("DEVICE") == "gpu" and HAS_CT2:
    model_path = f"~/.gains_models/ctranslate2/{model_name}"
    model = CT2(model_path, device="cuda", compute_type="float16")
    use_ct2 = True
else:
    model = WhisperModel(model_name, device=device, compute_type=compute)
    use_ct2 = False
