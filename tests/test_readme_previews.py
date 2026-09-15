from pathlib import Path
import xml.etree.ElementTree as ET


def test_white_preview_preserves_all_native_drawing_elements():
    from scripts.build_readme_previews import white_preview
    assets=Path(__file__).parents[1]/'assets'
    for source in assets.glob('*.svg'):
        original=source.read_text();preview=white_preview(original)
        old=ET.fromstring(original);new=ET.fromstring(preview)
        background=new[0]
        assert background.tag=='{http://www.w3.org/2000/svg}rect'
        assert background.get('fill')=='#ffffff'
        assert [float(background.get(k)) for k in ('x','y','width','height')]==list(map(float,old.get('viewBox').split()))
        new.remove(background)
        assert ET.tostring(new)==ET.tostring(old)
