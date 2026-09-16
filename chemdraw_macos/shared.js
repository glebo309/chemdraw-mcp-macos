// Native CDX only. Bounded, focus-guarded arrow keys move the pasted selection.
ObjC.import('AppKit');
ObjC.import('Foundation');
function positionSelection(placement,read,nudge,wait) {
    let box=read(),noops=0,confirmed=0,steps=1;
    for(let n=0;n<240;n++) {
        const dx=Math.round(placement.left-box[0]),dy=Math.round(placement.top-box[1]);
        if(!dx&&!dy)return {undo_steps:steps,confirmed_noops:confirmed};
        if(Math.abs(dx)>2000||Math.abs(dy)>2000)throw Error('Movement exceeds bounded placement');
        const axis=dx?0:1,delta=dx||dy,coarse=Math.abs(delta)>=10;
        nudge(axis,delta,coarse,noops);
        // Reconcile queued UI events with fresh reads before another key pulse.
        let next=read();
        for(let poll=0;poll<4 && next[0]===box[0] && next[1]===box[1];poll++) {
            wait();next=read();
        }
        if(next[0]===box[0]&&next[1]===box[1]) {
            noops++;confirmed++;
            if(noops>=3)throw Error('Keyboard movement did not execute after bounded reconciliation; no paste retry');
            continue;
        }
        const moved=next[axis]-box[axis],unit=coarse?10:1;
        if(next[1-axis]!==box[1-axis] || Math.abs((next[2]-next[0])-(box[2]-box[0]))>.03 ||
           Math.abs((next[3]-next[1])-(box[3]-box[1]))>.03 || Math.sign(moved)!==Math.sign(delta))
            throw Error('Selection geometry changed unexpectedly; stop without retry: '+JSON.stringify({before:box,after:next,axis:axis,delta:delta}));
        if(Math.abs(Math.abs(moved)/unit-Math.round(Math.abs(moved)/unit))>.01)
            throw Error('Unexpected native movement increment');
        steps+=Math.round(Math.abs(moved)/unit);box=next;noops=0;
    }
    throw Error('Movement exceeds bounded placement');
}
function run() {
    const data=$.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
    const o=JSON.parse(ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data,$.NSUTF8StringEncoding)));
    const appLiteral=JSON.stringify(o.app), did=Number(o.document_id);
    const pb=$.NSPasteboard.generalPasteboard, saved=[], start=Number(pb.changeCount);
    const original=pb.pasteboardItems;
    for(let i=0;i<Number(original.count);i++) {
        const item=original.objectAtIndex(i), formats=[];
        for(let j=0;j<Number(item.types.count);j++) {
            const type=item.types.objectAtIndex(j), bytes=item.dataForType(type);
            if(!bytes)throw Error('Unreadable clipboard; not changed');
            formats.push([type,bytes.copy]);
        }
        saved.push(formats);
    }
    if(Number(pb.changeCount)!==start)throw Error('Clipboard changed during backup');
    let owned=null, result={document_id:did,clipboard_restored:false,undo_steps:0};
    function apple(body,guard=true) {
        const source='try\ntell application '+appLiteral+'\n'+
            (guard?'if not frontmost then error "ChemDraw lost focus"\n'+
             'if ((id of document 1) as integer) is not '+did+' then error "Wrong front document"\n':'')+
            body+'\nend tell\nreturn "OK"\non error msg number num\nreturn "ERROR: " & num & ": " & msg\nend try';
        const engine=$.NSAppleScript.alloc.initWithSource(source);
        const value=engine.executeAndReturnError(null);
        const message=ObjC.unwrap(value.stringValue);
        if(message!=='OK')throw Error((message || 'Native script failed')+' [native step: '+body.split('\n')[0]+']');
    }
    function checkClipboard() {
        if(owned!==null && Number(pb.changeCount)!==owned)throw Error('Clipboard changed externally; no further write');
    }
    function snapshot(selectAll=true) {
        checkClipboard();
        if(selectAll)apple('if enabled of command "selectAll" then do command "selectAll"');
        apple('do menu item "CDXML Text" of submenu of menu item "Copy As" of menu "Edit"');
        owned=Number(pb.changeCount);
        const text=ObjC.unwrap(pb.stringForType($('public.utf8-plain-text')));
        if(!text || !text.includes('<CDXML'))throw Error('Native clipboard snapshot is missing');
        return text;
    }
    try {
        Application(o.app).activate();
        apple('repeat with d in documents\nif ((id of d) as integer) is '+did+' then\nset visible of window of d to true\nset index of window of d to 1\nend if\nend repeat',false);
        $.NSThread.sleepForTimeInterval(.25);
        if(o.cdx) {
            const before=snapshot();
            if(before!==o.expected)throw Error('Document changed before paste; no paste dispatched');
            checkClipboard();
            const item=$.NSPasteboardItem.alloc.init, bytes=$.NSData.dataWithContentsOfFile(o.cdx);
            if(!item.setDataForType(bytes,$('com.revvity.chemdraw.cdx-clipboard')))throw Error('Invalid native CDX clipboard');
            const items=$.NSMutableArray.alloc.init;items.addObject(item);
            pb.clearContents;owned=Number(pb.changeCount);
            if(!pb.writeObjects(items))throw Error('Cannot write native CDX clipboard');
            owned=Number(pb.changeCount);
            apple('do command "paste"');result.undo_steps=1;
            function selectedBounds() {
                const match=snapshot(false).match(/<CDXML\b[^>]*\bBoundingBox="([^"]+)"/);
                if(!match)throw Error('Pasted selection lacks measured bounds');
                const box=match[1].trim().split(/\s+/).map(Number);
                if(box.length!==4 || !box.every(Number.isFinite))throw Error('Invalid selection bounds');
                return box;
            }
            const movement=positionSelection(o.placement,selectedBounds,(axis,delta,coarse,noops)=>{
                const code=axis===0?(delta<0?28:29):(delta<0?30:31);
                apple('tell application "System Events"\n'+
                    'try\n'+
                    (coarse?'key down shift\n':'')+
                    'key down (ASCII character '+code+')\ndelay '+(.05+.025*noops)+'\n'+
                    'key up (ASCII character '+code+')\n'+
                    (coarse?'key up shift\n':'')+
                    'on error msg number num\nkey up (ASCII character '+code+')\n'+
                    (coarse?'key up shift\n':'')+'error msg number num\nend try\nend tell');
            },()=>$.NSThread.sleepForTimeInterval(.1));
            result.undo_steps=movement.undo_steps;
            result.confirmed_noops=movement.confirmed_noops;
        } else if(o.undo_steps) {
            for(let i=0;i<o.undo_steps;i++)apple('do command "undo"');
        }
        result.cdxml=snapshot();
    } catch(e) {result.error=String(e);}
    finally {
        if(owned!==null && Number(pb.changeCount)===owned) {
            const items=$.NSMutableArray.alloc.init;
            for(const formats of saved) {
                const item=$.NSPasteboardItem.alloc.init;
                for(const [type,bytes] of formats)if(!item.setDataForType(bytes,type))throw Error('Clipboard restore failed');
                items.addObject(item);
            }
            pb.clearContents;
            if(Number(items.count) && !pb.writeObjects(items))throw Error('Clipboard restore failed');
            const check=pb.pasteboardItems;
            if(Number(check.count)!==saved.length)throw Error('Clipboard restore count differs');
            for(let i=0;i<saved.length;i++) {
                if(Number(check.objectAtIndex(i).types.count)!==saved[i].length)throw Error('Clipboard restore types differ');
                for(const [type,bytes] of saved[i])if(!check.objectAtIndex(i).dataForType(type).isEqualToData(bytes))throw Error('Clipboard restore bytes differ');
            }
            result.clipboard_restored=true;
        } else if(owned!==null)result.clipboard_external_change_preserved=true;
    }
    return JSON.stringify(result);
}
