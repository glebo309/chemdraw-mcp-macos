from chemdraw_macos.draw import prepare_structures


def records(smiles):
    return prepare_structures([{'compound_id':str(i+1),'label':'Compound','smiles':s} for i,s in enumerate(smiles)])


def test_defaults_find_whole_supplied_parent_and_group_unrelated_scaffold_family():
    from chemdraw_macos.drawing_defaults import plan_drawing_defaults
    inputs=records(['CC(=O)c1ccccc1','CC(=O)c1ccc(C)cc1','CC(=O)c1ccc(OC)cc1',
                    'CC(=O)c1ccc(C#N)cc1','CC(=O)c1ccc(F)cc1'])
    result=plan_drawing_defaults(inputs)
    assert result['scaffold_smiles']=='CC(=O)c1ccccc1'
    assert [g['compound_ids'] for g in result['groups']]==[['1','2','3'],['4'],['5']]
    assert result['groups'][1]['label']=='Electron-withdrawing motifs'


def test_defaults_do_not_invent_a_core_for_unrelated_molecules():
    from chemdraw_macos.drawing_defaults import plan_drawing_defaults
    assert plan_drawing_defaults(records(['CCO','c1ccccc1','CC(=O)O','C1CCCCC1']))['scaffold_smiles'] is None


def test_single_structure_has_no_scope_decoration():
    from chemdraw_macos.drawing_defaults import plan_drawing_defaults
    result=plan_drawing_defaults(records(['c1ccccc1']))
    assert result['groups'] is None and result['scaffold_smiles'] is None


def test_multisite_substitution_not_mislabeled_as_one_electronic_group():
    from chemdraw_macos.drawing_defaults import plan_drawing_defaults
    result=plan_drawing_defaults(records(['CC(=O)c1ccccc1','CC(=O)c1ccc(C)cc1',
        'CC(=O)c1ccc(OC)cc1','CC(=O)c1cc(F)cc(F)c1']))
    assert result['groups'][-1]=={'label':'Other substitutions','compound_ids':['4']}


def test_defaults_do_not_need_parent_first():
    from chemdraw_macos.drawing_defaults import plan_drawing_defaults
    result=plan_drawing_defaults(records(['CC(=O)c1ccc(C)cc1','CC(=O)c1ccccc1',
        'CC(=O)c1ccc(OC)cc1','CC(=O)c1ccc(F)cc1']))
    assert result['scaffold_smiles']=='CC(=O)c1ccccc1'
    assert result['groups'][0]['compound_ids']==['2','1','3']
