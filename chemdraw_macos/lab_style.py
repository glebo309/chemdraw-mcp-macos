"""Portable numerical house styles. No embedded fonts, artwork, code or paths."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re

from .styles import validate_style

DEFAULTS = {
    'grid': {'h_gap':18.,'v_gap':24.,'label_gap':10.,'margin':36.},
    'reaction': {'gap':16.,'label_gap':10.,'condition_gap':10.,'row_gap':120.,'margin':36.},
}
LIMITS = {'h_gap':(2,100),'v_gap':(2,150),'label_gap':(2,60),'margin':(12,100),
          'gap':(2,100),'condition_gap':(2,60),'row_gap':(2,150),
          'span':(2,24),'line_width':(.2,3),'clearance':(1,12)}
CONVENTIONS = {
    'chemical_scale':'Shared bond length; never equal molecular bounding boxes.',
    'orientation':'Explicit shared-scaffold alignment; never infer stereochemistry from orientation.',
    'charges':'Native CirclePlus/Minus linked to existing formal charges, using the symbols workflow.',
    'electron_flow':'Explicit electron source and target; charge or lone-pair source where appropriate.',
    'review':'Native chemistry/layout checks plus human visual review. Not a chemical correctness certificate.',
}

def _settings(preset,sections):
    style=validate_style(preset)
    if set(sections)-{'grid','reaction','symbols'}:raise ValueError('Unknown lab style settings')
    defaults={**copy.deepcopy(DEFAULTS),'symbols':{'span':.75*float(style['LabelSize']),
              'line_width':float(style['LineWidth']),'clearance':2.}}
    result={'preset':style}
    for section,base in defaults.items():
        supplied=sections.get(section,{})
        if not isinstance(supplied,dict) or set(supplied)-set(base):raise ValueError('Unknown '+section+' settings')
        values={**base,**supplied}
        for key,value in values.items():
            if type(value) not in (int,float) or not math.isfinite(value) or not LIMITS[key][0]<=value<=LIMITS[key][1]:
                raise ValueError('Lab style setting outside limits: '+key)
        result[section]=values
    return result

def _digest(content):
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def make_package(name,version,preset,references=None,**sections):
    if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',name):raise ValueError('Use a safe lowercase package name')
    if not isinstance(version,str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',version):
        raise ValueError('Package version requires major.minor.patch')
    references=[] if references is None else copy.deepcopy(references)
    if not isinstance(references,list) or len(references)>30:raise ValueError('At most 30 plain reference records')
    names=set()
    for ref in references:
        if not isinstance(ref,dict) or set(ref)!={'name','sha256','description'}:raise ValueError('Reference requires name, sha256, description; no embedded files or paths')
        if not isinstance(ref['name'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,63}',ref['name']) or ref['name'] in names:raise ValueError('Invalid or duplicate reference name')
        names.add(ref['name'])
        if not isinstance(ref['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',ref['sha256']):raise ValueError('Invalid reference hash')
        text=ref['description']
        if not isinstance(text,str) or not 1<=len(text)<=300 or any(ord(c)<32 for c in text):raise ValueError('Invalid reference description')
    content={'schema_version':1,'package_name':name,'package_version':version,
             'settings':_settings(preset,sections),'conventions':copy.deepcopy(CONVENTIONS),'references':references}
    return {**content,'sha256':_digest(content)}

def validate_package(package):
    keys={'schema_version','package_name','package_version','settings','conventions','references','sha256'}
    if not isinstance(package,dict) or set(package)!=keys or type(package['schema_version']) is not int or package['schema_version']!=1:
        raise ValueError('Unsupported lab style schema or fields')
    content={k:v for k,v in package.items() if k!='sha256'}
    if package['sha256']!=_digest(content):raise ValueError('Lab style hash mismatch')
    settings=package['settings']
    if not isinstance(settings,dict) or set(settings)!={'preset','grid','reaction','symbols'}:raise ValueError('Invalid lab style sections')
    canonical=make_package(package['package_name'],package['package_version'],settings['preset'],
                           package['references'],**{k:v for k,v in settings.items() if k!='preset'})
    if canonical!=package:raise ValueError('Noncanonical or unsupported lab style conventions')
    return copy.deepcopy(package)

def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key: '+key)
        result[key]=value
    return result

def load_package(path):
    source=Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.stat().st_size>100_000:raise ValueError('Lab style must be a JSON file of at most 100 KB')
    return validate_package(json.loads(source.read_text(),object_pairs_hook=_unique))

def save_package(package,path):
    validated=validate_package(package);output=Path(path).expanduser()
    if not output.is_absolute() or not output.parent.is_dir():raise ValueError('Use a new absolute style file and existing parent')
    with output.open('x') as handle:json.dump(validated,handle,indent=2,ensure_ascii=False,allow_nan=False)
    return {'path':str(output),'sha256':validated['sha256'],'package_version':validated['package_version']}

def styled_options(package,workflow,recipe):
    """Locked defaults: conflicting recipe values fail instead of silently winning."""
    p=validate_package(package);settings=p['settings']
    if not isinstance(recipe,dict):raise ValueError('Recipe must be an object')
    options=copy.deepcopy(recipe)
    if workflow in ('draw','scope-job'):locked={'preset':settings['preset'],'layout':settings['grid']}
    elif workflow in ('reaction','reaction-series'):locked={'preset':settings['preset'],'layout':settings['reaction']}
    elif workflow=='grid':locked={'preset':settings['preset'],**settings['grid']}
    elif workflow=='symbols':locked=settings['symbols']
    else:raise ValueError('Unsupported styled workflow')
    for key,value in locked.items():
        if key in options:
            supplied=options[key]
            if isinstance(value,dict) and isinstance(supplied,dict):
                if any(k not in value or value[k]!=v for k,v in supplied.items()):raise ValueError('Recipe conflicts with locked lab style: '+key)
            elif supplied!=value:raise ValueError('Recipe conflicts with locked lab style: '+key)
        options[key]=copy.deepcopy(value)
    return options


def run_styled_job(bridge,package,workflow,recipe,output_dir):
    """Use one locked package through real native workflows, retaining its hash."""
    package=load_package(package) if isinstance(package,(str,Path)) else validate_package(package)
    options=styled_options(package,workflow,recipe)
    if type(options.get('schema_version',1)) is not int or options.pop('schema_version',1)!=1:
        raise ValueError('Unsupported styled recipe schema')
    fields={
        'draw':{'structures','preset','columns','pixels','scaffold_smiles','layout','charge_style'},
        'reaction':{'reactants','products','conditions_above','conditions_below','preset','pixels','scaffold_smiles','layout'},
        'reaction-series':{'steps','preset','pixels','layout'},
        'scope-job':{'parent_smiles','handle_atom_map','groups','accept_all','selected_candidate_ids','columns','preset','frame','separators','pixels','layout'},
        'grid':{'input','cells','expected_source_token','preset','columns','width','height','margin','h_gap','v_gap','label_gap','pixels'},
        'symbols':{'input','symbols','expected_source_token','span','line_width','clearance','pixels'},
    }
    if set(options)-fields[workflow]:raise ValueError('Unknown styled recipe fields')
    if workflow=='draw':
        from .draw import draw_structures
        result=draw_structures(bridge,output_dir=output_dir,**options)
    elif workflow=='reaction':
        from .reaction import build_reaction
        result=build_reaction(bridge,output_dir=output_dir,**options)
    elif workflow=='reaction-series':
        from .reaction_series import build_reaction_series
        result=build_reaction_series(bridge,output_dir=output_dir,**options)
    elif workflow=='scope-job':
        from .scope_job import build_scope_job
        result=build_scope_job(bridge,options,output_dir)
    else:
        if 'input' not in options:raise ValueError('Styled grid/symbols requires explicit CDXML input file')
        path=options.pop('input')
        if workflow=='grid':
            from .scope import grid_file
            result=grid_file(bridge,path,output_dir,**options)
        else:
            from .symbols import symbols_file
            result=symbols_file(bridge,path,output_dir,**options)
    save_package(package,Path(output_dir)/'lab-style.json')
    result['audit']['lab_style']={'package_name':package['package_name'],'package_version':package['package_version'],
        'sha256':package['sha256'],'workflow':workflow,'policy':'Conflicting explicit recipe settings rejected',
        'conventions':'Guidance; symbols require the explicit symbols workflow. Native and visual checks remain separate.'}
    from .workflow import _write_json
    _write_json(Path(output_dir)/'audit.json',result['audit'])
    return result
