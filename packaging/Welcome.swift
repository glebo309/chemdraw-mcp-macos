import AppKit
import SwiftUI
import UniformTypeIdentifiers

enum Palette {
    static let accent = Color(red: 0.96, green: 0.67, blue: 0.80)
    static let lavender = Color(red: 0.74, green: 0.68, blue: 0.89)
    static let gold = Color(red: 0.94, green: 0.82, blue: 0.55)
    static let cream = Color(red: 0.94, green: 0.92, blue: 0.89)
    static let sidebar = Color(red: 0.13, green: 0.115, blue: 0.15)
    static let panel = Color(red: 0.18, green: 0.155, blue: 0.19)
}

struct PrimaryButton: ButtonStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.system(size: 12, weight: .semibold))
            .padding(.horizontal, 13).padding(.vertical, 9)
            .foregroundStyle(enabled ? Color(red: 0.15, green: 0.10, blue: 0.16) : Palette.cream.opacity(0.35))
            .background(enabled ? Palette.accent.opacity(configuration.isPressed ? 0.8 : 1) : Color.white.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 5))
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Palette.cream.opacity(enabled ? 0.3 : 0.08), lineWidth: 0.5))
    }
}

struct ThemeCheckbox: ToggleStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        Button { configuration.isOn.toggle() } label: {
            HStack(spacing: 8) {
                ZStack {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(configuration.isOn ? Palette.accent : Color.white.opacity(0.08))
                    RoundedRectangle(cornerRadius: 3)
                        .stroke(Palette.lavender.opacity(0.65), lineWidth: 0.7)
                    if configuration.isOn {
                        Image(systemName: "checkmark").font(.system(size: 10, weight: .bold))
                            .foregroundStyle(Palette.sidebar)
                    }
                }.frame(width: 15, height: 15)
                configuration.label
            }.contentShape(Rectangle())
        }.buttonStyle(.plain).opacity(enabled ? 1 : 0.45)
            .accessibilityValue(configuration.isOn ? "Selected" : "Not selected")
    }
}

@MainActor final class SetupModel: ObservableObject {
    @Published var title = "Select your ChemDraw app"
    @Published var message = "Select ChemDraw and the assistants you want to connect."
    @Published var selectedApp: String?
    @Published var busy = false
    @Published var ready = false
    @Published var finished = false
    @Published var prepared = false
    @Published var existingFiles = false
    @Published var savedInstaller: URL?
    @Published var package: URL?
    @Published var directory: URL?
    @Published var details = ""
    @Published var molecules: [Molecule] = []
    @Published var flow = SetupFlow()
    @Published var preview = false
    @Published var clients = ClientSelection()
    var step: Int { flow.step }
    private var process: Process?
    private var input: FileHandle?
    private var buffer = Data()

