"""Build opaque documentation copies without changing native SVG exports."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def white_preview(svg):
    root=ET.fromstring(svg)
    x,y,width,height=map(float,root.attrib['viewBox'].split())
    rect=f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" fill="#ffffff"/>'
    return re.sub(r'(<svg\b[^>]*>\s*)',lambda match:match[0]+rect,svg,count=1)


def main():
    assets=Path(__file__).resolve().parents[1]/'assets'
    destination=assets/'readme';destination.mkdir(exist_ok=True)
    for source in sorted(assets.glob('*.svg')):
        target=destination/source.name
        target.write_text(white_preview(source.read_text()))
        print(target.relative_to(assets.parent))


if __name__=='__main__':main()
