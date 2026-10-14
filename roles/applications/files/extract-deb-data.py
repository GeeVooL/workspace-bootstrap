"""Extract only the data tar member of an official Debian ar archive."""
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:])
with source.open('rb') as archive:
    if archive.read(8) != b'!<arch>\n':
        raise ValueError('Not a Debian ar archive')
    while header := archive.read(60):
        if len(header) != 60 or header[58:60] != b'`\n':
            raise ValueError('Invalid ar header')
        name = header[:16].decode('ascii').strip().rstrip('/')
        size = int(header[48:58])
        if name in ('data.tar', 'data.tar.gz', 'data.tar.xz', 'data.tar.zst', 'data.tar.bz2'):
            with destination.open('xb') as output:
                remaining = size
                while remaining:
                    chunk = archive.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise ValueError('Truncated Debian data archive')
                    output.write(chunk)
                    remaining -= len(chunk)
            break
        archive.seek(size + size % 2, 1)
    else:
        raise ValueError('No data archive in Debian package')
