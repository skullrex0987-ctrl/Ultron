package com.ultron.floatwidget

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.os.IBinder
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageView

/** Draggable floating bubble. Tap=open HUD, Hold=talk (Vosk started by agent). */
class FloatingService : Service() {
    private lateinit var wm: WindowManager
    private lateinit var bubble: ImageView

    override fun onBind(i: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        bubble = ImageView(this).apply { setImageResource(android.R.drawable.ic_menu_compass) }
        val params = WindowManager.LayoutParams(
            120, 120, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.START; x = 50; y = 200 }

        var downX = 0f; var downY = 0f; var held = false
        bubble.setOnTouchListener { v, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> { downX = e.rawX; downY = e.rawY; held = true; true }
                MotionEvent.ACTION_MOVE -> {
                    params.x = (e.rawX - downX).toInt(); params.y = (e.rawY - downY).toInt()
                    wm.updateViewLayout(bubble, params); true
                }
                MotionEvent.ACTION_UP -> {
                    if (held) {
                        // tap vs hold decided by duration in real impl; here open HUD on tap
                        startActivity(Intent(this, MainActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    }
                    true
                }
                else -> false
            }
        }
        wm.addView(bubble, params)
    }

    override fun onDestroy() { super.onDestroy(); if (::bubble.isInitialized) wm.removeView(bubble) }
}