    init() {
        let manifest = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("manifest.json")
        if let data = try? Data(contentsOf: manifest),
           let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           value["name"] as? String == "chemdraw-macos" { clients.bundle = true }
        if let url = Bundle.main.url(forResource: "welcome", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let animation = try? JSONDecoder().decode(AnimationData.self, from: data) {
            molecules = animation.molecules
        }
    }

    func start() throws {
        if process != nil { return }
        guard let resources = Bundle.main.resourceURL else { throw CocoaError(.fileNoSuchFile) }
        let task = Process()
        task.executableURL = resources.appendingPathComponent("backend/chemdraw-runtime")
        task.arguments = ["--setup-service"]
        let incoming = Pipe(), outgoing = Pipe()
        task.standardInput = incoming
        task.standardOutput = outgoing
        task.standardError = FileHandle.nullDevice
        outgoing.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let bytes = handle.availableData
            Task { @MainActor in self?.receive(bytes) }
        }
        task.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                guard let self = self, !self.finished else { return }
                self.busy = false
                self.ready = false
                _ = self.flow.receive(status: "error", ready: false)
                self.title = "Setup helper stopped"
                self.message = "Close and reopen this setup window. If this repeats, download the build matching your Mac."
                self.process = nil
            }
        }
        try task.run()
        process = task
        input = incoming.fileHandleForWriting
    }

    func request(_ action: String, path: String? = nil) {
        guard !busy else { return }
        do {
            try start()
            var value: [String: Any] = ["action": action]
            if let path = path { value["path"] = path }
            if action == "finish" { value["clients"] = clients.identifiers }
            var bytes = try JSONSerialization.data(withJSONObject: value)
            bytes.append(10)
            busy = true
            if action == "choose_app" {
                selectedApp = nil
                prepared = false
                existingFiles = false
                savedInstaller = nil
                flow = SetupFlow()
                package = nil
                directory = nil
            }
            if action != "finish" { ready = false }
            title = action == "test" ? "Testing the live connection" : "Preparing your workspace"
            message = "Approve macOS Automation access if a permission window appears."
            try input?.write(contentsOf: bytes)
        } catch {
            busy = false
            _ = flow.receive(status: "error", ready: false)
            title = "Could not start setup"
            message = error.localizedDescription
        }
    }

    func receive(_ bytes: Data) {
        buffer.append(bytes)
        while let newline = buffer.firstIndex(of: 10) {
            let line = buffer[..<newline]
            buffer.removeSubrange(...newline)
            guard let value = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
            busy = false
            ready = value["ready"] as? Bool ?? false
            title = value["title"] as? String ?? title
            message = value["message"] as? String ?? message
            if let data = value["details"],
               let bytes = try? JSONSerialization.data(withJSONObject: data, options: [.prettyPrinted, .sortedKeys]) {
                details = String(decoding: bytes, as: UTF8.self)
            }
            let nextAction = flow.receive(status: value["status"] as? String ?? "error", ready: ready)
            switch value["status"] as? String {
            case "selected":
                selectedApp = value["app"] as? String
                title = "ChemDraw selected"
                message = "Click Next to prepare your ChemDraw connection."
            case "prepared":
                prepared = true
                existingFiles = value["existing_files"] as? Bool ?? false
                package = (value["package"] as? String).map { URL(fileURLWithPath: $0) }
                directory = (value["search_directory"] as? String).map { URL(fileURLWithPath: $0) }
                title = "Connect ChemDraw"
                message = "Open Add-ins > Add-in Manager in ChemDraw."
            case "exported":
                savedInstaller = (value["path"] as? String).map { URL(fileURLWithPath: $0) }
                title = "Installer saved"
                message = "In ChemDraw's Add-in Manager, choose Add from file and select this file from Downloads."
                if let savedInstaller = savedInstaller {
                    NSWorkspace.shared.activateFileViewerSelecting([savedInstaller])
                }
            case "ready" where ready:
                title = "Connected to ChemDraw"
                message = "Document read passed. Finish setup to save your connections, then restart your selected assistants."
            case "finished":
                finished = true
                try? input?.close()
            default: break
            }
            if nextAction == "prepare" { request("prepare") }
            if nextAction == "close" { NSApp.terminate(nil) }
        }
    }

    func chooseApp() {
        let panel = NSOpenPanel()
        panel.title = "Choose your ChemDraw application"
        panel.prompt = "Select ChemDraw"
        panel.directoryURL = URL(fileURLWithPath: "/Applications")
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowedContentTypes = [.applicationBundle]
        if panel.runModal() == .OK, let url = panel.url { request("choose_app", path: url.path) }
    }

    var canGoNext: Bool {
        !busy && selectedApp != nil && clients.canContinue && !finished && (!prepared || existingFiles || savedInstaller != nil)
    }
    func next() {
        guard canGoNext else { return }
        request(ready ? "finish" : prepared ? "test" : "check")
    }

    func saveInstaller() {
        let panel = NSSavePanel()
        panel.title = "Save the ChemDraw connection installer"
        panel.prompt = "Save installer"
        panel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
        panel.nameFieldStringValue = "ChemDraw MCP Native API.chemdrawaddin"
        if panel.runModal() == .OK, let url = panel.url { request("export_installer", path: url.path) }
    }

    func saveDiagnostics() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "ChemDraw connection check.txt"
        if panel.runModal() == .OK, let url = panel.url {
            try? (title+"\n"+message+"\n\n"+details).write(to: url, atomically: true, encoding: .utf8)
        }
    }

    func close() { try? input?.close() }
}

