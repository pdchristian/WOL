import SwiftUI

/*
 * Vereinfachtes Dashboard (Watch): Status + Uptime + Power, Dienst-Chips und
 * 2×2-Mini-Ringe für CPU/RAM/GPU/VRAM. Aktualisierung alle 5 s, nur solange
 * die Ansicht sichtbar und das Gerät online ist.
 */
struct DashboardView: View {
    @EnvironmentObject var state: AppState
    let device: WatchDevice

    @State private var metrics: WatchMetrics?
    /// Zählt Fehlschläge in Folge; die Warnbox erscheint erst ab 2, damit ein
    /// einzelner Timeout (llama-server ausgelastet) nicht sofort das Dashboard
    /// ersetzt — auch die iPhone-App behält bei flüchtigen Fehlern den letzten
    /// Stand.
    @State private var failCount = 0
    /// true, während eine Metrik-Anfrage läuft; verhindert überlappende
    /// Anfragen im 5-s-Takt (die Watch schickt sonst mehrere parallele
    /// metrics-Kommandos, die den Host-Service blockieren und in die
    /// Timeout-Falle laufen).
    @State private var inFlight = false
    @State private var timer: Timer?

    private var live: WatchDevice {
        state.devices.first { $0.id == device.id } ?? device
    }

    var body: some View {
        ZStack {
            Color(.black).ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    header
                    if live.online == true {
                        if let metrics {
                            serviceChips(metrics)
                            gaugeGrid(metrics)
                        } else if failCount >= 2 {
                            // Erst nach zwei Fehlschlägen in Folge warnen — ein
                            // einzelner Timeout (ausgelasteter Host) ist normal.
                            warnBox(Text("dash.unreachable"))
                        } else {
                            HStack {
                                Spacer()
                                ProgressView().tint(.teal)
                                Spacer()
                            }
                            .padding(.vertical, 16)
                        }
                    } else {
                        warnBox(Text("dash.offline"))
                    }
                }
                .padding(.horizontal, 10)
                .padding(.bottom, 12)
            }
        }
        .navigationTitle(device.name)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { startTicking() }
        .onDisappear { stopTicking() }
    }

    // MARK: - Kopfbereich

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                StatusPill(device: live)
                Spacer()
                PowerButton(device: live)
            }
            if let uptime = Fmt.uptime(metrics?.uptime), live.online == true {
                Label {
                    Text(uptime)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                } icon: {
                    Image(systemName: "clock")
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    // MARK: - Dienste

    @ViewBuilder
    private func serviceChips(_ m: WatchMetrics) -> some View {
        if m.processes.isEmpty {
            section(Text("dash.svc.none"))
                .foregroundStyle(.secondary)
        } else {
            VStack(alignment: .leading, spacing: 4) {
                section(Text("dash.svc"))
                FlowLayout(spacing: 5) {
                    ForEach(m.processes) { p in
                        ServiceChip(process: p)
                    }
                }
            }
        }
    }

    // MARK: - Ringe (CPU / RAM / GPU / VRAM)

    private func gaugeGrid(_ m: WatchMetrics) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            section(Text("dash.system"))
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)],
                      spacing: 8) {
                GaugeTile(labelKey: "m.cpu", value: m.cpu, detail: nil)
                GaugeTile(labelKey: "m.ram", value: m.ram, detail: nil)
                GaugeTile(labelKey: "m.gpu", value: m.gpu, detail: nil)
                GaugeTile(labelKey: "m.vram", value: m.vram, detail: nil)
            }
        }
    }

    private func section(_ text: Text) -> some View {
        text
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(.secondary)
            .textCase(.uppercase)
    }

    private func warnBox(_ text: Text) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 12))
            text
                .font(.system(size: 12))
        }
        .foregroundStyle(.orange)
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - Refresh (nur sichtbar & online)

    private func startTicking() {
        tick()
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { _ in
            tick()
        }
    }

    private func stopTicking() {
        timer?.invalidate()
        timer = nil
    }

    private func tick() {
        guard live.online == true, !inFlight else { return }
        let id = device.id
        inFlight = true
        Task { @MainActor in
            defer { inFlight = false }
            do {
                metrics = try await WatchService.shared.metrics(id: id)
                failCount = 0
            } catch {
                // Vorübergehender Fehler (Watch oft: Timeout, während das iPhone
                // im Hintergrund kalt startet): letzten Stand behalten und erst
                // nach zwei Fehlschlägen in Folge warnen.
                failCount += 1
            }
        }
    }
}

