"""Convert Bedienungsanleitung.md to PDF."""
import markdown
from xhtml2pdf import pisa

md = open("Bedienungsanleitung.md", encoding="utf-8").read()

html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: Segoe UI, Arial, sans-serif;
    margin: 60pt 50pt;
    line-height: 1.6;
    color: #333;
}}
h1 {{
    font-size: 24pt;
    color: #1a1a2e;
    border-bottom: 3px solid #0078d4;
    padding-bottom: 8pt;
}}
h2 {{
    font-size: 18pt;
    color: #0078d4;
    margin-top: 24pt;
}}
h3 {{
    font-size: 14pt;
    color: #333;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 8pt;
    text-align: left;
}}
th {{
    background: #0078d4;
    color: white;
}}
blockquote {{
    border-left: 4px solid #0078d4;
    padding: 8pt 16pt;
    margin: 12pt 0;
    background: #f0f6ff;
}}
code {{
    background: #f4f4f4;
    padding: 2pt 6pt;
    border-radius: 3pt;
}}
hr {{
    border: none;
    border-top: 2px solid #ddd;
    margin: 20pt 0;
}}
</style>
</head>
<body>
''' + markdown.markdown(md, extensions=['tables', 'fenced_code']) + '''
<footer style="text-align:center;font-size:10pt;color:#888;margin-top:30pt;">
Version 1.0.0 | Wake-on-LAN Manager
</footer>
</body>
</html>'''

with open("Bedienungsanleitung.pdf", "wb") as f:
    pisa.CreatePDF(html, dest=f)

print("PDF created successfully: Bedienungsanleitung.pdf")
