"""Plugin runner: discovers and spawns each ``plugins/<name>/plugin.py`` as a subprocess.

Previous version imported plugin modules in-process, but every plugin's
``plugin.py`` contains an infinite ``while True: sub.recv_json()`` loop, so
the import blocked forever on the first plugin. Now each plugin runs in its
own process and the runner manages their lifecycles.
"""
from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("gains.plugins")

PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def discover() -> list[Path]:
    if not PLUGINS_DIR.is_dir():
        return []
    return sorted(
        p / "plugin.py"
        for p in PLUGINS_DIR.iterdir()
        if p.is_dir() and (p / "plugin.py").is_file() and not p.name.startswith("_")
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    plugins = discover()
    if not plugins:
        log.warning("no plugins found under %s", PLUGINS_DIR)
        return

    procs: list[tuple[str, subprocess.Popen]] = []
    for path in plugins:
        name = path.parent.name
        log.info("starting plugin %s", name)
        procs.append((name, subprocess.Popen([sys.executable, str(path)])))

    def shutdown(*_args: object) -> None:
        for name, p in procs:
            log.info("stopping plugin %s", name)
            p.terminate()
        for name, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning("plugin %s did not exit cleanly, killing", name)
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        while True:
            time.sleep(1)
            for name, p in procs:
                if p.poll() is not None:
                    log.warning("plugin %s exited with code %s", name, p.returncode)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
