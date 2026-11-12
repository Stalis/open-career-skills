#!/usr/bin/env python3
"""Build a PDF from supported resume Markdown using project-local Typst."""
import argparse
import errno
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__:
    from .install_dependencies import ROOT, TYPST_VERSION, typst_executable
    from .resume_model import parse_markdown
else:
    from install_dependencies import ROOT, TYPST_VERSION, typst_executable
    from resume_model import parse_markdown

FONT_NAMES = ('Regular', 'Bold', 'Italic', 'BoldItalic')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source.suffix.lower() != '.md' or not source.is_file():
        raise ValueError('Select an existing Markdown (.md) resume')
    if output.suffix.lower() != '.pdf':
        raise ValueError('Output must be a .pdf file')
    if output.exists():
        raise ValueError(f'Refusing to overwrite {output}')
    if output.parent.name == 'final':
        work = output.parent.parent / 'work'
    elif output.parent.name == 'work':
        work = output.parent
    else:
        work = output.parent / 'work'
    manifest_path = work / (output.stem + '.manifest.json')
    if manifest_path.exists():
        raise ValueError(f'Refusing to overwrite {manifest_path}')
    markdown = source.read_bytes()
    model = parse_markdown(markdown.decode('utf-8-sig'))
    payload = json.dumps(model.to_dict(), ensure_ascii=False, separators=(',', ':'))
    # Linux limits each individual argument to 128 KiB; use the same predictable bound everywhere.
    if len(('data=' + payload).encode('utf-8')) > 120_000:
        raise ValueError('Resume JSON exceeds the 120000-byte --input limit; shorten the document')
    template = ROOT / 'templates/resume.typ'
    template_bytes = template.read_bytes()
    fonts = ROOT / 'documents/fonts/EB_Garamond'
    font_hashes = {}
    for name in FONT_NAMES:
        path = fonts / f'EBGaramond-{name}.ttf'
        if not path.is_file():
            raise ValueError(f'Missing licensed font: {path}; see docs/TYPST.md')
        font_hashes[path.name] = sha(path.read_bytes())
    if not (fonts / 'OFL.txt').is_file():
        raise ValueError(f'Missing font license: {fonts / "OFL.txt"}')
    binary = typst_executable()
    version = subprocess.check_output([str(binary), '--version'], text=True).strip()
    if not version.startswith(f'typst {TYPST_VERSION} '):
        raise ValueError(f'Unexpected Typst version: {version}; run make install')
    work.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='typst-', dir=work) as temporary:
        staging = Path(temporary)
        # Compile exact captured template/fonts; the manifest fingerprints these same bytes.
        local_template = staging / 'resume.typ'
        local_template.write_bytes(template_bytes)
        local_fonts = staging / 'fonts'
        local_fonts.mkdir()
        for name, digest in font_hashes.items():
            data = (fonts / name).read_bytes()
            if sha(data) != digest:
                raise ValueError('Font changed during build; retry')
            (local_fonts / name).write_bytes(data)
        pdf = staging / 'resume.pdf'
        args = [str(binary), 'compile', str(local_template), str(pdf), '--root', str(staging),
                '--font-path', str(local_fonts), '--ignore-system-fonts', '--ignore-embedded-fonts',
                '--creation-timestamp', '0', '--input', 'data=' + payload]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Typst compilation timed out after 180 seconds') from exc
        except OSError as exc:
            if exc.errno == errno.E2BIG or getattr(exc, 'winerror', None) == 206:
                raise ValueError('Resume JSON exceeds this OS command-line limit') from exc
            raise
        if result.returncode or not pdf.is_file():
            raise ValueError('Typst compilation failed: ' + (result.stderr.strip() or 'no PDF produced'))
        if 'warning:' in result.stderr:
            raise ValueError('Typst reported a warning; resolve before export: ' + result.stderr.strip())
        data = pdf.read_bytes()
        manifest = {'schema_version': 1, 'renderer': version, 'typst_binary_sha256': sha(binary.read_bytes()),
                    'python_version': sys.version.split()[0],
                    'markdown_it_py_version': importlib.metadata.version('markdown-it-py'),
                    'source': str(source), 'markdown_sha256': sha(markdown),
                    'model_sha256': sha(payload.encode('utf-8')), 'template_sha256': sha(template_bytes),
                    'fonts_sha256': font_hashes, 'pdf': str(output), 'pdf_sha256': sha(data),
                    'parameters': {'input': 'data=<JSON; hash above>', 'font': 'EB Garamond',
                                   'system_fonts': False, 'embedded_fonts': False, 'creation_timestamp': 0},
                    'scope': 'Build only; candidate text approval, export check and independent review are separate.'}
        created_pdf = False
        created_manifest = False
        try:
            with output.open('xb') as stream:
                created_pdf = True
                stream.write(data)
            with manifest_path.open('x', encoding='utf-8') as stream:
                created_manifest = True
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        except OSError:
            if created_pdf:
                output.unlink(missing_ok=True)
            if created_manifest:
                manifest_path.unlink(missing_ok=True)
            raise
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('markdown', type=Path)
    parser.add_argument('pdf', type=Path)
    args = parser.parse_args()
    try:
        manifest = build(args.markdown, args.pdf)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'{exc}\n')
    print(f'Created {args.pdf}; build manifest: {manifest}')


if __name__ == '__main__':
    main()
