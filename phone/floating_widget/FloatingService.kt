package com.ultron.floatwidget

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.net.Uri
import android.os.IBinder
import android.os.SystemClock
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import java.net.HttpURLConnection
import java.net.URL

/**
 * Draggable floating bubble for ULTRON (no root).
 *  - TAP  -> open the orb HUD (phone web UI at http://127.0.0.1:8080)
 *  - HOLD -> tell the agent to start listening (POST talk -> agent WS :8081,
 *           which triggers Vosk STT on the phone)
 */
class FloatingService : Service() {
    private lateinit var wm: WindowManager
    private lateinit var bubble: ImageView
    private var downTime = 0L
    private val HOLD_MS = 600L

    override fun onBind(i: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        bubble = ImageView(this).apply { setImageResource(android.R.drawable.ic_menu_compass) }
        val params = WindowManager.LayoutParams(
            120, 120, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.START; x = 50; y = 200 }

        var downX = 0f; var downY = 0f
        bubble.setOnTouchListener { v, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> { downX = e.rawX; downY = e.rawY; downTime = SystemClock.uptimeMillis(); true }
                MotionEvent.ACTION_MOVE -> {
                    params.x = (e.rawX - downX).toInt(); params.y = (e.rawY - downY).toInt()
                    wm.updateViewLayout(bubble, params); true
                }
                MotionEvent.ACTION_UP -> {
                    val held = SystemClock.uptimeMillis() - downTime >= HOLD_MS
                    if (held) {
                        // HOLD -> ask the agent to start listening (Vosk STT)
                        Thread { signalAgent("talk") }.start()
                    } else {
                        // TAP -> open the orb HUD in the default browser
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:8080"))
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        startActivity(intent)
                    }
                    true
                }
                else -> false
            }
        }
        wm.addView(bubble, params)
    }

    /** Notify the phone agent (FastAPI :8080 / WS :8081) to begin STT. */
    private fun signalAgent(signal: String) {
        try {
            val url = URL("http://127.0.0.1:8080/talk")
            val c = url.openConnection() as HttpURLConnection
            c.requestMethod = "POST"; c.doOutput = true
            c.outputStream.use { it.write(signal.toByteArray()) }
            c.responseCode
            c.disconnect()
        } catch (_: Exception) { /* agent not running; ignore */ }
    }

    override fun onDestroy() { super.onDestroy(); if (::bubble.isInitialized) wm.removeView(bubble) }
}
