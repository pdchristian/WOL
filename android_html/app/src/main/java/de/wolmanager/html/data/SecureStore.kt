package de.wolmanager.html.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Verschlüsselter Speicher für Geräte-Passwörter (Android Keystore).
 * devices.json bleibt dadurch frei von Klartext-Passwörtern.
 * Fällt die Erzeugung (Alpha-Bibliothek) aus, wird ein Klartext-Fallback genutzt,
 * damit die App nie abstürzt.
 */
class SecureStore(context: Context) {

    private val prefs: SharedPreferences = try {
        val key = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context, FILE_NAME, key,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    } catch (_: Exception) {
        context.getSharedPreferences(FILE_NAME_FALLBACK, Context.MODE_PRIVATE)
    }

    fun getPassword(deviceId: String): String = prefs.getString(key(deviceId), "") ?: ""

    fun setPassword(deviceId: String, password: String) {
        prefs.edit().putString(key(deviceId), password).apply()
    }

    fun removePassword(deviceId: String) {
        prefs.edit().remove(key(deviceId)).apply()
    }

    private fun key(deviceId: String) = "pw_$deviceId"

    companion object {
        private const val FILE_NAME = "wol_secure"
        private const val FILE_NAME_FALLBACK = "wol_secure_plain"
    }
}
