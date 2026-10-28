"""Compare exported CV text with an approved plain-text transcript."""
import argparse
import difflib
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET


def normalize(text):
    # Preserve case, punctuation and numeric boundaries; ignore only layout whitespace,
    # soft hyphens and Unicode compatibility forms (including presentation ligatures).
    text = unicodedata.normalize('NFKC', text).replace('\u00ad', '')
    return text.split()


def extract(path):
    if path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError('PDF extraction requires pypdf in the active Python environment.') from exc
        reader = PdfReader(path)
        pages = [page.extract_text() or '' for page in reader.pages]
        if not pages or any(not page.strip() for page in pages):
            raise ValueError('PDF contains a page without extractable text; inspect it manually (no OCR performed).')
        return '\n'.join(pages), 'pypdf ' + importlib.metadata.version('pypdf')
    if path.suffix.lower() == '.docx':
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
            # Includes table paragraphs and text boxes in XML order. Header/footer text
            # is appended and therefore intentionally produces differences if substantive.
            names = ['word/document.xml'] + sorted(
                name for name in archive.namelist()
                if re.fullmatch(r'word/(header|footer)\d+\.xml', name))
            paragraphs = []
            for name in names:
                tree = root if name == names[0] else ET.fromstring(archive.read(name))
                for paragraph in tree.findall('.//w:p', ns):
                    parts = []
                    for element in paragraph.iter():
                        if element.tag == '{%s}t' % ns['w']:
                            parts.append(element.text or '')
                        elif element.tag in ('{%s}tab' % ns['w'], '{%s}br' % ns['w']):
                            parts.append(' ')
                    paragraphs.append(''.join(parts))
        return '\n'.join(paragraphs), 'stdlib OOXML (XML order)'
    raise ValueError('Export must be PDF or DOCX.')


def compare(expected, actual):
    left, right = normalize(expected), normalize(actual)
    if not left:
        raise ValueError('Approved transcript is empty.')
    changes = []
    for tag, a, b, c, d in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if tag != 'equal':
            changes.append({'kind': tag, 'expected_token_offset': a,
                            'actual_token_offset': c, 'expected': ' '.join(left[a:b]),
                            'actual': ' '.join(right[c:d])})
    return {'status': 'PASS' if not changes else 'FAIL', 'changes': changes}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', required=True, type=Path,
                        help='Approved UTF-8 plain text in intended reading order; no Markdown markup.')
    parser.add_argument('--export', required=True, action='append', type=Path)
    parser.add_argument('--report', required=True, type=Path, help='New private JSON report (never overwritten).')
    args = parser.parse_args(argv)
    inputs = [args.expected, *args.export]
    if args.report.exists() or args.report.resolve() in [p.resolve() for p in inputs]:
        parser.error('Report must be a new file, separate from all inputs.')
    report = {'schema_version': 1, 'scope': 'Text fidelity only; not ATS certification or visual review.',
              'expected': str(args.expected.resolve()), 'exports': []}
    try:
        expected = args.expected.read_text(encoding='utf-8')
        if not normalize(expected):
            raise ValueError('Approved transcript is empty.')
        report['expected_sha256'] = sha(args.expected)
        for path in args.export:
            item = {'path': str(path.resolve())}
            try:
                item['sha256'] = sha(path)
                actual, engine = extract(path)
                item.update(compare(expected, actual))
                item.update(extractor=engine, extracted_text=actual)
            except Exception as exc:
                item.update(status='ERROR', error=str(exc))
            report['exports'].append(item)
        statuses = [item['status'] for item in report['exports']]
        report['status'] = 'ERROR' if 'ERROR' in statuses else ('FAIL' if 'FAIL' in statuses else 'PASS')
    except Exception as exc:
        report.update(status='ERROR', error=str(exc))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f"{report['status']}: {args.report}")
    return {'PASS': 0, 'FAIL': 1, 'ERROR': 2}[report['status']]


if __name__ == '__main__':
    sys.exit(main())
