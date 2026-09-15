"""v0.9 serial, private-copy acceptance tests against licensed ChemDraw."""
import json
import os
from pathlib import Path
import pytest
from chemdraw_macos.core import Bridge

pytestmark=pytest.mark.skipif(os.environ.get('CHEMDRAW_LIVE_TEST')!='1',reason='Requires licensed running ChemDraw')
ROOT=Path(__file__).resolve().parents[1]

def test_native_complete_scope_job(tmp_path):
    from chemdraw_macos.scope_job import build_scope_job
    b=Bridge();baseline=b.documents();final=None
    job={'schema_version':1,'parent_smiles':'CC(=O)[c:1]1ccccc1','handle_atom_map':1,
         'groups':[{'label':'Reference / donors','categories':['reference','electron_donating']},
                   {'label':'Withdrawers','categories':['electron_withdrawing','halogen']},
                   {'label':'Bulky / positional','categories':['steric','positional']}],
         'accept_all':True,'columns':4,'layout':{'margin':24,'h_gap':12,'v_gap':16,'label_gap':8}}
    try:
        result=build_scope_job(b,job,str(tmp_path/'scope'))
        final=result['document']['document_id']
        assert result['audit']['status']=='checks_passed'
        assert result['plan']['selected_count']==14
        assert len(result['plan']['groups'])==3
        assert (tmp_path/'scope/figure/figure.png').stat().st_size>1000
        print('V09_SCOPE_REVIEW='+result['review'])
    finally:
        if final is not None:b.close(final)
    assert b.documents()==baseline

@pytest.mark.asyncio
async def test_native_styled_job_over_mcp(tmp_path):
    import sys
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    params=StdioServerParameters(command=sys.executable,args=['-m','chemdraw_macos.server'],
        env=dict(os.environ,CHEMDRAW_MCP_WORKSPACE=str(tmp_path/'workspace')))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            async def call(tool_name,**args):
                response=await session.call_tool(tool_name,args)
                assert not response.isError,response
                return response.structuredContent or json.loads(response.content[0].text)
            baseline=await call('chemdraw_list_documents');created=[]
            try:
                preset={'BondLength':18,'LineWidth':1.58,'BoldWidth':2,'LabelSize':14,'CaptionSize':10,'font':'Arial'}
                await call('chemdraw_create_lab_style',name='native-test',version='1.0.0',preset=preset,
                           output_path=str(tmp_path/'style.json'),settings={'grid':{'label_gap':8,'h_gap':24}})
                package=await call('chemdraw_inspect_lab_style',path=str(tmp_path/'style.json'))
                result=await call('chemdraw_run_styled_job',package_path=str(tmp_path/'style.json'),workflow='draw',
                    recipe={'structures':[{'compound_id':'1','label':'Ethanol','smiles':'CCO'},
                                          {'compound_id':'2','label':'Ethanal','smiles':'CC=O'}],'columns':2},
                    output_dir=str(tmp_path/'styled'))
                final=result['document']['document_id']
                created.append(final)
                assert result['audit']['lab_style']['sha256']==package['sha256']
                assert result['audit']['status']=='checks_passed'
                assert json.loads((tmp_path/'styled/request.json').read_text())['layout']['label_gap']==8
                assert (tmp_path/'styled/lab-style.json').read_bytes()==(tmp_path/'style.json').read_bytes()
                print('V09_STYLED_REVIEW='+result['review'])
                cells=result['audit']['grid_audit']['verification']['cells']
                owners=[{'key':'compound'+cell['compound_id'],'fragment_ids':cell['fragment_ids'],
                         'caption_ids':[cell['caption_id'],cell['metadata_id']]} for cell in cells]
                state=await call('chemdraw_build_ownership',document_id=final,owners=owners)
                moved=await call('chemdraw_move_owned',document_id=final,output_dir=str(tmp_path/'moved-sheet'),
                    ownership=state,moves=[{'owner_key':owners[0]['key'],'delta':[10,20]}],expected_source_token=state['source_token'])
                created.append(moved['document']['document_id'])
                assert moved['audit']['status']=='checks_passed'
                print('V09_SHEET_MOVE_REVIEW='+moved['review'])
            finally:
                for did in reversed(created):await call('chemdraw_close_working_document',document_id=did)
            assert await call('chemdraw_list_documents')==baseline

