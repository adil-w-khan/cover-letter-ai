from weasyprint import HTML
from datetime import datetime

def text_to_simple_html(title: str, body_text: str) -> str:
    safe = (body_text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))
    safe = safe.replace("\n", "<br/>")

    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body {{ font-family: Arial, sans-serif; padding: 36px; line-height: 1.35; font-size: 12pt; }}
          .title {{ font-size: 14pt; font-weight: bold; margin-bottom: 16px; }}
        </style>
      </head>
      <body>
        <div class="title">{title}</div>
        <div>{safe}</div>
      </body>
    </html>
    """

def render_pdf_bytes(title: str, body_text: str) -> bytes:
    html = text_to_simple_html(title, body_text)
    return HTML(string=html).write_pdf()
