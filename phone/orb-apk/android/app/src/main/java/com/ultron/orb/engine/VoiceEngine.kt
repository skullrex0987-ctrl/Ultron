// ULTRON Android - VoiceEngine.kt
// Swappable wake-word and STT engine interface
// Default: Android SpeechRecognizer (offline) with fallback to Vosk

package com.ultron.orb.engine

import android.content.Context
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.RecognitionListener
import android.util.Log
import java.util.*

// Interface for swappable wake-word engines
interface WakeWordEngine {
    fun initialize(context: Context, wakeWord: String)
    fun startListening(callback: (String) -> Unit)
    fun stopListening()
    fun isListening(): Boolean
    fun setWakeWord(wakeWord: String)
    fun release()
}

// Interface for swappable STT engines
interface SttEngine {
    fun initialize(context: Context)
    fun startRecording(callback: (String) -> Unit)
    fun stopRecording()
    fun isRecording(): Boolean
    fun release()
}

// Default implementation using Android SpeechRecognizer (offline mode)
class AndroidWakeWordEngine : WakeWordEngine {
    private var speechRecognizer: SpeechRecognizer? = null
    private var isListining = false
    private var wakeWord = "ultron"
    private var currentCallback: ((String) -> Unit)? = null
    private var wakePhase = false
    private var commandBuffer = StringBuilder()
    
    override fun initialize(context: Context, wakeWord: String) {
        this.wakeWord = wakeWord
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
    }
    
    override fun startListening(callback: (String) -> Unit) {
        currentCallback = callback
        isListining = true
        wakePhase = false
        commandBuffer.clear()
        
        speechRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            
            override fun onError(error: Int) {
                if (isListining) {
                    restart()
                }
            }
            
            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (matches != null && matches.isNotEmpty()) {
                    handleRecognition(matches[0])
                }
            }
            
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        
        startWakeWordMode()
    }
    
    override fun stopListening() {
        isListining = false
        speechRecognizer?.stopListening()
    }
    
    override fun isListening(): Boolean = isListining
    
    override fun setWakeWord(wakeWord: String) {
        this.wakeWord = wakeWord
    }
    
    override fun release() {
        stopListening()
        speechRecognizer?.destroy()
        speechRecognizer = null
    }
    
    private fun startWakeWordMode() {
        wakePhase = false
        commandBuffer.clear()
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            }
        }
        speechRecognizer?.startListening(intent)
    }
    
    private fun startCommandMode() {
        wakePhase = true
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2000)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            }
        }
        speechRecognizer?.startListening(intent)
    }
    
    private fun handleRecognition(text: String) {
        val lower = text.lowercase(Locale.getDefault())
        
        if (!wakePhase) {
            // Looking for wake word
            if (lower.contains(wakeWord.lowercase())) {
                wakePhase = true
                commandBuffer.clear()
                startCommandMode()
            } else {
                restart()
            }
        } else {
            // Capturing command
            if (commandBuffer.isNotEmpty()) commandBuffer.append(" ")
            commandBuffer.append(text)
            
            if (isCommandComplete(text)) {
                currentCallback?.invoke(commandBuffer.toString().trim())
                commandBuffer.clear()
                wakePhase = false
                startWakeWordMode()
            } else {
                restart()
            }
        }
    }
    
    private fun isCommandComplete(text: String): Boolean {
        val stopWords = listOf("stop", "that's all", "done", "finish", "over and out", "thank you")
        return stopWords.any { text.lowercase().contains(it) }
    }
    
    private fun restart() {
        if (isListining) {
            if (wakePhase) {
                startCommandMode()
            } else {
                startWakeWordMode()
            }
        }
    }
}

// Fallback STT using Android SpeechRecognizer
class AndroidSttEngine : SttEngine {
    private var speechRecognizer: SpeechRecognizer? = null
    private var isRecording = false
    private var currentCallback: ((String) -> Unit)? = null
    
    override fun initialize(context: Context) {
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
    }
    
    override fun startRecording(callback: (String) -> Unit) {
        currentCallback = callback
        isRecording = true
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            }
        }
        
        speechRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onError(error: Int) { isRecording = false }
            
            override fun onResults(results: Bundle?) {
                isRecording = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                currentCallback?.invoke(matches?.firstOrNull() ?: "")
            }
            
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        
        speechRecognizer?.startListening(intent)
    }
    
    override fun stopRecording() {
        isRecording = false
        speechRecognizer?.stopListening()
    }
    
    override fun isRecording(): Boolean = isRecording
    
    override fun release() {
        speechRecognizer?.destroy()
        speechRecognizer = null
    }
}