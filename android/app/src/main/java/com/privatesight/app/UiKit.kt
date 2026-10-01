package com.privatesight.app

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Small helpers for building large, high-contrast, screen-reader-friendly
 * views in code. Keeping the UI programmatic guarantees that every control
 * has a matching accessibility label and a consistent 56dp touch target.
 */
object UiKit {

    const val TOUCH_TARGET_DP = 56

    fun dp(context: Context, value: Int): Int =
        (value * context.resources.displayMetrics.density).toInt()

    fun title(context: Context, text: String): TextView = TextView(context).apply {
        this.text = text
        textSize = 24f
        setTextColor(0xFFEEF2FF.toInt())
        setPadding(0, dp(context, 8), 0, dp(context, 4))
    }

    fun heading(context: Context, text: String): TextView = TextView(context).apply {
        this.text = text
        textSize = 16f
        setTextColor(0xFFA8B3D6.toInt())
        setPadding(0, dp(context, 16), 0, dp(context, 4))
        letterSpacing = 0.05f
    }

    fun body(context: Context, text: String, size: Float = 18f): TextView = TextView(context).apply {
        this.text = text
        textSize = size
        setTextColor(0xFFEEF2FF.toInt())
        setPadding(0, dp(context, 4), 0, dp(context, 4))
    }

    fun bigButton(
        context: Context,
        label: String,
        contentDescription: String = label,
        primary: Boolean = false,
        danger: Boolean = false,
        onClick: () -> Unit,
    ): Button = Button(context).apply {
        text = label
        this.contentDescription = contentDescription
        textSize = 18f
        isAllCaps = false
        minHeight = dp(context, TOUCH_TARGET_DP)
        setPadding(dp(context, 16), dp(context, 12), dp(context, 16), dp(context, 12))
        background = rounded(context, when {
            danger -> 0xFF4A1620.toInt()
            primary -> 0xFF14532D.toInt()
            else -> 0xFF1B2340.toInt()
        }, when {
            danger -> 0xFFB91C1C.toInt()
            primary -> 0xFF22C55E.toInt()
            else -> 0xFF2A3355.toInt()
        })
        setTextColor(0xFFEEF2FF.toInt())
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ).apply { marginEnd = dp(context, 10); topMargin = dp(context, 6); bottomMargin = dp(context, 6) }
        setOnClickListener { onClick() }
    }

    fun rounded(context: Context, fill: Int, stroke: Int, radiusDp: Int = 12, strokeDp: Int = 1): GradientDrawable =
        GradientDrawable().apply {
            setColor(fill)
            cornerRadius = dp(context, radiusDp).toFloat()
            setStroke(dp(context, strokeDp), stroke)
        }

    fun row(context: Context): LinearLayout = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        )
    }

    fun column(context: Context): LinearLayout = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        )
    }

    /** Make a view readable by TalkBack with an explicit description. */
    fun accessible(view: View, description: String): View = view.apply {
        contentDescription = description
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
    }
}
