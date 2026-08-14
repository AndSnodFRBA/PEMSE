import io

from reportlab.lib import colors
from reportlab.pdfgen import canvas as pdfcanvas


def _watermark_page(width, height, text):
    """Build a single-page watermark sized to match the target page — needed
    because some PDFs (e.g. the landscape certificate) aren't letter-portrait,
    and a mismatched watermark page merges off-center."""
    from PyPDF2 import PdfReader

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=(width, height))
    c.setFont('Helvetica-Bold', 72)
    c.setFillColor(colors.Color(0.8, 0.8, 0.8, alpha=0.3))
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def add_watermark(input_pdf_bytes, text='SAMPLE'):
    from PyPDF2 import PdfReader, PdfWriter

    writer = PdfWriter()
    reader = PdfReader(io.BytesIO(input_pdf_bytes))
    watermarks = {}
    for page in reader.pages:
        size = (float(page.mediabox.width), float(page.mediabox.height))
        if size not in watermarks:
            watermarks[size] = _watermark_page(size[0], size[1], text)
        page.merge_page(watermarks[size])
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def watermark_if_demo(pdf_bytes):
    """Apply the SAMPLE watermark to pdf_bytes when DEMO_MODE is on; otherwise
    return the bytes unchanged."""
    from django.conf import settings
    if not settings.DEMO_MODE:
        return pdf_bytes
    return add_watermark(pdf_bytes, 'SAMPLE')
