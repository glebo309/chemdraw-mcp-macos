"""Hide production intermediates; present only the successful outermost result."""
from functools import wraps


def production_job(function=None, *, shared_molecules=False):
    if function is None:
        return lambda fn:production_job(fn,shared_molecules=shared_molecules)
    @wraps(function)
    def run(bridge, *args, presentation='auto', document_id=None, **kwargs):
        modes=('auto','background','interactive','shared') if shared_molecules else ('auto','background','interactive')
        if presentation not in modes:
            raise ValueError('presentation must be auto, background or interactive')
        if document_id is not None and (not shared_molecules or presentation not in ('auto','shared')):
            raise ValueError('An existing document requires shared presentation')
        # Portable test backends do not manage native window state.
        from .core import Bridge
        if not isinstance(bridge, Bridge):
            return function(bridge, *args, **kwargs)
        with bridge.lock:
            depth = getattr(bridge, '_production_depth', 0)
            if depth:
                return function(bridge, *args, **kwargs)
            mode = ('shared' if shared_molecules else bridge.automatic_presentation()) if presentation == 'auto' else presentation
            separate_table=shared_molecules and kwargs.get('groups') is not None and mode=='interactive' and document_id is None
            if shared_molecules and not separate_table and (mode in ('shared','interactive') or document_id is not None):
                import inspect
                from pathlib import Path
                from .shared import run_shared
                bound=inspect.signature(function).bind(bridge,*args,**kwargs)
                bound.apply_defaults();plan=dict(bound.arguments);plan.pop('bridge')
                out=Path(plan.pop('output_dir')).expanduser()
                if not out.is_absolute() or not out.parent.is_dir():raise ValueError('Output requires absolute path and existing parent')
                if out.exists() or out.is_symlink():raise FileExistsError('Output already exists')
                plan['workflow']='molecules'
                return run_shared(bridge,plan,out,document_id)
            bridge._production_depth = depth + 1
            try:
                result = function(bridge, *args, **kwargs)
                did = result.get('document', {}).get('document_id')
                if did is not None:
                    if did not in bridge.managed:
                        raise ValueError('Production result is not an owned document')
                    if mode == 'background':
                        bridge.close(did)
                        result['document_closed'] = True
                    else:
                        bridge.set_visibility(did, True)
                result['presentation'] = {'mode': mode, 'intermediates': 'hidden'}
                return result
            finally:
                bridge._production_depth = depth
    run.production_presentation = True
    return run
