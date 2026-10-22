#!/usr/bin/env python3
"""Copy selected DOCX/XLSX sources and extract locatable text, without interpreting it."""
import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def docx(z):
    document = ET.fromstring(z.read('word/document.xml'))
    body = document.find(W + 'body')
    entries = []
    if body is None:
        raise ValueError('Missing document body')
    for i, paragraph in enumerate(body.iter(W + 'p'), 1):
        value = ''.join(x.text or '' for x in paragraph.iter(W + 't'))
        if value.strip():
            entries.append({'location': f'body paragraph {i}', 'text': value})
    warnings = ['Paragraph numbers are XML order, not page numbers; page layout is not extracted.',
                'Headers, footers, comments, text boxes, embedded files and images require separate inspection.']
    return entries, warnings


def xlsx(z):
    book = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets = {r.get('Id'): r.get('Target', '') for r in rels.findall(P + 'Relationship')}
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        shared_root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        shared = [''.join(n.text or '' for n in e.iter(S + 't')) for e in shared_root.findall(S + 'si')]
    entries, warnings = [], ['Formatting, charts, images, comments and embedded objects are not extracted.',
                              'Dates and formatted numbers are raw cell values; interpretation requires inspection.']
    for sheet in book.findall('.//' + S + 'sheet'):
        name, target = sheet.get('name'), targets.get(sheet.get(R + 'id'))
        if not target:
            warnings.append(f'Sheet {name}: missing relationship')
            continue
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        # OOXML relationship targets may include relative segments.
        import posixpath
        target = posixpath.normpath(target)
        if not target.startswith('xl/') or target not in z.namelist():
            warnings.append(f'Sheet {name}: content unavailable')
            continue
        root = ET.fromstring(z.read(target))
        for c in root.iter(S + 'c'):
            ref = c.get('r', '?')
            formula, v = c.find(S + 'f'), c.find(S + 'v')
            text = v.text if v is not None else None
            typ = c.get('t')
            if typ == 's' and text is not None:
                try: text = shared[int(text)]
                except (ValueError, IndexError):
                    warnings.append(f'Sheet {name} cell {ref}: invalid shared string')
                    text = None
            elif typ == 'inlineStr':
                text = ''.join(n.text or '' for n in c.iter(S + 't'))
            entry = {'location': f'{name}!{ref}', 'text': text}
            if formula is not None:
                entry['formula'] = formula.text or ''
                if text is None or text == '': warnings.append(f'Sheet {name} cell {ref}: formula has no cached value')
            if text not in (None, '') or formula is not None: entries.append(entry)
    return entries, warnings


def extract(root, source):
    source = Path(source)
    if not source.is_file() or source.suffix.lower() not in ('.docx', '.xlsx'):
        raise ValueError('Select an existing .docx or .xlsx file')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with zipfile.ZipFile(source) as z:
        entries, warnings = docx(z) if source.suffix.lower() == '.docx' else xlsx(z)
    dest = root / 'documents' / 'sources'
    dest.mkdir(parents=True, exist_ok=True)
    original = dest / (digest[:16] + source.suffix.lower())
    if original.exists() and hashlib.sha256(original.read_bytes()).hexdigest() != digest:
        raise ValueError('Source ID collision')
    if not original.exists(): shutil.copyfile(source, original)
    result = {'id': digest[:16], 'sha256': digest, 'original_name': source.name,
              'original_copy': str(original.relative_to(root)), 'received': date.today().isoformat(),
              'coverage': 'partial', 'warnings': warnings, 'entries': entries}
    extraction = dest / (digest[:16] + '.extraction.json')
    extraction.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+', help='explicitly selected DOCX/XLSX files')
    args = parser.parse_args()
    for source in args.sources:
        try:
            result = extract(ROOT, source)
        except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            parser.exit(1, f'{source}: extraction failed: {exc}\n')
        print(f"{result['id']} {result['original_copy']}: {len(result['entries'])} entries; coverage partial")


if __name__ == '__main__': main()
