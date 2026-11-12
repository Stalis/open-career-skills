// Generic reference-derived layout. All resume content arrives as JSON, never code.
#let data = json(bytes(sys.inputs.data))
#assert(data.schema_version == 1, message: "Unsupported resume schema")
#set page(paper: "a4", margin: 12.7mm)
#set text(font: "EB Garamond", size: 10pt, lang: "en", hyphenate: false, kerning: false,
  top-edge: "ascender", bottom-edge: "descender")
#set par(leading: 0pt, spacing: 0pt)
#set document(title: "Resume")
#show link: it => text(fill: rgb("1155cc"), underline(it))
// Keep literal hyphenated words intact in PDF text extraction.
#show regex("\\p{L}+(?:-\\p{L}+)+"): it => box(it)

#let rich(nodes) = {
  for node in nodes {
    if node.kind == "text" { text(node.text) }
    else if node.kind == "break" { linebreak() }
    else if node.kind == "strong" { strong(rich(node.children)) }
    else if node.kind == "emphasis" { emph(rich(node.children)) }
    else if node.kind == "link" { link(node.target, rich(node.children)) }
  }
}

#let render(b) = {
  if b.kind == "heading" {
    if b.role == "name" {
      block(width: 100%, above: 0pt, below: 0pt, sticky: true,
        align(center, text(size: 22pt, weight: "bold", rich(b.content))))
    } else if b.role == "subtitle" {
      block(width: 100%, above: 0pt, below: 0pt, sticky: true,
        align(center, text(size: 12pt, rich(b.content))))
    } else if b.role == "section" {
      block(width: 100%, above: 8pt, below: 0pt, sticky: true)[
        #text(size: 14pt, weight: "bold", rich(b.content))
        #v(1pt)
        #line(length: 100%, stroke: 0.75pt)
      ]
    } else {
      block(above: 5pt, below: 0pt, sticky: true, strong(rich(b.content)))
    }
  } else if b.kind == "paragraph" {
    if b.role == "subtitle" {
      block(width: 100%, above: 0pt, below: 0pt,
        align(center, text(size: 12pt, rich(b.content))))
    } else if b.role == "header" {
      block(width: 100%, above: 0pt, below: 0pt, align(center, rich(b.content)))
    } else {
      block(above: 0pt, below: 0pt, sticky: b.role == "employer", rich(b.content))
    }
  } else {
    if b.role == "experience_list" {
      for item in b.items { for p in item { render(p) } }
    } else if b.kind == "ordered_list" {
      enum(start: b.start, ..b.items.map(item => { for p in item { render(p) } }))
    } else {
      list(..b.items.map(item => { for p in item { render(p) } }))
    }
  }
}

#let full-height = 297mm - 25.4mm
#let grouped(blocks, separated: false) = {
  if separated { v(6pt, weak: true) }
  layout(size => {
  let body = { for b in blocks { render(b) } }
  let height = measure(block(width: size.width, body)).height
  block(width: 100%, breakable: height > full-height, above: 0pt, below: 0pt, body)
  })
}

#let pending = ()
#let group = none
#let previous-group = false
#for b in data.blocks {
  if b.group != group or b.group == none {
    if pending.len() > 0 {
      grouped(pending, separated: previous-group)
      previous-group = true
      pending = ()
    }
    group = b.group
  }
  if b.group == none {
    render(b)
    previous-group = false
  } else { pending.push(b) }
}
#if pending.len() > 0 { grouped(pending, separated: previous-group) }
