"""Turn REPORT.md into report/REPORT.pdf (A4, Times New Roman, cover page, contents, page numbers).

Run from the repo root:  uv run --with markdown python report/build_pdf.py
"""

import html
import pathlib
import re
import shutil
import subprocess
import tempfile

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent

TITLE = "The Final Chapter"
TITLE_AM = "የመጨረሻው ምዕራፍ"
SUBTITLE = "An AI-generated Amharic short film and the pipeline that made it"
AUTHOR = "Dagmawi Teferi"
COURSE = "B2W0: AI-Content Generation · Codebase and Report"
DATE = "26 November 2026"
REPO = "https://github.com/dagiteferi/AI-Content-Generations"

SERIF = "'Times New Roman', Times, 'Liberation Serif', 'Noto Serif Ethiopic', serif"

CSS = f"""
@page {{
  size: A4;
  margin: 25mm 25mm 22mm 25mm;
  @top-right {{ content: "{TITLE}: Project Report"; font: italic 9pt {SERIF}; color: #555; }}
  @bottom-center {{ content: counter(page); font: 10pt {SERIF}; }}
}}
@page cover {{ @top-right {{ content: none; }} @bottom-center {{ content: none; }} }}

body {{ font-family: {SERIF}; font-size: 12pt; line-height: 1.45; color: #000; }}
p, li {{ text-align: justify; hyphens: auto; }}
p {{ margin: 0 0 9pt; }}

.cover {{ page: cover; height: 245mm; display: flex; flex-direction: column;
          justify-content: center; text-align: center; page-break-after: always; }}
.cover .course {{ font-size: 12pt; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 40mm; }}
.cover h1 {{ font-size: 28pt; margin: 0; font-weight: bold; }}
.cover .am {{ font-size: 20pt; margin: 6pt 0 14pt; }}
.cover .subtitle {{ font-size: 14pt; font-style: italic; margin-bottom: 45mm; text-align: center; }}
.cover .meta {{ font-size: 12pt; line-height: 1.8; text-align: center; }}
.cover .rule {{ width: 60mm; border-top: 1.5px solid #000; margin: 0 auto 14pt; }}

.toc {{ page-break-after: always; }}
.toc h2 {{ border: none; }}
.toc ol {{ list-style: none; padding: 0; margin: 0; }}
.toc li {{ font-size: 12pt; padding: 5pt 0; border-bottom: 1px dotted #999; text-align: left; }}
.toc a {{ color: #000; text-decoration: none; }}

h2 {{ font-size: 15pt; font-weight: bold; margin: 20pt 0 8pt; page-break-after: avoid; }}
h3 {{ font-size: 13pt; margin: 14pt 0 6pt; }}
ul, ol {{ margin: 0 0 9pt; padding-left: 20pt; }}
li {{ margin: 2pt 0; }}
blockquote {{ margin: 10pt 20pt; padding: 0; font-style: normal; }}
blockquote p {{ text-align: left; }}
code {{ font-family: 'DejaVu Sans Mono', 'Courier New', monospace; font-size: 9.5pt; }}
pre {{ font-size: 6.9pt; max-width: 160mm; box-sizing: border-box; line-height: 1.3; border: 1px solid #bbb; padding: 8pt;
       page-break-inside: avoid; overflow: hidden; }}
pre code {{ font-size: inherit; }}
a {{ color: #000; }}

figure {{ margin: 12pt 0; text-align: center; page-break-inside: avoid; }}
img {{ max-width: 100%; }}
figure img {{ display: block; margin: 0 auto; width: auto; height: auto; max-width: 100%; max-height: 100mm; }}
figcaption {{ font-size: 10pt; margin-top: 5pt; text-align: center; }}
figcaption b {{ font-weight: bold; }}
.todo {{ border: 1px dashed #777; padding: 6pt 10pt; background: #f5f5f5; }}
"""


def figures(body: str) -> str:
    """<p><img></p><p><em>Figure N. text</em></p>  ->  <figure> with a proper caption."""
    pattern = re.compile(
        r'<p><img alt="[^"]*" src="([^"]+)" ?/?>\s*(?:</p>\s*<p>)?<em>(Figure \d+\.)\s*(.*?)</em></p>', re.S
    )
    return pattern.sub(
        lambda m: f'<figure><img src="{m[1]}"><figcaption><b>{m[2]}</b> {m[3]}</figcaption></figure>', body
    )


def numbered_anchors(body: str) -> tuple[str, list[tuple[str, str]]]:
    entries = []

    def anchor(match: re.Match) -> str:
        text = match[1]
        slug = f"sec{len(entries)}"
        entries.append((slug, text))
        return f'<h2 id="{slug}">{text}</h2>'

    return re.sub(r"<h2>(.*?)</h2>", anchor, body), entries


def build_html() -> str:
    source = (ROOT / "REPORT.md").read_text()
    source = source.split("\n---\n", 1)[1]  # the cover page replaces the markdown title block
    body = markdown.markdown(source, extensions=["tables", "fenced_code"])
    body = body.replace('src="report/', f'src="file://{ROOT}/report/')
    body = figures(body)
    body = body.replace("<blockquote>\n<p><strong>TODO", '<blockquote class="todo">\n<p><strong>TODO')
    body, entries = numbered_anchors(body)

    toc = "".join(f'<li><a href="#{slug}">{text}</a></li>' for slug, text in entries)
    cover = f"""
<section class="cover">
  <div class="course">{html.escape(COURSE)}</div>
  <h1>{TITLE}</h1>
  <div class="am">{TITLE_AM}</div>
  <div class="subtitle">{SUBTITLE}</div>
  <div class="rule"></div>
  <div class="meta"><b>{AUTHOR}</b><br>{DATE}<br>{REPO}</div>
</section>
<section class="toc"><h2>Contents</h2><ol>{toc}</ol></section>
"""
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{TITLE}: Project Report</title><style>{CSS}</style></head>"
        f"<body>{cover}{body}</body></html>"
    )


def main() -> None:
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or "chromium-browser"
    with tempfile.TemporaryDirectory() as scratch:
        page = pathlib.Path(scratch) / "report.html"
        page.write_text(build_html())
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             "--allow-file-access-from-files", f"--print-to-pdf={ROOT / 'report' / 'REPORT.pdf'}",
             f"file://{page}"],
            check=True, capture_output=True,
        )
    print("wrote report/REPORT.pdf")


if __name__ == "__main__":
    main()
