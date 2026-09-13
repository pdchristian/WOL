import SwiftUI

/*
 * Hauptansicht: Geräte als Karten oder Liste, umschaltbar. Power-Icon pro
 * Gerät: offline → aufwecken (türkis), online → herunterfahren (rot, mit
 * Bestätigung), waking → blinkendes Warten. Dazu Warnbox ohne iPhone und Toast.
 */
struct DeviceListView: View {
    @EnvironmentObject var state: AppState
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                Color(.black).ignoresSafeArea()
                content
                overlay
            }
            .navigationTitle(Text("nav.devices", value: "Geräte"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { viewModeButton }
                ToolbarItem(placement: .topBarTrailing) { refreshButton }
            }
            .navigationDestination(for: WatchDevice.self) { device in
                DashboardView(device: device)
            }
            .sheet(item: $state.confirmDevice) { device in
                ShutdownConfirmView(device: device)
            }
        }
    }

    // MARK: - Inhalt

    @ViewBuilder private var content: some View {
        if state.devices.isEmpty && !state.loading {
            VStack(spacing: 8) {
                Image(systemName: "desktopcomputer")
                    .font(.system(size: 30))
                    .foregroundStyle(.secondary)
                Text("devices.empty")
                    .font(.system(size: 15))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(16)
        } else {
            ScrollView {
                VStack(spacing: 8) {
                    if state.iPhoneUnreachable { warnBox }
                    summaryLine
                    if state.viewMode == .cards { cardGrid } else { listRows }
                }
                .padding(.horizontal, 10)
                .padding(.bottom, 12)
            }
        }
    }

    private var summaryLine: some View {
        let online = state.devices.filter { $0.online == true }.count
        return Text("\(online)/\(state.devices.count)")
            .font(.system(size: 13, weight: .medium))
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 2)
    }

    private var warnBox: some View {
        Label {
            Text("warn.iphone")
                .font(.system(size: 13))
        } icon: {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 13))
        }
        .foregroundStyle(.orange)
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - Karten / Liste

    private var cardGrid: some View {
        LazyVStack(spacing: 8) {
            ForEach(state.devices) { device in
                NavigationLink(value: device) {
                    DeviceCard(device: device)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var listRows: some View {
        VStack(spacing: 4) {
            ForEach(state.devices) { device in
                NavigationLink(value: device) {
                    DeviceRow(device: device)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Toolbar

    private var viewModeButton: some View {
        Button {
            state.viewMode = (state.viewMode == .cards) ? .list : .cards
        } label: {
            Image(systemName: state.viewMode == .cards ? "list.bullet" : "square.grid.2x2")
        }
        .accessibilityLabel(state.viewMode == .cards
            ? Text("devices.viewList") : Text("devices.viewCards"))
    }

    private var refreshButton: some View {
        Button {
            state.refresh()
        } label: {
            Image(systemName: state.loading ? "hourglass" : "arrow.clockwise")
        }
        .disabled(state.loading)
    }

    // MARK: - Overlay (Toast)

    @ViewBuilder private var overlay: some View {
        if let toast = state.toast {
            VStack {
                Spacer()
                Text(toast)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.bottom, 6)
            }
            .transition(.opacity)
            .allowsHitTesting(false)
        }
    }
}

// MARK: - Karten & Zeilen

/// Karte: Name, Status-Pill, IP, Power-Icon rechts.
struct DeviceCard: View {
    @EnvironmentObject var state: AppState
    let device: WatchDevice

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 3) {
                Text(device.name)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                StatusPill(device: device)
                if !device.ip.isEmpty {
                    Text(device.ip)
                        .font(.system(size: 12))
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 0)
            PowerButton(device: device)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(white: 0.12), in: RoundedRectangle(cornerRadius: 14))
    }
}

/// Kompakte Zeile (Listenansicht).
struct DeviceRow: View {
    @EnvironmentObject var state: AppState
    let device: WatchDevice

    var body: some View {
        HStack(spacing: 8) {
            StatusDot(device: device)
            VStack(alignment: .leading, spacing: 1) {
                Text(device.name)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                Text(device.ip.isEmpty ? "—" : device.ip)
                    .font(.system(size: 11))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            PowerButton(device: device)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Color(white: 0.1), in: RoundedRectangle(cornerRadius: 12))
    }
}

/// Power-Icon: offline → Wake (türkis), online → Shutdown (rot, Bestätigung),
/// waking → blinkend. Tap auf dem Icon stoppt die Navigation der Karte.
struct PowerButton: View {
    @EnvironmentObject var state: AppState
    let device: WatchDevice

    @State private var blink = false
    @State private var blinkTimer: Timer?

    private var isWaking: Bool { device.waking }
    private var isOnline: Bool { device.online == true }

    var body: some View {
        Button {
            if isOnline {
                state.requestShutdown(device)
            } else if !isWaking {
                state.wake(device)
            }
        } label: {
            Image(systemName: "power")
                .font(.system(size: 18, weight: .bold))
                .foregroundStyle(foreground)
                .frame(width: 38, height: 38)
                .background(background, in: Circle())
                .overlay(Circle().stroke(borderColor, lineWidth: 1.5))
                .opacity(isWaking && blink ? 0.3 : 1)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(isOnline
            ? Text("devices.shutdown") : Text("devices.wake"))
        .onAppear { updateBlink() }
        .onDisappear {
            blinkTimer?.invalidate()
            blinkTimer = nil
        }
        .onChange(of: isWaking) { _, _ in updateBlink() }
    }

    private var foreground: Color {
        if isWaking { return .teal }
        return isOnline ? Color(red: 1.0, green: 0.27, blue: 0.23) : .teal
    }

    private var background: Color {
        foreground.opacity(0.15)
    }

    private var borderColor: Color {
        foreground.opacity(0.5)
    }

    private func updateBlink() {
        if isWaking {
            guard blinkTimer == nil else { return }
            blinkTimer = Timer.scheduledTimer(withTimeInterval: 0.6, repeats: true) { _ in
                withAnimation(.easeInOut(duration: 0.3)) { blink.toggle() }
            }
        } else {
            blinkTimer?.invalidate()
            blinkTimer = nil
            blink = false
        }
    }
}

/// Status-Pill (Karte): online / offline / waking.
struct StatusPill: View {
    let device: WatchDevice

    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(dotColor).frame(width: 7, height: 7)
            Text(label)
                .font(.system(size: 12, weight: .medium))
        }
        .foregroundStyle(textColor)
        .padding(.horizontal, 7)
        .padding(.vertical, 3)
        .background(textColor.opacity(0.14), in: Capsule())
    }

    private var label: LocalizedStringKey {
        if device.waking { return "status.waking" }
        return device.online == true ? "status.online" : "status.offline"
    }

    private var dotColor: Color { textColor }

    private var textColor: Color {
        if device.waking { return .teal }
        return device.online == true
            ? Color(red: 0.3, green: 0.86, blue: 0.37)
            : Color(white: 0.55)
    }
}

/// Status-Punkt (Liste).
struct StatusDot: View {
    let device: WatchDevice

    var body: some View {
        Circle()
            .fill(color)
            .frame(width: 9, height: 9)
    }

    private var color: Color {
        if device.waking { return .teal.opacity(0.7) }
        return device.online == true
            ? Color(red: 0.3, green: 0.86, blue: 0.37)
            : Color(white: 0.4)
    }
}
