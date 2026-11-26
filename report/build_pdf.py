"""Turn REPORT.md into report/REPORT.pdf with headless Chrome.

Run from the repo root:  uv run --with markdown python report/build_pdf.py
"""

import pathlib
import shutil
import subprocess
import tempfile

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Noto Sans', 'Noto Sans Ethiopic', 'DejaVu Sans', sans-serif;
       font-size: 10.5pt; line-height: 1.5; color: #1d1d1f; }
h1 { font-size: 20pt; margin: 0 0 4px; color: #6b3e12; }
h2 { font-size: 14pt; margin: 22px 0 6px; color: #6b3e12;
     border-bottom: 1px solid #e3d5c3; padding-bottom: 3px; page-break-after: avoid; }
blockquote { margin: 10px 0; padding: 8px 14px; background: #faf5ee; border-left: 4px solid #c98a3c; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt; background: #f3f0eb;
       padding: 1px 4px; border-radius: 3px; }
pre { background: #f3f0eb; padding: 10px; font-size: 8.5pt; line-height: 1.35;
      border-radius: 4px; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
img { display: block; max-width: 100%; margin: 12px auto 4px; border-radius: 4px; page-break-inside: avoid; }
p em:only-child { display: block; text-align: center; font-size: 9pt; color: #555; }
hr { border: none; border-top: 1px solid #e3d5c3; }
li { margin: 2px 0; }
"""


def main() -> None:
    body = markdown.markdown((ROOT / "REPORT.md").read_text(), extensions=["tables", "fenced_code"])
    body = body.replace('src="report/', f'src="file://{ROOT}/report/')
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Report: The Final Chapter</title><style>{CSS}</style></head><body>{body}</body></html>"
    )
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or "chromium-browser"
    with tempfile.TemporaryDirectory() as scratch:
        page = pathlib.Path(scratch) / "report.html"
        page.write_text(html)
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             "--allow-file-access-from-files", f"--print-to-pdf={ROOT / 'report' / 'REPORT.pdf'}",
             f"file://{page}"],
            check=True, capture_output=True,
        )
    print("wrote report/REPORT.pdf")


if __name__ == "__main__":
    main()
