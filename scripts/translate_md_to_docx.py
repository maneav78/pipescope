import re
from pathlib import Path
from functools import lru_cache

from deep_translator import GoogleTranslator
from docx import Document

SRC = Path('/Users/mavoyan/Desktop/PipeScope/CAPSTONE_REPORT.md')
OUT_MD = Path('/Users/mavoyan/Desktop/PipeScope/tranlated_to_armenian.md')
OUT_DOCX = Path('/Users/mavoyan/Desktop/PipeScope/tranlated_to_armenian.docx')

translator = GoogleTranslator(source='en', target='hy')

PATTERNS = [
    r'```.*?```',
    r'`[^`]+`',
    r'https?://[^\s)]+',
    r'\b[A-Z_]{2,}\b',
    r'\b--[a-zA-Z0-9-]+\b',
    r'\b[A-Za-z0-9_./-]+\.(?:py|toml|yml|yaml|md|json|txt|sh|go|java|js|ts|env|whl|pdf|docx)\b',
    r'\bCVE-\d{4}-\d+\b',
    r'\bCWE-\d+\b',
    r'\bPS-[A-Z0-9-]+\b',
    r'\bPIPESCOPE-[A-Z0-9-]+\b',
]
COMBINED = re.compile('|'.join(f'({p})' for p in PATTERNS), re.DOTALL)

TABLE_SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$')


@lru_cache(maxsize=8192)
def tr(text: str) -> str:
    t = text.strip()
    if not t:
        return text
    if re.fullmatch(r'[-=`~_*#|:\[\]().,!+\d\s/\\]+', t):
        return text
    try:
        out = translator.translate(t)
    except Exception:
        return text
    if text.startswith(' ') and not out.startswith(' '):
        out = ' ' + out
    if text.endswith(' ') and not out.endswith(' '):
        out = out + ' '
    return out


def protect(text: str):
    mapping = {}

    def repl(m):
        key = f'__PH_{len(mapping)}__'
        mapping[key] = m.group(0)
        return key

    return COMBINED.sub(repl, text), mapping


def restore(text: str, mapping):
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def translate_line(line: str) -> str:
    if not line.strip():
        return line
    if TABLE_SEP.match(line):
        return line

    prefix = ''
    m = re.match(r'^(\s*(?:[-*+]\s+|\d+\.\s+|#{1,6}\s+|>\s+)*)', line)
    if m:
        prefix = m.group(1)
        body = line[len(prefix):]
    else:
        body = line

    if not body.strip():
        return line

    protected, mapping = protect(body)
    translated = tr(protected)
    translated = restore(translated, mapping)
    return prefix + translated


def main():
    text = SRC.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)

    out_lines = []
    in_fence = False

    for ln in lines:
        stripped = ln.rstrip('\n')
        if stripped.strip().startswith('```'):
            in_fence = not in_fence
            out_lines.append(ln)
            continue

        if in_fence:
            out_lines.append(ln)
            continue

        newline = '\n' if ln.endswith('\n') else ''
        translated = translate_line(stripped)
        out_lines.append(translated + newline)

    translated_md = ''.join(out_lines)
    OUT_MD.write_text(translated_md, encoding='utf-8')

    doc = Document()
    for l in translated_md.splitlines():
        doc.add_paragraph(l)
    doc.save(str(OUT_DOCX))

    print(f'Created: {OUT_MD}')
    print(f'Created: {OUT_DOCX}')


if __name__ == '__main__':
    main()
