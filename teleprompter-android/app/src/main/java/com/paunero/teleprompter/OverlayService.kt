package com.paunero.teleprompter

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.view.ContextThemeWrapper
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowInsets
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat

/**
 * Servicio en primer plano que mantiene el recuadro del teleprompter flotando
 * sobre cualquier app, en particular sobre la cámara del Pixel mientras grabas.
 */
class OverlayService : Service(), PrompterView.Listener {

    private lateinit var wm: WindowManager
    private lateinit var prefs: Prefs
    private lateinit var params: WindowManager.LayoutParams
    private var root: View? = null
    private var prompter: PrompterView? = null
    private var btnPlay: ImageButton? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        prefs = Prefs(this)
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_TOGGLE -> {
                prompter?.togglePlay()
                return START_NOT_STICKY
            }
            ACTION_REFRESH -> {
                if (root != null) applyPrefs()
                return START_NOT_STICKY
            }
        }

        startAsForeground()
        if (root == null) showOverlay() else applyPrefs()
        return START_NOT_STICKY
    }

    private fun startAsForeground() {
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
        } else {
            0
        }
        ServiceCompat.startForeground(this, NOTIFICATION_ID, buildNotification(false), type)
    }

    private fun showOverlay() {
        val themed = ContextThemeWrapper(this, R.style.Theme_Prompter_Fullscreen)
        val view = LayoutInflater.from(themed).inflate(R.layout.overlay_prompter, null)
        val prompterView = view.findViewById<PrompterView>(R.id.prompter)
        prompterView.listener = this

        val widthPx = overlayWidthPx()
        val (defaultX, defaultY) = defaultPosition(widthPx)
        params = WindowManager.LayoutParams(
            widthPx,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = if (prefs.overlayX == Prefs.POSITION_UNSET) defaultX else prefs.overlayX
            y = if (prefs.overlayY == Prefs.POSITION_UNSET) defaultY else prefs.overlayY
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }

        root = view
        prompter = prompterView
        btnPlay = view.findViewById(R.id.btnPlay)
        wireControls(view)
        applyPrefs()

        try {
            wm.addView(view, params)
        } catch (e: Exception) {
            root = null
            prompter = null
            Toast.makeText(this, R.string.overlay_failed, Toast.LENGTH_LONG).show()
            stopSelf()
        }
    }

    private fun wireControls(view: View) {
        val prompterView = prompter ?: return
        view.findViewById<ImageButton>(R.id.btnPlay).setOnClickListener { prompterView.togglePlay() }
        view.findViewById<ImageButton>(R.id.btnRestart).setOnClickListener { prompterView.restart() }
        view.findViewById<ImageButton>(R.id.btnSlower).setOnClickListener { changeSpeed(-Prefs.SPEED_STEP) }
        view.findViewById<ImageButton>(R.id.btnFaster).setOnClickListener { changeSpeed(Prefs.SPEED_STEP) }
        view.findViewById<ImageButton>(R.id.btnClose).setOnClickListener { stopSelf() }

        view.findViewById<ImageButton>(R.id.btnDrag).setOnTouchListener(object : View.OnTouchListener {
            private var startX = 0
            private var startY = 0
            private var downRawX = 0f
            private var downRawY = 0f

            override fun onTouch(v: View, e: MotionEvent): Boolean {
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        startX = params.x
                        startY = params.y
                        downRawX = e.rawX
                        downRawY = e.rawY
                        return true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        params.x = startX + (e.rawX - downRawX).toInt()
                        params.y = startY + (e.rawY - downRawY).toInt()
                        root?.let { wm.updateViewLayout(it, params) }
                        return true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                        prefs.overlayX = params.x
                        prefs.overlayY = params.y
                        v.performClick()
                        return true
                    }
                }
                return false
            }
        })
    }

    private fun changeSpeed(delta: Int) {
        prefs.speed = prefs.speed + delta
        prompter?.speedDpPerSec = prefs.speed.toFloat()
        Toast.makeText(this, getString(R.string.toast_speed, prefs.speed), Toast.LENGTH_SHORT).show()
    }

    private fun applyPrefs() {
        val view = root ?: return
        val prompterView = prompter ?: return

        prompterView.text = prefs.script
        prompterView.textSizeSp = prefs.textSizeSp.toFloat()
        prompterView.speedDpPerSec = prefs.speed.toFloat()
        prompterView.mirror = prefs.mirror
        prompterView.showMarker = prefs.showMarker
        prompterView.countdownSeconds = if (prefs.countdown) 3 else 0
        prompterView.visibleLines = prefs.visibleLines

        val alpha = (prefs.backgroundAlpha * 255 / 100).coerceIn(0, 255)
        view.background = GradientDrawable().apply {
            cornerRadius = 12f * resources.displayMetrics.density
            setColor(Color.argb(alpha, 0, 0, 0))
        }

        val widthPx = overlayWidthPx()
        if (params.width != widthPx) {
            params.width = widthPx
            if (view.isAttachedToWindow) wm.updateViewLayout(view, params)
        }
    }

    private fun overlayWidthPx(): Int = screenWidthPx() * prefs.widthPercent / 100

    private fun screenWidthPx(): Int =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            wm.currentWindowMetrics.bounds.width()
        } else {
            resources.displayMetrics.widthPixels
        }

    /** Centrado horizontalmente y justo debajo del recorte de la cámara frontal. */
    private fun defaultPosition(widthPx: Int): Pair<Int, Int> {
        val x = (screenWidthPx() - widthPx) / 2
        var top = 0
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val insets = wm.currentWindowMetrics.windowInsets
            top = insets.displayCutout?.safeInsetTop
                ?: insets.getInsets(WindowInsets.Type.statusBars()).top
        } else {
            @Suppress("DiscouragedApi")
            val id = resources.getIdentifier("status_bar_height", "dimen", "android")
            if (id > 0) top = resources.getDimensionPixelSize(id)
        }
        return x to top
    }

    override fun onPlayStateChanged(playing: Boolean) {
        btnPlay?.apply {
            setImageResource(if (playing) R.drawable.ic_pause else R.drawable.ic_play)
            contentDescription = getString(if (playing) R.string.action_pause else R.string.action_play)
        }
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(playing))
    }

    override fun onDestroy() {
        root?.let { view ->
            if (view.isAttachedToWindow) {
                try {
                    wm.removeView(view)
                } catch (e: Exception) {
                    // La ventana ya no está; no hay nada que limpiar.
                }
            }
        }
        root = null
        prompter = null
        btnPlay = null
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        isRunning = false
        super.onDestroy()
    }

    private fun createChannel() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notif_channel),
            NotificationManager.IMPORTANCE_LOW,
        ).apply { setShowBadge(false) }
        nm.createNotificationChannel(channel)
    }

    private fun buildNotification(playing: Boolean): Notification {
        val openApp = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val toggle = servicePendingIntent(ACTION_TOGGLE, 1)
        val stop = servicePendingIntent(ACTION_STOP, 2)

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_prompter)
            .setContentTitle(getString(R.string.notif_title))
            .setContentText(getString(R.string.notif_text))
            .setContentIntent(openApp)
            .setOngoing(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .addAction(
                if (playing) R.drawable.ic_pause else R.drawable.ic_play,
                getString(if (playing) R.string.action_pause else R.string.action_play),
                toggle,
            )
            .addAction(R.drawable.ic_close, getString(R.string.action_close), stop)
            .build()
    }

    private fun servicePendingIntent(action: String, requestCode: Int): PendingIntent {
        val intent = Intent(this, OverlayService::class.java).setAction(action)
        return PendingIntent.getService(
            this, requestCode, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }

    companion object {
        private const val CHANNEL_ID = "prompter_overlay"
        private const val NOTIFICATION_ID = 1

        const val ACTION_START = "com.paunero.teleprompter.START"
        const val ACTION_STOP = "com.paunero.teleprompter.STOP"
        const val ACTION_TOGGLE = "com.paunero.teleprompter.TOGGLE"
        const val ACTION_REFRESH = "com.paunero.teleprompter.REFRESH"

        @Volatile
        var isRunning: Boolean = false
            private set

        fun start(context: Context) {
            isRunning = true
            val intent = Intent(context, OverlayService::class.java).setAction(ACTION_START)
            ContextCompat.startForegroundService(context, intent)
        }

        fun refresh(context: Context) {
            if (!isRunning) return
            context.startService(Intent(context, OverlayService::class.java).setAction(ACTION_REFRESH))
        }

        fun stop(context: Context) {
            isRunning = false
            context.startService(Intent(context, OverlayService::class.java).setAction(ACTION_STOP))
        }
    }
}
