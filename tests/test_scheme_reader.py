"""Reading an existing scheme: offline, roles proposed not certified."""
from pathlib import Path
import pytest

pytest.importorskip('rdkit')
from chemdraw_macos.scheme_reader import read_reaction
from chemdraw_macos.identifiers import inspect_identifier

FIXTURE = Path(__file__).parent / 'fixtures' / 'cdxml-toolkit-KL-CC-002-scheme.cdxml'


def canon(s):
    return inspect_identifier(s)['canonical_smiles']


def smiles(rows):
    return {canon(r['smiles']) for r in rows if r.get('smiles')}


def test_roles_on_known_scheme():
    out = read_reaction(path=str(FIXTURE))
    assert canon('c1nc(N2CCOCC2)c2ccsc2n1') in smiles(out['reactants'])
    assert canon('Cc1ccc(S(=O)(=O)OCc2ccc[nH]2)cc1') in smiles(out['reactants'])  # electrophile, not a reagent
    assert canon('c1c[nH]c(Cc2cc3c(N4CCOCC4)ncnc3s2)c1') in smiles(out['products'])
    reagent_names = {r['name'] for r in out['reagents']}
    assert {'n-BuLi', 'THF'} <= reagent_names
    assert out['conditions'] == ['-78 °C', '1 h']
    assert 'review' in out


def test_text_and_path_agree():
    by_path = read_reaction(path=str(FIXTURE))
    by_text = read_reaction(cdxml=FIXTURE.read_text('utf-8'))
    assert by_path['reaction_smiles'] == by_text['reaction_smiles']


@pytest.mark.parametrize('kwargs', [{}, {'cdxml': '<x/>', 'path': str(FIXTURE)}])
def test_exactly_one_input(kwargs):
    with pytest.raises(ValueError, match='exactly one'):
        read_reaction(**kwargs)


def test_rejects_non_cdxml_and_entity_tricks(tmp_path):
    with pytest.raises(ValueError, match='not CDXML'):
        read_reaction(cdxml='<html/>')
    evil = '<!DOCTYPE CDXML [<!ENTITY a "x">]><CDXML>&a;</CDXML>'
    with pytest.raises(Exception):
        read_reaction(cdxml=evil)
    with pytest.raises(ValueError, match='existing .cdxml'):
        read_reaction(path=str(tmp_path / 'missing.cdxml'))


def test_no_network_or_chemscript_modules_are_vendored():
    root = Path(__file__).resolve().parents[1] / 'chemdraw_macos' / '_cdxml_toolkit'
    assert not (root / 'resolve' / 'cas_resolver.py').exists()
    assert not list(root.rglob('chemscript*')) and not list(root.rglob('*chemscanner*')) \
        and not list(root.rglob('superatom_data.json'))
