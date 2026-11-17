/* Persistent host for the bundled native script (macOS JXA).
 *
 * Reads one JSON request per line on stdin: first {"script": text}, then
 * {"args": [strings]}. Runs the compiled script's run handler with those
 * arguments and writes one JSON reply per line. Arguments are passed as an
 * AppleEvent list, never spliced into source. The wrapped script catches its
 * own errors and returns "R<result>" or "E<number>:<message>"; the error
 * out-parameter of executeAppleEvent is not used because it crashes JXA.
 */
ObjC.import('Foundation');

function reply(value) {
    const text = $.NSString.alloc.initWithUTF8String(JSON.stringify(value) + '\n');
    $.NSFileHandle.fileHandleWithStandardOutput.writeData(text.dataUsingEncoding($.NSUTF8StringEncoding));
}

function run() {
    const input = $.NSFileHandle.fileHandleWithStandardInput;
    let script = null;
    let pending = '';
    function handle(request) {
        if (request.script !== undefined) {
            script = $.NSAppleScript.alloc.initWithSource(request.script);
            if (!script.compileAndReturnError(null)) {
                script = null;
                return reply({ok: false, error: 'The native script did not compile'});
            }
            return reply({ok: true});
        }
        if (!script) return reply({ok: false, error: 'No native script loaded'});
        const list = $.NSAppleEventDescriptor.listDescriptor;
        request.args.forEach((arg, index) =>
            list.insertDescriptorAtIndex($.NSAppleEventDescriptor.descriptorWithString(String(arg)), index + 1));
        // kCoreEventClass 'aevt', kAEOpenApplication 'oapp': the run handler, as osascript sends it.
        const event = $.NSAppleEventDescriptor.appleEventWithEventClassEventIDTargetDescriptorReturnIDTransactionID(
            0x61657674, 0x6f617070, $.NSAppleEventDescriptor.currentProcessDescriptor, -1, 0);
        event.setParamDescriptorForKeyword(list, 0x2d2d2d2d);
        const result = script.executeAppleEventError(event, null);
        if (!result || result.isNil()) return reply({ok: false, error: 'The native script returned no result'});
        return reply({ok: true, result: ObjC.unwrap(result.stringValue)});
    }
    while (true) {
        const data = input.availableData;
        if (Number(data.length) === 0) return '';
        pending += ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding));
        let end;
        while ((end = pending.indexOf('\n')) >= 0) {
            const line = pending.slice(0, end);
            pending = pending.slice(end + 1);
            try { handle(JSON.parse(line)); }
            catch (e) { reply({ok: false, error: 'Native helper failure: ' + String(e)}); }
        }
    }
}
