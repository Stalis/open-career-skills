from pathlib import Path
import json
import tempfile
import unittest
import zipfile
from scripts import check_export as ce


class ExportTest(unittest.TestCase):
    def test_layout_whitespace_and_ligatures(self):
        self.assertEqual(ce.compare('Office 2020–2024 C#', 'Ofﬁce\n2020–2024\tC#')['status'], 'PASS')

    def test_factual_changes_and_reading_order_fail(self):
        for text in ('Reduced by 80%', 'Reduced by 8', '8% by Reduced', 'Reduced by 8% extra'):
            self.assertEqual(ce.compare('Reduced by 8%', text)['status'], 'FAIL')
        with self.assertRaises(ValueError):
            ce.compare('', '')

    def test_docx_tables_runs_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / 'cv.docx'
            with zipfile.ZipFile(doc, 'w') as archive:
                archive.writestr('word/document.xml', '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
                <w:p><w:r><w:t>Jane </w:t></w:r><w:r><w:t>Doe</w:t></w:r></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:r><w:t>C# 2024</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
                </w:body></w:document>''')
            expected = root / 'approved.txt'
            expected.write_text('Jane Doe\nC# 2024')
            report = root / 'report.json'
            self.assertEqual(ce.main(['--expected', str(expected), '--export', str(doc), '--report', str(report)]), 0)
            result = json.loads(report.read_text())
            self.assertEqual(result['exports'][0]['sha256'], ce.sha(doc))
            with self.assertRaises(SystemExit):
                ce.main(['--expected', str(expected), '--export', str(doc), '--report', str(report)])

    def test_extraction_failure_never_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'approved.txt').write_text('Jane Doe')
            report = root / 'report.json'
            self.assertEqual(ce.main(['--expected', str(root / 'approved.txt'), '--export', str(root / 'missing.pdf'), '--report', str(report)]), 2)
            self.assertEqual(json.loads(report.read_text())['status'], 'ERROR')

    def test_pdf_text_layer_and_empty_page(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest('pypdf not installed; run with project .venv')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cv.pdf'
            writer = PdfWriter()
            page = writer.add_blank_page(width=600, height=800)
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
            stream = DecodedStreamObject()
            stream.set_data(b'BT /F1 12 Tf 20 700 Td (Jane Doe 2024) Tj ET')
            page[NameObject('/Contents')] = stream
            writer.write(path)
            self.assertEqual(ce.compare('Jane Doe 2024', ce.extract(path)[0])['status'], 'PASS')
            writer.add_blank_page(width=600, height=800)
            writer.write(path)
            with self.assertRaisesRegex(ValueError, 'without extractable text'):
                ce.extract(path)
