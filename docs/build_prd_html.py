#!/usr/bin/env python3
"""docs/PRD.md → docs/PRD.html 변환기 (의존성 0).

표준 라이브러리만 사용하는 경량 Markdown→HTML 변환기. PRD.md 가 쓰는
부분집합(제목/표/코드블록/순서·비순서 리스트/인용/HR/굵게/인라인코드/링크)만
처리하며, 자동 목차(TOC)와 임베디드 CSS 를 포함한 단독 HTML 을 생성한다.

사용:
    python docs/build_prd_html.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "PRD.md"
DST = HERE / "PRD.html"

_CODE_TOKEN = "\x00C{}\x00"

_LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_HR_RE = re.compile(r"^-{3,}\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def slugify(text: str, used: set[str]) -> str:
    """GitHub 류 슬러그(유니코드 글자 보존). 중복 시 -N 접미사."""
    s = text.strip().lower()
    s = re.sub(r"[`*_~]", "", s)            # 인라인 마커 제거
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)  # 구두점 제거(글자/숫자/_/공백/- 유지)
    s = re.sub(r"\s+", "-", s).strip("-")
    s = s or "section"
    base = s
    i = 1
    while s in used:
        s = f"{base}-{i}"
        i += 1
    used.add(s)
    return s


def render_inline(text: str) -> str:
    """인라인 포맷: 이스케이프 → 코드스팬 보호 → 링크 → 굵게 → 코드 복원."""
    codes: list[str] = []

    def _stash(m: re.Match) -> str:
        codes.append(m.group(1))
        return _CODE_TOKEN.format(len(codes) - 1)

    # 1) 인라인 코드 원본 추출(이스케이프 전) → 플레이스홀더
    text = re.sub(r"`([^`]+)`", _stash, text)
    # 2) 나머지 HTML 이스케이프
    text = html.escape(text, quote=False)
    # 3) 링크 [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        text,
    )
    # 4) 굵게 **...**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 5) 코드 복원(코드 내부는 추가 포맷 없이 이스케이프만)
    for i, raw in enumerate(codes):
        text = text.replace(
            _CODE_TOKEN.format(i),
            f"<code>{html.escape(raw, quote=False)}</code>",
        )
    return text


def convert(lines: list[str], headings: list[tuple[int, str, str]] | None,
            used_slugs: set[str]) -> str:
    """블록 단위 변환. headings 가 주어지면 h2/h3 를 수집(TOC용)."""
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 빈 줄
        if not line.strip():
            i += 1
            continue

        # 펜스 코드 블록
        if line.lstrip().startswith("```"):
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 닫는 ``` 소비
            code = html.escape("\n".join(buf), quote=False)
            out.append(f"<pre><code>{code}</code></pre>")
            continue

        # 테이블 (현재 줄이 |...| 이고 다음 줄이 구분선)
        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            header = _split_row(line)
            i += 2  # 헤더 + 구분선 소비
            rows: list[list[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            out.append(_render_table(header, rows))
            continue

        # 제목
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            slug = slugify(text, used_slugs)
            inner = render_inline(text)
            out.append(f'<h{level} id="{slug}">{inner}</h{level}>')
            if headings is not None and level in (2, 3):
                headings.append((level, text, slug))
            i += 1
            continue

        # 수평선
        if _HR_RE.match(line):
            out.append("<hr>")
            i += 1
            continue

        # 인용 블록 (연속 > 줄 → 내부 재귀 변환)
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner_html = convert(buf, None, used_slugs)
            out.append(f"<blockquote>{inner_html}</blockquote>")
            continue

        # 리스트 (연속 항목)
        if _LIST_RE.match(line):
            items: list[str] = []
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            while i < n and _LIST_RE.match(lines[i]):
                items.append(_LIST_RE.match(lines[i]).group(3))
                i += 1
            tag = "ol" if ordered else "ul"
            li = "".join(f"<li>{render_inline(it)}</li>" for it in items)
            out.append(f"<{tag}>{li}</{tag}>")
            continue

        # 문단 (연속 비-블록 줄을 합침)
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not _is_block_start(lines[i], lines, i):
            buf.append(lines[i])
            i += 1
        out.append(f"<p>{render_inline(' '.join(s.strip() for s in buf))}</p>")
    return "\n".join(out)


def _is_block_start(line: str, lines: list[str], idx: int) -> bool:
    if line.lstrip().startswith(("```", ">")):
        return True
    if _HEADING_RE.match(line) or _HR_RE.match(line) or _LIST_RE.match(line):
        return True
    if "|" in line and idx + 1 < len(lines) and _TABLE_SEP_RE.match(lines[idx + 1]):
        return True
    return False


def _split_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _render_table(header: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{render_inline(c)}</th>" for c in header)
    body = []
    for row in rows:
        # 열 수 보정
        row = (row + [""] * len(header))[: len(header)]
        tds = "".join(f"<td>{render_inline(c)}</td>" for c in row)
        body.append(f"<tr>{tds}</tr>")
    return (
        "<table><thead><tr>" + th + "</tr></thead><tbody>"
        + "".join(body) + "</tbody></table>"
    )


def build_toc(headings: list[tuple[int, str, str]]) -> str:
    if not headings:
        return ""
    items = []
    for level, text, slug in headings:
        cls = "toc-h2" if level == 2 else "toc-h3"
        # 제목 텍스트의 인라인 마커는 제거하고 표시
        label = re.sub(r"[`*_]", "", text)
        items.append(f'<li class="{cls}"><a href="#{slug}">{html.escape(label, quote=False)}</a></li>')
    return '<nav class="toc"><div class="toc-title">목차</div><ul>' + "".join(items) + "</ul></nav>"


CSS = """
:root{--fg:#24292f;--muted:#57606a;--bg:#ffffff;--soft:#f6f8fa;--border:#d0d7de;
--accent:#0969da;--accent2:#8250df;--code:#cf222e;}
*{box-sizing:border-box;}
body{margin:0;background:#eef1f5;color:var(--fg);
font-family:-apple-system,"Segoe UI",Roboto,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;
line-height:1.65;font-size:16px;}
.wrap{max-width:1000px;margin:32px auto;background:var(--bg);padding:48px 56px;
border:1px solid var(--border);border-radius:10px;box-shadow:0 2px 16px rgba(0,0,0,.06);}
h1{font-size:2em;border-bottom:2px solid var(--border);padding-bottom:.3em;margin-top:0;}
h2{font-size:1.5em;border-bottom:1px solid var(--border);padding-bottom:.25em;margin-top:2em;}
h3{font-size:1.2em;color:var(--accent2);margin-top:1.6em;}
h4{font-size:1.05em;margin-top:1.3em;}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
p{margin:.7em 0;}
code{background:var(--soft);padding:.15em .4em;border-radius:5px;
font-family:Consolas,"D2Coding","Courier New",monospace;font-size:.88em;color:var(--code);}
pre{background:var(--soft);border:1px solid var(--border);border-radius:8px;
padding:14px 16px;overflow-x:auto;line-height:1.5;}
pre code{background:none;padding:0;color:var(--fg);font-size:.85em;white-space:pre;}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em;display:block;overflow-x:auto;}
th,td{border:1px solid var(--border);padding:8px 12px;text-align:left;vertical-align:top;}
th{background:var(--soft);font-weight:700;}
tbody tr:nth-child(even){background:#fbfcfd;}
blockquote{margin:1em 0;padding:.6em 1.1em;border-left:4px solid var(--accent);
background:#f3f8ff;border-radius:0 8px 8px 0;color:var(--muted);}
blockquote p:first-child{margin-top:0;}
blockquote p:last-child{margin-bottom:0;}
hr{border:none;border-top:1px solid var(--border);margin:2em 0;}
ul,ol{padding-left:1.6em;}
li{margin:.25em 0;}
.toc{background:var(--soft);border:1px solid var(--border);border-radius:8px;
padding:14px 20px;margin:1.5em 0 2em;}
.toc-title{font-weight:700;color:var(--muted);margin-bottom:.4em;font-size:.95em;}
.toc ul{list-style:none;padding-left:0;margin:0;columns:2;column-gap:32px;}
.toc li{margin:.18em 0;break-inside:avoid;}
.toc-h3{padding-left:1.2em;font-size:.92em;}
.toc-h3 a{color:var(--muted);}
.footer{margin-top:2.5em;padding-top:1em;border-top:1px solid var(--border);
color:var(--muted);font-size:.85em;}
@media print{body{background:#fff;}.wrap{box-shadow:none;border:none;margin:0;max-width:none;padding:0;}.toc ul{columns:2;}}
"""


def main() -> int:
    md = SRC.read_text(encoding="utf-8")
    lines = md.replace("\r\n", "\n").split("\n")

    # 첫 H1 을 문서 제목으로 사용
    title = "PRD"
    for ln in lines:
        m = _HEADING_RE.match(ln)
        if m and len(m.group(1)) == 1:
            title = re.sub(r"[`*_]", "", m.group(2)).strip()
            break

    used: set[str] = set()
    headings: list[tuple[int, str, str]] = []
    body = convert(lines, headings, used)
    toc = build_toc(headings)

    # TOC 를 첫 H1 직후에 삽입
    h1_close = body.find("</h1>")
    if h1_close != -1:
        insert_at = h1_close + len("</h1>")
        body = body[:insert_at] + "\n" + toc + "\n" + body[insert_at:]
    else:
        body = toc + body

    out = (
        "<!DOCTYPE html>\n"
        '<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title, quote=False)}</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        f'<div class="wrap">\n{body}\n'
        '<div class="footer">이 문서는 <code>docs/PRD.md</code> 를 '
        '<code>docs/build_prd_html.py</code> 로 변환한 산출물입니다. '
        "원본 수정 후 재실행하여 동기화하세요.</div>\n"
        "</div>\n</body>\n</html>\n"
    )
    DST.write_text(out, encoding="utf-8")
    print(f"OK: wrote {DST} ({len(out)} bytes, {len(headings)} TOC entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
