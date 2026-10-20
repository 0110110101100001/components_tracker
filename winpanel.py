"""Start and stop the detached panel on Windows: what systemd-run / systemctl do on Linux.

The running panel is found by its command line (a python naming this widget.py),
not by a pid file: Windows reuses pids, and a stale file would block or kill the
wrong process.

Autostart is a value in the per-user Run key (listed, and can be disabled, in
Task Manager > Startup) that opens the panel at login through autostart.vbs.
"""

import os
import subprocess
import sys
import winreg
from pathlib import Path

import psutil

WIDGET = Path(__file__).resolve().with_name("widget.py")
LOG_PATH = WIDGET.with_name("data") / "panel.log"
LAUNCHER = WIDGET.with_name("autostart.vbs")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "pc-monitor"
# A panel that dies on startup (missing DLL, bad config) does so within this.
STARTUP_SECONDS = 3


def same_file(arg, cwd):
    return os.path.normcase(os.path.join(cwd, arg)) == os.path.normcase(WIDGET)


def panels():
    """The running panel processes, foreground (`pixi run panel`) ones included."""
    found = []
    for proc in psutil.process_iter(["cmdline"]):
        try:
            args = [arg for arg in proc.info["cmdline"] or []
                    if arg.lower().endswith("widget.py")]
            if args and any(same_file(arg, proc.cwd()) for arg in args):
                found.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def start():
    running = panels()
    if running:
        print(f"pc-monitor: already running (pid {running[0].pid})", file=sys.stderr)
        return 1
    LOG_PATH.parent.mkdir(exist_ok=True)
    # pythonw, not python: a detached console program gets a console window of
    # its own. The child inherits pixi's environment, so the GTK DLLs resolve.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    with open(LOG_PATH, "w", encoding="utf-8") as log:
        child = subprocess.Popen(
            [str(pythonw), str(WIDGET)], cwd=WIDGET.parent,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        code = child.wait(timeout=STARTUP_SECONDS)
    except subprocess.TimeoutExpired:
        print(f"pc-monitor: started (pid {child.pid})")
        return 0
    print(f"pc-monitor: exited on startup with code {code}, see {LOG_PATH}",
          file=sys.stderr)
    return 1


def stop():
    running = panels()
    if not running:
        print("pc-monitor: not running")
        return 0
    for proc in running:
        proc.terminate()
    _gone, alive = psutil.wait_procs(running, timeout=5)
    for proc in alive:
        proc.kill()
    print(f"pc-monitor: stopped (pid {', '.join(str(p.pid) for p in running)})")
    return 0


def resurrect():
    """Stop whatever panel runs (off-screen, wedged, or none at all), then open a fresh one."""
    stop()
    return start()


def autostart_command():
    # wscript, not cscript: a .vbs run by wscript has no console window.
    # PIXI_EXE is set by `pixi run`; passed on so login needs no pixi on PATH.
    wscript = Path(os.environ["SystemRoot"], "System32", "wscript.exe")
    return f'"{wscript}" //B //Nologo "{LAUNCHER}" "{os.environ["PIXI_EXE"]}"'


def autostart():
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, autostart_command())
    print(f"pc-monitor: opens at login (HKCU\\{RUN_KEY}\\{RUN_VALUE})")
    return 0


def autostart_off():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except FileNotFoundError:
        print("pc-monitor: autostart was not on")
        return 0
    print("pc-monitor: no longer opens at login")
    return 0


def main(argv):
    commands = {"start": start, "stop": stop, "resurrect": resurrect,
                "autostart": autostart, "autostart-off": autostart_off}
    if len(argv) != 2 or argv[1] not in commands:
        print(f"usage: {argv[0]} {'|'.join(commands)}", file=sys.stderr)
        return 2
    return commands[argv[1]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
