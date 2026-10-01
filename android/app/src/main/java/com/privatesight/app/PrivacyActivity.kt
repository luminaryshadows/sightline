package com.privatesight.app

import android.os.Bundle
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ScrollView
import androidx.appcompat.app.AppCompatActivity

/**
 * Privacy Mode screen (Phase 10).
 *
 * States the privacy guarantees plainly, for screen readers and sighted
 * users alike, and offers a single obvious "delete everything" action.
 */
class PrivacyActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val column = UiKit.column(this).apply {
            setPadding(UiKit.dp(this@PrivacyActivity, 24), UiKit.dp(this@PrivacyActivity, 24),
                UiKit.dp(this@PrivacyActivity, 24), UiKit.dp(this@PrivacyActivity, 24))
        }

        column.addView(UiKit.title(this, getString(R.string.privacy_mode)))

        column.addView(bigStatement(getString(R.string.privacy_1)))
        column.addView(bigStatement(getString(R.string.privacy_2)))
        column.addView(bigStatement(getString(R.string.privacy_3)))
        column.addView(bigStatement(getString(R.string.privacy_4)))

        column.addView(UiKit.heading(this, getString(R.string.privacy_technical)))
        column.addView(UiKit.body(this, getString(R.string.privacy_technical_detail), 16f))

        val deleteAll = UiKit.bigButton(
            this,
            getString(R.string.delete_all),
            contentDescription = getString(R.string.delete_all),
            danger = true,
        ) {
            // Delete every transient artifact this app may have written.
            // The MVP keeps documents in memory only, so this clears the
            // cache directory that ExecuTorch model copies are placed in.
            cacheDir.listFiles()?.forEach { it.deleteRecursively() }
            finish()
        }
        column.addView(deleteAll)

        setContentView(ScrollView(this).apply { addView(column) })
    }

    private fun bigStatement(text: String) = UiKit.body(this, text, 22f).apply {
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ).apply { topMargin = UiKit.dp(this@PrivacyActivity, 12) }
    }
}
