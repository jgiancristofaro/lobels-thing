"""Wrap site/index.html (an artifact-style body fragment) into a full page for GitHub Pages."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src, out = ROOT / "site", ROOT / "_site"
shutil.rmtree(out, ignore_errors=True)
shutil.copytree(src, out)
body = (src / "index.html").read_text()
(out / "index.html").write_text(
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    '<meta name="theme-color" content="#EEF1EF">\n</head>\n<body>\n' + body + "\n</body>\n</html>\n"
)
print("built", out)
