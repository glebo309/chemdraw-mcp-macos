use framework "Foundation"
use scripting additions

on jsonText(value)
    set dataValue to current application's NSJSONSerialization's dataWithJSONObject:value options:0 |error|:(missing value)
    return (current application's NSString's alloc()'s initWithData:dataValue encoding:4) as text
end jsonText

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
            return my jsonText(my documentRow(item 1 of matches))
        end if
        set wantedID to (item 2 of argv) as integer
        set targetDoc to missing value
        repeat with candidate in documents
            if ((id of candidate) as integer) is wantedID then set targetDoc to contents of candidate
        end repeat
        if targetDoc is missing value then error "Document ID is stale or absent; list documents again"
        if operation is "inspect" then
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
            if diskPath is "" then error "Untitled document cannot be exported safely: native save would assign a filename. No save dispatched."
            set targetPath to item 3 of argv
            set targetFormat to item 4 of argv
            save targetDoc in (my fileReference(targetPath)) as targetFormat
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
