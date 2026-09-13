import Foundation

/*
 * Metriken → UI-JSON (Bytes → Prozent/GB, gerundet).
 *
 * Früher eine private Methode in WebView/Bridge.swift; hier ausgelagert, damit
 * iPhone-WebView UND Apple-Watch-Brücke (WatchCommandDispatcher) exakt dasselbe
 * flache, display-fertige Format liefern. Reine Funktion → ohne Netzwerk testbar.
 */
enum MetricsUI {

    /// Wire-Format (Bytes) → UI-Format (Prozent/GB, gerundet) — analog Kotlin.
    static func uiJson(_ m: MetricsSnapshot) -> [String: Any] {
        let GBd = 1024.0 * 1024.0 * 1024.0
        let ramTotal = m.ramTotal ?? 0
        let ramPct = ramTotal > 0 ? (m.ramUsed ?? 0) / ramTotal * 100 : 0
        let vramTotal = m.vramTotal ?? 0
        let vramPct = vramTotal > 0 ? (m.vramUsed ?? 0) / vramTotal * 100 : 0
        func r1(_ v: Double) -> Double { (v * 10).rounded() / 10 }

        var out: [String: Any] = [
            "protocol": m.protocolVersion,
            "hostname": m.hostname,
            "cpu": m.cpu.map { ($0).rounded() },
            "cpuCount": m.cpuCount ?? NSNull(),
            "ram": ramPct.rounded(),
            "ramUsedGB": r1((m.ramUsed ?? 0) / GBd),
            "ramTotalGB": r1(ramTotal / GBd),
            "uptime": m.uptime.map { Int64($0) } ?? NSNull(),
            "gpu": m.gpu.map { ($0).rounded() },
            "vram": vramTotal > 0 ? vramPct.rounded() : NSNull(),
            "vramUsedGB": m.vramUsed.map { r1($0 / GBd) } as Any,
            "vramTotalGB": m.vramTotal.map { r1($0 / GBd) } as Any,
            "gpuName": m.gpuName as Any,
        ]
        out["processes"] = m.processes.map { (key, w) -> [String: Any] in
            // Host v5: per-model throughput (t/s) + total tokens.
            let metrics: [String: Any] = Dictionary(uniqueKeysWithValues:
                w.modelMetrics.map { (model, mm) in
                    (model, [
                        "promptTps": mm.promptTps ?? NSNull(),
                        "predictedTps": mm.predictedTps ?? NSNull(),
                        "totalTokens": mm.totalTokens ?? NSNull(),
                    ] as [String: Any])
                })
            return [
                "key": key,
                "running": w.running,
                "pid": w.pid ?? NSNull(),
                "cpu": w.cpu.map { ($0).rounded() } as Any,
                "ram": w.ram.map { r1($0 / GBd) } as Any,
                "uptime": w.uptime.map { Int64($0) } as Any,
                "model": w.model as Any,
                "apiPort": w.apiPort ?? NSNull(),
                "apiPortOpen": w.apiPortOpen ?? NSNull(),
                "models": w.models,
                "modelMetrics": metrics,
            ]
        }
        return out
    }
}
