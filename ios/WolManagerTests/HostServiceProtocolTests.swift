import XCTest
@testable import WolManager

/* Host-Service-Antworten (Protokoll v4) gegen die Datenmodelle — analog HostServiceProtocolTest.kt. */
final class HostServiceProtocolTests: XCTestCase {

    func testMetricsFullResponse() throws {
        // Beispiel analog protocol/SPEC.md (v4)
        let body = """
        {
          "status": "ok",
          "protocol": 4,
          "hostname": "BUERO-PC",
          "cpu": 12.5,
          "cpu_count": 8,
          "ram_used": 8589934592,
          "ram_total": 17179869184,
          "uptime": 3600,
          "gpu": 42.0,
          "vram_used": 2147483648,
          "vram_total": 8589934592,
          "gpu_name": "NVIDIA GeForce RTX 3060",
          "processes": {
            "llama-server.exe": {
              "running": true, "count": 1, "pid": 4242,
              "cpu": 3.2, "ram": 1073741824, "uptime": 300,
              "model": "mistral-7b.gguf", "api_port": 8080, "api_port_open": true,
              "models": ["mistral-7b.gguf"]
            },
            "notepad.exe": { "running": false, "count": 0 }
          }
        }
        """
        let m = try JSONDecoder().decode(MetricsSnapshot.self, from: Data(body.utf8))
        XCTAssertEqual(m.protocolVersion, 4)
        XCTAssertEqual(m.hostname, "BUERO-PC")
        XCTAssertEqual(m.cpuCount, 8)
        XCTAssertEqual(m.ramUsed! / 1_073_741_824.0, 8.0, accuracy: 0.001)
        XCTAssertEqual(m.ramTotal! / 1_073_741_824.0, 16.0, accuracy: 0.001)
        XCTAssertEqual(m.gpu!, 42.0, accuracy: 0.001)
        XCTAssertEqual(m.processes.count, 2)
        let llama = m.processes["llama-server.exe"]!
        XCTAssertTrue(llama.running)
        XCTAssertEqual(llama.pid, 4242)
        XCTAssertEqual(llama.apiPort, 8080)
        XCTAssertEqual(llama.apiPortOpen, true)
        XCTAssertEqual(llama.models, ["mistral-7b.gguf"])
        let notepad = m.processes["notepad.exe"]!
        XCTAssertEqual(notepad.running, false)
        XCTAssertNil(notepad.pid)
    }

    func testMetricsMinimalResponse() throws {
        let body = """
        {"status":"ok","protocol":4,"hostname":"PC","cpu":1.0}
        """
        let m = try JSONDecoder().decode(MetricsSnapshot.self, from: Data(body.utf8))
        XCTAssertEqual(m.protocolVersion, 4)
        XCTAssertNil(m.gpu)
        XCTAssertTrue(m.processes.isEmpty)
    }

    func testErrorResponseShape() throws {
        let body = """
        {"status":"error","message":"Batches sind deaktiviert. Starten Sie den Dienst mit \\"--enable-batch\\"."}
        """
        let obj = try JSONSerialization.jsonObject(with: Data(body.utf8)) as? [String: Any]
        XCTAssertEqual(obj?["status"] as? String, "error")
        XCTAssertTrue((obj?["message"] as? String)!.contains("--enable-batch"))
    }

    /// run_batch-Antwort: duration_ms als String → Int64, truncated als String → Bool.
    func testBatchResultWireConversion() {
        let body: [String: Any] = [
            "status": "ok", "exit_code": 0, "stdout": "hi", "stderr": "",
            "duration_ms": "1234", "truncated": "false",
        ]
        let r = HostServiceClient.parseBatch(body)
        XCTAssertEqual(r.exitCode, 0)
        XCTAssertEqual(r.stdout, "hi")
        XCTAssertEqual(r.durationMs, 1234)
        XCTAssertEqual(r.truncated, false)
    }

    func testBatchResultWireConversionNumeric() {
        let body: [String: Any] = [
            "status": "ok", "exit_code": 1, "stdout": "", "stderr": "boom",
            "duration_ms": 99, "truncated": true,
        ]
        let r = HostServiceClient.parseBatch(body)
        XCTAssertEqual(r.exitCode, 1)
        XCTAssertEqual(r.stderr, "boom")
        XCTAssertEqual(r.durationMs, 99)
        XCTAssertEqual(r.truncated, true)
    }
}
