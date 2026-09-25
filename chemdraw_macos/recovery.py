"""Read-only recovery evidence shared by CLI and MCP workflow results."""
import json
from pathlib import Path


def retained_job_failure(output_dir, error):
    out=Path(output_dir).expanduser();audit={}
    try:audit=json.loads((out/'audit.json').read_text())
    except (OSError,ValueError):pass
    artifacts={}
    for fmt in ('cdxml','svg','png'):
        for candidate in (out/f'figure.{fmt}',out/'figure'/f'figure.{fmt}'):
            if candidate.is_file():artifacts[fmt]=str(candidate);break
    return {'status':'uncertain','code':'native_state_uncertain','message':str(error),
        'retry_safe':False,'output_dir':str(out),'audit':str(out/'audit.json'),
        'document':{'document_id':audit.get('working_document_id',audit.get('document_id'))},
        'checks':audit.get('checks',{}),'artifacts':artifacts,
        'next_action':'Do not draw, import, decorate, or launch another CLI connection again. '
            'Inspect the retained document and audit using read-only tools. '
            'Available artifacts are diagnostic until all required checks pass.'}
