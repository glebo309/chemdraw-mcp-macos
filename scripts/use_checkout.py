"""Switch existing local MCP and terminal launchers to this editable checkout."""
import json
from pathlib import Path
from chemdraw_macos.client_install import connect_checkout


if __name__=='__main__':
    print(json.dumps(connect_checkout(Path(__file__).resolve().parents[1]),indent=2))
