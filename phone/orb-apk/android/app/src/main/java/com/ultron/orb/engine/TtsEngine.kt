// ULTRON Android - TtsEngine.kt
// Text-to-speech with markdown stripping, queuing, and replay support

package com.ultron.orb.engine

import android.content.Context
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.*

class TtsEngine(private val context: Context) {
    
    private var tts: TextToSpeech? = null
    private var isInitialized = false
    private var lastSpokenText = ""
    private var speakCallback: (() -> Unit)? = null
    
    companion object {
        private const val TAG = "TtsEngine"
        private const val UTTERANCE_ID = "ultron_tts"
    }
    
    fun initialize() {
        tts = TextToSpeech(context) { status ->
            isInitialized = (status == TextToSpeech.SUCCESS)
            if (isInitialized) {
                tts?.language = Locale.getDefault()
                // Set up completion listener
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                    tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                        override fun onStart(utteranceId: String?) {}
                        override fun onDone(utteranceId: String?) {
                            if (utteranceId == UTTERANCE_ID) {
                                speakCallback?.invoke()
                            }
                        }
                        override fun onError(utteranceId: String?) {}
                    })
                }
                Log.d(TAG, "TTS initialized")
            }
        }
    }
    
    fun speak(text: String, callback: (() -> Unit)? = null) {
        if (!isInitialized) {
            Log.w(TAG, "TTS not initialized")
            return
        }
        
        val cleanText = stripMarkdown(text)
        lastSpokenText = cleanText
        speakCallback = callback
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, UTTERANCE_ID)
        } else {
            @Suppress("DEPRECATION")
            tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null)
        }
    }
    
    fun speakQueued(text: String) {
        if (!isInitialized) return
        val cleanText = stripMarkdown(text)
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            tts?.speak(cleanText, TextToSpeech.QUEUE_ADD, null, null)
        } else {
            @Suppress("DEPRECATION")
            tts?.speak(cleanText, TextToSpeech.QUEUE_ADD, null)
        }
    }
    
    fun replayLast() {
        if (lastSpokenText.isNotEmpty()) {
            speak(lastSpokenText)
        }
    }
    
    fun getLastSpokenText(): String = lastSpokenText
    
    fun stop() {
        tts?.stop()
    }
    
    fun isSpeaking(): Boolean {
        return tts?.isSpeaking ?: false
    }
    
    fun release() {
        tts?.stop()
        tts?.shutdown()
        tts = null
    }
    
    fun stripMarkdown(text: String): String {
        return text
            // Remove code blocks
            .replace(Regex("```[\\s\\S]*?```"), "")
            .replace(Regex("`[^`]+`"), "")
            // Remove bold/italic
            .replace(Regex("\\*\\*\\*([^*]+)\\*\\*\\*"), "$1")
            .replace(Regex("\\*\\*([^*]+)\\*\\*"), "$1")
            .replace(Regex("\\*([^*]+)\\*"), "$1")
            .replace(Regex("___([^_]+)___"), "$1")
            .replace(Regex("__([^_]+)__"), "$1")
            .replace(Regex("_([^_]+)_"), "$1")
            // Remove headers
            .replace(Regex("^#{1,6}\\s+", RegexOption.MULTILINE), "")
            // Remove links (keep text)
            .replace(Regex("\\[([^\\]]+)\\]\\([^)]+\\)"), "$1")
            // Remove images
            .replace(Regex("!\\[[^\\]]*\\]\\([^)]+\\)"), "")
            // Remove blockquotes
            .replace(Regex("^>\\s+", RegexOption.MULTILINE), "")
            // Remove code fences
            .replace(Regex("^```.*$", RegexOption.MULTILINE), "")
            .replace(Regex("^\\s*[-*+]\\s+", RegexOption.MULTILINE), "")
            // Remove horizontal rules
            .replace(Regex("^---+\$", RegexOption.MULTILINE), "")
            // Remove strikethrough
            .replace(Regex("~~([^~]+)~~"), "$1")
            // Collapse whitespace
            .replace(Regex("\\n{3,}"), "\n\n")
            .trim()
    }
}