"""Read and answer ChemDraw's own dialogs and alert sheets.

Scoped to the ChemDraw process through macOS Accessibility: it lists the
dialog's text, fields, radio buttons, checkboxes and buttons, and presses a
named button. No keystrokes, mouse movement or focus change, and no other
application is touched.
"""
from __future__ import annotations

import json
import plistlib
import subprocess
import time

_SCRIPT = r'''
function run(argv) {
  const request = JSON.parse(argv[0]);
  const se = Application('System Events');
  const proc = se.processes.byName(request.process);
  if (!proc.exists()) return JSON.stringify({dialogs: []});
  const found = [];
  for (const w of proc.windows()) {
    let wname = '';
    try { wname = w.name() || ''; } catch (e) {}
    let sheets = [];
    try { sheets = w.sheets(); } catch (e) {}
    for (const s of sheets) found.push({el: s, kind: 'sheet', window: wname});
    let sub = '';
    try { sub = w.subrole(); } catch (e) {}
    if (sub === 'AXDialog' || sub === 'AXSystemDialog') found.push({el: w, kind: 'dialog', window: wname});
  }
  function describe(item) {
    const d = {kind: item.kind, window: item.window, text: [], buttons: [], fields: [], radio_buttons: [], checkboxes: []};
    const refs = {buttons: {}, fields: [], radios: {}, checks: {}};
    function walk(el, depth) {
      let children = [];
      try { children = el.uiElements(); } catch (e) { return; }
      for (const c of children) {
        let role = '';
        try { role = c.role(); } catch (e) { continue; }
        let name = '';
        try { name = c.name() || ''; } catch (e) {}
        if (role === 'AXStaticText') {
          let v = ''; try { v = c.value(); } catch (e) {}
          if (v) d.text.push(String(v));
        } else if (role === 'AXButton') {
          if (name) { d.buttons.push(name); refs.buttons[name] = c; }
        } else if (role === 'AXTextField' || role === 'AXComboBox') {
          let v = ''; try { v = c.value(); } catch (e) {}
          d.fields.push({index: d.fields.length + 1, value: v === null ? '' : String(v)});
          refs.fields.push(c);
        } else if (role === 'AXRadioButton') {
          let v = 0; try { v = c.value(); } catch (e) {}
          d.radio_buttons.push({name: name, selected: Number(v) === 1}); refs.radios[name] = c;
        } else if (role === 'AXCheckBox') {
          let v = 0; try { v = c.value(); } catch (e) {}
          d.checkboxes.push({name: name, checked: Number(v) === 1}); refs.checks[name] = c;
        } else if (depth < 4) {
          walk(c, depth + 1);
        }
      }
    }
    walk(item.el, 0);
    return {d: d, refs: refs};
  }
  const described = found.map(describe);
  if (request.mode === 'read') {
    return JSON.stringify({dialogs: described.map((x, i) => Object.assign({index: i}, x.d))});
  }
  const target = described[request.dialog];
  if (!target || target.d.kind !== request.kind || target.d.window !== request.window)
    throw Error('The dialog changed before it could be answered; read it again');
  for (const [key, value] of Object.entries(request.fields || {})) {
    const field = target.refs.fields[Number(key) - 1];
    if (!field) throw Error('Dialog field ' + key + ' is absent');
    field.value = String(value);
  }
  if (request.choose) {
    const radio = target.refs.radios[request.choose];
    if (!radio) throw Error('Radio button is absent: ' + request.choose);
    radio.click();
  }
  for (const [name, wanted] of Object.entries(request.check || {})) {
    const box = target.refs.checks[name];
    if (!box) throw Error('Checkbox is absent: ' + name);
    if ((Number(box.value()) === 1) !== wanted) box.click();
  }
  const button = target.refs.buttons[request.button];
  if (!button) throw Error('Button is absent: ' + request.button);
  button.click();
  return JSON.stringify({pressed: request.button});
}
'''

_PERMISSION = ('Reading ChemDraw dialogs needs macOS Accessibility permission for the app that runs this '
               'MCP server (System Settings > Privacy & Security > Accessibility). Close the dialog in '
               'ChemDraw by hand until that is granted.')


def _process_name(bridge) -> str:
    try:
        with (bridge.app/'Contents/Info.plist').open('rb') as handle:
            info = plistlib.load(handle)
        return info.get('CFBundleName') or info.get('CFBundleExecutable') or 'ChemDraw'
    except OSError:
        return 'ChemDraw'


def _call(bridge, request: dict) -> dict:
    request = {**request, 'process': _process_name(bridge)}
    try:
        done = subprocess.run(['/usr/bin/osascript', '-l', 'JavaScript', '-e', _SCRIPT, json.dumps(request)],
                              capture_output=True, text=True, timeout=15, check=True)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Reading ChemDraw dialogs timed out; nothing was pressed again.') from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or '').strip()
        if '-25211' in message or 'assistive' in message.lower() or '-1719' in message:
            raise RuntimeError(_PERMISSION) from exc
        raise RuntimeError('ChemDraw dialog access failed: ' + message) from exc
    return json.loads(done.stdout)


def read_dialogs(bridge) -> list[dict]:
    """Every open ChemDraw sheet or dialog, in a stable order."""
    return _call(bridge, {'mode': 'read'})['dialogs']


def _act(bridge, request: dict) -> None:
    _call(bridge, {'mode': 'act', **request})


def respond_dialog(bridge, button: str | None = None, fields: dict | None = None,
                   choose: str | None = None, check: dict | None = None, dialog: int = 0) -> dict:
    """Without a button: list open dialogs. With a button: fill, then press it."""
    open_dialogs = read_dialogs(bridge)
    if button is None:
        if fields or choose or check:
            raise ValueError('Name the button to press after filling the dialog')
        return {'dialogs': open_dialogs}
    if not open_dialogs:
        raise ValueError('No ChemDraw dialog is open')
    if not isinstance(dialog, int) or not 0 <= dialog < len(open_dialogs):
        raise ValueError('dialog index is out of range')
    target = open_dialogs[dialog]
    if button not in target['buttons']:
        raise ValueError(f'No button {button!r}; this dialog has {target["buttons"]}')
    fields = {str(k): v for k, v in (fields or {}).items()}
    for key, value in fields.items():
        if not key.isdigit() or not 1 <= int(key) <= len(target['fields']):
            raise ValueError(f'No field {key}; this dialog has {len(target["fields"])} field(s)')
        if not isinstance(value, (str, int, float)) or len(str(value)) > 200:
            raise ValueError('Field values must be short text or numbers')
    radios = [r['name'] for r in target['radio_buttons']]
    if choose is not None and choose not in radios:
        raise ValueError(f'No radio button {choose!r}; this dialog has {radios}')
    boxes = [c['name'] for c in target['checkboxes']]
    check = dict(check or {})
    for name, wanted in check.items():
        if name not in boxes or type(wanted) is not bool:
            raise ValueError(f'Checkbox {name!r} must be one of {boxes} with true/false')
    _act(bridge, {'dialog': dialog, 'kind': target['kind'], 'window': target['window'], 'button': button,
                  'fields': fields, 'choose': choose, 'check': check})
    time.sleep(.1)
    remaining = bridge._run('dialog_count', _process_name(bridge))[0]
    return {'pressed': button, 'remaining_dialogs': read_dialogs(bridge) if remaining > 0 else []}
