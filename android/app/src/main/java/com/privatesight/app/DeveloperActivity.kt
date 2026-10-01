package com.privatesight.app

import android.os.Bundle
import android.widget.LinearLayout
import android.widget.ScrollView
import androidx.appcompat.app.AppCompatActivity

/**
 * Developer / privacy status screen.
 *
 * Shows the hackathon demo facts: zero network requests, device processing,
 * local models, protected privacy status. Doubles as an audit surface.
 */
class DeveloperActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val column = UiKit.column(this).apply {
            setPadding(UiKit.dp(this@DeveloperActivity, 24), UiKit.dp(this@DeveloperActivity, 24),
                UiKit.dp(this@DeveloperActivity, 24), UiKit.dp(this@DeveloperActivity, 24))
        }

        column.addView(UiKit.title(this, getString(R.string.developer_status)))

        val facts = listOf(
            getString(R.string.dev_network) to "0",
            getString(R.string.dev_location) to "DEVICE",
            getString(R.string.dev_model) to "LOCAL (ExecuTorch, XNNPACK)",
            getString(R.string.dev_privacy) to "PROTECTED",
            getString(R.string.dev_internet_perm) to "NOT DECLARED",
            getString(R.string.dev_cleartext) to "DISABLED",
        )
        for ((label, value) in facts) {
            column.addView(UiKit.body(this, "$label: $value", 20f))
        }

        column.addView(UiKit.heading(this, getString(R.string.dev_explanation)))
        column.addView(
            UiKit.body(
                this,
                getString(R.string.dev_explanation_text),
                16f,
            )
        )

        setContentView(ScrollView(this).apply { addView(column) })
    }
}