struct MolecularAnimation: View {
    let molecules: [Molecule]
    let stopped: Bool
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var began = Date(timeIntervalSinceNow: -0.7)
    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0/25.0, paused: stopped || reduceMotion)) { timeline in
            let elapsed = max(0, timeline.date.timeIntervalSince(began))
            Canvas { context, size in
                guard !molecules.isEmpty else { return }
                let molecule = molecules[(reduceMotion ? 0 : Int(elapsed/1.4)) % molecules.count]
                guard let sprite = molecule.sprites.max(by: { $0.width < $1.width }),
                      let layout = sprite.layout(in: size) else { return }
                let scale = layout.scale
                let width = layout.bounds.width / scale
                let offset = layout.bounds.origin
                let sweep = (reduceMotion || stopped) ? width+10 : min(1, elapsed.truncatingRemainder(dividingBy: 1.4)/0.476)*(width+8)
                for point in layout.points {
                            let px = point.x, py = point.y
                            guard px < sweep else { continue }
                            let rect = CGRect(x: offset.x+px*scale, y: offset.y+py*scale, width: scale*0.9, height: scale*0.9)
                            context.fill(Path(ellipseIn: rect), with: .color(sweep-px < 8 ? Palette.gold : Palette.cream))
                }
            }
        }
        .accessibilityLabel("Animated molecular structures from native ChemDraw drawings")
    }
}

// Fine-line framing around the artwork, without adding another control or panel.
struct FineLineFrame: View {
    var body: some View {
        GeometryReader { proxy in
            Path { path in
                let w = proxy.size.width, h = proxy.size.height
                for (x, y, dx, dy) in [(0.0, 0.0, 1.0, 1.0), (w, h, -1.0, -1.0)] {
                    path.move(to: CGPoint(x: x, y: y + dy*10))
                    path.addLine(to: CGPoint(x: x, y: y))
                    path.addLine(to: CGPoint(x: x + dx*10, y: y))
                }
            }.stroke(Palette.lavender.opacity(0.55), lineWidth: 0.6)
        }.allowsHitTesting(false).accessibilityHidden(true)
    }
}

