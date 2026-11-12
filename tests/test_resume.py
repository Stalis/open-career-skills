import errno
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_resume as builder
from scripts import install_dependencies as installer
from scripts.resume_model import MarkdownError, inline_text, parse_markdown

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = '''# Alex Example
Software Engineer

[Email](mailto:alex@example.com) | [Portfolio](https://example.com)

## Summary
Builds **reliable** *services* with Unicode: Привет мир.

## Experience
### Example Company — Engineer
2024–2026

Delivered APIs with **Python** and [documentation](https://example.com/docs).

### Earlier Company — Developer
2022–2024

Maintained systems.

## Skills
- Python
- SQL

## Training
3. First course
4. Second course
'''


def plain_blocks(blocks):
    parts = []
    for block in blocks:
        if block.items:
            for item in block.items:
                parts.extend(plain_blocks(item))
        else:
            parts.append(inline_text(block.content))
    return parts


class ResumeModelTests(unittest.TestCase):
    def test_headings_roles_groups_and_order(self):
        model = parse_markdown(SAMPLE)
        self.assertEqual(model.blocks[0].role, 'name')
        employers = [b for b in model.blocks if b.role == 'employer']
        self.assertEqual([b.group for b in employers], [1, 2])
        self.assertIn('Maintained systems.', plain_blocks(model.blocks))
        self.assertEqual(model.blocks[-1].start, 3)
        self.assertEqual(model.blocks[-2].role, 'section')
        self.assertEqual(json.loads(json.dumps(model.to_dict()))['schema_version'], 1)

    def test_bold_employers_and_consecutive_promotions(self):
        model = parse_markdown('''# Alex
## Backend Engineer
## Experience
**Company — Engineer** | 2023–2025  
**Team Lead** | 2025–2026

Built services.

**Other Company — Engineer** | 2021–2023

Maintained services.
''')
        self.assertEqual(model.blocks[1].role, 'subtitle')
        headers = [b for b in model.blocks if b.role == 'employer']
        # Consecutive lines may be one paragraph or separate paragraphs; both stay together.
        self.assertEqual([b.group for b in headers], [1, 2])
        self.assertEqual(model.blocks[-1].group, 2)

    def test_inline_preserves_text_breaks_and_nested_format(self):
        model = parse_markdown('# Alex\n\n## Summary\nOne\nsoft  \nline **bold *and italic*** [web](https://example.com?q=a&b=c).')
        self.assertEqual(inline_text(model.blocks[-1].content), 'One soft\nline bold and italic web.')

    def test_lists_in_experience_become_unbulleted(self):
        model = parse_markdown('# Alex\n## Experience\n### Company\n- First result\n- Second result')
        self.assertEqual(model.blocks[-1].role, 'experience_list')
        self.assertEqual(plain_blocks(model.blocks[-1].items[0]), ['First result'])

    def test_unsupported_markdown_reports_line(self):
        for content in ('![alt](x.png)', '<div>HTML</div>', '```python\nx=1\n```',
                        '`code`', '> quote', '| A | B |\n| --- | --- |\n| C | D |',
                        '#### Deep', '- outer\n  - nested'):
            expected_line = 4 if content.startswith('| A') else 3
            with self.subTest(content=content), self.assertRaisesRegex(MarkdownError, f'Line {expected_line}:'):
                parse_markdown('# Alex\n\n' + content)

    def test_empty_and_unused_reference_rejected(self):
        for content in ('', '[unused]: https://example.com'):
            with self.assertRaises(MarkdownError):
                parse_markdown(content)

    def test_literal_typst_is_text_and_links_are_data(self):
        model = parse_markdown('# Alex\n## Summary\n#eval("secret") $x$ {x} \\ path "quoted" [web](https://example.com).')
        self.assertIn('#eval("secret")', plain_blocks(model.blocks)[-1])


class ResumeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'templates').mkdir()
        (self.root / 'templates/resume.typ').write_bytes((ROOT / 'templates/resume.typ').read_bytes())
        fonts = self.root / 'documents/fonts/EB_Garamond'
        fonts.mkdir(parents=True)
        for name in builder.FONT_NAMES:
            (fonts / f'EBGaramond-{name}.ttf').write_bytes(b'fake font')
        (fonts / 'OFL.txt').write_text('test license')
        self.source = self.root / 'cv.md'
        self.source.write_text(SAMPLE, encoding='utf-8')
        self.pdf = self.root / 'final/resume.pdf'
        self.binary = self.root / 'typst'
        self.binary.write_bytes(b'test binary')
        for mocked in (patch.object(builder, 'ROOT', self.root),
                       patch.object(builder, 'typst_executable', return_value=self.binary),
                       patch.object(builder.subprocess, 'check_output', return_value=f'typst {installer.TYPST_VERSION} (test)')):
            mocked.start()
            self.addCleanup(mocked.stop)

    def compile(self, args, **kwargs):
        self.assertNotIn('shell', kwargs)
        payload = args[args.index('--input') + 1]
        self.assertTrue(payload.startswith('data='))
        self.assertEqual(json.loads(payload[5:])['schema_version'], 1)
        Path(args[3]).write_bytes(b'%PDF-test')
        return subprocess.CompletedProcess(args, 0, '', '')

    def test_json_command_and_manifest(self):
        with patch.object(builder.subprocess, 'run', side_effect=self.compile):
            manifest = builder.build(self.source, self.pdf)
        record = json.loads(manifest.read_text())
        self.assertEqual(record['pdf_sha256'], hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        self.assertEqual(manifest.parent, (self.root / 'work').resolve())
        self.assertEqual(list(self.pdf.parent.iterdir()), [self.pdf])

    def test_refuses_existing_pdf_or_manifest(self):
        self.pdf.parent.mkdir()
        self.pdf.write_bytes(b'original')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            builder.build(self.source, self.pdf)
        self.assertEqual(self.pdf.read_bytes(), b'original')
        self.pdf.unlink()
        work = self.root / 'work'
        work.mkdir()
        (work / 'resume.manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            builder.build(self.source, self.pdf)

    def test_compilation_failure_leaves_no_final_pdf(self):
        with patch.object(builder.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'bad template')):
            with self.assertRaisesRegex(ValueError, 'bad template'):
                builder.build(self.source, self.pdf)
        self.assertFalse(self.pdf.exists())

    def test_compiler_warning_or_timeout_leaves_no_pdf(self):
        for result in (subprocess.CompletedProcess([], 0, '', 'warning: unknown font'),
                       subprocess.TimeoutExpired('typst', 180)):
            with self.subTest(result=result):
                kwargs = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
                with patch.object(builder.subprocess, 'run', **kwargs):
                    with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                        builder.build(self.source, self.pdf)
                self.assertFalse(self.pdf.exists())

    def test_missing_font_is_actionable(self):
        (self.root / 'documents/fonts/EB_Garamond/EBGaramond-Bold.ttf').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing licensed font'):
            builder.build(self.source, self.pdf)

    def test_os_argument_limit_is_actionable(self):
        with patch.object(builder.subprocess, 'run', side_effect=OSError(errno.E2BIG, 'too large')):
            with self.assertRaisesRegex(ValueError, 'command-line limit'):
                builder.build(self.source, self.pdf)
        self.assertFalse(self.pdf.exists())

    def test_large_payload_rejected_before_launch(self):
        self.source.write_text('# Alex\n## Summary\n' + 'Large ' * 25000)
        with self.assertRaisesRegex(ValueError, '120000-byte'):
            builder.build(self.source, self.pdf)

    def test_missing_typst_and_wrong_version(self):
        with patch.object(builder, 'typst_executable', side_effect=RuntimeError('run make install')):
            with self.assertRaisesRegex(RuntimeError, 'make install'):
                builder.build(self.source, self.pdf)
        with patch.object(builder.subprocess, 'check_output', return_value='typst wrong'):
            with self.assertRaisesRegex(ValueError, 'Unexpected Typst'):
                builder.build(self.source, self.pdf)


class TypstInstallationTests(unittest.TestCase):
    def test_project_binary_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tools = root / '.tools'
            tools.mkdir()
            (tools / 'installed.json').write_text(json.dumps({'typst': {'version': installer.TYPST_VERSION, 'path': '../outside'}}))
            with patch.object(installer, 'ROOT', root), patch.object(installer, 'TOOLS', tools):
                with self.assertRaisesRegex(RuntimeError, 'project-local Typst'):
                    installer.typst_executable()

    def test_checksum_and_installation_preserve_existing_manifest(self):
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tools = root / '.tools'
            tools.mkdir()
            record = tools / 'installed.json'
            record.write_text(json.dumps({'soffice': '.tools/existing/soffice', 'uv_version': 'existing'}))
            archive = root / 'typst.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('typst-test/typst.exe', b'fake binary')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch.object(installer, 'ROOT', root), patch.object(installer, 'TOOLS', tools), \
                 patch.object(installer.platform, 'system', return_value='Windows'), \
                 patch.object(installer.platform, 'machine', return_value='AMD64'), \
                 patch.object(installer, 'download', return_value=archive), \
                 patch.object(installer.subprocess, 'check_output', return_value=f'typst {installer.TYPST_VERSION} (test)'):
                with patch.dict(installer.TYPST_TARGETS, {('Windows', 'x86_64'): ('test', '0' * 64)}):
                    with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                        installer.install_typst()
                self.assertNotIn('typst', json.loads(record.read_text()))
                with patch.dict(installer.TYPST_TARGETS, {('Windows', 'x86_64'): ('test', digest)}):
                    installer.install_typst()
                self.assertEqual(json.loads(record.read_text())['uv_version'], 'existing')
                binary = installer.typst_executable()
                binary.write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
                    installer.typst_executable()


class TypstIntegrationTests(unittest.TestCase):
    def test_small_employer_stays_on_one_page_and_literal_typst_is_safe(self):
        try:
            installer.typst_executable()
        except RuntimeError as exc:
            self.skipTest(str(exc))
        if not (ROOT / 'documents/fonts/EB_Garamond/EBGaramond-Regular.ttf').is_file():
            self.skipTest('Licensed EB Garamond fonts are not installed')
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            source = Path(folder) / 'cv.md'
            pdf = Path(folder) / 'resume.pdf'
            filler = '\n\n'.join(f'Preparation paragraph {i} with sufficient words to fill several lines of the resume.' for i in range(55))
            source.write_text('# Alex\n## Summary\n' + filler + '\n\n## Experience\n### GROUPSTART Employer\n2024–2026\n\n' +
                              'Literal #eval("secret") $x$ {braces} "quotes" stays visible.\n\n' +
                              'GROUPEND Last employer paragraph.', encoding='utf-8')
            builder.build(source, pdf)
            pages = [p.extract_text() for p in PdfReader(pdf).pages]
            self.assertEqual(next(i for i,t in enumerate(pages) if 'GROUPSTART' in t),
                             next(i for i,t in enumerate(pages) if 'GROUPEND' in t))
            self.assertIn('#eval("secret")', '\n'.join(pages))

    def test_real_pdf_text_links_fonts_and_long_employer(self):
        try:
            installer.typst_executable()
        except RuntimeError as exc:
            self.skipTest(str(exc))
        if not (ROOT / 'documents/fonts/EB_Garamond/EBGaramond-Regular.ttf').is_file():
            self.skipTest('Licensed EB Garamond fonts are not installed')
        from pypdf import PdfReader
        from scripts.check_export import normalize
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            source = Path(folder) / 'cv.md'
            pdf = Path(folder) / 'resume.pdf'
            # A single employer longer than one page must split without clipping.
            source.write_text(SAMPLE.replace('Maintained systems.',
                              'TypeScript Terraform Worked NATS image-testing.\n\n' + '\n\n'.join(
                f'Long employer paragraph {i}: Maintained reliable services with clear documentation.' for i in range(100))), encoding='utf-8')
            builder.build(source, pdf)
            reader = PdfReader(pdf)
            actual = '\n'.join(page.extract_text() for page in reader.pages)
            expected = '\n'.join(plain_blocks(parse_markdown(source.read_text()).blocks))
            # General lists retain visible markers; remove them only for this comparison.
            import re
            actual = re.sub(r'(?m)^\s*(?:[•‣▪]|[34]\.)\s*', '', actual)
            self.assertEqual(normalize(expected), normalize(actual))
            self.assertGreater(len(reader.pages), 1)
            targets = []
            for page in reader.pages:
                for ref in page.get('/Annots', []):
                    action = ref.get_object().get('/A', {})
                    if action.get('/URI'):
                        targets.append(action['/URI'])
                self.assertAlmostEqual(float(page.mediabox.width), 595.276, places=1)
                for ref in page['/Resources'].get('/Font', {}).values():
                    font = ref.get_object()
                    for descendant in font.get('/DescendantFonts', [font]):
                        descriptor = descendant.get_object().get('/FontDescriptor')
                        if descriptor:
                            self.assertTrue(any(k in descriptor for k in ('/FontFile', '/FontFile2', '/FontFile3')))
            self.assertIn('https://example.com/docs', targets)


if __name__ == '__main__':
    unittest.main()
