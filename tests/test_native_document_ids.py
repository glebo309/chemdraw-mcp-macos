"""Exercise the production ID serializer without launching ChemDraw."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from chemdraw_macos.core import Bridge


def test_active_document_uses_json_integer_serialization():
    script = Path('chemdraw_macos/native.applescript').read_text()
    branch = script.split('if operation is "active_document" then', 1)[1].split('end if', 1)[0]
    assert 'my jsonInteger(' in branch
    assert 'as text' not in branch


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires macOS AppleScript, not ChemDraw')
@pytest.mark.parametrize('document_id', [0, 42, 39262464, 999999999, 1000000000,
                                       1234567890, 2147483647, -1234567890, -2147483648, None])
def test_native_active_id_roundtrip_is_exact_integer(document_id):
    template = Path('chemdraw_macos/native.applescript').read_text()
    helpers = template.split('on documentRow(d)', 1)[0]
    branch = template.split('if operation is "active_document" then', 1)[1].split('end if', 1)[0]
    branch = branch.replace('(count of documents)', 'fixtureCount').replace('id of document 1', 'fixtureID')
    script = helpers + f'\nset fixtureCount to {int(document_id is not None)}\n'
    script += f'set fixtureID to {document_id or 0}\n' + branch
    result = subprocess.run(['/usr/bin/osascript', '-'], input=script,
                            capture_output=True, text=True, check=True, timeout=10)
    value = json.loads(result.stdout)
    if document_id is None:
        assert value is None
    else:
        assert type(value) is int
        assert Bridge._id(value) == document_id
