# Native session coordination

Updated CLI and MCP processes use the same per-user advisory lock at `~/Library/Caches/chemdraw-mcp-macos/native.lock`, independent of their scratch workspace. The lock coordinates cooperating clients running this implementation, not ChemDraw itself.

Native working-copy workflows hold the gate across their import, snapshot, native edits, exports and cleanup. Low-level create/import/close also hold it across their full transaction. Nested operations in the owning thread are reentrant. Independent threads and processes wait at most two seconds by default; if still occupied, the caller receives `NativeBusy` before its native command is dispatched. The CLI returns a nonzero error and MCP reports a tool error. Doctor reports `busy`, not an installation or permission problem. Offline identifier/resolver/proposal operations do not take this gate.

The kernel releases the advisory lock when the process exits. The file is deliberately not deleted: deleting an active lock file could allow two different inodes to be locked simultaneously. No stale-file deletion or native-operation retry is performed. Lock files must be owned regular files with a single hard link; final-component symlinks are refused. Native timeouts remain uncertain outcomes and must not be confused with lock contention.

## Limits

- Manual GUI changes, older builds, other users and third-party automation are outside this cooperative protocol. Do not edit a drawing concurrently by hand.
- Existing source-token and preservation checks remain necessary. This is not a database transaction or rollback mechanism.
- Locks are local to the Mac and user; they do not coordinate separate Macs through a shared NAS.
- A process exit releases the lock but does not prove that an already dispatched AppleEvent finished. Inspect ChemDraw after an interrupted native operation before starting another write.

Regression tests cover independent workspaces, reentrancy, competing processes/threads, process exit, symlink rejection, bounded waits, busy versus uncertain errors, no subprocess dispatch under contention, and workflow/CLI transaction boundaries. Native acceptance uses private copies and preserves pre-existing documents.
