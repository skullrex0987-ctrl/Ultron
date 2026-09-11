// ULTRON Android - VoiceManager.kt
// Central orchestrator for voice features: wake word, STT, TTS, message reading

package com.ultron.orb.manager

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.util.Log
import com.ultron.orb.engine.*
import com.ultron.orb.settings.VoiceSettings

class VoiceManager(
    private val context: Context,
    private val settings: VoiceSettings
) {
    
    private val wakeEngine: AndroidWakeWordEngine = AndroidWakeWordEngine()
    private val sttEngine: AndroidSttEngine = AndroidSttEngine()
    private val ttsEngine: TtsEngine = TtsEngine(context)
    private var isInitialized = false
    
    companion object {
        private const val TAG = "VoiceManager"
    }
    
    fun initialize() {
        if (isInitialized) return
        
        wakeEngine.initialize(context, settings.wakeWord)
        sttEngine.initialize(context)
        ttsEngine.initialize()
        
        isInitialized = true
        Log.d(TAG, "Voice manager initialized")
    }
    
    fun startWakeWord() {
        if (!isInitialized) return
        wakeEngine.startListening { command ->
            Log.d(TAG, "Voice command: $command")
            // Forward to agent via broadcast
            val intent = Intent("com.ultron.orb.VOICE_COMMAND").apply {
                putExtra("command", command)
            }
            context.sendBroadcast(intent)
        }
    }
    
    fun stopWakeWord() {
        wakeEngine.stopListening()
    }
    
    fun speak(text: String, callback: (() -> Unit)? = null) {
        if (!settings.ttsEnabled) return
        ttsEngine.speak(text, callback)
    }
    
    fun speakQueued(text: String) {
        ttsEngine.speakQueued(text)
    }
    
    fun replayLast() {
        ttsEngine.replayLast()
    }
    
    fun stopSpeaking() {
        ttsEngine.stop()
    }
    
    fun isSpeaking(): Boolean = ttsEngine.isSpeaking()
    
    fun getLastSpokenText(): String = ttsEngine.getLastSpokenText()
    
    fun stripMarkdown(text: String): String = ttsEngine.stripMarkdown(text)
    
    fun release() {
        wakeEngine.release()
        sttEngine.release()
        ttsEngine.release()
        isInitialized = false
    }
}