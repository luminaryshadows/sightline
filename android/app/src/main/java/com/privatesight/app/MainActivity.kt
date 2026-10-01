package com.privatesight.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.privatesight.app.analysis.DocumentAnalysis
import com.privatesight.app.analysis.DocumentAnalyzer
import com.privatesight.app.analysis.ExecuTorchOcrEngine
import com.privatesight.app.camera.CaptureGuide
import com.privatesight.app.camera.DocumentCaptureAnalyzer
import com.privatesight.app.storage.DocumentStore
import com.privatesight.app.tts.SpeechEngine
import com.privatesight.app.voice.QuestionInput
import kotlinx.coroutines.launch

/**
 * SCAN DOCUMENT screen.
 *
 * Flow: live camera preview with spoken guidance -> capture -> on-device
 * analysis -> spoken + readable results -> ask questions -> delete.
 *
 * Accessibility: every control is a >=56dp target with a content description;
 * guidance and results are announced automatically.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var speech: SpeechEngine
    private lateinit var store: DocumentStore
    private lateinit var analyzer: DocumentAnalyzer
    private lateinit var guide: CaptureGuide
    private lateinit var questionInput: QuestionInput

    private var imageCapture: ImageCapture? = null
    private var captureAnalyzer: DocumentCaptureAnalyzer? = null
    private var currentAnalysis: DocumentAnalysis? = null
    private var currentDocId: String? = null

    // Views
    private lateinit var root: LinearLayout
    private lateinit var previewView: PreviewView
    private lateinit var statusText: TextView
    private lateinit var captureButton: Button
    private lateinit var resultsContainer: LinearLayout

    private val cameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else {
            statusText.text = getString(R.string.camera_permission_denied)
            speech.speak(getString(R.string.camera_permission_denied))
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        speech = SpeechEngine(this)
        store = DocumentStore()
        guide = CaptureGuide()
        questionInput = QuestionInput(this)
        analyzer = DocumentAnalyzer(ExecuTorchOcrEngine(this))

        buildUi()

        // Announce the screen for screen-reader users.
        speech.speak(getString(R.string.screen_intro))

        if (hasCameraPermission()) startCamera() else cameraPermission.launch(Manifest.permission.CAMERA)
    }

    // ── UI construction ───────────────────────────────────────

    private fun buildUi() {
        root = UiKit.column(this).apply {
            setPadding(UiKit.dp(this@MainActivity, 20), UiKit.dp(this@MainActivity, 16),
                UiKit.dp(this@MainActivity, 20), UiKit.dp(this@MainActivity, 24))
        }

        root.addView(UiKit.title(this, getString(R.string.app_name)))
        root.addView(UiKit.body(this, getString(R.string.privacy_banner_speech), 15f))

        // Camera preview
        previewView = PreviewView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, UiKit.dp(this@MainActivity, 320),
            ).apply { topMargin = UiKit.dp(this@MainActivity, 12) }
            contentDescription = getString(R.string.camera_preview_desc)
        }
        root.addView(previewView)

        statusText = UiKit.body(this, getString(R.string.guidance_starting)).apply {
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = UiKit.dp(this@MainActivity, 8) }
        }
        root.addView(statusText)

        captureButton = UiKit.bigButton(
            this,
            getString(R.string.scan_document),
            contentDescription = getString(R.string.scan_document),
            primary = true,
        ) { captureDocument() }

        val controls = UiKit.row(this).apply { gravity = Gravity.CENTER_VERTICAL }
        controls.addView(captureButton)
        controls.addView(
            UiKit.bigButton(this, getString(R.string.privacy_mode),
                contentDescription = getString(R.string.privacy_mode)) {
                startActivity(Intent(this, PrivacyActivity::class.java))
            })
        controls.addView(
            UiKit.bigButton(this, getString(R.string.developer_status),
                contentDescription = getString(R.string.developer_status)) {
                startActivity(Intent(this, DeveloperActivity::class.java))
            })
        root.addView(controls)

        resultsContainer = UiKit.column(this).apply { visibility = View.GONE }
        root.addView(resultsContainer)

        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)
    }

    // ── Camera ────────────────────────────────────────────────

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()

            val preview = Preview.Builder().build().also {
                it.surfaceProvider = previewView.surfaceProvider
            }

            imageCapture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                .build()

            captureAnalyzer = DocumentCaptureAnalyzer(
                guide = guide,
                onGuidance = { message, _ ->
                    runOnUiThread { statusText.text = message }
                    speech.speak(message, interrupt = true)
                },
                onReady = { assessment ->
                    runOnUiThread {
                        statusText.text = getString(R.string.document_ready)
                        captureButton.isEnabled = true
                    }
                    speech.speak(getString(R.string.document_ready), interrupt = true)
                },
            ).also { it.paused = true } // guidance starts once the user taps Scan

            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also { it.setAnalyzer(ContextCompat.getMainExecutor(this), captureAnalyzer!!) }

            val selector = CameraSelector.DEFAULT_BACK_CAMERA
            try {
                provider.unbindAll()
                provider.bindToLifecycle(this, selector, preview, imageCapture, analysis)
            } catch (e: Exception) {
                statusText.text = getString(R.string.camera_start_failed)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun captureDocument() {
        val capture = imageCapture ?: return
        captureAnalyzer?.paused = true
        statusText.text = getString(R.string.capturing)
        speech.speak(getString(R.string.capturing), interrupt = true)

        capture.takePicture(
            ContextCompat.getMainExecutor(this),
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val bitmap = image.toBitmap()
                    image.close()
                    analyzeBitmap(bitmap)
                }

                override fun onError(exception: ImageCaptureException) {
                    statusText.text = getString(R.string.capture_failed)
                    speech.speak(getString(R.string.capture_failed), interrupt = true)
                    captureAnalyzer?.paused = false
                    captureAnalyzer?.reset()
                }
            },
        )
    }

    private fun analyzeBitmap(bitmap: Bitmap) {
        statusText.text = getString(R.string.analysing)
        lifecycleScope.launch {
            val result = analyzer.analyze(bitmap)
            currentAnalysis = result
            currentDocId = store.add(result)
            renderResults(result)
            speech.speak(result.accessibleSummary, interrupt = true)
        }
    }

    // ── Results ───────────────────────────────────────────────

    private fun renderResults(a: DocumentAnalysis) {
        resultsContainer.removeAllViews()
        resultsContainer.visibility = View.VISIBLE

        resultsContainer.addView(UiKit.heading(this, getString(R.string.result_what_is)))
        resultsContainer.addView(UiKit.body(this, "${a.documentType.displayName} — ${(a.classificationConfidence * 100).toInt()}%", 20f))

        resultsContainer.addView(UiKit.heading(this, getString(R.string.result_summary)))
        resultsContainer.addView(UiKit.body(this, a.accessibleSummary))

        resultsContainer.addView(UiKit.heading(this, getString(R.string.result_sensitive)))
        val sensitive = if (a.sensitiveData.detected)
            "Detected. Risk level ${a.sensitiveData.riskLevel}. ${a.sensitiveData.entityCount} items: ${a.sensitiveData.entityTypes.joinToString(", ")}"
        else "None detected."
        resultsContainer.addView(UiKit.body(this, sensitive))

        resultsContainer.addView(UiKit.heading(this, getString(R.string.result_fields)))
        if (a.extraction.fields.isEmpty()) {
            resultsContainer.addView(UiKit.body(this, getString(R.string.no_fields)))
        } else {
            a.extraction.fields.forEach { resultsContainer.addView(UiKit.body(this, "${it.label}: ${it.value}")) }
            a.extraction.monetaryValues.forEach { resultsContainer.addView(UiKit.body(this, "${it.first}: ${it.second}")) }
            a.extraction.deadlines.forEach { resultsContainer.addView(UiKit.body(this, "${it.first}: ${it.second}")) }
        }

        if (a.warnings.isNotEmpty()) {
            resultsContainer.addView(UiKit.heading(this, getString(R.string.result_warnings)))
            a.warnings.forEach { resultsContainer.addView(UiKit.body(this, "• $it", 16f)) }
        }

        // Question row + quick answers
        resultsContainer.addView(UiKit.heading(this, getString(R.string.ask_question)))
        val questionRow = UiKit.row(this)
        val questionBox = EditText(this).apply {
            hint = getString(R.string.question_hint)
            contentDescription = getString(R.string.question_hint)
            minHeight = UiKit.dp(this@MainActivity, UiKit.TOUCH_TARGET_DP)
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
        val answerText = UiKit.body(this, "")
        questionRow.addView(questionBox)
        questionRow.addView(UiKit.bigButton(this, getString(R.string.ask),
            contentDescription = getString(R.string.ask)) {
            askQuestion(questionBox.text.toString(), answerText)
        })
        resultsContainer.addView(questionRow)

        // Quick question buttons (fallback when voice input is unavailable)
        val quick = UiKit.row(this)
        listOf(
            R.string.q_what_is to getString(R.string.q_what_is),
            R.string.q_action to getString(R.string.q_action),
            R.string.q_deadline to getString(R.string.q_deadline),
            R.string.q_amount to getString(R.string.q_amount),
        ).forEach { (_, q) ->
            quick.addView(UiKit.bigButton(this, q, contentDescription = q) {
                questionBox.setText(q)
                askQuestion(q, answerText)
            })
        }
        resultsContainer.addView(quick)

        quick.addView(UiKit.bigButton(this, getString(R.string.ask_voice),
            contentDescription = getString(R.string.ask_voice)) {
            questionInput.listen(object : QuestionInput.Callback {
                override fun onResult(text: String) {
                    questionBox.setText(text)
                    askQuestion(text, answerText)
                }
                override fun onError(message: String) {
                    answerText.text = message
                    speech.speak(message)
                }
            })
        })

        resultsContainer.addView(answerText)

        // Action buttons
        val actions = UiKit.row(this)
        actions.addView(UiKit.bigButton(this, getString(R.string.read_summary),
            contentDescription = getString(R.string.read_summary)) { speech.speak(a.accessibleSummary) })
        actions.addView(UiKit.bigButton(this, getString(R.string.read_full),
            contentDescription = getString(R.string.read_full)) { speech.speak(a.ocr.fullText) })
        resultsContainer.addView(actions)

        val actions2 = UiKit.row(this)
        actions2.addView(UiKit.bigButton(this, getString(R.string.scan_again),
            contentDescription = getString(R.string.scan_again)) { resetForScan() })
        actions2.addView(UiKit.bigButton(this, getString(R.string.delete_document),
            contentDescription = getString(R.string.delete_document), danger = true) { deleteCurrent() })
        resultsContainer.addView(actions2)

        resultsContainer.announceForAccessibility(getString(R.string.result_ready))
    }

    private fun askQuestion(question: String, answerView: TextView) {
        val analysis = currentAnalysis ?: return
        if (question.isBlank()) return
        val answer = analyzer.ask(analysis, question)
        answerView.text = answer.answer
        speech.speak(answer.answer)
        if (answer.isMedical && answer.medicalDisclaimer.isNotEmpty()) {
            answerView.text = "${answer.answer}\n\n${answer.medicalDisclaimer}"
        }
    }

    private fun resetForScan() {
        resultsContainer.visibility = View.GONE
        resultsContainer.removeAllViews()
        currentAnalysis = null
        currentDocId = null
        statusText.text = getString(R.string.guidance_starting)
        captureAnalyzer?.reset()
        captureAnalyzer?.paused = false
        speech.speak(getString(R.string.guidance_starting), interrupt = true)
    }

    private fun deleteCurrent() {
        currentDocId?.let { store.delete(it) }
        currentAnalysis = null
        currentDocId = null
        resultsContainer.visibility = View.GONE
        resultsContainer.removeAllViews()
        statusText.text = getString(R.string.document_deleted)
        speech.speak(getString(R.string.document_deleted), interrupt = true)
    }

    override fun onDestroy() {
        super.onDestroy()
        questionInput.release()
        store.deleteAll()
        speech.shutdown()
    }
}
