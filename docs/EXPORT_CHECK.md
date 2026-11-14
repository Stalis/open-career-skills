# Export text fidelity check

`scripts/check_export.py` compares final PDF/DOCX text with an approved UTF-8 plain-text transcript. It does not rewrite documents, invoke AI, submit applications, or change status. DOCX uses standard-library OOXML extraction; PDF uses the pinned `pypdf` dependency installed in the project's ignored `.venv/` by `make install`. Run `make doctor` to validate the local setup.

For the default Typst pipeline check the PDF only. Include `--export <file.docx>` as an additional argument only when DOCX was explicitly requested and generated. No internal DOCX is required. Preserve the Typst build manifest alongside the check report; a successful build does not certify candidate approval.

After the candidate checks the CV text, prepare `approved-text.txt` inside the private application folder. It must contain exactly the visible content expected in the export, in intended reading order: headings, name, contacts, dates, skills and experience. Remove Markdown syntax and private editorial notes, but preserve the approved wording and punctuation. Check the transcript against `cv.md`; the helper cannot prove that this manual preparation was faithful. Markdown links must use the visible label; hyperlink targets need separate inspection.

```sh
.venv/bin/python scripts/check_export.py \
  --expected output/applications/YYYY-MM-DD/<application>/approved-text.txt \
  --export output/applications/YYYY-MM-DD/<application>/cv.pdf \
  --report output/applications/YYYY-MM-DD/<application>/export-check-001.json
```

The JSON report contains SHA-256 input fingerprints, extractor/version, complete extracted text and ordered token differences. It contains personal data: keep it in ignored `output/` or `tmp/`. Existing reports are never overwritten. Exit codes: 0 PASS, 1 text differences, 2 extraction/input error. All exports must pass; missing dependencies, unreadable/encrypted PDFs and pages without extractable text cannot produce PASS. Scans receive no OCR.

Comparison ignores whitespace, soft hyphens and Unicode compatibility forms (such as presentation ligatures). Case, punctuation, word order, dates and numeric boundaries remain significant. Missing, additional, changed or reordered tokens fail, even if most words match. Line-end visible hyphens and decorative/page-number text can cause failures: inspect and correct the export, or explicitly document approved visible content in the transcript; never silently ignore differing numbers or regenerate the transcript from the export just to obtain PASS.

DOCX paragraphs, including table contents, are read in XML order; headers and footers are appended. This is a conservative check, not Word's visual reading order. Substantive contact data in headers can therefore produce differences requiring inspection. The checker does not evaluate hyperlink targets, images, hidden/deleted text semantics, clipping, fonts, layout, or employer ATS behavior. PDF extraction order also depends on the generator. Keep visual review and final independent review mandatory.

Give the report and exact files to the final reviewer and reference the report from `final-review.md`. Check recorded hashes against current files. A new export or transcript requires a new check. PASS alone never sets READY_TO_APPLY.
