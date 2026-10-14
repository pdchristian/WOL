import SwiftUI

/*
 * Bestätigung vor dem Starten eines Batches — zentrierte Karte im Stil der
 * Shutdown-Abfrage (Play-Icon, große Ja/Nein-Buttons). "Ja" löst die Ausführung
 * auf dem iPhone aus; das Ergebnis meldet der iPhone-Dispatcher später per
 * Toast (ein Batch kann Minuten laufen).
 */
struct BatchRunConfirmView: View {
    @EnvironmentObject var state: AppState
    let pending: AppState.PendingBatch

    var body: some View {
        ZStack {
            Color.black.opacity(0.85).ignoresSafeArea()
            VStack(spacing: 10) {
                Image(systemName: "play.fill")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundStyle(.teal)
                    .frame(width: 48, height: 48)
                    .background(Color.teal.opacity(0.15), in: Circle())
                Text("batch.run.title")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                Text(String(format: L10n.key("batch.run.message"),
                            pending.batch.name, pending.deviceName))
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                /* Konvention: links "Ja", rechts daneben "Nein", Buttons mittig */
                HStack(spacing: 8) {
                    Button {
                        state.confirmRunBatch()
                    } label: {
                        Text("yes")
                            .font(.system(size: 15, weight: .semibold))
                            .frame(minWidth: 56)
                            .frame(minHeight: 44)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.teal)

                    Button {
                        state.confirmBatch = nil
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
