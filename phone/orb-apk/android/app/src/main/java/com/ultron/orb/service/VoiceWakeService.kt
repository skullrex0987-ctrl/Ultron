// ULTRON Orb - VoiceWakeService.kt
// Foreground service for always-on wake word detection (screen on/off)
// Uses Android SpeechRecognizer in offline mode for wake word + command

package com.ultron.orb.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.RecognitionListener
import android.util.Log
import androidx.core.app.NotificationCompat
import com.ultron.orb.MainActivity
import java.io.*
import java.util.*

class VoiceWakeService : Service() {

    private lateinit var prefs: SharedPreferences
    private var speechRecognizer: SpeechRecognizer? = null
    private var isListening = false
    private var wakeWordDetected = false
    private var pendingCommand = StringBuilder()
    
    companion object {
        private const val TAG = "VoiceWakeService"
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "ultron_voice"
        
        const val ACTION_START = "com.ultron.orb.action.START_VOICE"
        const val ACTION_STOP = "com.ultron.orb.action.STOP_VOICE"
        const val ACTION_TOGGLE = "com.ultron.orb.action.TOGGLE_VOICE"
        
        fun isRunning(context: Context): Boolean {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? android.app.ActivityManager
            am?.let {
                for (service in it.getRunningServices(Integer.MAX_VALUE)) {
                    if (service.service.className == VoiceWakeService::class.java.name) {
                        return true
                    }
                }
            }
            return false
        }
        
        fun start(context: Context) {
            val intent = Intent(context, VoiceWakeService::class.java).apply {
                action = ACTION_START
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
        
        fun stop(context: Context) {
            context.stopService(Intent(context, VoiceWakeService::class.java))
        }
    }
    
    override fun onCreate() {
        super.onCreate()
        prefs = getSharedPreferences("ultron_voice", Context.MODE_PRIVATE)
        createNotificationChannel()
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startListening()
            ACTION_STOP -> stopListening()
            ACTION_TOGGLE -> {
                if (isListening) stopListening() else startListening()
            }
        }
        return START_STICKY
    }
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "ULTRON Voice",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Always-on voice wake word detection"
                setShowBadge(false)
            }
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }
    
    private fun startListening() {
        if (isListening) return
        isListening = true
        
        val notification = createNotification()
        startForeground(NOTIFICATION_ID, notification)
        
        // Start SpeechRecognizer in offline mode for wake word detection
        startWakeWordDetection()
        
        Log.d(TAG, "Voice wake service started")
    }
    
    private fun stopListening() {
        isListening = false
        speechRecognizer?.stopListening()
        speechRecognizer?.destroy()
        speechRecognizer = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
        Log.d(TAG, "Voice wake service stopped")
    }
    
    private fun createNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("ULTRON is listening")
            .setContentText("Say 'ultron' to activate")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
    
    private fun startWakeWordDetection() {
        try {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)
            
            speechRecognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    Log.d(TAG, "Ready for speech")
                }
                
                override fun onBeginningOfSpeech() {
                    Log.d(TAG, "Beginning of speech")
                }
                
                override fun onRmsChanged(rmsdB: Float) {
                    // Send audio level to orb
                    sendAudioLevel(rmsdB / 100f)
                }
                
                override fun onBufferReceived(buffer: ByteArray?) {}
                
                override fun onEndOfSpeech() {
                    Log.d(TAG, "End of speech")
                    if (wakeWordDetected) {
                        // Command capture ended - process it
                        processPendingCommand()
                    }
                }
                
                override fun onError(error: Int) {
                    val errorMsg = when (error) {
                        SpeechRecognizer.ERROR_NO_MATCH -> "no match"
                        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "timeout"
                        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "busy"
                        SpeechRecognizer.ERROR_CLIENT -> "client error"
                        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "no permission"
                        SpeechRecognizer.ERROR_NETWORK -> "network"
                        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "network timeout"
                        SpeechRecognizer.ERROR_AUDIO -> "audio error"
                        SpeechRecognizer.ERROR_SERVER -> "server error"
                        SpeechRecognizer.ERROR_TOO_MANY_REQUESTS -> "too many"
                        SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED -> "language not supported"
                        else -> "unknown"
                    }
                    Log.e(TAG, "Speech error: $errorMsg")
                    
                    // Restart listening after error
                    if (isListening) {
                        restartWakeWordDetection()
                    }
                }
                
                override fun onResults(results: Bundle?) {
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (matches != null && matches.isNotEmpty()) {
                        val text = matches[0].lowercase(Locale.getDefault())
                        Log.d(TAG, "Recognized: '$text'")
                        
                        if (!wakeWordDetected) {
                            // Check for wake word
                            if (text.contains("ultron")) {
                                wakeWordDetected = true
                                onWakeWordDetected()
                            }
                        } else {
                            // Capture command after wake word
                            if (text.isNotEmpty()) {
                                if (pendingCommand.isNotEmpty()) pendingCommand.append(" ")
                                pendingCommand.append(text)
                                
                                // Check for stop conditions
                                if (isCommandComplete(text)) {
                                    processPendingCommand()
                                } else {
                                    // Continue listening for more
                                    restartListeningForCommand()
                                }
                            }
                        }
                    }
                }
                
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            
            // Start continuous listening
            restartWakeWordDetection()
            
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start wake word detection", e)
        }
    }
    
    private fun restartWakeWordDetection() {
        wakeWordDetected = false
        pendingCommand.clear()
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 30000)
            
            // Prefer offline recognition
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            }
        }
        
        speechRecognizer?.startListening(intent)
    }
    
    private fun restartListeningForCommand() {
        wakeWordDetected = true  // Keep wake word state
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2000)
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            }
        }
        
        speechRecognizer?.startListening(intent)
    }
    
    private fun onWakeWordDetected() {
        Log.d(TAG, "Wake word 'ultron' detected!")
        
        // Update notification
        updateNotification("Listening for command...")
        
        // Notify the UI via broadcast
        val broadcast = Intent("com.ultron.orb.WAKE_WORD_DETECTED")
        sendBroadcast(broadcast)
        
        // Prepare for command capture
        pendingCommand.clear()
    }
    
    private fun isCommandComplete(text: String): Boolean {
        val stopWords = listOf("stop", "that's all", "done", "finish", "over and out", "thank you")
        return stopWords.any { text.contains(it) }
    }
    
    private fun processPendingCommand() {
        val command = pendingCommand.toString().trim()
        pendingCommand.clear()
        wakeWordDetected = false
        
        if (command.isNotEmpty()) {
            Log.d(TAG, "Processing command: '$command'")
            
            // Send command to agent via WebSocket
            val broadcast = Intent("com.ultron.orb.VOICE_COMMAND").apply {
                putExtra("command", command)
            }
            sendBroadcast(broadcast)
            
            // Reset for next wake word
            updateNotification("ULTRON is listening")
            restartWakeWordDetection()
        } else {
            restartWakeWordDetection()
        }
    }
    
    private fun sendAudioLevel(level: Float) {
        val broadcast = Intent("com.ultron.orb.AUDIO_LEVEL").apply {
            putExtra("level", level)
        }
        sendBroadcast(broadcast)
    }
    
    private fun updateNotification(text: String) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("ULTRON")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        
        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(NOTIFICATION_ID, notification)
    }
    
    override fun onDestroy() {
        stopListening()
        super.onDestroy()
    }
}