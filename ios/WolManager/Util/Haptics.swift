import UIKit

/* Haptik — iOS-Äquivalent zu Vibrator (Android). Vibration ist auf iOS nur
   über Feedback-Generatoren möglich; die leichteste Taktile passt am besten. */
enum Haptics {

    private static let light = UIImpactFeedbackGenerator(style: .light)

    /// Kurzer Vibrations-Impuls (Bridge: vibrate {ms}). iOS kennt keine
    /// Dauersteuerung → fester leichter Impuls.
    static func vibrate(ms: Int = 12) {
        DispatchQueue.main.async {
            light.impactOccurred(intensity: ms >= 20 ? 1.0 : 0.6)
        }
    }
}