// MARK: - Bausteine

/// Mini-Ring mit Prozentwert und Beschriftung.
///
/// Layout: Ring zentriert über der Beschriftung. Der Wert wird immer als
/// Ganzzahl-Prozent dargestellt ("9%"), damit die Kacheln auf der schmalen
/// Watch-Anzeige lesbar bleiben; Ring und Label skalieren mit, statt
/// umzubrechen (Zeilenumbruch ließ die Beschriftung zuvor vertikal stehen).
struct GaugeTile: View {
    let labelKey: LocalizedStringKey
    let value: Double?
    let detail: String?

    var body: some View {
        VStack(spacing: 5) {
            ZStack {
                Circle()
                    .stroke(Color.white.opacity(0.12), lineWidth: 5)
                Circle()
                    .trim(from: 0, to: min(max((value ?? 0) / 100, 0), 1))
                    .stroke(ringColor, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text(Self.percent(value))
                    .font(.system(size: 15, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.5)
                    .padding(8)
            }
            .frame(width: 56, height: 56)

            Text(labelKey)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            if let detail {
                Text(detail)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color(white: 0.1), in: RoundedRectangle(cornerRadius: 12))
    }

    /// Ganzzahliges Prozent ohne Nachkommastellen ("9%", "—"). `Int(rounded)`
    /// statt `Double`-Interpolation, damit nie "9.0" oder lokalisiert
    /// "9,0000" erscheint.
    static func percent(_ value: Double?) -> String {
        guard let value, value.isFinite else { return "—" }
        return "\(Int(value.rounded()))%"
    }

    private var ringColor: Color {
        let v = value ?? 0
        if v >= 90 { return Color(red: 1.0, green: 0.27, blue: 0.23) }
        if v >= 70 { return .orange }
        return .teal
    }
}

/// Dienst-Chip: laufend (grün), gestoppt (grau).
struct ServiceChip: View {
    let process: WatchProcess

    var body: some View {
        HStack(spacing: 3) {
            Circle()
                .fill(process.running
                      ? Color(red: 0.3, green: 0.86, blue: 0.37)
                      : Color(white: 0.45))
                .frame(width: 6, height: 6)
            Text(process.key)
                .font(.system(size: 11, weight: .medium))
                .lineLimit(1)
        }
        .foregroundStyle(process.running ? Color(red: 0.3, green: 0.86, blue: 0.37) : Color(white: 0.6))
        .padding(.horizontal, 7)
        .padding(.vertical, 4)
        .background(Color(white: 0.14), in: Capsule())
    }
}

/// Einfacher Flow-Layout (Chips umbrechen lassen), watchOS-kompatibel.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        layout(proposal: proposal, subviews: subviews).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = layout(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions {
            let size = subviews[index].sizeThatFits(.unspecified)
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y),
                                  anchor: .topLeading, proposal: .init(size))
        }
    }

    private func layout(proposal: ProposedViewSize, subviews: Subviews)
        -> (size: CGSize, positions: [(Int, CGPoint)]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [(Int, CGPoint)] = []
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0, maxX: CGFloat = 0
        for (index, sub) in subviews.enumerated() {
            let size = sub.sizeThatFits(.unspecified)
            if x + size.width > maxWidth, x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append((index, CGPoint(x: x, y: y)))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            maxX = max(maxX, x)
        }
        return (CGSize(width: maxX, height: y + rowHeight), positions)
    }
}