@pytest.mark.parametrize('source,target',[
    ({'kind':'symbol','id':'1500'},{'kind':'atom','id':'2103'}),
    ({'kind':'bond','id':'2105'},{'kind':'atom','id':'2104'}),
])
def test_native_selected_route(tmp_path,source,target):
    from chemdraw_macos.route_suggestions import suggest_routes,annotate_selected_route_file
    path=ROOT/'examples/sn2-annotation-input.cdxml'
    suggestions=suggest_routes(path.read_text(),source,target)
    assert suggestions['candidates']
    b=Bridge();baseline=b.documents();final=None
    try:
        result=annotate_selected_route_file(b,path,str(tmp_path/'route'),suggestions,suggestions['candidates'][0]['candidate_id'])
        final=result['document']['document_id']
        assert result['audit']['status']=='checks_passed'
        assert result['audit']['route_selection']['native_curve_id']
        assert (tmp_path/'route/route-suggestions.json').exists()
        print('V09_ROUTE_REVIEW='+result['review'])
    finally:
        if final is not None:b.close(final)
    assert b.documents()==baseline

def test_native_owned_movement_with_charge_caption_and_internal_arrow(tmp_path):
    from chemdraw_macos.annotations import plan_annotations
    from chemdraw_macos.ownership import build_ownership,move_file
    from chemdraw_macos.editing import source_token
    source=(ROOT/'examples/sn2-annotation-input.cdxml').read_text()
    arrow={'key':'leaving','electrons':2,'source':{'kind':'bond','id':'2105','offset':[0,0]},
           'target':{'kind':'atom','id':'2104','offset':[4,13]},'controls':[[-5,26],[8,14]]}
    text,plan=plan_annotations(source,[arrow]);path=tmp_path/'input.cdxml';path.write_text(text)
    owners=[{'key':name,'fragment_ids':[fid],'caption_ids':[tid]} for name,fid,tid in
            [('bromide','1001','970'),('substrate','2002','971'),('product','3003','972'),('iodide','4004','973')]]
    state=build_ownership(text,owners,[{'curve_id':plan['arrows'][0]['curve_id'],
          'source':{'kind':'bond','id':'2105'},'target':{'kind':'atom','id':'2104'}}])
    b=Bridge();baseline=b.documents();final=None
    try:
        result=move_file(b,path,str(tmp_path/'move'),state,[{'owner_key':'bromide','delta':[10,0]},
                                                            {'owner_key':'substrate','delta':[10,0]}])
        final=result['document']['document_id']
        assert result['audit']['status']=='checks_passed'
        assert result['ownership']['source_token']==source_token((tmp_path/'move/figure.cdxml').read_text())
        assert path.read_text()==text
        print('V09_MOVE_REVIEW='+result['review'])
    finally:
        if final is not None:b.close(final)
    assert b.documents()==baseline

def test_native_expanded_reaction_with_salt_water_halides_and_coefficients(tmp_path):
    from chemdraw_macos.reaction_series import build_reaction_series
    def p(key,label,smiles,coefficient=1):return dict(compound_id=key,label=label,smiles=smiles,coefficient=coefficient)
    steps=[{'step_id':'substitution','reactants':[p('bromide','Bromide','[Br-]'),p('iodomethane','Methyl iodide','CI')],
            'products':[p('bromomethane','Methyl bromide','CBr'),p('iodide','Iodide','[I-]')],
            'conditions_above':'SN2'},
           {'step_id':'neutralization','reactants':[p('acid','Acetic acid','CC(=O)O',2),p('base','NaOH','[Na+].[OH-]',2)],
            'products':[p('salt','NaOAc','CC(=O)[O-].[Na+]',2),p('water','Water','O',2)],
            'conditions_above':'Acid + base'}]
    b=Bridge();baseline=b.documents();final=None
    try:
        result=build_reaction_series(b,steps,str(tmp_path/'reactions'),layout={'gap':8,'margin':18})
        final=result['document']['document_id']
        assert result['audit']['status']=='checks_passed'
        assert len(result['audit']['verification']['steps'])==2
        assert not result['audit']['chemical_balance_certified']
        print('V09_REACTION_REVIEW='+result['review'])
    finally:
        if final is not None:b.close(final)
    assert b.documents()==baseline
