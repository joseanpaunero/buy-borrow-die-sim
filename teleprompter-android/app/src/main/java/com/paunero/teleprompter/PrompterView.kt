package com.paunero.teleprompter

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import android.graphics.Shader
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.util.AttributeSet
import android.util.TypedValue
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/**
 * Vista de teleprompter: el texto se desplaza hacia arriba a velocidad constante.
 *
 * La "línea de lectura" está pegada al borde superior, que es el que queda más cerca
 * de la cámara frontal cuando la vista se coloca arriba del todo. Las líneas siguientes
 * se desvanecen hacia abajo para que la mirada no tenga motivo para bajar.
 *
 * Gestos: un toque pausa/reanuda; arrastrar desplaza el texto a mano.
 */
class PrompterView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : View(context, attrs, defStyleAttr) {

    interface Listener {
        fun onPlayStateChanged(playing: Boolean) {}
        fun onFinished() {}
        fun onCountdownTick(remaining: Int) {}
    }

    var listener: Listener? = null

    private val density = resources.displayMetrics.density

    private val textPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        typeface = Typeface.DEFAULT_BOLD
    }
    private val markerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = MARKER_COLOR }
    private val countdownPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        typeface = Typeface.DEFAULT_BOLD
        textAlign = Paint.Align.CENTER
    }
    private val fadePaint = Paint().apply { xfermode = PorterDuffXfermode(PorterDuff.Mode.DST_IN) }
    private val markerPath = Path()

    private var layout: StaticLayout? = null
    private var offset = 0f
    private var lastFrameNs = 0L
    private var countdownRemaining = 0

    var playing = false
        private set

    val isCountingDown: Boolean get() = countdownRemaining > 0

    var text: String = ""
        set(value) {
            if (field == value) return
            field = value
            rebuildLayout(keepProgress = false)
        }

    var textSizeSp: Float = 22f
        set(value) {
            if (field == value) return
            field = value
            applyTextSize()
            rebuildLayout(keepProgress = true)
            requestLayout()
        }

    /** Velocidad en dp por segundo. */
    var speedDpPerSec: Float = 40f

    var lineSpacingMult: Float = 1.2f
        set(value) {
            if (field == value) return
            field = value
            rebuildLayout(keepProgress = true)
            requestLayout()
        }

    /** Invierte horizontalmente el texto (para cristales de teleprompter). */
    var mirror: Boolean = false
        set(value) {
            field = value
            invalidate()
        }

    var showMarker: Boolean = true
        set(value) {
            field = value
            invalidate()
        }

    /** Líneas visibles cuando la altura no viene impuesta por el padre. */
    var visibleLines: Int = 3
        set(value) {
            field = value.coerceAtLeast(1)
            requestLayout()
        }

    /** Segundos de cuenta atrás antes de arrancar; 0 desactiva la cuenta atrás. */
    var countdownSeconds: Int = 3

    var alignCenter: Boolean = true
        set(value) {
            if (field == value) return
            field = value
            rebuildLayout(keepProgress = true)
        }

    /** Altura de una línea en píxeles con el tamaño de letra actual. */
    val lineHeightPx: Int
        get() {
            val fm = textPaint.fontMetrics
            return ceil((fm.descent - fm.ascent) * lineSpacingMult).toInt()
        }

    private val topFadePx: Float get() = lineHeightPx * TOP_FADE_LINES

    /** Progreso de lectura 0..1. */
    val progress: Float
        get() {
            val max = maxOffset()
            return if (max > 0f) (offset / max).coerceIn(0f, 1f) else 0f
        }

    private val gestures = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
        override fun onDown(e: MotionEvent): Boolean = true

        override fun onSingleTapUp(e: MotionEvent): Boolean {
            performClick()
            togglePlay()
            return true
        }

        override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
            if (playing) pause()
            cancelCountdown()
            offset = (offset + distanceY).coerceIn(0f, maxOffset())
            invalidate()
            return true
        }
    })

    private val ticker = object : Runnable {
        override fun run() {
            if (!playing) return
            val now = System.nanoTime()
            val dt = (now - lastFrameNs) / 1_000_000_000f
            lastFrameNs = now
            offset += speedDpPerSec * density * dt
            val max = maxOffset()
            if (offset >= max) {
                offset = max
                invalidate()
                pause()
                listener?.onFinished()
                return
            }
            invalidate()
            postOnAnimation(this)
        }
    }

    private val countdownTick = object : Runnable {
        override fun run() {
            countdownRemaining--
            listener?.onCountdownTick(countdownRemaining)
            if (countdownRemaining <= 0) {
                countdownRemaining = 0
                play()
            } else {
                invalidate()
                postDelayed(this, 1000L)
            }
        }
    }

    init {
        applyTextSize()
    }

    /** Altura total necesaria para mostrar [lines] líneas con el tamaño actual. */
    fun heightForLines(lines: Int): Int =
        paddingTop + paddingBottom + ceil(topFadePx).toInt() + lines * lineHeightPx

    fun play() {
        cancelCountdown()
        if (playing) return
        val max = maxOffset()
        if (max > 0f && offset >= max) offset = 0f
        playing = true
        lastFrameNs = System.nanoTime()
        postOnAnimation(ticker)
        listener?.onPlayStateChanged(true)
    }

    fun pause() {
        cancelCountdown()
        if (!playing) return
        playing = false
        removeCallbacks(ticker)
        listener?.onPlayStateChanged(false)
    }

    /** Un toque: pausa si está en marcha, cancela la cuenta atrás si la hay, o arranca. */
    fun togglePlay() {
        when {
            isCountingDown -> cancelCountdown()
            playing -> pause()
            countdownSeconds > 0 -> startCountdown()
            else -> play()
        }
    }

    fun restart() {
        pause()
        offset = 0f
        invalidate()
    }

    fun startCountdown() {
        if (playing) return
        if (countdownSeconds <= 0) {
            play()
            return
        }
        removeCallbacks(countdownTick)
        countdownRemaining = countdownSeconds
        listener?.onCountdownTick(countdownRemaining)
        invalidate()
        postDelayed(countdownTick, 1000L)
    }

    private fun cancelCountdown() {
        if (countdownRemaining > 0) {
            countdownRemaining = 0
            removeCallbacks(countdownTick)
            invalidate()
        }
    }

    private fun applyTextSize() {
        textPaint.textSize = TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_SP, textSizeSp, resources.displayMetrics
        )
    }

    private fun maxOffset(): Float {
        val l = layout ?: return 0f
        if (l.lineCount == 0) return 0f
        return l.getLineTop(l.lineCount - 1).toFloat()
    }

    private fun rebuildLayout(keepProgress: Boolean) {
        val availW = width - paddingLeft - paddingRight
        if (availW <= 0) {
            layout = null
            return
        }
        val prevProgress = if (keepProgress) progress else 0f
        val src = text.ifBlank { context.getString(R.string.empty_script_placeholder) }
        layout = StaticLayout.Builder.obtain(src, 0, src.length, textPaint, availW)
            .setAlignment(if (alignCenter) Layout.Alignment.ALIGN_CENTER else Layout.Alignment.ALIGN_NORMAL)
            .setLineSpacing(0f, lineSpacingMult)
            .setIncludePad(false)
            .build()
        offset = prevProgress * maxOffset()
        invalidate()
    }

    private fun buildFade() {
        val h = height.toFloat()
        if (h <= 0f) return
        val top = paddingTop.toFloat()
        val bottom = (height - paddingBottom).toFloat()
        val readY = top + topFadePx
        val bottomFade = min(lineHeightPx * BOTTOM_FADE_LINES, max(0f, (bottom - readY) - lineHeightPx))
        val colors = intArrayOf(0x00FFFFFF, Color.WHITE, Color.WHITE, 0x00FFFFFF)
        val positions = floatArrayOf(
            top / h,
            readY / h,
            (bottom - bottomFade) / h,
            bottom / h,
        )
        fadePaint.shader = LinearGradient(0f, 0f, 0f, h, colors, positions, Shader.TileMode.CLAMP)
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val wMode = MeasureSpec.getMode(widthMeasureSpec)
        val w = if (wMode == MeasureSpec.UNSPECIFIED) (300 * density).toInt()
        else MeasureSpec.getSize(widthMeasureSpec)
        val h = resolveSize(heightForLines(visibleLines), heightMeasureSpec)
        setMeasuredDimension(w, h)
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        rebuildLayout(keepProgress = true)
        buildFade()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val l = layout ?: return
        val w = width.toFloat()
        val h = height.toFloat()
        val readY = paddingTop + topFadePx

        val layer = canvas.saveLayer(0f, 0f, w, h, null)
        canvas.save()
        if (mirror) canvas.scale(-1f, 1f, w / 2f, h / 2f)
        canvas.clipRect(paddingLeft, paddingTop, width - paddingRight, height - paddingBottom)
        canvas.translate(paddingLeft.toFloat(), readY - offset)
        l.draw(canvas)
        canvas.restore()
        if (fadePaint.shader != null) canvas.drawRect(0f, 0f, w, h, fadePaint)
        canvas.restoreToCount(layer)

        if (showMarker) drawMarker(canvas, readY)
        if (countdownRemaining > 0) drawCountdown(canvas, w, h)
    }

    private fun drawMarker(canvas: Canvas, readY: Float) {
        val cy = readY + lineHeightPx / 2f
        val half = min(6f * density, lineHeightPx / 4f)
        val x0 = 2f * density
        val x1 = x0 + min(7f * density, max(4f * density, paddingLeft - 4f * density))
        markerPath.reset()
        markerPath.moveTo(x0, cy - half)
        markerPath.lineTo(x1, cy)
        markerPath.lineTo(x0, cy + half)
        markerPath.close()
        canvas.drawPath(markerPath, markerPaint)
    }

    private fun drawCountdown(canvas: Canvas, w: Float, h: Float) {
        canvas.drawColor(0x99000000.toInt())
        countdownPaint.textSize = min(h * 0.7f, 64f * density)
        val fm = countdownPaint.fontMetrics
        val baseline = h / 2f - (fm.ascent + fm.descent) / 2f
        canvas.drawText(countdownRemaining.toString(), w / 2f, baseline, countdownPaint)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        gestures.onTouchEvent(event)
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(ticker)
        removeCallbacks(countdownTick)
        playing = false
        countdownRemaining = 0
        super.onDetachedFromWindow()
    }

    private companion object {
        const val MARKER_COLOR = 0xFFFFC107.toInt()
        const val TOP_FADE_LINES = 0.3f
        const val BOTTOM_FADE_LINES = 1.2f
    }
}
