"""Keep pairing secrets bound to their TLS certificate audience."""
import json
import os
import tempfile
from pathlib import Path


def write_credentials(chosen, credentials):
    record = {key: credentials[key] for key in ('link_id', 'link_secret')}
    if not all(isinstance(value, str) and value for value in record.values()):
        raise ValueError('credentials_invalid')
    if chosen.mode == 'local':
        record['core_sha256'] = chosen.fingerprint.hex()
    path = chosen.credentials_path
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.link-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(record, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_credentials(chosen):
    path = chosen.credentials_path
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if chosen.mode == 'local' and record.get('core_sha256') != chosen.fingerprint.hex():
        raise ValueError('credential_audience_mismatch')
    if not all(isinstance(record.get(key), str) and record[key] for key in ('link_id', 'link_secret')):
        raise ValueError('credentials_invalid')
    return {key: record[key] for key in ('link_id', 'link_secret')}


def migrate_legacy(chosen):
    # Called once at startup, using the configuration that existed before edits.
    # Never call this when selecting a new Core in the form.
    if chosen.mode != 'local':
        return
    legacy = chosen.credentials_path.parent / 'local-link.json'
    if not legacy.exists():
        return
    if not chosen.credentials_path.exists():
        record = json.loads(legacy.read_text())
        if record.get('core_sha256') not in (None, chosen.fingerprint.hex()):
            raise ValueError('credential_audience_mismatch')
        write_credentials(chosen, record)
    else:
        read_credentials(chosen)
    os.replace(legacy, legacy.with_name('local-link.migrated.json'))
