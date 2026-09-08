import Foundation
import Security

/*
 * Verschlüsselter Speicher für Geräte-Passwörter (iOS Keychain).
 * devices.json bleibt dadurch frei von Klartext-Passwörtern.
 * Analog zu SecureStore.kt (Android: EncryptedSharedPreferences).
 */
final class SecureStore {

    private let service = "de.wolmanager.device"

    func getPassword(deviceId: String) -> String {
        var query: [String: Any] = baseQuery(deviceId)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return "" }
        return String(data: data, encoding: .utf8) ?? ""
    }

    func setPassword(deviceId: String, password: String) {
        if password.isEmpty {
            removePassword(deviceId: deviceId)
            return
        }
        let data = Data(password.utf8)
        var query: [String: Any] = baseQuery(deviceId)
        let attributes: [String: Any] = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            query[kSecValueData as String] = data
            SecItemAdd(query as CFDictionary, nil)
        }
    }

    func removePassword(deviceId: String) {
        SecItemDelete(baseQuery(deviceId) as CFDictionary)
    }

    private func baseQuery(_ deviceId: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: "pw_\(deviceId)",
            // Nach dem ersten Entsperren verfügbar (Wecker ohne UI), gerätegebunden.
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
    }
}
