"""Named commands, dialogs, NMR, checks, settings, preview and changes over real MCP stdio."""
import json
import math
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from chemdraw_macos.core import style_cdxml

pytestmark = pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST') != '1', reason='Requires licensed running ChemDraw')


def benzene(extra_bond=False):
    cdxml = '<CDXML><page id="1" BoundingBox="0 0 600 750"><fragment id="10">'
    points = [(200 + 30*math.cos(math.pi/3*i), 200 + 30*math.sin(math.pi/3*i)) for i in range(6)]
    for i, (x, y) in enumerate(points):
        hydrogens = '' if extra_bond and i == 0 else ' NumHydrogens="1"'
        cdxml += f'<n id="{11+i}" p="{x:.2f} {y:.2f}" Element="6"{hydrogens}/>'
    for i in range(6):
        cdxml += f'<b id="{20+i}" B="{11+i}" E="{11+(i+1) % 6}" Order="{2 if i % 2 else 1}"/>'
    if extra_bond:
        cdxml += '<n id="40" p="260 200"/><n id="41" p="200 140"/><b id="42" B="11" E="40"/><b id="43" B="11" E="41"/>'
    return style_cdxml(cdxml + '</fragment></page></CDXML>', 'house')


@pytest.mark.asyncio
async def test_native_commands_through_mcp():
    params = StdioServerParameters(command=sys.executable, args=['-m', 'chemdraw_macos.server'], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(tool, **arguments):
                r = await session.call_tool(tool, arguments)
                assert not r.isError, r
                return r.structuredContent or json.loads(r.content[0].text)

            created = await call('chemdraw_create_document', cdxml=benzene())
            did = created['document']['document_id']
            bad = (await call('chemdraw_create_document', cdxml=benzene(extra_bond=True)))['document']['document_id']
            try:
                listed = await call('chemdraw_list_commands', pattern='^(undo|redo|mapReactionAtoms|quit)$')
                assert {c['name']: c['allowed'] for c in listed['commands']} == {
                    'undo': True, 'redo': True, 'mapReactionAtoms': True, 'quit': False}

                flipped = await call('chemdraw_run_command', document_id=did, command='flipObjectsHorizontal', selection='all')
                assert flipped['status'] == 'completed' and flipped['counts_after']['atoms'] == 6
                assert (await call('chemdraw_run_command', document_id=did, command='undo'))['status'] == 'completed'

                refused = await session.call_tool('chemdraw_run_command', {'document_id': did, 'command': 'paste'})
                assert refused.isError

                sheet = await call('chemdraw_run_command', document_id=did, command='showScaleDialog', selection='all')
                assert sheet['status'] == 'dialog_open' and 'Cancel' in sheet['dialogs'][0]['buttons']
                assert (await call('chemdraw_dialog', button='Cancel'))['remaining_dialogs'] == []

                checked = await call('chemdraw_check_structure', document_id=bad)
                assert checked['ok'] is False and 'too many bonds' in checked['warnings'][0]['warning']
                assert (await call('chemdraw_check_structure', document_id=did))['ok'] is True

                settings = await call('chemdraw_document_settings', document_id=did, settings={'bond_length_pt': 14.4})
                assert settings['settings']['bond_length_pt'] == 14.4 and settings['not_applied'] == {}

                baseline = await call('chemdraw_document_changes', document_id=did)
                assert baseline['baseline'] is True and baseline['molecules'] == ['c1ccccc1']
                await call('chemdraw_run_command', document_id=did, command='clear', selection='all')
                changed = await call('chemdraw_document_changes', document_id=did)
                assert changed['molecules_removed'] == ['c1ccccc1']
                await call('chemdraw_run_command', document_id=did, command='undo')

                image = await session.call_tool('chemdraw_preview', {'document_id': did, 'pixels': 600})
                assert not image.isError and image.content[0].type == 'image'

                nmr = await call('chemdraw_predict_nmr', smiles='CCOC(C)=O', nucleus='1H', keep_open=False)
                assert sorted(round(s['shift_ppm'], 1) for s in nmr['shifts']) == [1.3, 2.0, 4.1]
                carbon = await call('chemdraw_predict_nmr', document_id=did, nucleus='13C', keep_open=False)
                assert {s['shift_ppm'] for s in carbon['shifts']} == {128.5}
            finally:
                for doc in (did, bad):
                    await session.call_tool('chemdraw_close_working_document', {'document_id': doc})
