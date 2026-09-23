import Foundation
import CoreGraphics

struct SetupDiagnostics {
    private(set) var events: [[String: Any]] = []

    mutating func record(action: String, status: String, details: [String: Any]) {
        events.append(["timestamp": ISO8601DateFormatter().string(from: Date()),
                       "action": action, "status": status, "details": details])
        if events.count > 50 { events.removeFirst(events.count - 50) }
    }

    var text: String {
        let report: [String: Any] = ["schema_version": 1,
            "helper_build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "development",
            "macos": ProcessInfo.processInfo.operatingSystemVersionString, "events": events]
        let header = "ChemDraw MCP setup diagnostics\nNo drawings or connection keys are included. Raw error text and personal paths are omitted.\n\n"
        do {
            let bytes = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
            return header + String(decoding: bytes, as: UTF8.self) + "\n"
        } catch {
            return header + "Diagnostic report encoding failed.\n"
        }
    }
}

enum DiagnosticExport {
    static func save(_ report: String, to url: URL) -> Result<URL, Error> {
        Result {
            try report.write(to: url, atomically: true, encoding: .utf8)
            return url
        }
    }
}

struct ClientSelection {
    var bundle = false
    var claude = false
    var codex = false
    var identifiers: [String] { (bundle ? ["bundle"] : []) + (claude ? ["claude"] : []) + (codex ? ["codex"] : []) }
    var canContinue: Bool { bundle || claude || codex }
}

// Presentation state only. Readiness still comes from the live backend check.
struct SetupFlow {
    private(set) var step = 0
    private(set) var connected = false
    private(set) var finished = false
    private var prepared = false
    private(set) var showDiagnostics = false
    var showInstructions: Bool { prepared && !connected && !finished }

    mutating func receive(status: String, ready: Bool) -> String? {
        connected = status == "ready" && ready
        showDiagnostics = false
        switch status {
        case "selected": self = SetupFlow()
        case "local_ready": return "prepare"
        case "prepared": prepared = true; step = 1
        case "exported": break
        case "ready" where ready: step = 2
        case "finished": finished = true; return "close"
        default:
            showDiagnostics = true
            step = prepared ? 1 : 0
        }
        return nil
    }
}

struct Sprite: Decodable {
    let width: Int
    let height: Int
    let rows: [String]

    var dots: [CGPoint] {
        let offsets = [(0,0), (0,1), (0,2), (1,0), (1,1), (1,2), (0,3), (1,3)]
        var points: [CGPoint] = []
        for (y, row) in rows.enumerated() {
            for (x, character) in row.unicodeScalars.enumerated() {
                guard (0x2801...0x28ff).contains(character.value) else { continue }
                let mask = Int(character.value)-0x2800
                for (bit, dot) in offsets.enumerated() where mask & (1 << bit) != 0 {
                    points.append(CGPoint(x: Double(x*2+dot.0), y: Double(y*4+dot.1)))
                }
            }
        }
        return points
    }

    func layout(in size: CGSize) -> SpriteLayout? {
        let points = dots
        guard let first = points.first, size.width > 24, size.height > 24 else { return nil }
        let minX = points.reduce(first.x) { min($0, $1.x) }
        let minY = points.reduce(first.y) { min($0, $1.y) }
        let maxX = points.reduce(first.x) { max($0, $1.x) } + 0.9
        let maxY = points.reduce(first.y) { max($0, $1.y) } + 0.9
        let scale = min((size.width-24)/(maxX-minX), (size.height-24)/(maxY-minY))
        let bounds = CGRect(x: (size.width-(maxX-minX)*scale)/2,
                            y: (size.height-(maxY-minY)*scale)/2,
                            width: (maxX-minX)*scale, height: (maxY-minY)*scale)
        return SpriteLayout(points: points.map { CGPoint(x: $0.x-minX, y: $0.y-minY) },
                            scale: scale, bounds: bounds)
    }
}
struct SpriteLayout {
    let points: [CGPoint]
    let scale: Double
    let bounds: CGRect
}
struct Molecule: Decodable { let sprites: [Sprite] }
struct AnimationData: Decodable { let molecules: [Molecule] }
