#!/usr/bin/env python3
"""Render a PDF to PNGs using project-local PDFium; refuses an existing output folder."""
import argparse
import json
from pathlib import Path
import pypdfium2 as pdfium


def render(pdf, output, scale=1.5):
    output.mkdir(parents=True, exist_ok=False)
    pages = []
    with pdfium.PdfDocument(pdf) as document:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            target = output / f'page-{index+1}.png'
            image.save(target)
            pages.append(str(target))
            image.close()
            bitmap.close()
            page.close()
    return pages


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.pdf, args.output), indent=2))
