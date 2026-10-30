package com.paunero.teleprompter

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.provider.Settings
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.slider.Slider
import com.paunero.teleprompter.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var b: ActivityMainBinding
    private lateinit var prefs: Prefs

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { startOverlayNow() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityMainBinding.inflate(layoutInflater)
        setContentView(b.root)
        prefs = Prefs(this)

        if (!prefs.firstRunDone) {
            prefs.firstRunDone = true
            if (prefs.script.isBlank()) prefs.script = getString(R.string.sample_script)
        }

        b.editScript.setText(prefs.script)
        bindSettings()

        b.btnOverlay.setOnClickListener { onOverlayClicked() }
        b.btnFullscreen.setOnClickListener {
            saveScript()
            startActivity(Intent(this, PrompterActivity::class.java))
        }
        b.btnStop.setOnClickListener {
            OverlayService.stop(this)
            updateRunningState()
        }
    }

    override fun onResume() {
        super.onResume()
        updateRunningState()
    }

    override fun onPause() {
        saveScript()
        super.onPause()
    }

    private fun saveScript() {
        val current = b.editScript.text?.toString() ?: ""
        if (current != prefs.script) {
            prefs.script = current
            OverlayService.refresh(this)
        }
    }

    private fun bindSettings() {
        bindSlider(b.sliderTextSize, prefs.textSizeSp) { v ->
            prefs.textSizeSp = v
            b.labelTextSize.text = getString(R.string.label_text_size, v)
        }
        bindSlider(b.sliderSpeed, prefs.speed) { v ->
            prefs.speed = v
            b.labelSpeed.text = getString(R.string.label_speed, v)
        }
        bindSlider(b.sliderWidth, prefs.widthPercent) { v ->
            prefs.widthPercent = v
            b.labelWidth.text = getString(R.string.label_width, v)
        }
        bindSlider(b.sliderLines, prefs.visibleLines) { v ->
            prefs.visibleLines = v
            b.labelLines.text = getString(R.string.label_lines, v)
        }
        bindSlider(b.sliderAlpha, prefs.backgroundAlpha) { v ->
            prefs.backgroundAlpha = v
            b.labelAlpha.text = getString(R.string.label_alpha, v)
        }
        bindSlider(b.sliderFsSize, prefs.fullscreenTextSizeSp) { v ->
            prefs.fullscreenTextSizeSp = v
            b.labelFsSize.text = getString(R.string.label_fs_size, v)
        }

        b.switchMirror.isChecked = prefs.mirror
        b.switchMirror.setOnCheckedChangeListener { _, on ->
            prefs.mirror = on
            OverlayService.refresh(this)
        }
        b.switchMarker.isChecked = prefs.showMarker
        b.switchMarker.setOnCheckedChangeListener { _, on ->
            prefs.showMarker = on
            OverlayService.refresh(this)
        }
        b.switchCountdown.isChecked = prefs.countdown
        b.switchCountdown.setOnCheckedChangeListener { _, on ->
            prefs.countdown = on
            OverlayService.refresh(this)
        }
        b.switchOpenCamera.isChecked = prefs.openCamera
        b.switchOpenCamera.setOnCheckedChangeListener { _, on -> prefs.openCamera = on }
    }

    /** Ajusta el valor inicial al paso del slider para evitar excepciones de Material. */
    private fun bindSlider(slider: Slider, initial: Int, onChange: (Int) -> Unit) {
        val step = slider.stepSize.takeIf { it > 0f } ?: 1f
        val from = slider.valueFrom
        val snapped = from + Math.round((initial - from) / step) * step
        slider.value = snapped.coerceIn(slider.valueFrom, slider.valueTo)
        onChange(slider.value.toInt())
        slider.addOnChangeListener { _, value, fromUser ->
            onChange(value.toInt())
            if (fromUser) OverlayService.refresh(this)
        }
    }

    private fun onOverlayClicked() {
        saveScript()
        if (!Settings.canDrawOverlays(this)) {
            MaterialAlertDialogBuilder(this)
                .setTitle(R.string.overlay_perm_title)
                .setMessage(R.string.overlay_perm_msg)
                .setPositiveButton(R.string.open_settings) { _, _ ->
                    val intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName"),
                    )
                    startActivity(intent)
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
            return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        startOverlayNow()
    }

    private fun startOverlayNow() {
        OverlayService.start(this)
        updateRunningState()
        Toast.makeText(this, R.string.toast_overlay_started, Toast.LENGTH_SHORT).show()
        if (prefs.openCamera) openCamera()
    }

    private fun openCamera() {
        val intent = Intent(MediaStore.INTENT_ACTION_VIDEO_CAMERA)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(this, R.string.camera_not_found, Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateRunningState() {
        val running = OverlayService.isRunning
        b.btnStop.visibility = if (running) View.VISIBLE else View.GONE
        b.btnOverlay.setText(if (running) R.string.btn_overlay_update else R.string.btn_overlay)
    }
}
