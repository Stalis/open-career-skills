#!/usr/bin/env python3
"""Create a private application directory with deterministic identity; no submissions."""
import argparse
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent


def canonical_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('A valid HTTP(S) URL without credentials is required')
    host = parts.hostname.lower()
    port = parts.port
    netloc = host if port is None or (parts.scheme.lower(), port) in (('http', 80), ('https', 443)) else f'{host}:{port}'
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('ref', 'source', 'trk')]
    return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip('/') or '/', urlencode(sorted(query)), ''))


def slug(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:48] or 'role'


def initialize(root, company, role, url=None, source_id=None):
    if not company.strip() or not role.strip():
        raise ValueError('Company and role are required')
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
    for path in base.glob('*/identity.json'):
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
        (folder / 'identity.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return folder
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    folder = base / f'{slug(company)}-{slug(role)}-{digest}'
    folder.mkdir(exist_ok=False)
    data = {'identity': identity, 'source_id': source_id or None, 'url': normalized}
    (folder / 'identity.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (folder / 'job.md').write_text(f'# Job\n\n- Source URL: {url or "not provided"}\n- Received: {date.today().isoformat()}\n- Coverage: unknown; full text not yet recorded\n\n## Available text\n', encoding='utf-8')
    (folder / 'status.md').write_text('# Status\n\n- State: INBOX\n- Eligibility: unknown\n- Next step: record available job text and coverage\n', encoding='utf-8')
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--company', required=True)
    init.add_argument('--role', required=True)
    init.add_argument('--url')
    init.add_argument('--source-id')
    args = parser.parse_args()
    try:
        print(initialize(ROOT, args.company, args.role, args.url, args.source_id).relative_to(ROOT))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
