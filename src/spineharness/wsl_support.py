"""Linux/WSL2 application-check confinement. Never fall back to unsandboxed tests."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def linux_sandbox_command(command, root):
    if sys.platform != 'linux' or not shutil.which('bwrap'):
        raise RuntimeError('WSL2 Ubuntu requires bubblewrap: sudo apt-get install bubblewrap')
    root = Path(root).resolve()
    if root == Path('/') or not root.is_dir():
        raise ValueError('Sandbox root must be an existing disposable repository directory')
    temporary = root / '.benchmark-tmp'; temporary.mkdir(exist_ok=True)
    # All mounts read-only except this disposable checkout. No host network or PID namespace.
    argv = ['bwrap', '--die-with-parent', '--new-session', '--unshare-user', '--unshare-pid',
            '--unshare-net', '--unshare-ipc', '--unshare-uts', '--ro-bind', '/', '/',
            '--proc', '/proc', '--dev', '/dev', '--bind', str(root), str(root),
            '--chdir', str(root), '--', *command]
    return argv, temporary


def verify_linux_sandbox():
    """Exercise real confinement before model spending; namespace denials are fatal."""
    if sys.platform != 'linux': raise RuntimeError('This smoke test requires Linux/WSL2')
    with tempfile.TemporaryDirectory(prefix='harness-confinement-', dir='/tmp') as temp:
        base = Path(temp); repo = base / 'repo'; repo.mkdir()
        outside = base / 'outside.txt'; outside.write_text('unchanged')
        (repo / 'escape').symlink_to(outside)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen()
            script = '''import pathlib,socket,sys
root=pathlib.Path(sys.argv[1]);outside=pathlib.Path(sys.argv[2])
(root/'allowed.txt').write_text('ok')
for path in (outside,root/'escape'):
    try: path.write_text('forbidden')
    except OSError: pass
    else: raise RuntimeError('sandbox allowed a write outside the repository')
s=socket.socket();s.settimeout(2)
try: s.connect(('127.0.0.1',int(sys.argv[3])))
except OSError: pass
else: raise RuntimeError('sandbox reached a host network listener')
finally: s.close()
print('read-only outside repository; symlink escape blocked; host network isolated')
'''
            command, scratch = linux_sandbox_command([sys.executable, '-c', script, str(repo), str(outside), str(listener.getsockname()[1])], repo)
            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL')}
            env.update(TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
            p = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
        if p.returncode or outside.read_text() != 'unchanged' or not (repo/'allowed.txt').exists():
            raise RuntimeError('WSL2 bubblewrap confinement failed; do not run without it. Check WSL2/kernel and namespace policy. ' + (p.stderr or p.stdout)[-1500:])
        print(p.stdout.strip())

if __name__ == '__main__': verify_linux_sandbox()
