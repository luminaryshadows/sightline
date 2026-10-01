package com.privatesight.app.tts

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Android TextToSpeech wrapper.
 *
 * Uses the device's local TTS engine. No audio or text is sent anywhere.
 * Accessible defaults: slightly slower speech, queued utterances, immediate
 * announcements for camera guidance.
 */
class SpeechEngine(context: Context) {

    private var ready = AtomicBoolean(false)
    private val pending = ArrayDeque<Pair<String, Boolean>>()

    private val tts: TextToSpeech = TextToSpeech(context.applicationContext) { status ->
        if (status == TextToSpeech.SUCCESS) {
            ready.set(true)
            // English (UK) is the target locale for the MVP
            tts.language = Locale.UK
            tts.setSpeechRate(0.95f)
            flushPending()
        }
    }

    init {
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) {}
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {}
            override fun onError(utteranceId: String?, errorCode: Int) {}
        })
    }

    val isReady: Boolean get() = ready.get()

    /**
     * Speak text.
     *
     * @param text      the text to speak
     * @param interrupt if true, stops current speech (use for camera guidance)
     */
    fun speak(text: String, interrupt: Boolean = false) {
        if (text.isBlank()) return
        if (!ready.get()) {
            synchronized(pending) { pending.addLast(text to interrupt) }
            return
        }
        val mode = if (interrupt) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
        tts.speak(text, mode, null, UUID.randomUUID().toString())
    }

    fun stop() = tts.stop()

    fun shutdown() {
        tts.stop()
        tts.shutdown()
    }

    private fun flushPending() {
        val queued = synchronized(pending) {
            val copy = pending.toList()
            pending.clear()
            copy
        }
        queued.forEach { (text, interrupt) -> speak(text, interrupt) }
    }
}
