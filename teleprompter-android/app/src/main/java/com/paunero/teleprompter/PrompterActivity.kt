package com.paunero.teleprompter

import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.paunero.teleprompter.databinding.ActivityPrompterBinding

/** Modo pantalla completa: para usar el móvil como teleprompter junto a otra cámara. */
class PrompterActivity : AppCompatActivity(), PrompterView.Listener {

    private lateinit var b: ActivityPrompterBinding
    private lateinit var prefs: Prefs

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityPrompterBinding.inflate(layoutInflater)
        setContentView(b.root)
        prefs = Prefs(this)

        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, b.root).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }

        b.prompter.apply {
            listener = this@PrompterActivity
            text = prefs.script
            textSizeSp = prefs.fullscreenTextSizeSp.toFloat()
            speedDpPerSec = prefs.speed.toFloat()
            mirror = prefs.mirror
            showMarker = prefs.showMarker
            countdownSeconds = if (prefs.countdown) 3 else 0
        }

        b.btnPlay.setOnClickListener { b.prompter.togglePlay() }
        b.btnRestart.setOnClickListener { b.prompter.restart() }
        b.btnSlower.setOnClickListener { changeSpeed(-Prefs.SPEED_STEP) }
        b.btnFaster.setOnClickListener { changeSpeed(Prefs.SPEED_STEP) }
        b.btnMirror.setOnClickListener {
            prefs.mirror = !prefs.mirror
            b.prompter.mirror = prefs.mirror
        }
        b.btnClose.setOnClickListener { finish() }
        updateSpeedLabel()
    }

    private fun changeSpeed(delta: Int) {
        prefs.speed = prefs.speed + delta
        b.prompter.speedDpPerSec = prefs.speed.toFloat()
        updateSpeedLabel()
    }

    private fun updateSpeedLabel() {
        b.labelSpeed.text = prefs.speed.toString()
    }

    override fun onPlayStateChanged(playing: Boolean) {
        b.btnPlay.setImageResource(if (playing) R.drawable.ic_pause else R.drawable.ic_play)
        b.btnPlay.contentDescription = getString(if (playing) R.string.action_pause else R.string.action_play)
    }

    override fun onPause() {
        b.prompter.pause()
        super.onPause()
    }
}
