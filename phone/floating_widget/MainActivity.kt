package com.ultron.floatwidget

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle

/** Launcher: opens the Termux-served ULTRON web HUD in a browser. */
class MainActivity : Activity() {
    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("http://localhost:8080")))
        finish()
    }
}
