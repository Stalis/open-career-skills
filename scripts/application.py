#!/usr/bin/env python3
"""Create a private application directory with deterministic identity; no submissions."""
import argparse
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def valid_date(value):
    if value is None:
        return date.today().isoformat()
    value = str(value).strip()
    if not DATE_RE.fullmatch(value):
        raise ValueError('Date must be in YYYY-MM-DD format')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Date must be a valid calendar date in YYYY-MM-DD format') from exc
    return value


def iter_identity_files(base):
    seen = set()
    for pattern in ('[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/*/identity.json', '*/identity.json'):
        for path in sorted(base.glob(pattern)):
            resolved = path.resolve()
            if resolved not in seen and path.is_file():
                seen.add(resolved)
                yield path


def canonical_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('A valid HTTP(S) URL without credentials is required')
    host = parts.hostname.lower()
    port = parts.port
    host = f'[{host}]' if ':' in host else host
    netloc = host if port is None or (parts.scheme.lower(), port) in (('http', 80), ('https', 443)) else f'{host}:{port}'
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('ref', 'source', 'trk')]
    fragment = parts.fragment if parts.fragment.startswith(('/', '!')) else ''
    return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip('/') or '/', urlencode(sorted(query)), fragment))


def slug(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:48] or 'role'


def initialize(root, company, role, url=None, source_id=None, created_date=None):
    if not company.strip() or not role.strip():
        raise ValueError('Company and role are required')
    day = valid_date(created_date)
    source_id = (source_id or '').strip()
    normalized = canonical_url(url) if url else None
    if not source_id and not normalized:
        raise ValueError('Supply a stable source ID or URL')
    identity = 'source:' + source_id if source_id else 'url:' + normalized
    base = root / 'output' / 'applications'
    base.mkdir(parents=True, exist_ok=True)
    # Existing metadata also matches either source identifier, avoiding a new folder
    # if a second identifier becomes available later. Ambiguous matches require review.
    matches = []
    for path in iter_identity_files(base):
        data = json.loads(path.read_text(encoding='utf-8'))
        if (source_id and data.get('source_id') == source_id) or (normalized and data.get('url') == normalized):
            matches.append((path.parent, data))
    if len(matches) > 1:
        raise ValueError('Multiple matching applications; resolve the duplicate manually')
    if matches:
        folder, data = matches[0]
        if source_id and data.get('source_id') and data['source_id'] != source_id:
            raise ValueError('URL already has a different source ID; review possible duplicate')
        if normalized and data.get('url') and data['url'] != normalized:
            raise ValueError('Source ID already has a different URL; review possible duplicate')
        data['source_id'] = data.get('source_id') or source_id or None
        data['url'] = data.get('url') or normalized
        fd, temporary = tempfile.mkstemp(dir=folder, prefix='.identity-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            os.replace(temporary, folder / 'identity.json')
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return folder
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    day_dir = base / day
    day_dir.mkdir(parents=True, exist_ok=True)
    folder = day_dir / f'{slug(company)}-{slug(role)}-{digest}'
    data = {'identity': identity, 'source_id': source_id or None, 'url': normalized}
    with tempfile.TemporaryDirectory(prefix='.pending-', dir=day_dir) as temporary:
        pending = Path(temporary)
        (pending / 'identity.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (pending / 'job.md').write_text(f'# Job\n\n- Source URL: {url or "not provided"}\n- Received: {day}\n- Coverage: unknown; full text not yet recorded\n\n## Available text\n', encoding='utf-8')
        (pending / 'status.md').write_text('# Status\n\n- State: INBOX\n- Eligibility: unknown\n- Next step: record available job text and coverage\n', encoding='utf-8')
        pending.rename(folder)
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--company', required=True)
    init.add_argument('--role', required=True)
    init.add_argument('--url')
    init.add_argument('--source-id')
    init.add_argument('--date', dest='created_date', help='Creation date YYYY-MM-DD (defaults to today; use date_applied for Hirify imports)')
    args = parser.parse_args()
    try:
        print(initialize(ROOT, args.company, args.role, args.url, args.source_id, args.created_date).relative_to(ROOT))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
