import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from rdkit import Chem

from chemdraw_macos.draw import prepare_structures, combine_native_structures, draw_structures
from chemdraw_macos.polish import chemical_signature


def test_smiles_seed_preserves_assigned_stereo_and_isotope():
    records = prepare_structures([{'compound_id':'a','label':'Test label','smiles':'[13CH3][C@H](O)C(=O)O'}])
    item = records[0]
    mol = Chem.MolFromMolBlock(item['molblock'], removeHs=False)
    assert Chem.MolToSmiles(mol) == item['canonical_smiles']
    assert item['label'] == 'Test label'


def test_assigned_smiles_stereo_sets_absolute_molfile_flag():
    item=prepare_structures([{'compound_id':'a','label':'Chiral test','smiles':'C[C@H](O)C(=O)O'}])[0]
    assert item['molblock'].splitlines()[3][12:15].strip()=='1'


@pytest.mark.parametrize('entry', [
    {'compound_id':'../x','label':'X','smiles':'CCO'},
    {'compound_id':'x','label':'X','smiles':'CCO hidden name'},
    {'compound_id':'x','label':'X','smiles':'*CC'},
    {'compound_id':'x','label':'X','smiles':'[Na+].[Cl-]'},
    {'compound_id':'x','label':'X','smiles':'[CH3]'},
    {'compound_id':'x','label':'X','smiles':'CCO','yield_percent':42},
    {'compound_id':'x','label':'bad\nlabel','smiles':'CCO'},
])
def test_invalid_creation_request_rejected(entry):
    with pytest.raises(ValueError):prepare_structures([entry])


def test_duplicates_and_empty_rejected():
    a={'compound_id':'a','label':'Ethanol','smiles':'CCO'}
    with pytest.raises(ValueError):prepare_structures([])
    with pytest.raises(ValueError):prepare_structures([a,a])


ETHANOL='''<CDXML LabelFont="3" LabelSize="10"><fonttable><font id="3" name="Arial" charset="Unicode"/></fonttable><page id="99" BoundingBox="0 0 540 720"><fragment id="1"><n id="2" p="40 40"/><n id="3" p="56 49"/><n id="4" p="72 40" Element="8" NumHydrogens="1"><t p="72 40"><s font="3" size="10" face="96">OH</s></t></n><b id="5" B="2" E="3"/><b id="6" B="3" E="4"/></fragment></page></CDXML>'''


def test_combine_native_structures_remaps_ids_and_owns_names():
    items=prepare_structures([{'compound_id':'a','label':'First','smiles':'CCO'},
                              {'compound_id':'b','label':'Second','smiles':'CCO'}])
    text,cells=combine_native_structures([ETHANOL,ETHANOL],items)
    assert chemical_signature(text)==['CCO','CCO']
    root=ET.fromstring(text)
    ids=[e.get('id') for e in root.find('page').iter() if e.get('id')]
    assert len(ids)==len(set(ids))
    assert [c['compound_id'] for c in cells]==['a','b']
    assert all(c['yield_percent'] is None for c in cells)
    assert [''.join(t.itertext()) for t in root.findall('page/t')]==['First','Second']


def test_changed_native_identity_rejected_before_combining():
    item=prepare_structures([{'compound_id':'a','label':'Methanol','smiles':'CO'}])
    with pytest.raises(ValueError,match='identity'):
        combine_native_structures([ETHANOL],item)


def test_assembly_keeps_native_page_and_initial_objects_inside_it():
    items=prepare_structures([{'compound_id':str(i),'label':'Ethanol','smiles':'CCO'} for i in range(12)])
    text,_=combine_native_structures([ETHANOL]*12,items)
    root=ET.fromstring(text)
    assert root.find('page').get('BoundingBox')=='0 0 540 720'
    for node in root.findall('.//n'):
        x,y=map(float,node.get('p').split())
        assert 36<x<504 and 36<y<684


def test_assembly_seed_molecular_ink_does_not_overlap():
    from chemdraw_macos.polish import bounds
    from chemdraw_macos.geometry import find_overlaps
    items=prepare_structures([{'compound_id':str(i),'label':'Ethanol','smiles':'CCO'} for i in range(12)])
    text,_=combine_native_structures([ETHANOL]*12,items)
    assert not find_overlaps([bounds(f) for f in ET.fromstring(text).findall('page/fragment')])


def test_assembly_normalizes_native_cleanup_scale_before_page_fit():
    from chemdraw_macos.polish import bond_lengths
    large=ETHANOL.replace('56 49','120 100').replace('72 40','200 40')
    items=prepare_structures([{'compound_id':str(i),'label':'Ethanol','smiles':'CCO'} for i in range(14)])
    text,_=combine_native_structures([large]*14,items)
    assert bond_lengths(ET.fromstring(text).find('page/fragment'))==pytest.approx([18,18],abs=.01)


def test_draw_preflight_before_native_creation(tmp_path):
    class NoNative:
        def __getattr__(self,name):raise AssertionError('Unexpected native call '+name)
    with pytest.raises(FileExistsError):
        draw_structures(NoNative(),[{'compound_id':'a','label':'X','smiles':'CCO'}],str(tmp_path))
    with pytest.raises(ValueError):
        draw_structures(NoNative(),[{'compound_id':'a','label':'X','smiles':'bad'}],str(tmp_path/'new'))


def test_uncertain_import_not_retried_or_closed(tmp_path):
    class Timeout:
        calls=0
        def documents(self):return {'documents':[]}
        def import_file(self,path):
            self.calls+=1
            raise RuntimeError('timeout')
        def close(self,did):raise AssertionError('No close after uncertainty')
    b=Timeout()
    with pytest.raises(RuntimeError,match='timeout'):
        draw_structures(b,[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}],str(tmp_path/'out'))
    assert b.calls==1
    assert json.loads((tmp_path/'out'/'audit.json').read_text())['status']=='uncertain'


def test_missing_requested_scaffold_rejected_before_native_calls(tmp_path):
    class NoNative:
        def __getattr__(self,name):raise AssertionError('Unexpected native call '+name)
    with pytest.raises(ValueError,match='scaffold'):
        draw_structures(NoNative(),[{'compound_id':'a','label':'Ethanol','smiles':'CCO'}],
                        str(tmp_path/'out'),scaffold_smiles='c1ccccc1')
