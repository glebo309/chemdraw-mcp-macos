"""Exercise the same Swift state and ink geometry used by the native window."""
import os
from pathlib import Path
import platform
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(platform.system() != 'Darwin', reason='Native Swift presentation')
def test_setup_flow_and_sprite_ink_geometry(tmp_path):
    harness = tmp_path/'main.swift'
    harness.write_text(r'''
import Foundation
var clients = ClientSelection()
assert(!clients.canContinue && clients.identifiers.isEmpty)
clients.codex = true
assert(clients.canContinue && clients.identifiers == ["codex"])
clients.claude = true
assert(clients.identifiers == ["claude", "codex"])
var bundle = ClientSelection()
bundle.bundle = true
assert(bundle.canContinue && bundle.identifiers == ["bundle"])
var flow = SetupFlow()
assert(flow.step == 0 && !flow.showDiagnostics && !flow.showInstructions)
assert(flow.receive(status: "selected", ready: false) == nil)
assert(flow.receive(status: "local_ready", ready: false) == "prepare")
assert(flow.step == 0) // No redundant software-checked page.
assert(flow.receive(status: "prepared", ready: false) == nil)
assert(flow.step == 1 && flow.showInstructions && !flow.showDiagnostics)
assert(flow.receive(status: "needs_document", ready: false) == nil)
assert(flow.showDiagnostics && flow.showInstructions)
assert(flow.receive(status: "ready", ready: false) == nil)
assert(!flow.connected) // A status word alone cannot establish readiness.
assert(flow.receive(status: "ready", ready: true) == nil)
assert(flow.step == 2 && flow.connected && !flow.showInstructions && !flow.showDiagnostics)
assert(flow.receive(status: "error", ready: false) == nil)
assert(!flow.connected && flow.showDiagnostics && flow.showInstructions)
_ = flow.receive(status: "ready", ready: true)
assert(flow.receive(status: "finished", ready: false) == "close")
assert(flow.finished && !flow.showInstructions && !flow.showDiagnostics)

let padded = Sprite(width: 100, height: 5, rows: ["   ", "   ⣿⣿", "   ⣿⣿", ""])
let tight = Sprite(width: 2, height: 2, rows: ["⣿⣿", "⣿⣿"])
let viewport = CGSize(width: 232, height: 145)
let a = padded.layout(in: viewport)!
let b = tight.layout(in: viewport)!
assert(abs(a.scale-b.scale) < 0.0001)
assert(abs(a.bounds.midX-116) < 0.0001 && abs(a.bounds.midY-72.5) < 0.0001)
assert(a.bounds.minX >= 12 && a.bounds.maxX <= 220)
assert(abs(a.bounds.height-121) < 0.0001)
assert(Sprite(width: 100, height: 1, rows: ["  ⠀"]).layout(in: viewport) == nil)
let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
let animation = try JSONDecoder().decode(AnimationData.self, from: data)
for molecule in animation.molecules {
    let sprite = molecule.sprites.max(by: { $0.width < $1.width })!
    let layout = sprite.layout(in: viewport)!
    assert(abs(layout.bounds.midX-116) < 0.0001)
    assert(abs(layout.bounds.midY-72.5) < 0.0001)
    assert(abs(layout.bounds.width-208) < 0.001 || abs(layout.bounds.height-121) < 0.001)
}
print("Three-page flow, finish-close action and all molecular ink bounds passed")
''')
    flags = []
    if overlay := os.environ.get('CHEMDRAW_BUILD_SWIFT_OVERLAY'):
        flags = ['-vfsoverlay', overlay, '-Xcc', '-ivfsoverlay', '-Xcc', overlay]
    subprocess.run(['swiftc', *flags, str(ROOT/'packaging/SetupPresentation.swift'),
                    str(harness), '-o', str(tmp_path/'test')], check=True, capture_output=True)
    subprocess.run([str(tmp_path/'test'), str(ROOT/'chemdraw_macos/data/welcome.json')], check=True)


def test_extension_declares_its_bundled_logo():
    from chemdraw_macos.desktop_setup import extension_manifest
    assert extension_manifest('0.10.0-rc.7', 'arm64')['icon'] == 'icon.png'
    assert (ROOT/'packaging/icon.svg').is_file()


@pytest.mark.skipif(platform.system() != 'Darwin', reason='Native Swift diagnostics')
def test_diagnostics_export_writes_text_and_returns_io_failures(tmp_path):
    harness = tmp_path/'main.swift'
    harness.write_text(r'''
import Foundation
var report = SetupDiagnostics()
report.record(action: "test", status: "unavailable", details: ["failure": ["kind": "addin_timeout"]])
let text = report.text
assert(text.contains("addin_timeout") && text.contains("test"))
assert(text.contains("timestamp") && text.contains("No drawings or connection keys"))
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let target = root.appendingPathComponent("Connection check.txt")
let saved = try DiagnosticExport.save(text, to: target).get()
assert(saved == target)
let readBack = try String(contentsOf: target, encoding: .utf8)
assert(readBack == text)
let automatic = try DiagnosticExport.autosave(text, directory: root.appendingPathComponent("logs"), session: "test-session").get()
assert(automatic.pathExtension == "txt")
let automaticText = try String(contentsOf: automatic, encoding: .utf8)
assert(automaticText == text)
let attributes = try FileManager.default.attributesOfItem(atPath: automatic.path)
assert((attributes[.posixPermissions] as! NSNumber).intValue == 0o600)
let again = try DiagnosticExport.autosave(text + "updated", directory: automatic.deletingLastPathComponent(), session: "test-session").get()
assert(again == automatic)
let failure = DiagnosticExport.save(text, to: root.appendingPathComponent("missing/report.txt"))
switch failure {
case .success: fatalError("An unsuccessful write must be visible to the caller")
case .failure(let error): assert(!error.localizedDescription.isEmpty)
}
for _ in 0..<100 { report.record(action: "test", status: "ready", details: [:]) }
assert(report.events.count == 50)
print("Diagnostics file roundtrip, failed-write result and bounded history passed")
''')
    flags = []
    if overlay := os.environ.get('CHEMDRAW_BUILD_SWIFT_OVERLAY'):
        flags = ['-vfsoverlay', overlay, '-Xcc', '-ivfsoverlay', '-Xcc', overlay]
    result = subprocess.run(['swiftc', *flags, str(ROOT/'packaging/SetupPresentation.swift'),
                             str(harness), '-o', str(tmp_path/'test')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    subprocess.run([str(tmp_path/'test'), str(tmp_path)], check=True)


def test_save_panel_handles_results_and_offers_copy_fallback():
    source = (ROOT/'packaging/Welcome.swift').read_text()
    save = source.split('func saveDiagnostics()')[1].split('func close()')[0]
    assert 'allowedContentTypes = [.plainText]' in save
    assert 'DiagnosticExport.save(' in save
    assert 'case .failure' in save and 'case .success' in save
    assert 'Copy report' in save and 'NSPasteboard.general' in save
    assert 'activateFileViewerSelecting' in save
    assert 'diagnostics.record(' in source
    assert 'Button("Copy diagnostics")' in source


def test_native_setup_autosaves_diagnostics_and_exposes_saved_report():
    source = (ROOT/'packaging/Welcome.swift').read_text()
    assert 'DiagnosticExport.autosave(' in source
    assert 'Button("Show saved report")' in source
    assert source.count('diagnostics.record(') == 1
    assert source.count('recordDiagnostic(') >= 5
