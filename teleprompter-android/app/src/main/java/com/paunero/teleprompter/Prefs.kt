package com.paunero.teleprompter

import android.content.Context
import androidx.core.content.edit

/** Persistencia sencilla de guion y ajustes. */
class Prefs(context: Context) {

    private val sp = context.getSharedPreferences("prompter", Context.MODE_PRIVATE)

    var script: String
        get() = sp.getString(KEY_SCRIPT, null) ?: ""
        set(value) = sp.edit { putString(KEY_SCRIPT, value) }

    /** Tamaño de letra del recuadro flotante, en sp. */
    var textSizeSp: Int
        get() = sp.getInt(KEY_TEXT_SIZE, 22).coerceIn(TEXT_SIZE_MIN, TEXT_SIZE_MAX)
        set(value) = sp.edit { putInt(KEY_TEXT_SIZE, value.coerceIn(TEXT_SIZE_MIN, TEXT_SIZE_MAX)) }

    /** Tamaño de letra en pantalla completa, en sp. */
    var fullscreenTextSizeSp: Int
        get() = sp.getInt(KEY_FS_TEXT_SIZE, 40).coerceIn(FS_TEXT_SIZE_MIN, FS_TEXT_SIZE_MAX)
        set(value) = sp.edit { putInt(KEY_FS_TEXT_SIZE, value.coerceIn(FS_TEXT_SIZE_MIN, FS_TEXT_SIZE_MAX)) }

    /** Velocidad de desplazamiento en dp por segundo. */
    var speed: Int
        get() = sp.getInt(KEY_SPEED, 40).coerceIn(SPEED_MIN, SPEED_MAX)
        set(value) = sp.edit { putInt(KEY_SPEED, value.coerceIn(SPEED_MIN, SPEED_MAX)) }

    /** Ancho del recuadro flotante como porcentaje de la pantalla. */
    var widthPercent: Int
        get() = sp.getInt(KEY_WIDTH, 60).coerceIn(WIDTH_MIN, WIDTH_MAX)
        set(value) = sp.edit { putInt(KEY_WIDTH, value.coerceIn(WIDTH_MIN, WIDTH_MAX)) }

    /** Líneas visibles en el recuadro flotante. */
    var visibleLines: Int
        get() = sp.getInt(KEY_LINES, 3).coerceIn(LINES_MIN, LINES_MAX)
        set(value) = sp.edit { putInt(KEY_LINES, value.coerceIn(LINES_MIN, LINES_MAX)) }

    /** Opacidad del fondo del recuadro flotante, 0..100. */
    var backgroundAlpha: Int
        get() = sp.getInt(KEY_BG_ALPHA, 60).coerceIn(0, 100)
        set(value) = sp.edit { putInt(KEY_BG_ALPHA, value.coerceIn(0, 100)) }

    var mirror: Boolean
        get() = sp.getBoolean(KEY_MIRROR, false)
        set(value) = sp.edit { putBoolean(KEY_MIRROR, value) }

    var showMarker: Boolean
        get() = sp.getBoolean(KEY_MARKER, true)
        set(value) = sp.edit { putBoolean(KEY_MARKER, value) }

    var countdown: Boolean
        get() = sp.getBoolean(KEY_COUNTDOWN, true)
        set(value) = sp.edit { putBoolean(KEY_COUNTDOWN, value) }

    var openCamera: Boolean
        get() = sp.getBoolean(KEY_OPEN_CAMERA, true)
        set(value) = sp.edit { putBoolean(KEY_OPEN_CAMERA, value) }

    /** Posición guardada del recuadro flotante; [POSITION_UNSET] si nunca se ha movido. */
    var overlayX: Int
        get() = sp.getInt(KEY_OVERLAY_X, POSITION_UNSET)
        set(value) = sp.edit { putInt(KEY_OVERLAY_X, value) }

    var overlayY: Int
        get() = sp.getInt(KEY_OVERLAY_Y, POSITION_UNSET)
        set(value) = sp.edit { putInt(KEY_OVERLAY_Y, value) }

    var firstRunDone: Boolean
        get() = sp.getBoolean(KEY_FIRST_RUN, false)
        set(value) = sp.edit { putBoolean(KEY_FIRST_RUN, value) }

    companion object {
        const val POSITION_UNSET = Int.MIN_VALUE

        const val TEXT_SIZE_MIN = 14
        const val TEXT_SIZE_MAX = 60
        const val FS_TEXT_SIZE_MIN = 24
        const val FS_TEXT_SIZE_MAX = 80
        const val SPEED_MIN = 10
        const val SPEED_MAX = 150
        const val SPEED_STEP = 5
        const val WIDTH_MIN = 45
        const val WIDTH_MAX = 100
        const val LINES_MIN = 1
        const val LINES_MAX = 8

        private const val KEY_SCRIPT = "script"
        private const val KEY_TEXT_SIZE = "text_size_sp"
        private const val KEY_FS_TEXT_SIZE = "fs_text_size_sp"
        private const val KEY_SPEED = "speed_dp_s"
        private const val KEY_WIDTH = "width_percent"
        private const val KEY_LINES = "visible_lines"
        private const val KEY_BG_ALPHA = "bg_alpha"
        private const val KEY_MIRROR = "mirror"
        private const val KEY_MARKER = "marker"
        private const val KEY_COUNTDOWN = "countdown"
        private const val KEY_OPEN_CAMERA = "open_camera"
        private const val KEY_OVERLAY_X = "overlay_x"
        private const val KEY_OVERLAY_Y = "overlay_y"
        private const val KEY_FIRST_RUN = "first_run_done"
    }
}
