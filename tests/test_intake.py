import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.intake import extract


class IntakeTest(unittest.TestCase):
    def test_docx_and_xlsx_locations_and_missing_formula_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / 'source.docx'
            with zipfile.ZipFile(doc, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Built a service</w:t></w:r></w:p></w:body></w:document>')
            result = extract(root, doc)
            self.assertEqual(result['entries'][0]['location'], 'body paragraph 1')
            self.assertEqual((root / result['original_copy']).read_bytes(), doc.read_bytes())
            book = root / 'source.xlsx'
            with zipfile.ZipFile(book, 'w') as z:
                z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Work" r:id="r1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>Engineer</t></is></c><c r="B1"><f>1+1</f></c></row></sheetData></worksheet>')
            result = extract(root, book)
            self.assertEqual(result['entries'][0]['location'], 'Work!A1')
            self.assertEqual(result['entries'][0]['text'], 'Engineer')
            self.assertTrue(any('no cached value' in w for w in result['warnings']))
            self.assertEqual(result['coverage'], 'partial')


if __name__ == '__main__': unittest.main()
