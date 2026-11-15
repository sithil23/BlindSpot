"""Small static SVG trend charts without interactive chart toolbars."""

from html import escape
from math import isfinite


def line_chart_svg(values, title: str, unit: str = "", width: int = 700, height: int = 205) -> str:




    samples = []
    for val in values:
        try:
            number = float(val) if val is not None else None
            if number is not None and not isfinite(number):
                number = None
        except (ValueError, TypeError, OverflowError):
            number = None
        samples.append(number)
    available = [v for v in samples if v is not None]
    name = escape(str(title), quote=True)
    units = escape(str(unit), quote=True)
    left, top, right, bottom = 54, 30, width - 16, height - 32
    if not available:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
                f'role="img" aria-label="{name}: no reliable readings">'
                f'<rect width="100%" height="100%" fill="#fff" stroke="#b6b6b6"/>'
                '<text x="20" y="100" font-family="Arial" fill="#444">No reliable readings</text></svg>')
    low, high = min(available), max(available)
    pad = max((high - low) * 0.15, abs(high) * 0.015, 0.1)
    low, high = low - pad, high + pad
    def x(i):
        return left + (right - left) * (i / max(1, len(samples) - 1))
    def y(v):
        return bottom - (v - low) / (high - low) * (bottom - top)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'role="img" aria-label="{name} trend, {units}">',
             '<rect width="100%" height="100%" fill="#fff" stroke="#b6b6b6"/>']
    for i in range(3):
        v = low + i * (high - low) / 2
        yp = y(v)
        parts.append(f'<line x1="{left}" y1="{yp:.1f}" x2="{right}" y2="{yp:.1f}" '
                     'stroke="#dddddd" stroke-width="1"/>')
        parts.append(f'<text x="{left-7}" y="{yp+4:.1f}" text-anchor="end" font-size="12" '
                     f'font-family="Arial" fill="#444">{v:.1f}</text>')
    segment = []
    for i, val in enumerate(samples + [None]):
        if val is not None:
            segment.append(f'{x(i):.1f},{y(val):.1f}')
        elif segment:
            if len(segment) > 1:
                parts.append(f'<polyline points="{" ".join(segment)}" fill="none" '
                             'stroke="#144e8b" stroke-width="2"/>')
            else:
                cx, cy = segment[0].split(',')
                parts.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="#144e8b"/>')
            segment = []
    parts.append(f'<text x="{left}" y="{height-9}" font-size="11" font-family="Arial" '
                 f'fill="#444">Samples: {len(samples)} · {units}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def chart_document(values, title: str, unit: str = "") -> str:




    svg = line_chart_svg(values, title, unit)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>html,body{margin:0;padding:0;overflow:hidden;background:#fff;}'
        'svg{display:block;width:100%;height:auto;max-height:230px;}'
        '*{animation:none!important;transition:none!important;}'
        '</style></head><body>' + svg + '</body></html>'
    )
