import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wsl_support
from project_adapter import sandboxed_command


class WSLTests(unittest.TestCase):
    def test_command_confines_writes_and_network_and_preserves_argv(self):
        with tempfile.TemporaryDirectory(prefix='test space ') as t:
            root = Path(t).resolve()
            with patch('wsl_support.sys.platform', 'linux'), patch('wsl_support.shutil.which', return_value='/usr/bin/bwrap'):
                cmd, scratch = sandboxed_command(['python3', '-c', 'print("space; $HOME")'], root)
            self.assertEqual(cmd[cmd.index('--ro-bind')+1:cmd.index('--ro-bind')+3], ['/', '/'])
            self.assertEqual(cmd[cmd.index('--bind')+1:cmd.index('--bind')+3], [str(root), str(root)])
            for flag in ('--unshare-net','--unshare-pid','--unshare-user','--die-with-parent','--new-session'): self.assertIn(flag, cmd)
            self.assertEqual(cmd[-3:], ['python3','-c','print("space; $HOME")'])
            self.assertEqual(scratch, root / '.benchmark-tmp')

    def test_missing_bubblewrap_fails_closed(self):
        with patch('wsl_support.sys.platform','linux'), patch('wsl_support.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'bubblewrap'): wsl_support.linux_sandbox_command(['true'], Path('/tmp'))

    def test_native_windows_fails_closed(self):
        with patch('wsl_support.sys.platform','win32'):
            with self.assertRaises(RuntimeError): sandboxed_command(['true'], Path('/tmp'))

    def test_refuse_root_write_mount(self):
        with patch('wsl_support.sys.platform','linux'), patch('wsl_support.shutil.which', return_value='/usr/bin/bwrap'):
            with self.assertRaises(ValueError): wsl_support.linux_sandbox_command(['true'], Path('/'))

    def test_namespace_denial_fails_smoke_probe(self):
        with patch('wsl_support.sys.platform','linux'), patch('wsl_support.shutil.which', return_value='/usr/bin/bwrap'), patch('wsl_support.subprocess.run', return_value=subprocess.CompletedProcess([],1,'','namespace denied')), patch('wsl_support.socket.socket') as sock:
            sock.return_value.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 12345)
            with self.assertRaisesRegex(RuntimeError, 'namespace denied'): wsl_support.verify_linux_sandbox()

if __name__ == '__main__': unittest.main()
