import copy
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


def recipe():
    return {'schema_version': 1, 'label': 'Explicit coordination fixture',
            'atoms': [
                {'id': 'cu', 'element': 'Cu', 'charge': 2, 'hydrogens': 0, 'position': [150, 150, 0]},
                {'id': 'n1', 'element': 'N', 'charge': 0, 'hydrogens': 3, 'position': [95, 150, 0]},
                {'id': 'n2', 'element': 'N', 'charge': 0, 'hydrogens': 3, 'position': [205, 150, 0]},
                {'id': 'n3', 'element': 'N', 'charge': 0, 'hydrogens': 3, 'position': [150, 95, 20]},
                {'id': 'n4', 'element': 'N', 'charge': 0, 'hydrogens': 3, 'position': [150, 205, -20]},
            ], 'bonds': [
                {'begin': f'n{i}', 'end': 'cu', 'order': 'dative'} for i in range(1, 5)]}


def test_explicit_complex_preserves_positions_and_donor_direction():
    from chemdraw_macos.complexes import plan_complex, verify_complex
    text, plan = plan_complex(recipe())
    root = ET.fromstring(text)
    atoms = root.findall('page/fragment/n')
    assert len(atoms) == 5 and all(n.get('xyz') for n in atoms)
    assert all(b.get('Order') == 'dative' for b in root.findall('page/fragment/b'))
    assert verify_complex(text, text)['checks']['explicit_atom_bond_records_preserved']
    assert plan['geometry'] == 'caller-supplied, not optimized or inferred'


@pytest.mark.parametrize('change', ['charge', 'xyz', 'direction', 'display', 'hydrogens', 'extra'])
def test_native_complex_semantic_changes_fail_closed(change):
    from chemdraw_macos.complexes import plan_complex, verify_complex
    text, _ = plan_complex(recipe()); root = ET.fromstring(text)
    atom = root.find('page/fragment/n'); bond = root.find('page/fragment/b')
    if change == 'charge': atom.set('Charge', '1')
    if change == 'xyz': atom.set('xyz', '150 150 2')
    if change == 'hydrogens': atom.set('NumHydrogens', '1')
    if change == 'direction': bond.set('B', atom.get('id')); bond.set('E', '4')
    if change == 'display': bond.set('Display', 'Dash')
    if change == 'extra': ET.SubElement(root.find('page'), 'curve', {'id': '500'})
    with pytest.raises(ValueError): verify_complex(text, ET.tostring(root, encoding='unicode'))


@pytest.mark.parametrize('change', ['unknown', 'nan', 'duplicate', 'dangling', 'reverse', 'disconnected'])
def test_ambiguous_complex_inputs_fail_before_native_work(change):
    from chemdraw_macos.complexes import plan_complex
    r = recipe()
    if change == 'unknown': r['oxidation_state'] = 2
    if change == 'nan': r['atoms'][0]['position'][2] = float('nan')
    if change == 'duplicate': r['atoms'][1]['id'] = 'cu'
    if change == 'dangling': r['bonds'][0]['end'] = 'absent'
    if change == 'reverse': r['bonds'][0] = {'begin': 'cu', 'end': 'n1', 'order': 'dative'}
    if change == 'disconnected': r['bonds'].pop()
    with pytest.raises(ValueError): plan_complex(r)


def test_complex_cli_and_mcp_are_callable(capsys, monkeypatch):
    from chemdraw_macos import cli, server
    with pytest.raises(SystemExit) as result: cli.main(['complex-draw', '--help'])
    assert result.value.code == 0
    assert '--recipe' in capsys.readouterr().out
    monkeypatch.setattr(server, 'draw_complex', lambda *a, **kw: {'called': True})
    monkeypatch.setattr(server, 'bridge', lambda: object())
    assert server.chemdraw_draw_complex(recipe(), '/new/output')['called']


def test_multi_charge_uses_explicit_superscript_run():
    from chemdraw_macos.complexes import plan_complex
    text,_=plan_complex(recipe())
    runs=ET.fromstring(text).findall('page/fragment/n/t/s')
    assert any(s.text=='2+' and s.get('face')=='64' for s in runs)


def test_native_zero_z_omission_is_equivalent_but_nonzero_loss_is_not():
    from chemdraw_macos.complexes import plan_complex, verify_complex
    text,_=plan_complex(recipe()); root=ET.fromstring(text)
    for atom in root.findall('page/fragment/n'):
        if float(atom.get('xyz').split()[2])==0: atom.attrib.pop('xyz')
    assert verify_complex(text,ET.tostring(root,encoding='unicode'))['checks']['supplied_xyz_preserved']
    root.findall('page/fragment/n')[3].attrib.pop('xyz')
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


@pytest.mark.parametrize('change',['isotope','query','nested','radical','bond','position','missing','count'])
def test_unrequested_native_complex_changes_are_rejected(change):
    from chemdraw_macos.complexes import plan_complex,verify_complex
    text,_=plan_complex(recipe()); root=ET.fromstring(text); node=root.find('page/fragment/n')
    if change=='isotope': node.set('Isotope','65')
    if change=='query': node.set('NodeType','GenericNickname')
    if change=='nested': ET.SubElement(node,'fragment',{'id':'987'})
    if change=='radical': node.set('Radical','Doublet')
    if change=='bond': root.find('page/fragment/b').set('Order','1')
    if change=='position': node.set('p','151 150')
    if change=='missing': root.find('page/fragment').remove(node)
    if change=='count': ET.SubElement(root.find('page/fragment'),'b',{'id':'900','B':'3','E':'4'})
    with pytest.raises(ValueError): verify_complex(text,ET.tostring(root,encoding='unicode'))


def test_invalid_complex_never_touches_native_or_destination(tmp_path):
    from chemdraw_macos.complexes import draw_complex
    class NoNative:
        def __getattr__(self,name): raise AssertionError('Native should not be reached')
    bad=recipe(); bad['atoms'][0]['position'][0]=float('inf')
    with pytest.raises(ValueError): draw_complex(NoNative(),bad,str(tmp_path/'out'))
    assert not (tmp_path/'out').exists()
