"""Portable chemistry breadth tests. These are not native visual acceptance."""
import pytest
from chemdraw_macos.harness import plan_request, run_drawing
from chemdraw_macos.identifiers import inspect_identifier


@pytest.mark.parametrize('smiles',[
    'CCO','CC(=O)O','CC#N','C=CC=C','C/C=C/C',r'C/C=C\C','CC(C)C',
    'C1CCCCC1','C1CC1','c1ccccc1','c1ccncc1','c1ccoc1','c1ccsc1',
    'c1ncc[nH]1','c1ccc2[nH]ccc2c1','c1ccc2ccccc2c1',
    'C1CC2CCC1C2','C1CCC2(CC1)CCCC2',
    'C[S+](C)C','OP(=O)(O)O','CS(=O)(=O)C','C[N+](C)(C)C',
    '[NH3+]CC(=O)[O-]','[13CH3]CO','CC(F)(F)F','CI','CF',
    'C[C@H](O)C(=O)O','C[C@@H](O)C(=O)O','N[C@@H](Cc1ccccc1)C(=O)O',
    'O=[N+]([O-])c1ccccc1','OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O',
])
def test_supported_input_graph_is_never_silently_changed(smiles):
    plan=plan_request({'molecules':[{'value':smiles,'format':'smiles'}]})
    assert plan['structures'][0]['smiles']==inspect_identifier(smiles)['canonical_smiles']
    assert plan['scaffold_smiles'] is None
    assert plan['groups'] is None


@pytest.mark.parametrize('smiles',['[Fe+2]','*CC','[CH3]','CCO invented_name','[Na+].[Cl-]','CC |bad|'])
def test_unsupported_input_does_not_reach_native_or_create_output(tmp_path,smiles):
    result=run_drawing(object(),{'molecules':[{'value':smiles,'format':'smiles'}]},str(tmp_path/'out'))
    assert result['status']=='rejected'
    assert result['stage']=='input'
    assert not (tmp_path/'out').exists()
