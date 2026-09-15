import SwiftUI

/*
 * Bestätigung vor dem Herunterfahren — zentrierte Karte mit Power-Icon und
 * großen Buttons (Watch-taugliche Touch-Ziele).
 */
struct ShutdownConfirmView: View {
    @EnvironmentObject var state: AppState
    let device: WatchDevice

    var body: some View {
        ZStack {
            Color.black.opacity(0.85).ignoresSafeArea()
            VStack(spacing: 10) {
                Image(systemName: "power")
                    .font(.system(size: 26, weight: .bold))
                    .foregroundStyle(Color(red: 1.0, green: 0.27, blue: 0.23))
                    .frame(width: 48, height: 48)
                    .background(Color(red: 1.0, green: 0.27, blue: 0.23).opacity(0.15), in: Circle())
                Text("shutdown.title")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                Text("shutdown.message \(device.name)")
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                /* Konvention: links "Ja", rechts daneben "Nein", Buttons mittig */
                HStack(spacing: 8) {
                    Button {
                        state.confirmShutdown()
                    } label: {
                        Text("yes")
                            .font(.system(size: 15, weight: .semibold))
                            .frame(minWidth: 56)
                            .frame(minHeight: 44)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(red: 1.0, green: 0.27, blue: 0.23))

                    Button {
                        state.confirmDevice = nil
                    } label: {
                        Text("no")
                            .font(.system(size: 15, weight: .semibold))
                            .frame(minWidth: 56)
                            .frame(minHeight: 44)
                    }
                    .buttonStyle(.bordered)
                    .tint(.gray)
                }
            }
            .padding(14)
            .background(Color(white: 0.12), in: RoundedRectangle(cornerRadius: 18))
            .padding(.horizontal, 10)
        }
    }
}
