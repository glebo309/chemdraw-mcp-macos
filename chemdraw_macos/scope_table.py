"""Complete native scope tables with one measurement and one final document."""
from contextlib import nullcontext
from pathlib import Path
import xml.etree.ElementTree as ET

from .api_drawing import plan_addition
from .batch import _native, _document_content, _verify, NativeUncertain
from .core import style_cdxml
from .reaction_batch import EMPTY, PAPERS, set_paper, _verify_paper
from .scope_job import arrange_scope_groups
from .scope import verify_scope
from .scope_decoration import plan_scope_decoration, verify_scope_decoration
from .workflow import _write_json
from .timing import StageTimer


def _layout(measured, records, groups, columns, layout, frame, separators, *, seed):
    from .workflow import remap_ids
    page=ET.fromstring(seed).find('page');mapping=remap_ids(seed,measured)
    cells=[{'compound_id':r['compound_id'],'fragment_ids':[mapping[f.get('id')]],
            'caption_id':None,'metadata_id':mapping[t.get('id')],'metadata_text':r['label'],'yield_percent':None}
           for r,f,t in zip(records,page.findall('fragment'),page.findall('t'))]
    if len(cells)!=len(records):raise ValueError('Native scope object count changed')
    errors=[]
    for paper in PAPERS:
        for cols in range(min(columns or 3,len(records)),0,-1):
            try:
                arranged,plan=arrange_scope_groups(set_paper(measured,paper),cells,groups,
                    cols,layout,frame,separators)
                decorated,decoration=plan_scope_decoration(arranged,plan['decoration_groups'],frame,separators)
                return arranged,decorated,plan,decoration,paper
            except ValueError as exc:errors.append(str(exc))
    raise ValueError('Complete scope table does not fit supported physical paper at this scale: '+errors[-1])


