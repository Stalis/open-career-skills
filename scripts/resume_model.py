"""Lossless supported-Markdown document model; never infers candidate facts."""
from dataclasses import asdict, dataclass, field
import re
from typing import List, Optional

from markdown_it import MarkdownIt


@dataclass
class Inline:
    kind: str
    text: str = ''
    children: List['Inline'] = field(default_factory=list)
    target: Optional[str] = None


@dataclass
class Block:
    kind: str
    line: int
    content: List[Inline] = field(default_factory=list)
    level: int = 0
    items: List[List['Block']] = field(default_factory=list)
    start: int = 1
    group: Optional[int] = None
    role: str = 'body'


@dataclass
class ResumeDocument:
    blocks: List[Block]
    schema_version: int = 1

    def to_dict(self):
        return asdict(self)


class MarkdownError(ValueError):
    def __init__(self, line, message):
        super().__init__(f'Line {line}: {message}')


def inline_text(nodes):
    return ''.join('\n' if n.kind == 'break' else
                   n.text if n.kind == 'text' else inline_text(n.children) for n in nodes)


def parse_inline(token):
    line = token.map[0] + 1 if token.map else 1
    root = []
    stack = [root]
    for child in token.children or []:
        kind = child.type
        if kind == 'text':
            if child.content:
                stack[-1].append(Inline('text', child.content))
        elif kind in ('softbreak', 'hardbreak'):
            stack[-1].append(Inline('text', ' ') if kind == 'softbreak' else Inline('break'))
            line += 1
        elif kind in ('strong_open', 'em_open', 'link_open'):
            target = child.attrGet('href') if kind == 'link_open' else None
            if target and not re.match(r'^(https?://|mailto:|tel:)', target, re.I):
                raise MarkdownError(line, 'links must use http, https, mailto or tel')
            node = Inline({'strong_open': 'strong', 'em_open': 'emphasis', 'link_open': 'link'}[kind], target=target)
            stack[-1].append(node)
            stack.append(node.children)
        elif kind in ('strong_close', 'em_close', 'link_close'):
            stack.pop()
        else:
            raise MarkdownError(line, f'unsupported inline Markdown: {kind}')
    return root


def parse_markdown(source):
    """Parse CommonMark blocks without relying on resume line positions."""
    # Tables are deliberately not enabled: detect them rather than render pipes silently.
    for number, line in enumerate(source.splitlines(), 1):
        if re.match(r'^\s*\|?\s*:?-+:?\s*\|(?:\s*:?-+:?\s*\|?)+\s*$', line):
            raise MarkdownError(number, 'tables are not supported')
    env = {}
    tokens = MarkdownIt('commonmark', {'html': True}).parse(source, env)
    index = 0

    def read_blocks(stop=None):
        nonlocal index
        result = []
        while index < len(tokens):
            token = tokens[index]
            line = token.map[0] + 1 if token.map else 1
            if token.type == stop:
                index += 1
                return result
            if token.type in ('heading_open', 'paragraph_open'):
                level = int(token.tag[1:]) if token.type == 'heading_open' else 0
                if level > 3:
                    raise MarkdownError(line, 'only heading levels 1–3 are supported')
                result.append(Block('heading' if level else 'paragraph', line,
                                    parse_inline(tokens[index + 1]), level=level))
                index += 3
            elif token.type in ('bullet_list_open', 'ordered_list_open'):
                block = Block('ordered_list' if token.type == 'ordered_list_open' else 'bullet_list',
                              line, start=int(token.attrGet('start') or 1))
                close = token.type.replace('_open', '_close')
                index += 1
                while tokens[index].type != close:
                    if tokens[index].type != 'list_item_open':
                        raise MarkdownError(line, 'invalid list')
                    index += 1
                    item = read_blocks('list_item_close')
                    if any(b.kind != 'paragraph' for b in item):
                        raise MarkdownError(line, 'nested lists and headings inside lists are not supported')
                    block.items.append(item)
                index += 1
                result.append(block)
            else:
                raise MarkdownError(line, f'unsupported Markdown: {token.type}')
        return result

    blocks = read_blocks()
    if not blocks:
        raise MarkdownError(1, 'resume is empty')
    # Reference definitions are not rendered; disallow orphan definitions.
    used = {n.target for b in blocks for n in walk_inline(b) if n.kind == 'link'}
    for reference in env.get('references', {}).values():
        if reference['href'] not in used:
            raise MarkdownError(reference['map'][0] + 1, 'unused link reference')
    assign_roles(blocks)
    return ResumeDocument(blocks)


def walk_inline(block):
    def visit(nodes):
        for node in nodes:
            yield node
            yield from visit(node.children)
    yield from visit(block.content)
    for item in block.items:
        for child in item:
            yield from walk_inline(child)


def assign_roles(blocks):
    experience = False
    in_header = True
    group = 0
    active = None
    has_body = False
    seen_name = False
    preamble_seen = False
    section_names = {'summary', 'profile', 'professional summary', 'skills', 'technical skills',
                     'experience', 'work experience', 'professional experience', 'education',
                     'education and languages', 'training', 'languages', 'projects',
                     'selected personal projects', 'personal work & ai development practice',
                     'additional database experience', 'о себе', 'навыки', 'опыт', 'опыт работы',
                     'профессиональный опыт', 'образование', 'проекты', 'языки'}
    for block in blocks:
        text = inline_text(block.content).strip()
        if block.kind == 'heading' and block.level <= 2:
            # Both existing formats have a name H1. Other pre-section content is header.
            if block.level == 1 and in_header and not seen_name:
                block.role = 'name'
                seen_name = True
                continue
            if block.level == 2 and in_header and text.casefold() not in section_names:
                block.role = 'subtitle'
                continue
            in_header = False
            experience = text.casefold() in ('experience', 'work experience', 'professional experience',
                                             'опыт', 'опыт работы', 'профессиональный опыт')
            active = None
            block.role = 'section'
            continue
        if in_header:
            is_contact = any(n.kind == 'link' for n in walk_inline(block)) or any(c in text for c in ('@', '|', ','))
            block.role = 'subtitle' if seen_name and not preamble_seen and not is_contact else 'header'
            preamble_seen = True
        if not experience:
            continue
        employer = (block.kind == 'heading' and block.level == 3) or (
            block.kind == 'paragraph' and block.content and block.content[0].kind == 'strong'
            and bool(re.search(r'\b(?:19|20)\d{2}\b', text)))
        if employer:
            if active is None or has_body:
                group += 1
                active = group
            has_body = False
            block.role = 'employer'
        else:
            has_body = True
        block.group = active
        # Experience list markers are intentionally removed, retaining separate paragraphs.
        if block.kind in ('bullet_list', 'ordered_list'):
            block.role = 'experience_list'
