// ULTRON Orb - MessageReaderService.kt
// Reads incoming notifications aloud via TTS
// Has built-in denylist for banking/OTP apps

package com.ultron.orb.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Build
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import androidx.core.app.NotificationCompat
import java.util.*

class MessageReaderService : NotificationListenerService() {

    private var tts: TextToSpeech? = null
    private lateinit var prefs: SharedPreferences
    private val messageBuffer = LinkedList<String>()
    private var lastSpokenText = ""
    
    companion object {
        private const val TAG = "MessageReader"
        private const val MAX_BUFFER_SIZE = 50
        private const val PREFS_NAME = "ultron_message_reader"
        private const val KEY_ALLOWED_APPS = "allowed_apps"
        private const val KEY_ENABLED = "reader_enabled"
        private const val CHANNEL_ID = "ultron_message_reader"
        
        // Default denylist for sensitive apps
        val DEFAULT_BLOCKED_APPS = setOf(
            // Banking apps
            "com.google.android.apps.walletnfcrel",  // Google Wallet
            "com.sbi",  // SBI
            "com.hdfc",  // HDFC
            "com.icici", // ICICI
            "com.paypal.android", // PayPal
            "com.yono", // YONO
            "com.axis", // Axis
            "com.citi", // Citibank
            "com.kotak", // Kotak
            "com.indusind", // IndusInd
            
            // OTP/2FA
            "com.google.android.apps.authenticator2",  // Google Authenticator
            "com.authy", // Authy
            "com.azure.authenticator", // Microsoft Authenticator
            "com.lastpass.authenticator", // LastPass Authenticator
            "com.twilio.authy", // Twilio Authy
            
            // Password managers
            "com.lastpass.lpandroid", // LastPass
            "com.1password.android", // 1Password
            "com.dashlane", // Dashlane
            "com.bitwarden", // Bitwarden
            "com.iproov", // iProov
            
            // Payment
            "com.google.android.apps.nbu.paisa.user", // Google Pay
            "com.apple.android.mobilepayment", // Apple Pay
            "com.phonepe.app", // PhonePe
            "net.one97.paytm", // Paytm
            "com.amazon.mShop.android.shopping", // Amazon
            
            // SMS apps (often contain OTPs)
            "com.google.android.apps.messaging", // Messages
            "com.android.mms", // Default SMS
        )
        
        fun isEnabled(context: Context): Boolean {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            return prefs.getBoolean(KEY_ENABLED, false)
        }
        
        fun setEnabled(context: Context, enabled: Boolean) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit().putBoolean(KEY_ENABLED, enabled).apply()
        }
        
        fun getAllowedApps(context: Context): Set<String> {
            return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getStringSet(KEY_ALLOWED_APPS, emptySet()) ?: emptySet()
        }
        
        fun setAllowedApps(context: Context, apps: Set<String>) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit().putStringSet(KEY_ALLOWED_APPS, apps).apply()
        }
    }
    
    override fun onCreate() {
        super.onCreate()
        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        
        // Initialize TTS
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.getDefault()
                Log.d(TAG, "TTS initialized")
            }
        }
    }
    
    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null || !prefs.getBoolean(KEY_ENABLED, false)) return
        
        val packageName = sbn.packageName
        
        // Check if app is in denylist
        if (isSensitiveApp(packageName, sbn.notification)) {
            Log.d(TAG, "Skipping sensitive notification from $packageName")
            return
        }
        
        // Check if app is in allowed list
        val allowedApps = prefs.getStringSet(KEY_ALLOWED_APPS, emptySet()) ?: emptySet()
        if (allowedApps.isNotEmpty() && packageName !in allowedApps) {
            return
        }
        
        // Extract notification text
        val notification = sbn.notification
        val extras = notification.extras
        
        val title = extras.getString(Notification.EXTRA_TITLE, "")
        val text = extras.getString(Notification.EXTRA_TEXT, "")
        
        if (text.isNullOrEmpty()) return
        
        // Skip OTP patterns
        if (isOTP(text)) {
            Log.d(TAG, "Skipping OTP notification")
            return
        }
        
        // Build spoken message
        val spoken = if (title.isNotEmpty()) {
            "New message from $title: $text"
        } else {
            text
        }
        
        // Add to buffer
        messageBuffer.add(spoken)
        while (messageBuffer.size > MAX_BUFFER_SIZE) {
            messageBuffer.removeFirst()
        }
        
        // Speak it
        speakText(spoken)
    }
    
    override fun onNotificationRemoved(sbn: StatusBarNotification?) {}
    
    fun speakText(text: String) {
        lastSpokenText = text
        
        // Strip markdown
        val cleanText = text
            .replace(Regex("[*#_`~\\[\\]()>|]"), "")
            .replace(Regex("\\n+"), " ")
            .trim()
        
        tts?.let {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                it.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, "ultron_tts")
            } else {
                // Legacy
                @Suppress("DEPRECATION")
                it.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null)
            }
        }
    }
    
    fun repeatLast() {
        if (lastSpokenText.isNotEmpty()) {
            speakText(lastSpokenText)
        }
    }
    
    fun getRecentMessages(count: Int = 5): List<String> {
        return messageBuffer.takeLast(count)
    }
    
    private fun isSensitiveApp(packageName: String, notification: Notification): Boolean {
        // Check if package is in denylist
        if (packageName in DEFAULT_BLOCKED_APPS) {
            return true
        }
        
        // Check notification extras for OTP patterns
        val extras = notification.extras ?: return false
        
        // Check if it's an OTP message
        val text = extras.getString(Notification.EXTRA_TEXT, "") ?: ""
        val title = extras.getString(Notification.EXTRA_TITLE, "") ?: ""
        
        return isOTP(text) || isOTP(title) || 
               text.contains(Regex("\\b\\d{4,8}\\b"))  // Any message with 4-8 digit code
    }
    
    private fun isOTP(text: String): Boolean {
        val otpPatterns = listOf(
            Regex("OTP|otp|One.?Time.?Password", RegexOption.IGNORE_CASE),
            Regex("verification.?code", RegexOption.IGNORE_CASE),
            Regex("security.?code", RegexOption.IGNORE_CASE),
            Regex("2FA|two.?factor", RegexOption.IGNORE_CASE),
            Regex("login.?code", RegexOption.IGNORE_CASE),
            Regex("\\b\\d{4,8}\\b.*(?:valid|expires?|minutes?|secure)", RegexOption.IGNORE_CASE),
            Regex("(?:valid|expires?|minutes?|secure).*\\b\\d{4,8}\\b", RegexOption.IGNORE_CASE),
        )
        return otpPatterns.any { it.containsMatchIn(text) }
    }
    
    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }
}