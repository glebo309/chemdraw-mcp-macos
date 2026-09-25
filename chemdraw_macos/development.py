"""Explicit checkout launcher; never redirects to a frozen installed build."""
import os
import sys


def main(argv=None):
    from . import diagnostics  # Capture the checkout fingerprint at process startup.
    from .desktop_setup import read_settings,validate_app
    args=list(sys.argv[1:] if argv is None else argv)
    settings=read_settings()
    if settings.get('chemdraw_app'):
        os.environ['CHEMDRAW_APP']=str(validate_app(settings['chemdraw_app']))
    os.environ.pop('CHEMDRAW_DESKTOP_EXTENSION',None)
    if args[:1]==['--cli']:
        from .cli import main as cli
        return cli(args[1:])
    if args==['--desktop-serve']:args=['--profile','full']
    elif args[:1]==['--server']:args=args[1:]
    from .server import main as server
    return server(args)


if __name__=='__main__':main()
