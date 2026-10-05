"""Verify release checksums without third-party packages or model access."""
from pathlib import Path
import hashlib
root = Path(__file__).resolve().parent
count = 0
for line in (root / 'SHA256SUMS').read_text().splitlines():
    digest, relative = line.split('  ', 1)
    p = (root / relative).resolve()
    if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        raise SystemExit('Integrity check failed: ' + relative)
    count += 1
print(f'Verified {count} packaged files.')
