import asyncio
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chemdraw_macos.editing import inspect_editable, plan_edit, verify_native_edit, edit_document
from chemdraw_macos.polish import chemical_signature
from test_workflow import FakeBridge


ETHANOL = '''<CDXML BondLength="18" LineWidth="1.58" LabelFont="3" LabelSize="14">
<fonttable><font id="3" name="Helvetica Neue" charset="Unicode"/></fonttable>
<page id="100" BoundingBox="0 0 540 720"><fragment id="1">
<n id="2" p="50 60"/><n id="3" p="65.588457 69"/>
<n id="4" p="81.176914 60" Element="8" NumHydrogens="1"><t p="77 64"><s font="3" size="14" face="96">OH</s></t></n>
<b id="5" B="2" E="3"/><b id="6" B="3" E="4"/>
</fragment><t id="10" p="66 100" Justification="Center"><s font="3" size="10">Ethanol</s></t></page></CDXML>'''
SWAP = [{'kind':'atom','id':'4','element':'S','hydrogens':1}]
CAPTION = {'10':'Ethanethiol'}
CHIRAL = '''<CDXML LabelFont="3" LabelSize="14" LineWidth="1.58" BondLength="18"><fonttable><font id="3" name="Helvetica Neue" charset="Unicode"/></fonttable><page id="100"><fragment id="1">
<n id="2" p="90 60"/><n id="3" p="74.411543 69"/><n id="4" p="105.588457 69"/>
<n id="5" p="121.176914 60" Element="17" NumHydrogens="0"><t p="116 64"><s font="3" size="14" face="96">Cl</s></t></n>
<n id="6" p="90 42" Element="8" NumHydrogens="1"><t p="86 46"><s font="3" size="14" face="96">OH</s></t></n>
<b id="7" B="2" E="3"/><b id="8" B="2" E="4"/><b id="9" B="4" E="5"/><b id="10" B="2" E="6" Display="WedgeBegin"/>
</fragment></page></CDXML>'''


def test_inspection_exposes_atom_bond_ids_and_stale_guard():
    report = inspect_editable(ETHANOL)
    assert len(report['source_token']) == 64
    assert report['atoms'][2]['element'] == 'O'
    assert report['atoms'][2]['id'] == '4'
    assert report['bonds'][1]['id'] == '6'
    assert report['captions'][0]['id'] == '10'


def test_element_edit_changes_label_graph_not_coordinates():
    text, diff = plan_edit(ETHANOL, SWAP, CAPTION)
    before, after = ET.fromstring(ETHANOL), ET.fromstring(text)
    assert [n.get('p') for n in before.iter('n')] == [n.get('p') for n in after.iter('n')]
    assert chemical_signature(text) == ['CCS']
    assert ''.join(after.find('.//n[@id="4"]').itertext()) == 'SH'
    assert diff['before_smiles'] == ['CCO'] and diff['after_smiles'] == ['CCS']
    assert diff['atom_changes'][0]['id'] == '4'
    assert 'Ethanethiol' in text


def test_carbonyl_bond_edit_requires_explicit_hydrogen_decision():
    ops = [{'kind':'bond','id':'6','order':2}, {'kind':'atom','id':'4','hydrogens':0}]
    text, diff = plan_edit(ETHANOL, ops, {'10':'Ethanal'})
    assert chemical_signature(text) == ['CC=O']
    assert ''.join(ET.fromstring(text).find('.//n[@id="4"]').itertext()) == 'O'
    assert diff['bond_changes'][0]['id'] == '6'
    assert {'id':'3','before':2,'after':1} in diff['observed_hydrogen_changes']
    with pytest.raises(ValueError): plan_edit(ETHANOL, ops[:1], {'10':'Ethanal'})


@pytest.mark.parametrize('ops', [
    [], SWAP+SWAP,
    [{'kind':'atom','id':'999','element':'S','hydrogens':1}],
    [{'kind':'atom','id':'4','element':'N','hydrogens':1}],
    [{'kind':'atom','id':'4','element':'O','hydrogens':1}],
    [{'kind':'atom','id':'4','element':'S'}],
    [{'kind':'atom','id':'4','element':'S','hydrogens':True}],
    [{'kind':'atom','id':'4','element':'S','hydrogens':1,'charge':1}],
    [{'kind':'bond','id':'6','order':4}],
])
def test_bad_or_ambiguous_edits_fail_closed(ops):
    with pytest.raises(ValueError): plan_edit(ETHANOL, ops, CAPTION)


def test_every_caption_requires_explicit_decision_and_can_be_removed():
    with pytest.raises(ValueError, match='caption'): plan_edit(ETHANOL, SWAP, {})
    text, _ = plan_edit(ETHANOL, SWAP, {'10':None})
    assert ET.fromstring(text).find('page/t') is None


def test_wedge_bond_edit_and_edited_isotope_rejected():
    with pytest.raises(ValueError):
        plan_edit(ETHANOL.replace('id="6"','id="6" Display="WedgeBegin"'),
                  [{'kind':'bond','id':'6','order':2},{'kind':'atom','id':'4','hydrogens':0}], {'10':'Ethanal'})
    with pytest.raises(ValueError): plan_edit(ETHANOL.replace('Element="8"','Element="8" Isotope="18"'), SWAP, CAPTION)


def test_new_alkene_stereochemistry_is_not_inferred_from_old_zigzag():
    source='''<CDXML><page><fragment id="1"><n id="2" p="0 0"/><n id="3" p="18 10"/><n id="4" p="36 0"/><n id="5" p="54 10"/><b id="6" B="2" E="3"/><b id="7" B="3" E="4"/><b id="8" B="4" E="5"/></fragment></page></CDXML>'''
    with pytest.raises(ValueError, match='stereo'):
        plan_edit(source,[{'kind':'bond','id':'7','order':2}],{})


