use framework "Foundation"
use scripting additions

on jsonText(value)
    set dataValue to current application's NSJSONSerialization's dataWithJSONObject:value options:0 |error|:(missing value)
    return (current application's NSString's alloc()'s initWithData:dataValue encoding:4) as text
end jsonText

on jsonInteger(value)
    -- AppleScript text coercion uses scientific notation for large integers.
    -- Serialize through Foundation, then unwrap the single JSON array item.
    set encoded to my jsonText({value as integer})
    return text 2 thru -2 of encoded
end jsonInteger

on fileReference(p)
    return POSIX file p
end fileReference

on pathOfFile(f)
    return POSIX path of f
end pathOfFile

on documentRow(d)
    tell application __APP__
        set diskPath to ""
        try
            set diskPath to my pathOfFile(file of d)
        end try
        return {(id of d) as integer, name of d, diskPath, modified of d, count of molecules of d}
    end tell
end documentRow

on run argv
    set operation to item 1 of argv
    tell application __APP__
        if operation is "active_document" then
            if (count of documents) is 0 then return "null"
            return my jsonInteger((id of document 1) as integer)
        end if
        if operation is "active_document_state" then
            if (count of documents) is 0 then return "null"
            set stateRow to my documentRow(document 1)
            if (count of documents) is 0 then error "Active document changed during read"
            if ((id of document 1) as integer) is not (item 1 of stateRow) then error "Active document changed during read"
            return my jsonText(stateRow)
        end if
        if operation is "addin_available" then
            set addinPath to item 2 of argv
            if (name of every command) contains addinPath then return "true"
            return "false"
        end if
        if operation is "addin_open" then
            set addinPath to item 2 of argv
            activate
            do command addinPath
            return "true"
        end if
        if operation is "visible_documents" then
            set visibleIDs to {}
            repeat with d in documents
                if visible of window of d then set end of visibleIDs to ((id of d) as integer)
            end repeat
            return my jsonText(visibleIDs)
        end if
        if operation is "list" then
            set rows to {}
            repeat with d in documents
                set end of rows to my documentRow(d)
            end repeat
            return my jsonText(rows)
        end if
        if operation is "open" then
            set targetPath to item 2 of argv
            open (my fileReference(targetPath))
            set matches to {}
            repeat with candidate in documents
                try
                    if (my pathOfFile(file of candidate)) is targetPath then set end of matches to contents of candidate
                end try
            end repeat
            if (count of matches) is not 1 then error "Could not identify the imported document uniquely"
            if (count of argv) > 2 then
                if item 3 of argv is "false" then set visible of window of (item 1 of matches) to false
            end if
            return my jsonText(my documentRow(item 1 of matches))
        end if
        set wantedID to (item 2 of argv) as integer
        set targetDoc to missing value
        repeat with candidate in documents
            if ((id of candidate) as integer) is wantedID then set targetDoc to contents of candidate
        end repeat
        if targetDoc is missing value then error "Document ID is stale or absent; list documents again"
        if operation is "select_document" then
            set expectedID to (item 3 of argv) as integer
            if ((id of document 1) as integer) is not expectedID then error "Active document changed before preservation read"
            set index of window of targetDoc to 1
            if ((id of document 1) as integer) is not wantedID then error "Could not select preservation-read document"
            return "true"
        else if operation is "clear_owned_scope" then
            if ((id of document 1) as integer) is not wantedID then error "Active scope changed; no clear dispatched"
            if (my pathOfFile(file of targetDoc)) is not (item 3 of argv) then error "Working scope file changed"
            if modified of targetDoc then error "Working scope was edited; no clear dispatched"
            do command "selectAll"
            if ((id of document 1) as integer) is not wantedID then error "Active scope changed before clear"
            if modified of targetDoc then error "Working scope was edited before clear"
            do command "clear"
            if ((id of document 1) as integer) is not wantedID then error "Active scope changed during clear"
            if (count of objects of targetDoc) is not 0 then error "Working scope clear incomplete"
            return my jsonText(my documentRow(targetDoc))
        else if operation is "empty_document_style" then
            if ((id of document 1) as integer) is not wantedID then error "Active document changed before setting defaults"
            if (count of objects of targetDoc) is not 0 then error "Document is no longer empty; defaults unchanged"
            set fixed length of targetDoc to (item 3 of argv) as integer
            set line width of targetDoc to (item 4 of argv) as integer
            set bold width of targetDoc to (item 5 of argv) as integer
            set label size of targetDoc to (item 6 of argv) as integer
            set caption size of targetDoc to (item 7 of argv) as integer
            set label font of targetDoc to item 8 of argv
            set caption font of targetDoc to item 8 of argv
            set bond spacing of targetDoc to (item 9 of argv) as integer
            set chain angle of targetDoc to (item 10 of argv) as integer
            set margin width of targetDoc to (item 11 of argv) as integer
            set hash spacing of targetDoc to (item 12 of argv) as integer
            return "true"
        else if operation is "visibility" then
            set desiredVisible to (item 3 of argv is "true")
            set visible of window of targetDoc to desiredVisible
            return my jsonText({my documentRow(targetDoc), visible of window of targetDoc})
        else if operation is "live_state" then
            set countsRow to {count of atoms of selection of targetDoc, count of bonds of selection of targetDoc, count of molecules of selection of targetDoc, count of captions of selection of targetDoc}
            return my jsonText({my documentRow(targetDoc), visible of window of targetDoc, bounds of selection of targetDoc, countsRow})
        else if operation is "inspect" then
            set moleculeRows to {}
            repeat with i from 1 to (count of molecules of targetDoc)
                set end of moleculeRows to {i as integer, bounds of molecule i of targetDoc}
            end repeat
            set settingsRow to {fixed length of targetDoc, line width of targetDoc, label size of targetDoc, label font of targetDoc, caption size of targetDoc, caption font of targetDoc}
            return my jsonText({my documentRow(targetDoc), moleculeRows, settingsRow})
        else if operation is "export" then
            set diskPath to ""
            try
                set diskPath to my pathOfFile(file of targetDoc)
            end try
            set targetPath to item 3 of argv
            set targetFormat to item 4 of argv
            if diskPath is "" and targetFormat is not "Scalable Vector Graphics (SVG)" then error "Untitled document cannot be exported safely in this format: native save would assign a filename. No save dispatched."
            save targetDoc in (my fileReference(targetPath)) as targetFormat
            return my jsonText(my documentRow(targetDoc))
        else if operation is "native_action" then
            if (id of document 1) is not wantedID then error "Native action requires the owned front document; no command dispatched"
            set nativeCommand to item 3 of argv
            set selectionMode to item 4 of argv
            set supportedCommands to {"cleanStructure", "cleanReaction", "alignLeftEdges", "alignRightEdges", "alignTopEdges", "alignBottomEdges", "alignLeftRightCenters", "alignTopBottomCenters", "distributeObjectsHorizontally", "distributeObjectsVertically", "expandLabel", "contractLabel"}
            if nativeCommand is not in supportedCommands then error "Unsupported native command"
            if selectionMode is not in {"current", "all"} then error "Unsupported native selection mode"
            if selectionMode is "all" then do command "selectAll"
            if not (enabled of command nativeCommand) then return my jsonText({my documentRow(targetDoc), false})
            do command nativeCommand
            if (id of document 1) is not wantedID then error "Front document changed during native action; inspect ChemDraw"
            return my jsonText({my documentRow(targetDoc), true})
        else if operation is "convert_name" then
            if (id of document 1) is not wantedID then error "Name conversion requires the owned front document; no command dispatched"
            if (count of molecules of targetDoc) is not 0 then error "Name conversion requires a caption-only document"
            if (count of captions of targetDoc) is not 1 then error "Name conversion requires exactly one caption"
            do command "selectAll"
            if not (enabled of command "convertNameToStructure") then error "Native name conversion is unavailable"
            do command "convertNameToStructure"
            if (id of document 1) is not wantedID then error "Front document changed during native name conversion; inspect ChemDraw"
            return my jsonText(my documentRow(targetDoc))
        else if operation is "clean" then
            set wantedMolecule to item 3 of argv
            if wantedMolecule is "" then
                clean targetDoc
            else
                set moleculeIndex to wantedMolecule as integer
                if moleculeIndex < 1 or moleculeIndex > (count of molecules of targetDoc) then error "Molecule index is absent; inspect document again"
                clean molecule moleculeIndex of targetDoc
            end if
            return my jsonText(my documentRow(targetDoc))
        else if operation is "close" then
            close targetDoc saving no
            return my jsonText({true})
        else
            error "Unsupported operation"
        end if
    end tell
end run
