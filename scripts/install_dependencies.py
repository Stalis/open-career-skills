#!/usr/bin/env python3
"""Install document tools locally. Bootstrap requires Python 3.9+, curl and OS unpack tools."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / '.tools'
UV_VERSION = '0.9.5'
LO_VERSION = '25.8.2.2'


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        partial = target.with_suffix(target.suffix + '.partial')
        run(['curl', '--fail', '--location', '--retry', '3', '--output', partial, url])
        partial.replace(target)
    return target


def verify(path, checksum_url):
    checksum = download(checksum_url, path.with_suffix(path.suffix + '.sha256'))
    expected = checksum.read_text().split()[0].lower()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f'Checksum mismatch for {path}; remove cached download and retry')
    return actual


def environment():
    env = os.environ.copy()
    for key, relative in {'UV_CACHE_DIR': '.tools/cache/uv',
                          'UV_PYTHON_INSTALL_DIR': '.tools/python',
                          'UV_PYTHON_BIN_DIR': '.tools/bin',
                          'PIP_CACHE_DIR': '.tools/cache/pip'}.items():
        env[key] = str(ROOT / relative)
    return env


def executable():
    record = TOOLS / 'installed.json'
    if not record.exists():
        raise RuntimeError('Run make install first')
    data = json.loads(record.read_text())
    path = (ROOT / data['soffice']).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise RuntimeError('Invalid or missing project-local LibreOffice')
    return path


def uv_executable(archive_path, system):
    name = 'uv.exe' if system == 'Windows' else 'uv'
    uv_dir = TOOLS / 'uv'
    existing = next(uv_dir.rglob(name), None) if uv_dir.exists() else None
    if existing:
        return existing
    if uv_dir.exists():
        shutil.rmtree(uv_dir)
    with tempfile.TemporaryDirectory(prefix='.uv-', dir=TOOLS) as staging:
        unpacked = Path(staging) / 'uv'
        unpacked.mkdir()
        if system == 'Windows':
            import zipfile
            with zipfile.ZipFile(archive_path) as package:
                package.extractall(unpacked)
        else:
            run(['tar', '-xzf', archive_path, '-C', unpacked])
        if not any(unpacked.rglob(name)):
            raise RuntimeError('uv archive did not contain its executable')
        unpacked.rename(uv_dir)
    return next(uv_dir.rglob(name))


def install():
    system = platform.system()
    arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'AMD64': 'x86_64',
            'x86_64': 'x86_64'}.get(platform.machine())
    triples = {('Darwin', 'aarch64'): 'aarch64-apple-darwin',
               ('Darwin', 'x86_64'): 'x86_64-apple-darwin',
               ('Linux', 'x86_64'): 'x86_64-unknown-linux-gnu',
               ('Windows', 'x86_64'): 'x86_64-pc-windows-msvc'}
    if (system, arch) not in triples:
        raise RuntimeError(f'Unsupported native distribution: {system}/{platform.machine()}')
    TOOLS.mkdir(exist_ok=True)
    env = environment()
    triple = triples[system, arch]
    extension = 'zip' if system == 'Windows' else 'tar.gz'
    uv_name = f'uv-{triple}.{extension}'
    uv_archive = download(f'https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{uv_name}', TOOLS / 'downloads' / uv_name)
    verify(uv_archive, f'https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{uv_name}.sha256')
    uv = uv_executable(uv_archive, system)
    run([uv, 'python', 'install', '3.12.12'], env=env)
    venv = ROOT / '.venv'
    cfg = venv / 'pyvenv.cfg'
    if cfg.exists() and str(TOOLS / 'python') not in cfg.read_text():
        backup = TOOLS / ('previous-venv-' + str(time.time_ns()))
        venv.rename(backup)
        print('Preserved external-runtime environment at', backup)
    if not venv.exists():
        run([uv, 'venv', '--python', '3.12.12', venv], env=env)
    python = venv / ('Scripts/python.exe' if system == 'Windows' else 'bin/python')
    run([uv, 'pip', 'install', '--python', python, '-r', ROOT / 'requirements.txt'], env=env)
    lo = TOOLS / 'libreoffice' / f'{LO_VERSION}-{system}-{arch}'
    if system == 'Darwin':
        filename = f'LibreOffice_{LO_VERSION}_MacOS_{arch}.dmg'
        suffix = f'mac/{arch}/{filename}'
        soffice = lo / 'LibreOffice.app/Contents/MacOS/soffice'
    elif system == 'Linux':
        filename = f'LibreOffice_{LO_VERSION}_Linux_x86-64_deb.tar.gz'
        suffix = f'deb/x86_64/{filename}'
        soffice = lo / 'opt' / ('libreoffice' + '.'.join(LO_VERSION.split('.')[:2])) / 'program/soffice'
    else:
        filename = f'LibreOffice_{LO_VERSION}_Win_x86-64.msi'
        suffix = f'win/x86_64/{filename}'
        soffice = lo / 'program/soffice.exe'
    url = f'https://downloadarchive.documentfoundation.org/libreoffice/old/{LO_VERSION}/{suffix}'
    package = download(url, TOOLS / 'downloads' / filename)
    digest = verify(package, url + '.sha256')
    if not soffice.exists():
        lo.mkdir(parents=True, exist_ok=True)
        if system == 'Darwin':
            mount = TOOLS / 'mount'
            mount.mkdir(exist_ok=True)
            run(['hdiutil', 'attach', '-nobrowse', '-readonly', '-mountpoint', mount, package])
            try:
                run(['ditto', mount / 'LibreOffice.app', lo / 'LibreOffice.app'])
            finally:
                run(['hdiutil', 'detach', mount])
        elif system == 'Linux':
            unpack = TOOLS / 'unpack'
            unpack.mkdir(exist_ok=True)
            run(['tar', '-xzf', package, '-C', unpack])
            for deb in sorted(unpack.rglob('*.deb')):
                run(['dpkg-deb', '-x', deb, lo])
        else:
            run(['msiexec', '/a', package, '/qn', f'TARGETDIR={lo}'])
    version = subprocess.check_output([str(soffice), '--version'], text=True).strip()
    (TOOLS / 'installed.json').write_text(json.dumps({
        'platform': system, 'arch': arch, 'soffice': str(soffice.relative_to(ROOT)),
        'libreoffice_version': version, 'download_url': url, 'sha256': digest,
        'uv_version': UV_VERSION}, indent=2) + '\n')
    print(version)
    print('Project dependencies installed. Run make doctor.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--doctor', action='store_true')
    args = parser.parse_args()
    if args.doctor:
        import lxml, docx, pypdf, pdfplumber, pypdfium2, PIL
        print(subprocess.check_output([str(executable()), '--version'], text=True).strip())
        print('Python:', sys.executable)
    else:
        install()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
