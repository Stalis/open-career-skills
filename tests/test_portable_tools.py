import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'scripts/install_dependencies.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PortableToolsTests(unittest.TestCase):
    def test_manifest_cannot_select_external_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tools = root / '.tools'
            tools.mkdir()
            (tools / 'installed.json').write_text(json.dumps({'soffice': '../outside/soffice'}))
            with patch.object(installer, 'ROOT', root), patch.object(installer, 'TOOLS', tools):
                with self.assertRaisesRegex(RuntimeError, 'Invalid'):
                    installer.executable()

    def test_download_checksum_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / 'package'
            package.write_bytes(b'wrong')
            checksum = Path(folder) / 'checksum'
            checksum.write_text('0' * 64 + ' package')
            with patch.object(installer, 'download', return_value=checksum):
                with self.assertRaisesRegex(RuntimeError, 'Checksum mismatch'):
                    installer.verify(package, 'https://example.invalid/checksum')


    def test_partial_uv_extract_is_replaced_on_retry(self):
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tools = root / '.tools'
            partial = tools / 'uv'
            partial.mkdir(parents=True)
            (partial / 'incomplete').touch()
            archive = root / 'uv.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('uv-x86_64/uv.exe', b'uv')
            with patch.object(installer, 'TOOLS', tools):
                executable = installer.uv_executable(archive, 'Windows')
            self.assertEqual(executable.read_bytes(), b'uv')
            self.assertFalse((partial / 'incomplete').exists())
    def test_caches_and_python_stay_inside_project(self):
        env = installer.environment()
        for key in ['UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR', 'UV_PYTHON_BIN_DIR', 'PIP_CACHE_DIR']:
            self.assertTrue(Path(env[key]).is_relative_to(installer.ROOT))