def draw_scope_table(bridge, structures, output_dir, *, groups, preset='house', columns=None,
                     pixels=3200, scaffold_smiles=None, layout=None, frame=True, separators=True,exports='full'):
    from .draw import prepare_structures
    from .grouped_draw import validate_draw_groups
    from .styles import require_style_fonts, verify_custom_style
    from .raster import rasterize_svg
    from .physical_export import physical_png, physical_svg
    timer=StageTimer();out=Path(output_dir).expanduser()
    if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
    if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
    if exports not in ('canvas','preview','full'):raise ValueError('Invalid exports mode')
    records=prepare_structures(structures)
    validate_draw_groups(groups,[r['compound_id'] for r in records])
    require_style_fonts(preset)
    if columns is not None and (type(columns) is not int or not 1<=columns<=len(records)):
        raise ValueError('Columns must be 1 through structure count')
    if type(pixels) is not int or not 256<=pixels<=8192:raise ValueError('Pixels must be 256 through 8192')
    # One whole-table seed. Its physical pages can expand for measurement only;
    # final paper is selected from measured native ink, without shrinking bonds.
    seed,planning=plan_addition(style_cdxml(set_paper(EMPTY,'A3 landscape'),preset),structures,
        preset=preset,columns=columns or 3,scaffold_smiles=scaffold_smiles,allow_page_expansion=True)
    timer.mark('input_and_seed')
    audit={'status':'in_progress','checks':{},'visual_review':'required'};owned=[]
    with getattr(bridge,'lock',nullcontext()):
        baseline=_native(bridge.documents)['documents']
        content={d['document_id']:_document_content(bridge,d['document_id']) for d in baseline}
        out.mkdir();_write_json(out/'request.json',{'structures':structures,'groups':groups,'preset':preset,
            'columns':columns,'scaffold_smiles':scaffold_smiles,'frame':frame,'separators':separators,'exports':exports})
        (out/'seed.cdxml').write_text(seed);_write_json(out/'audit.json',audit)
        try:
            created=_native(bridge.create,seed,visible=False);did=created['document']['document_id'];owned.append(did)
            audit['working_document_id']=did;_write_json(out/'audit.json',audit)
            snap=out/'measured.cdxml';_native(bridge.export,did,str(snap),'cdxml')
            measured=snap.read_text();_verify(seed,measured)
            arranged,decorated,plan,decoration,paper=_layout(measured,records,groups,columns,layout,frame,separators,seed=seed)
            _native(bridge.close,did);owned.remove(did)
            audit['working_document_id']=None
            _write_json(out/'audit.json',audit)
            timer.mark('native_measurement_and_layout')
            (out/'arranged.cdxml').write_text(arranged);(out/'decorated.cdxml').write_text(decorated)
            _write_json(out/'layout.json',plan)
            created=_native(bridge.create,decorated,visible=False);did=created['document']['document_id'];owned.append(did)
            audit['working_document_id']=did;_write_json(out/'audit.json',audit)
            figure=out/'figure';figure.mkdir();cdxml=figure/'figure.cdxml'
            _native(bridge.export,did,str(cdxml),'cdxml');native=cdxml.read_text()
            verification=verify_scope_decoration(arranged,native,decoration)
            root=ET.fromstring(native);page=root.find('page')
            extras=set(verification['id_map'][i] for i in decoration['label_ids'])
            for e in list(page):
                if e.tag=='graphic' or e.get('id') in extras:page.remove(e)
            plain=ET.tostring(root,encoding='unicode')
            verify_scope(arranged,plain,plan['layout']);verify_custom_style(arranged,plain,preset)
            _verify_paper(native,{'width_pt':PAPERS[paper][0],'height_pt':PAPERS[paper][1]})
            audit['checks'].update(verification['checks'],native_layout=True,native_style=True,physical_paper=True)
            timer.mark('native_final_verification')
            artifacts={'cdxml':str(cdxml)}
            if exports!='canvas':
                svg=figure/'figure.svg';_native(bridge.export,did,str(svg),'svg');raw=svg.read_text()
                (figure/'preview.png').write_bytes(rasterize_svg(raw,1200,background='white'))
                artifacts.update(svg=str(svg),preview=str(figure/'preview.png'))
                if exports=='full':
                    (figure/'figure.png').write_bytes(physical_png(raw,600));artifacts['png']=str(figure/'figure.png')
                svg.write_text(physical_svg(raw)[0])
                post=out/'post-export.cdxml';_native(bridge.export,did,str(post),'cdxml')
                verify_scope_decoration(arranged,post.read_text(),decoration)
                audit['checks']['native_svg_export']=True
            current=[d for d in _native(bridge.documents)['documents'] if d['document_id']!=did]
            if sorted(current,key=lambda d:d['document_id'])!=sorted(baseline,key=lambda d:d['document_id']):
                raise ValueError('Pre-existing document inventory changed')
            for oid,before in content.items():
                if _document_content(bridge,oid)!=before:raise ValueError('Pre-existing document content changed')
            timer.mark('exports_and_preservation')
            audit['checks'].update(preexisting_documents_unchanged=True)
            audit.update(status='checks_passed',timings=timer.report(),planning={**planning,
                'columns':plan['layout']['columns'],'paper':paper})
            result={'status':'completed','document':created['document'],'checks':audit['checks'],'audit':audit,
                'artifacts':artifacts,'delivery':{'mode':exports,'export_tool':'chemdraw_export_figure'},
                'timings':timer.report(),'visual_review':'required','output_dir':str(out),'group_plan':plan,
                'presentation':{'measurement_documents':1,'final_documents':1},
                'note':'Complete framed table. Do not call decorate_scope or import the result again.'}
            _write_json(out/'audit.json',audit);_write_json(out/'result.json',result)
            return result
        except NativeUncertain as exc:
            audit.update(status='uncertain',error=str(exc),owned_document_ids=owned,timings=timer.report())
            _write_json(out/'audit.json',audit);raise
        except Exception as exc:
            audit.update(status='failed',error=str(exc),timings=timer.report());_write_json(out/'audit.json',audit)
            for did in reversed(owned):
                try:_native(bridge.close,did)
                except NativeUncertain as closing:
                    audit.update(status='uncertain',error=str(closing),owned_document_ids=owned)
                    _write_json(out/'audit.json',audit);raise
            raise
