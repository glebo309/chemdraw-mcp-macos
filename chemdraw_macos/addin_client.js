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
        const result = {id: job.id, version: ChemDrawAPI.version, write_attempted: false};
        try {
            if (job.operation !== 'close') {
                const doc = ChemDrawAPI.activeDocument;
                const before = doc.getCDXML();
                if (job.operation === 'append') {
                    if (before !== job.expected) throw Error('Document changed before append');
                    result.write_attempted = true;
                    doc.addCDXML(job.cdxml);
                } else if (job.operation !== 'read') throw Error('Unknown operation');
                result.cdxml = doc.getCDXML();
                result.selection = doc.selection.getCDXML();
            }
        } catch (e) { result.error = String(e); }
        document.getElementById('status').textContent = result.error || 'Connected to local MCP.';
        await exchange('/result', result);
        if (job.operation === 'close') ChemDrawAPI.window.close();
    } catch (e) {
        document.getElementById('status').textContent = 'Local MCP disconnected: ' + String(e);
        if (++disconnected >= 120) ChemDrawAPI.window.close();
    } finally { busy = false; }
}
const timer = setInterval(poll, 250);
ChemDrawAPI.window.onClose(() => clearInterval(timer));
