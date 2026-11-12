# Markdown → Typst resume PDFs

The default final resume is PDF, built directly from candidate-checked `cv.md`.
DOCX is generated only on explicit request using the existing reference-OOXML
and project-local LibreOffice workflow. Existing applications and review snapshots
are never migrated automatically.

## Setup and invocation

Run `make install`, then `make doctor` from the repository root. The installer
pins Typst **0.15.0**, verifies its official release archive against the SHA-256
digests recorded in the installer, and records its local binary/hash in
`.tools/installed.json`. The supported distributions are macOS arm64/x86_64,
Linux x86_64 and Windows x86_64; only macOS arm64 has been exercised for this
pipeline. Other platforms must not be described as verified without testing.
The renderer never searches PATH for a substitute executable. To add Typst to an
existing managed installation without reinstalling Python/LibreOffice, run
`.venv/bin/python scripts/install_dependencies.py --typst-only`, then install the
updated project requirements with the project-local uv.

Place the licensed, static EB Garamond files `EBGaramond-Regular.ttf`,
`EBGaramond-Bold.ttf`, `EBGaramond-Italic.ttf`, `EBGaramond-BoldItalic.ttf`
and their `OFL.txt` in ignored `documents/fonts/EB_Garamond/`. They are not
redistributed in this repository. Missing files, missing glyphs and font warnings
are errors; system/embedded fallback fonts are disabled.

```sh
.venv/bin/python scripts/build_resume.py path/to/cv.md path/to/work/resume.pdf
.venv/bin/python scripts/render_pages.py path/to/work/resume.pdf path/to/work/pages
.venv/bin/python scripts/check_export.py \
  --expected path/to/approved-text.txt \
  --export path/to/work/resume.pdf \
  --report path/to/work/export-check-001.json
```

Windows uses `.venv/Scripts/python.exe`. Input must be UTF-8 Markdown; UTF-8 BOM
is accepted. Output must end in `.pdf`. Existing PDFs/manifests are never
overwritten. Keep trials outside `final/` and promote only reviewed exact final
files per `AGENTS.md`; this command does not approve text, promote files or
change tracker/status. A `final/` destination places its manifest in the sibling
`work/` directory. A `work/` destination keeps its manifest in that directory;
other destinations use a `work/` subdirectory for manifests.

## Model and supported Markdown

`scripts/resume_model.py` defines `ResumeDocument`, `Block` and `Inline` with
standard-library dataclasses. `parse_markdown(text)` returns the document;
`to_dict()` produces the versioned JSON payload. This is a presentation model,
not a candidate fact database or an inferred employment schema. It retains
source line numbers, content order, formatting, link targets and list start.

The parser uses pinned CommonMark `markdown-it-py` and supports headings H1–H3,
paragraphs, soft wraps, hard line breaks, bold/italic (including nesting), links,
and flat ordered/unordered lists with paragraph content. Soft wraps become spaces;
two trailing spaces or a Markdown backslash produce a hard break. Link labels
are visible text and targets retain HTTP(S), mailto or tel URLs.

Tables, images, raw HTML, fenced/indented code, inline code, quotes, horizontal
rules, deeper headings and nested lists are rejected with the source line.
Unsupported constructs are never discarded. Reference links work; unused link
definitions are rejected. Literal Typst syntax remains text.

H1 starts the name. Preamble paragraphs form the centered header; the first plain
preamble paragraph without contact separators/links uses subtitle styling. An initial H2
not matching a recognized resume section is treated as a subtitle (the existing
second input format). H2 sections retain their original labels. Experience
grouping recognizes Experience / Work Experience / Professional Experience and
their Russian equivalents, then H3 employers or bold-leading employer/role lines
with a four-digit year. Adjacent promotion headers share a group until body
content occurs. Grouping never changes the underlying text or infers facts.
Lists in experience render as separate unbulleted paragraphs; other lists retain
markers and numbering. Include visible non-experience list markers/numbers in the
independently checked transcript used for export comparison.

## Rendering and audit

The Python entry point serializes UTF-8 JSON and invokes Typst with an argument
list, `--input data=<JSON>`, and no shell. The template uses
`json(bytes(sys.inputs.data))` and renders strings as content, never with `eval`.
The payload has a portable 120000-byte ceiling; OS-specific argument limits also
produce an explicit error. There is no fallback to JSON files or stdin.

The shared template follows the private reference DOCX: A4, 12.7 mm margins,
22 pt name, 12 pt subtitle, 10 pt body/contact text, 14 pt section headings,
8 pt space before sections, 0.75 pt divider and blue underlined links. The agreed
font is EB Garamond. Employer groups fitting one page stay together; larger
groups can split. Different engines may wrap lines differently; visual comparison
and user agreement to material deviations remain required.

Compilation uses a private staging directory under `work/`, captured template and
font bytes, fixed PDF creation timestamp, disabled system/embedded fonts, and a
180-second timeout. Warnings and failures prevent PDF publication. The build
manifest records renderer/Python/parser versions, source/model/template/font/PDF
SHA-256 values and rendering parameters, without putting resume JSON into logs.
It contains private paths and belongs outside tracked files.

The build manifest does not replace separately candidate-checked
`approved-text.txt`, the export fidelity report, every-page visual inspection,
font/link/geometry checks or fresh independent final review. Only requested
DOCX files join the export/review package. Keep all existing candidate pauses
and readiness/submission rules.

## Verification

Run `make test`. Synthetic parser/build tests cover both existing input shapes,
Unicode, formatting, links, lists, unsupported constructs, dependencies, compiler
failure, overwrite protection and argument limits. The real-compiler integration
test checks PDF text, hyperlinks, font embedding and multi-page employer content;
it explicitly skips when project-local Typst or private font assets are absent.
Synthetic comparison artifacts belong in ignored `tmp/`, never tracked resumes.

References: [Typst external inputs](https://typst.app/docs/reference/foundations/sys/),
[JSON decoding](https://typst.app/docs/reference/data-loading/json/),
[layout measurement](https://typst.app/docs/reference/layout/layout/),
[official release and asset digests](https://github.com/typst/typst/releases/tag/v0.15.0).