@MainActor struct WelcomeView: View {
    @StateObject var model: SetupModel
    init(model: SetupModel? = nil) { _model = StateObject(wrappedValue: model ?? SetupModel()) }
    @State private var help = false
    private let accent = Palette.accent
    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                Text("CHEMDRAW / MCP").font(.system(size: 12, weight: .semibold, design: .monospaced)).tracking(3).foregroundStyle(accent)
                HStack(spacing: 4) {
                    Rectangle().fill(accent).frame(width: 36, height: 1)
                    Rectangle().fill(Palette.lavender).frame(width: 22, height: 1)
                    Rectangle().fill(Palette.gold).frame(width: 12, height: 1)
                }.accessibilityHidden(true)
                Spacer()
                MolecularAnimation(molecules: model.molecules, stopped: model.finished || model.preview)
                    .frame(height: 145).overlay(FineLineFrame())
                Text("Natural language to\nchemical structure.").font(.system(size: 21, weight: .medium)).lineSpacing(2)
                Text("One canvas. You and your assistant.").font(.system(size: 11)).foregroundStyle(.white.opacity(0.55))
                Spacer()
                Text("Created by Glenn Bojanov").font(.system(size: 10)).foregroundStyle(.white.opacity(0.45))
            }.padding(24).frame(width: 280).frame(maxHeight: .infinity)
                .background(Palette.sidebar)
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    ForEach(0..<3) { index in
                        Capsule().fill(index < model.step ? accent : Color.white.opacity(0.13)).frame(height: 3)
                    }
                }
                Text("STEP \(model.step + 1) OF 3").font(.system(size: 10, weight: .semibold)).tracking(2).foregroundStyle(accent)
                Text(model.title).font(.system(size: 23, weight: .semibold)).fixedSize(horizontal: false, vertical: true)
                Text(model.message).font(.system(size: 12)).lineSpacing(2).foregroundStyle(.white.opacity(0.72)).fixedSize(horizontal: false, vertical: true)
                if model.busy { ProgressView().controlSize(.small).tint(accent) }
                if model.ready {
                    Label("Document read: pass", systemImage: "checkmark.circle.fill")
                        .font(.system(size: 13)).foregroundStyle(Palette.gold)
                }
                if model.step == 0 {
                    VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 12) {
                    Button("Select ChemDraw…") { model.chooseApp() }
                        .buttonStyle(PrimaryButton())
                        .controlSize(.large).disabled(model.busy)
                    if let app = model.selectedApp {
                        Label(URL(fileURLWithPath: app).lastPathComponent, systemImage: "checkmark.circle.fill")
                            .font(.system(size: 12)).foregroundStyle(accent)
                            .lineLimit(1).truncationMode(.middle).help(app)
                    }
                    }
                    Text("CONNECT TO").font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .tracking(1.5).foregroundStyle(Palette.lavender).padding(.top, 4)
                    if model.clients.bundle {
                        Label("Current MCP app: bundle installed", systemImage: "checkmark.circle")
                            .font(.system(size: 11)).foregroundStyle(Palette.gold)
                    } else {
                        Toggle("Claude Desktop", isOn: $model.clients.claude)
                    }
                    Toggle("Codex / ChatGPT", isOn: $model.clients.codex)
                    Text("Choose one or both. One shared installation.")
                        .font(.system(size: 10)).foregroundStyle(.white.opacity(0.55))
                    }.toggleStyle(ThemeCheckbox()).font(.system(size: 12))
                }
                if model.flow.showInstructions {
                    ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                    VStack(alignment: .leading, spacing: 6) {
                            Text("If ChemDraw MCP Native API is listed, enable it. If not:")
                            Button("Save add-in installer to Downloads…") { model.saveInstaller() }
                                .buttonStyle(PrimaryButton())
                                .disabled(model.busy)
                            Text("1. Click + > Add from file.")
                            Text("2. Choose the saved .chemdrawaddin file in Downloads; enable it.")
                            Text("3. Open a drawing, then click Test connection.")
                            Text("You can delete the Downloads installer after setup succeeds.")
                                .font(.system(size: 10)).foregroundStyle(Palette.cream.opacity(0.7))
                            if let savedInstaller = model.savedInstaller {
                                Button("Show saved installer") { NSWorkspace.shared.activateFileViewerSelecting([savedInstaller]) }
                                    .buttonStyle(.bordered)
                            }
                        DisclosureGroup("Troubleshooting", isExpanded: $help) {
                            Text("Duplicate name? Cancel the import and enable the existing entry. Invalid file? Save the installer again using the button above. The installer is private to this Mac; do not share it.")
                            Text("In ChemDraw Preferences > Directories, add this folder to ChemDraw Items. Then restart ChemDraw when your work is saved.").padding(.top, 8)
                            if let directory = model.directory {
                                Text(directory.path).textSelection(.enabled).font(.system(size: 10, design: .monospaced))
                                Button("Show folder") { NSWorkspace.shared.open(directory) }.buttonStyle(.link)
                            }
                        }
                    }.font(.system(size: 11)).lineSpacing(1).padding(8)
                        .background(Color.white.opacity(0.04)).clipShape(RoundedRectangle(cornerRadius: 12))
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    }.frame(maxHeight: .infinity)
                } else {
                    Spacer(minLength: 0)
                }
                if !model.finished {
                    HStack {
                        if model.flow.showDiagnostics {
                            Button("Save diagnostics…") { model.saveDiagnostics() }.buttonStyle(.bordered)
                        }
                        Spacer()
                        Button(model.ready ? "Finish setup" : model.prepared ? "Test connection" : "Next") { model.next() }
                            .buttonStyle(PrimaryButton())
                            .controlSize(.large).disabled(!model.canGoNext)
                    }.font(.system(size: 11)).disabled(model.busy)
                }
                if !model.ready {
                Text("Requires licensed ChemDraw. Experimental Mac build.")
                    .font(.system(size: 10)).foregroundStyle(.white.opacity(0.4))
                }
            }.padding(24).frame(width: 520).frame(maxHeight: .infinity)
                .background(Palette.panel)
        }.frame(width: 800, height: 400).foregroundStyle(Palette.cream)
            .environment(\.colorScheme, .dark).preferredColorScheme(.dark)
            .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in model.close() }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Offscreen rendering of the real view for build-time visual acceptance.
        // This does not inspect or automate other applications.
        if let index = CommandLine.arguments.firstIndex(of: "--render-preview"),
           CommandLine.arguments.count > index+1 {
            NSApp.appearance = NSAppearance(named: .darkAqua)
            let model = SetupModel()
            model.preview = true
            if let i = CommandLine.arguments.firstIndex(of: "--molecule"),
               CommandLine.arguments.count > i+1, let m = Int(CommandLine.arguments[i+1]),
               model.molecules.indices.contains(m) { model.molecules = [model.molecules[m]] }
            if CommandLine.arguments.contains("--selected") || CommandLine.arguments.contains("--prepared") {
                model.selectedApp = "/Applications/ChemDraw 23.0.1.app"
                model.title = "ChemDraw selected"
                model.message = "Click Next to check the bundled chemistry tools."
                model.clients.claude = true
                model.clients.codex = true
                model.clients.bundle = false
            }
            if CommandLine.arguments.contains("--prepared") {
                model.prepared = true
                _ = model.flow.receive(status: "prepared", ready: false)
                model.existingFiles = CommandLine.arguments.contains("--existing")
                model.title = "Connect ChemDraw"
                model.message = "Open Add-ins > Add-in Manager in ChemDraw."
                model.directory = URL(fileURLWithPath: "/Users/example/Library/Application Support/com.revvity.ChemDraw")
            }
            if CommandLine.arguments.contains("--connected") {
                model.selectedApp = "/Applications/ChemDraw.app"
                model.prepared = true
                model.existingFiles = true
                model.ready = true
                _ = model.flow.receive(status: "ready", ready: true)
                model.title = "Connected to ChemDraw"
                model.clients.claude = true
                model.clients.codex = true
                model.message = "Document read passed. Finish setup to save your connections, then restart your selected assistants."
            }
            let view = NSHostingView(rootView: WelcomeView(model: model))
            let bounds = NSRect(x: 0, y: 0, width: 800, height: 400)
            let window = NSWindow(contentRect: bounds, styleMask: .borderless, backing: .buffered, defer: false)
            window.contentView = view
            view.frame = bounds
            view.layoutSubtreeIfNeeded()
            if let bitmap = view.bitmapImageRepForCachingDisplay(in: bounds) {
                view.cacheDisplay(in: bounds, to: bitmap)
                if let data = bitmap.representation(using: .png, properties: [:]) {
                    try? data.write(to: URL(fileURLWithPath: CommandLine.arguments[index+1]))
                }
            }
            NSApp.terminate(nil)
            return
        }
        NSApp.activate(ignoringOtherApps: true)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main struct WelcomeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        WindowGroup("ChemDraw MCP") { WelcomeView() }
            .windowResizability(.contentSize)
            .commands { CommandGroup(replacing: .newItem) {} }
    }
}
