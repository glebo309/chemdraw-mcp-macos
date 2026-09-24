/* Original local transport for the documented desktop ChemDraw API. */
let busy = false;
let disconnected = 0;
const seen = new Set();
async function exchange(path, data) {
    const headers = {Authorization: 'Bearer ' + config.secret};
    const options = {headers, cache: 'no-store'};
    if (data !== undefined) {
        options.method = 'POST'; headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
    }
    const response = await fetch(config.url + path, options);
    if (!response.ok) throw Error('Local bridge rejected request');
    return response.json();
}
async function poll() {
    if (busy) return;
    busy = true;
    try {
        const job = await exchange('/job'); disconnected = 0;
        if (!job.id) return;
        if (seen.has(job.id)) throw Error('Duplicate job refused');
        seen.add(job.id);
        const result = {id: job.id, write_attempted: false};
        let stage = 'api_version';
        try {
            if (job.operation !== 'close') {
                result.version = ChemDrawAPI.version;
                stage = 'active_document';
                const doc = ChemDrawAPI.activeDocument;
                if (!doc) {
                    result.error_code = 'no_open_document';
                    throw Error('Open a drawing in ChemDraw, then test again');
                }
                stage = 'document_cdxml';
                const before = doc.getCDXML();
                if (job.operation === 'append') {
                    stage = 'append';
                    if (before !== job.expected) throw Error('Document changed before append');
                    result.write_attempted = true;
                    doc.addCDXML(job.cdxml);
                } else if (job.operation !== 'read') throw Error('Unknown operation');
                stage = 'document_cdxml';
                result.cdxml = job.operation === 'read' ? before : doc.getCDXML();
                // A document read does not depend on selection support.
                try {
                    result.selection = doc.selection.getCDXML();
                    result.selection_available = typeof result.selection === 'string';
                } catch (_) { result.selection_available = false; }
            }
        } catch (e) {
            result.error = String(e);
            result.error_stage = stage;
            result.error_code = result.error_code || 'native_api_error';
        }
        await exchange('/result', result);
        document.getElementById('status').textContent = result.error ?
            (result.error_code === 'no_open_document' ? 'Open a drawing, then test again' : 'Read failed: see setup diagnostics') :
            'Document sent to local MCP';
        if (job.operation === 'close') ChemDrawAPI.window.close();
    } catch (e) {
        document.getElementById('status').textContent = 'Local MCP disconnected: ' + String(e);
        if (++disconnected >= 120) ChemDrawAPI.window.close();
    } finally { busy = false; }
}
const timer = setInterval(poll, 250);
// Optional window APIs must never interrupt the transport on another API version.
try { ChemDrawAPI.window.setDefaultSize(240, 64); } catch (_) {}
try { ChemDrawAPI.window.onClose(() => clearInterval(timer)); } catch (_) {}
