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
TYPST_VERSION = '0.15.0'
# SHA-256 digests from the official v0.15.0 GitHub release asset metadata.
TYPST_TARGETS = {
    ('Darwin', 'aarch64'): ('aarch64-apple-darwin', 'fe53838737abf93a774495952a1a797b4686e9c4a21c2d99b9fdf77f46cc3572'),
    ('Darwin', 'x86_64'): ('x86_64-apple-darwin', '30210c7c539c7954db94c063cd98b43fd0a0cad285d656dbbce2a40aee2e79be'),
    ('Linux', 'x86_64'): ('x86_64-unknown-linux-musl', '59b207df01be2dab9f13e80f73d04d7ff8273ffd46b3dd1b9eef5c60f3eeabea'),
    ('Windows', 'x86_64'): ('x86_64-pc-windows-msvc', '66ae7f0907b4b9afed5c7d6cb9b21e07f0f3c3d4e293ba3e0026a54d88202fe9'),
}


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


def typst_executable():
    record = TOOLS / 'installed.json'
    if not record.is_file():
        raise RuntimeError('Missing project-local Typst; run make install')
    entry = json.loads(record.read_text()).get('typst', {})
    path = (ROOT / entry.get('path', '')).resolve()
    if (entry.get('version') != TYPST_VERSION or not path.is_relative_to(TOOLS.resolve())
            or not path.is_file()):
        raise RuntimeError('Invalid or missing project-local Typst; run make install')
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get('binary_sha256'):
        raise RuntimeError('Project-local Typst hash mismatch; reinstall Typst')
    return path


def install_typst():
    system = platform.system()
    arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'AMD64': 'x86_64',
            'x86_64': 'x86_64'}.get(platform.machine())
    if (system, arch) not in TYPST_TARGETS:
        raise RuntimeError(f'Unsupported Typst platform: {system}/{platform.machine()}')
    triple, expected = TYPST_TARGETS[system, arch]
    extension = 'zip' if system == 'Windows' else 'tar.xz'
    name = f'typst-{triple}.{extension}'
    url = f'https://github.com/typst/typst/releases/download/v{TYPST_VERSION}/{name}'
    TOOLS.mkdir(exist_ok=True)
    package = download(url, TOOLS / 'downloads' / f'{TYPST_VERSION}-{name}')
    if hashlib.sha256(package.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Typst download checksum mismatch; remove cached archive and retry')
    directory = TOOLS / 'typst' / TYPST_VERSION / triple
    binary = directory / ('typst.exe' if system == 'Windows' else 'typst')
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.typst-', dir=TOOLS) as temporary:
        unpacked = Path(temporary)
        if system == 'Windows':
            import zipfile
            with zipfile.ZipFile(package) as archive:
                archive.extractall(unpacked)
        else:
            run(['tar', '-xJf', package, '-C', unpacked])
        staged = next(unpacked.rglob(binary.name), None)
        if staged is None:
            raise RuntimeError('Typst archive did not contain an executable')
        version = subprocess.check_output([str(staged), '--version'], text=True).strip()
        if not version.startswith(f'typst {TYPST_VERSION} '):
            raise RuntimeError(f'Unexpected downloaded Typst version: {version}')
        directory.mkdir(exist_ok=True)
        os.replace(staged, binary)
    record = TOOLS / 'installed.json'
    data = json.loads(record.read_text()) if record.exists() else {}
    data['typst'] = {'version': TYPST_VERSION, 'path': str(binary.relative_to(ROOT)),
                     'download_url': url, 'sha256': expected,
                     'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    temporary_record = record.with_suffix('.json.new')
    temporary_record.write_text(json.dumps(data, indent=2) + '\n')
    temporary_record.replace(record)
    print(version)


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
    install_typst()
    print('Project dependencies installed. Run make doctor.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--typst-only', action='store_true', help='Add/update Typst without replacing an existing Python/LibreOffice setup')
    args = parser.parse_args()
    if args.doctor:
        import lxml, docx, pypdf, pdfplumber, pypdfium2, PIL
        print(subprocess.check_output([str(executable()), '--version'], text=True).strip())
        print(subprocess.check_output([str(typst_executable()), '--version'], text=True).strip())
        import markdown_it
        print('Python:', sys.executable)
    elif args.typst_only:
        install_typst()
    else:
        install()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
