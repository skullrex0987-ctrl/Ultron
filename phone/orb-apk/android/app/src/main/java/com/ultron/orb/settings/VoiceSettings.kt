// ULTRON Android - VoiceSettings.kt
// Settings for voice wake word, TTS, message reading, and denylist

package com.ultron.orb.settings

import android.content.Context
import android.content.SharedPreferences

class VoiceSettings(context: Context) {
    
    private val prefs: SharedPreferences = context.getSharedPreferences("ultron_voice_settings", Context.MODE_PRIVATE)
    
    companion object {
        const val KEY_WAKE_WORD = "wake_word"
        const val KEY_WAKE_ENABLED = "wake_enabled"
        const val KEY_TTS_ENABLED = "tts_enabled"
        const val KEY_VOICE_ONLY_MODE = "voice_only_mode"
        const val KEY_MESSAGE_READER_ENABLED = "message_reader_enabled"
        const val KEY_MESSAGE_APP_WHITELIST = "message_app_whitelist"
        const val KEY_NOTIFICATION_DENYLIST = "notification_denylist"
        const val KEY_REPLAY_BUFFER_SIZE = "replay_buffer_size"
    }
    
    // Wake word
    var wakeWord: String
        get() = prefs.getString(KEY_WAKE_WORD, "ultron") ?: "ultron"
        set(value) { prefs.edit().putString(KEY_WAKE_WORD, value).apply() }
    
    var wakeEnabled: Boolean
        get() = prefs.getBoolean(KEY_WAKE_ENABLED, false)  // Default: off (privacy)
        set(value) { prefs.edit().putBoolean(KEY_WAKE_ENABLED, value).apply() }
    
    // TTS
    var ttsEnabled: Boolean
        get() = prefs.getBoolean(KEY_TTS_ENABLED, true)
        set(value) { prefs.edit().putBoolean(KEY_TTS_ENABLED, value).apply() }
    
    var voiceOnlyMode: Boolean
        get() = prefs.getBoolean(KEY_VOICE_ONLY_MODE, false)
        set(value) { prefs.edit().putBoolean(KEY_VOICE_ONLY_MODE, value).apply() }
    
    // Message reading
    var messageReaderEnabled: Boolean
        get() = prefs.getBoolean(KEY_MESSAGE_READER_ENABLED, false)  // Default: off
        set(value) { prefs.edit().putBoolean(KEY_MESSAGE_READER_ENABLED, value).apply() }
    
    var allowedAppsForReading: Set<String>
        get() = prefs.getStringSet(KEY_MESSAGE_APP_WHITELIST, emptySet()) ?: emptySet()
        set(value) { prefs.edit().putStringSet(KEY_MESSAGE_APP_WHITELIST, value).apply() }
    
    // Denylist for sensitive apps
    var blockedAppOverrides: Set<String>
        get() = prefs.getStringSet(KEY_NOTIFICATION_DENYLIST, emptySet()) ?: emptySet()
        set(value) { prefs.edit().putStringSet(KEY_NOTIFICATION_DENYLIST, value).apply() }
    
    var replayBufferSize: Int
        get() = prefs.getInt(KEY_REPLAY_BUFFER_SIZE, 10)
        set(value) { prefs.edit().putInt(KEY_REPLAY_BUFFER_SIZE, value).apply() }
    
    fun isAppAllowedForReading(packageName: String): Boolean {
        val allowed = allowedAppsForReading
        if (allowed.isEmpty()) return false  // Default: none allowed
        return packageName in allowed
    }
    
    fun addAllowedApp(packageName: String) {
        val apps = allowedAppsForReading.toMutableSet()
        apps.add(packageName)
        allowedAppsForReading = apps
    }
    
    fun removeAllowedApp(packageName: String) {
        val apps = allowedAppsForReading.toMutableSet()
        apps.remove(packageName)
        allowedAppsForReading = apps
    }
}