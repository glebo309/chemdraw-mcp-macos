"""Switch a multi-page document to one page only when that loses nothing.

Templates often open as poster layouts (for example 2 pages wide by 3 tall). Shared drawing
places objects on one physical page width, so such a document is set to 1 x 1 first, but
only when it is empty or everything on it already lies on the first physical page.
"""
from .core import validate_cdxml
from .polish import numbers

MANUAL_FIX = ('In ChemDraw open File > Document Settings, set the layout to 1 page wide and '
              '1 page high, then retry. Nothing was changed.')


def _pages(page):
    wide, high = page.get('WidthPages', '1'), page.get('HeightPages', '1')
    if not (wide.isdigit() and high.isdigit()) or int(wide) < 1 or int(high) < 1:
        raise ValueError('Unreadable document page layout. ' + MANUAL_FIX)
    return int(wide), int(high)


def describe(pages):
    wide, high = pages
    return (f'This document is {wide} page{"s" if wide != 1 else ""} wide and '
            f'{high} page{"s" if high != 1 else ""} tall')


def content_record(page):
    """Every object on the page with all attributes, for an exact before/after comparison."""
    def record(e):
        return (e.tag, sorted(e.attrib.items()), e.text or '', [record(c) for c in e])
    return [record(e) for e in page]


def first_page_fit(text, allow_page_expansion=True):
    """Return None when drawing accepts the page as it is, else the page counts and the first
    physical page that a 1 x 1 layout keeps. Refuse when content lies outside that page."""
    page = validate_cdxml(text).find('page')
    pages = _pages(page)
    if pages[0] == 1 and (pages[1] == 1 or allow_page_expansion):
        return None
    x, y, r, b = numbers(page.get('BoundingBox'), 4)
    first = (x, y, x + (r - x) / pages[0], y + (b - y) / pages[1])
    for e in page:
        if e.tag == 'chemicalproperty':
            continue
        if not e.get('BoundingBox'):
            raise ValueError(describe(pages) + ', and the position of its content could not be measured, '
                             'so it was not switched to one page automatically. ' + MANUAL_FIX)
        left, top, right, bottom = numbers(e.get('BoundingBox'), 4)
        left, right = sorted((left, right)); top, bottom = sorted((top, bottom))
        if left < first[0] - .01 or top < first[1] - .01 or right > first[2] + .01 or bottom > first[3] + .01:
            raise ValueError(describe(pages) + ', and some content lies outside the first page, so it was '
                             'not switched to one page automatically. Move that content onto the first page '
                             'or draw in a new document. Nothing was changed.')
    return {'pages': pages, 'first_page': first}
