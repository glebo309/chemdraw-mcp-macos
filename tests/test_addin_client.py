"""Execute the shipped add-in JavaScript against bounded API fixtures."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('scenario', ['empty', 'selection', 'version', 'post', 'compact'])
def test_addin_read_failures_and_status(scenario):
    node = shutil.which('node')
    if not node: pytest.skip('Node required for add-in protocol tests')
    source = Path('chemdraw_macos/addin_client.js').read_text()
    harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const scenario = process.argv[1];
let posted, reads = 0, size;
const status = {textContent: ''};
const doc = {getCDXML() { reads++; return '<CDXML/>'; },
    get selection() { if (scenario === 'selection') throw Error('PRIVATE selection error');
        return {getCDXML() { return '<CDXML/>'; }}; }};
const api = {get version() { if (scenario === 'version') throw Error('PRIVATE version error'); return '1.6'; },
    activeDocument: scenario === 'empty' ? null : doc,
    window: {setDefaultSize(w,h) { size = [w,h]; }, onClose() {}, close() {}}};
const ctx = vm.createContext({ChemDrawAPI: api, config: {url: 'local', secret: 'secret'},
    document: {getElementById() { return status; }}, setInterval() {}, clearInterval() {},
    async fetch(url, options) {
        if (url.endsWith('/job')) return {ok: true, async json() { return {id: 'job', operation: 'read'}; }};
        posted = JSON.parse(options.body);
        assert(!status.textContent.includes('Connected'));
        return {ok: scenario !== 'post', async json() { return {ok: true}; }};
    }});
vm.runInContext(SOURCE, ctx);
vm.runInContext('poll()', ctx).then(() => {
    assert(posted, 'Every claimed read must return a result');
    if (scenario === 'empty') assert.equal(posted.error_code, 'no_open_document');
    if (scenario === 'version') assert.equal(posted.error_stage, 'api_version');
    if (scenario === 'selection') {
        assert.equal(posted.cdxml, '<CDXML/>');
        assert.equal(posted.selection_available, false);
        assert(!posted.error);
    }
    if (scenario === 'post') assert(status.textContent.includes('disconnected'));
    if (scenario === 'compact') {
        assert.deepEqual(size, [240, 64]);
        assert.equal(reads, 1);
        assert.equal(status.textContent, 'Document sent to local MCP');
    }
}).catch(e => { console.error(e); process.exitCode = 1; });
'''.replace('SOURCE', __import__('json').dumps(source))
    result = subprocess.run([node, '-e', harness, scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
