// ULTRON Android - OrbView.kt
// 3D Orb with audio-reactive animation and gesture feedback

package com.ultron.orb.ui

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import kotlin.math.*

class OrbView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    enum class State {
        IDLE, LISTENING, THINKING, SPEAKING, ERROR
    }

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG)

    private var centerX = 0f
    private var centerY = 0f
    private var radius = 0f
    private var pulsePhase = 0f
    private var rotationAngle = 0f
    private var audioLevel = 0f
    private var gesturePulse = 0f

    private var state = State.IDLE
    private var orbColor = Color.parseColor("#ffaa30")
    private var glowColor = Color.parseColor("#ffcc66")

    private var onOrbClickListener: (() -> Unit)? = null

    private val animator = object : Runnable {
        override fun run() {
            updateAnimation()
            invalidate()
            postDelayed(this, 16) // ~60fps
        }
    }

    init {
        textPaint.color = Color.WHITE
        textPaint.textSize = 48f
        textPaint.textAlign = Paint.Align.CENTER
        textPaint.typeface = Typeface.DEFAULT_BOLD

        post(animator)
    }

    fun setOnOrbClickListener(listener: () -> Unit) {
        onOrbClickListener = listener
    }

    fun setState(newState: State) {
        state = newState
        when (state) {
            State.IDLE -> {
                orbColor = Color.parseColor("#ffaa30")
                glowColor = Color.parseColor("#ffcc66")
            }
            State.LISTENING -> {
                orbColor = Color.parseColor("#ffcc66")
                glowColor = Color.parseColor("#ffee88")
            }
            State.THINKING -> {
                orbColor = Color.parseColor("#66ccff")
                glowColor = Color.parseColor("#88ddff")
            }
            State.SPEAKING -> {
                orbColor = Color.parseColor("#66ff99")
                glowColor = Color.parseColor("#88ffbb")
            }
            State.ERROR -> {
                orbColor = Color.parseColor("#ff4444")
                glowColor = Color.parseColor("#ff6666")
            }
        }
    }

    fun setAudioLevel(level: Float) {
        audioLevel = level.coerceIn(0f, 1f)
    }

    fun pulseGesture() {
        gesturePulse = 1f
    }

    private fun updateAnimation() {
        pulsePhase += 0.05f
        rotationAngle += 1f
        if (rotationAngle > 360f) rotationAngle -= 360f

        // Decay gesture pulse
        if (gesturePulse > 0.001f) {
            gesturePulse *= 0.94f
        } else {
            gesturePulse = 0f
        }
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        centerX = w / 2f
        centerY = h / 2f
        radius = minOf(w, h) * 0.35f
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        val currentRadius = radius + (sin(pulsePhase) * 10f) + (audioLevel * 30f) + (gesturePulse * 50f)

        // Outer glow
        glowPaint.color = glowColor
        glowPaint.alpha = 80 + (audioLevel * 100).toInt() + (gesturePulse * 100).toInt()
        canvas.drawCircle(centerX, centerY, currentRadius * 1.5f, glowPaint)

        // Main orb
        paint.color = orbColor
        paint.style = Paint.Style.FILL
        canvas.drawCircle(centerX, centerY, currentRadius, paint)

        // Inner highlight
        paint.color = Color.WHITE
        paint.alpha = 100
        canvas.drawCircle(centerX - currentRadius * 0.3f, centerY - currentRadius * 0.3f, currentRadius * 0.2f, paint)

        // Rotation indicator for thinking state
        if (state == State.THINKING) {
            paint.color = Color.WHITE
            paint.alpha = 150
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 4f
            val sweepAngle = (rotationAngle * 3) % 360
            canvas.drawArc(
                centerX - currentRadius * 0.7f,
                centerY - currentRadius * 0.7f,
                centerX + currentRadius * 0.7f,
                centerY + currentRadius * 0.7f,
                sweepAngle.toFloat(),
                90f,
                false,
                paint
            )
        }

        // State text
        paint.style = Paint.Style.FILL
        paint.color = Color.WHITE
        paint.alpha = 200
        val stateText = when (state) {
            State.IDLE -> "TAP TO TALK"
            State.LISTENING -> "LISTENING..."
            State.THINKING -> "THINKING..."
            State.SPEAKING -> "SPEAKING..."
            State.ERROR -> "ERROR"
        }
        canvas.drawText(stateText, centerX, centerY + currentRadius + 60f, textPaint)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                parent?.requestDisallowInterceptTouchEvent(true)
                return true
            }
            MotionEvent.ACTION_UP -> {
                onOrbClickListener?.invoke()
                performClick()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }
}