def test_native_renumbering_and_reordering_are_verified_per_atom():
    planned, _ = plan_edit(ETHANOL, SWAP, CAPTION)
    root=ET.fromstring(planned);frag=root.find('.//fragment')
    atoms=frag.findall('n')
    for n in atoms:frag.remove(n)
    for n in reversed(atoms):frag.insert(0 if n==atoms[-1] else len(frag),n)
    for e in root.find('page').iter():
        for k in ('id','B','E'):
            if e.get(k):e.set(k,str(int(e.get(k))+100))
    report=verify_native_edit(planned,ET.tostring(root,encoding='unicode'))
    assert report['atom_id_map']['4']=='104'
    assert report['maximum_displacement_pt']==0
    bad=ET.fromstring(planned)
    bad.find('.//n[@id="4"]').set('p','99 60')
    with pytest.raises(ValueError):verify_native_edit(planned,ET.tostring(bad,encoding='unicode'))


def test_same_formula_wrong_atom_placement_and_stale_glyph_fail():
    planned,_=plan_edit(ETHANOL,SWAP,CAPTION)
    wrong=planned.replace('Element="16"','Element="8"')
    with pytest.raises(ValueError):verify_native_edit(planned,wrong)
    with pytest.raises(ValueError):verify_native_edit(planned,planned.replace('>SH<','>OH<'))


def test_edit_workflow_keeps_source_and_writes_review(tmp_path):
    bridge=FakeBridge(tmp_path/'work');bridge.docs[1]=ETHANOL
    token=inspect_editable(ETHANOL)['source_token']
    result=edit_document(bridge,1,str(tmp_path/'out'),SWAP,CAPTION,token)
    assert bridge.docs[1]==ETHANOL
    assert all(result['audit']['checks'].values())
    assert result['audit']['visual_review']=='required'
    for file in ('before.cdxml','before.svg','before.png','figure.cdxml','figure.svg','figure.png','review.html','audit.json','recipe.json'):
        assert (tmp_path/'out'/file).is_file()


def test_stale_source_rejected_without_creating_native_copy(tmp_path):
    bridge=FakeBridge(tmp_path/'work');bridge.docs[1]=ETHANOL
    with pytest.raises(ValueError,match='stale'):
        edit_document(bridge,1,str(tmp_path/'out'),SWAP,CAPTION,'0'*64)
    assert not any(e[0]=='create' for e in bridge.events)


def test_edit_is_callable_through_cli_and_mcp(capsys):
    from chemdraw_macos.cli import main
    from chemdraw_macos.server import mcp
    with pytest.raises(SystemExit) as exc:main(['edit','--help'])
    assert exc.value.code==0
    assert '--recipe' in capsys.readouterr().out
    assert 'chemdraw_edit_document' in {t.name for t in asyncio.run(mcp.list_tools())}


def test_analysis_includes_editable_selection_and_token(tmp_path):
    from chemdraw_macos.workflow import analyze_document
    bridge=FakeBridge(tmp_path/'work');bridge.docs[1]=ETHANOL
    result=analyze_document(bridge,1)
    assert result['editing']['atoms'][2]['id']=='4'
    assert result['editing']['source_token']==inspect_editable(ETHANOL)['source_token']


def test_cli_file_edit_remaps_native_atom_and_caption_ids(tmp_path,monkeypatch,capsys):
    from chemdraw_macos.cli import main
    source=tmp_path/'ethanol.cdxml';source.write_text(ETHANOL)
    recipe=tmp_path/'recipe.json';recipe.write_text(json.dumps({'schema_version':1,'operations':SWAP,'captions':CAPTION}))
    bridge=FakeBridge(tmp_path/'work')
    def imported(path):
        root=ET.fromstring(source.read_text())
        for e in root.find('page').iter():
            for k in ('id','B','E'):
                if e.get(k):e.set(k,str(int(e.get(k))+100))
        return bridge.create(ET.tostring(root,encoding='unicode'))
    bridge.import_file=imported
    monkeypatch.setattr('chemdraw_macos.cli.Bridge',lambda:bridge)
    assert main(['edit','--input',str(source),'--recipe',str(recipe),'--output',str(tmp_path/'out')])==0
    result=json.loads(capsys.readouterr().out)
    assert result['audit']['chemical_diff']['after_smiles']==['CCS']


def test_included_aromatic_analogue_fixture():
    source=(Path(__file__).parents[1]/'examples/chlorobenzoic-acid.cdxml').read_text()
    text,diff=plan_edit(source,[{'kind':'atom','id':'8','element':'Br','hydrogens':0}],{'30':'4-Bromobenzoic acid'})
    assert diff['before_smiles']==['O=C(O)c1ccc(Cl)cc1']
    assert diff['after_smiles']==['O=C(O)c1ccc(Br)cc1']


def test_existing_chiral_scaffold_survives_remote_halogen_swap():
    assert '@' in chemical_signature(CHIRAL)[0]
    planned,diff=plan_edit(CHIRAL,[{'kind':'atom','id':'5','element':'Br','hydrogens':0}],{})
    assert '@' in diff['after_smiles'][0]
    assert diff['after_smiles'][0]==diff['before_smiles'][0].replace('Cl','Br')
    assert ET.fromstring(planned).find('.//b[@id="10"]').get('Display')=='WedgeBegin'
