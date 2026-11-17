"""The persistent native script helper, exercised with plain scripts (no ChemDraw)."""
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS osascript')

SCRIPT = '''on run argv
    set op to item 1 of argv
    if op is "echo" then return "{\\"echo\\": \\"" & (item 2 of argv) & "\\"}"
    if op is "length" then return (count of characters of (item 2 of argv)) as text
    if op is "fail" then error "Document ID is stale or absent; list documents again" number 2700
    if op is "sleep" then
        delay (item 2 of argv) as real
        return "true"
    end if
    return "null"
end run'''


@pytest.fixture
def helper():
    from chemdraw_macos.native_helper import NativeHelper
    h = NativeHelper(SCRIPT)
    yield h
    h.close()


def test_calls_return_parsed_json_and_reuse_one_process(helper):
    assert helper.call(['echo', 'a b'], timeout=10) == {'echo': 'a b'}
    pid = helper.pid
    start = time.perf_counter()
    for _ in range(10):
        assert helper.call(['echo', 'x'], timeout=10) == {'echo': 'x'}
    assert helper.pid == pid
    assert (time.perf_counter() - start) / 10 < .05


def test_script_errors_keep_their_message_and_the_helper(helper):
    with pytest.raises(RuntimeError, match=r'automation failed: Document ID is stale.*\(2700\)'):
        helper.call(['fail'], timeout=10)
    assert helper.call(['echo', 'still here'], timeout=10) == {'echo': 'still here'}


def test_timeout_is_uncertain_not_retried_and_the_next_call_starts_fresh(helper):
    with pytest.raises(RuntimeError, match='not retried'):
        helper.call(['sleep', '3'], timeout=.5)
    assert helper.call(['echo', 'next'], timeout=10) == {'echo': 'next'}


def test_arguments_are_data_not_script(helper):
    text = '" & (do shell script "false") & "'
    assert helper.call(['length', text], timeout=10) == len(text)


def test_bridge_uses_the_helper_and_old_path_remains_selectable(tmp_path, monkeypatch):
    from chemdraw_macos import core, native_helper
    app = tmp_path / 'ChemDraw.app'
    app.mkdir()
    calls = []
    class Fake:
        def call(self, args, timeout):
            calls.append((args, timeout)); return [1]
    monkeypatch.setattr(native_helper, 'helper_for', lambda script: Fake())
    b = core.Bridge(app_path=app, workspace=tmp_path)
    assert b._run('list', 3) == [1] and calls == [(['list', 3], b.timeout)]
    monkeypatch.setenv('CHEMDRAW_MCP_NATIVE_HELPER', '0')
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: type('P', (), {'stdout': '[2]'})())
    assert b._run('list') == [2]
