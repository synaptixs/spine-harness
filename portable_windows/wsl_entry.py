"""Argument-preserving bridge from PowerShell/wsl.exe; no shell evaluation."""
import os
import sys
from pathlib import Path


def main():
    if sys.platform != 'linux': raise SystemExit('Use this entry point inside WSL2 Ubuntu')
    if not sys.argv[1:]: raise SystemExit('Missing harness command')
    root = Path(__file__).resolve().parent
    os.chdir(root)
    home = Path.home()
    os.environ['PATH'] = os.pathsep.join((str(home/'.local/bin'), str(home/'.npm-global/bin'), os.environ.get('PATH', '')))
    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])

if __name__ == '__main__': main()
