#!/usr/bin/env python3
"""Convert a DOCX to PDF with headless LibreOffice, found without Codex-only tooling."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from install_dependencies import ROOT, executable


def find_soffice():
    return str(executable())


def render(docx, pdf, soffice=None):
    docx, pdf = Path(docx).resolve(), Path(pdf).resolve()
    if docx.suffix.lower() != '.docx' or not docx.is_file():
        raise ValueError('Select an existing .docx file')
    if pdf.exists():
        raise ValueError(f'Refusing to overwrite {pdf}')
    soffice = soffice or find_soffice()
    pdf.parent.mkdir(parents=True, exist_ok=True)
    work = ROOT / 'tmp' / 'render'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as out, tempfile.TemporaryDirectory(dir=work) as profile:
        # Private profile: avoids lock-ups with a running LibreOffice and keeps results repeatable.
        cmd = [soffice, f'-env:UserInstallation={Path(profile).as_uri()}', '--headless', '--convert-to', 'pdf:writer_pdf_Export', '--outdir', out, str(docx)]
        env = os.environ.copy()
        env.update(HOME=profile, XDG_CONFIG_HOME=str(Path(profile) / 'config'),
                   XDG_CACHE_HOME=str(Path(profile) / 'cache'), TMPDIR=out, TEMP=out, TMP=out)
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
        produced = Path(out) / (docx.stem + '.pdf')
        if done.returncode or not produced.is_file():
            raise ValueError(f'LibreOffice exited {done.returncode}: ' + ((done.stderr or done.stdout).strip() or 'no diagnostic output; check OS/application execution restrictions'))
        shutil.move(produced, pdf)
    version = subprocess.run([soffice, '--version'], capture_output=True, text=True).stdout.strip()
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docx', type=Path)
    parser.add_argument('pdf', type=Path)
    args = parser.parse_args()
    try:
        print(f'{args.pdf}: rendered by {render(args.docx, args.pdf)}')
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(f'render failed: {exc}')


if __name__ == '__main__':
    main()
