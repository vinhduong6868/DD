"""Migrate existing private state to Supervisor's app-specific config volume."""
import os
import re
import tempfile
from pathlib import Path


def migrate_private_data(source='/data', destination='/config'):
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    names = {'transport.json', 'shared_entities.json', 'link.json', 'local-link.json', 'local-link.migrated.json'}
    for item in source.iterdir():
        if item.name not in names and not re.fullmatch(r'local-link-[a-f0-9]{64}\.json', item.name):
            continue
        if item.is_symlink() or not item.is_file():
            raise ValueError('private_data_invalid')
        if item.name == 'local-link.json' and (destination / 'local-link.migrated.json').exists():
            continue
        target = destination / item.name
        if target.exists():
            continue
        fd, temporary = tempfile.mkstemp(prefix='.migrate-', dir=destination)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(item.read_bytes())
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
