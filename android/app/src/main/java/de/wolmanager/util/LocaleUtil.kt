package de.wolmanager.util

import android.content.Context
import android.content.res.Configuration
import java.util.Locale as JLocale

/**
 * Sprachumschaltung ("" = System, sonst de/en/fr/es) — funktioniert ohne
 * Activity-Neustart über createConfigurationContext.
 */
object LocaleUtil {

    fun wrap(context: Context, language: String): Context {
        val target = when (language) {
            "de", "en", "fr", "es" -> JLocale(language)
            else -> return context
        }
        JLocale.setDefault(target)
        val config = Configuration(context.resources.configuration)
        config.setLocale(target)
        return context.createConfigurationContext(config)
    }
}
