package com.privatesight.app.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.util.Locale

/**
 * Offline-capable voice input for asking questions.
 *
 * Uses the platform SpeechRecognizer. On devices with an on-device recogniser
 * installed this works in airplane mode; where it does not, callers must fall
 * back to the large accessible text buttons (see [isAvailable]).
 */
class QuestionInput(private val context: Context) {

    interface Callback {
        fun onResult(text: String)
        fun onError(message: String)
    }

    private var recognizer: SpeechRecognizer? = null

    /** Whether a speech recogniser exists on this device at all. */
    fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    /** Whether recognition is likely to work offline (heuristic, best-effort). */
    fun isOnDeviceCapable(): Boolean =
        SpeechRecognizer.isOnDeviceRecognitionAvailable(context)

    fun listen(callback: Callback) {
        if (!isAvailable()) {
            callback.onError("Voice input is not available on this device. Use the question buttons instead.")
            return
        }

        val rec = recognizer ?: SpeechRecognizer.createSpeechRecognizer(context).also { recognizer = it }
        rec.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                if (text.isNullOrBlank()) callback.onError("I did not catch that. Please try again.")
                else callback.onResult(text)
            }
            override fun onError(error: Int) {
                callback.onError("I did not catch that. Please use the question buttons.")
            }
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.UK.toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        }
        try {
            rec.startListening(intent)
        } catch (e: Exception) {
            callback.onError("Voice input could not start. Please use the question buttons.")
        }
    }

    fun release() {
        recognizer?.destroy()
        recognizer = null
    }
}
