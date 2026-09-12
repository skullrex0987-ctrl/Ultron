// ULTRON Android - MainActivity.kt
// Main activity with model management bridge and local HTTP server

package com.ultron.orb

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.annotation.NonNull
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.ultron.orb.bridge.ModelBridge
import com.ultron.orb.model.ModelManager
import com.ultron.orb.server.AssetHttpServer
import fi.iki.elonen.NanoHTTPD

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var modelManager: ModelManager
    private lateinit var modelBridge: ModelBridge
    private var httpServer: AssetHttpServer? = null
    private var serverPort = 0

    companion object {
        private const val PERMISSION_REQUEST_CODE = 1001
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start local HTTP server for serving assets (bypasses file:// ES module restrictions)
        httpServer = AssetHttpServer(this, 0, "public")
        try {
            httpServer?.start(NanoHTTPD.StartType.RUNNING)
            serverPort = httpServer?.boundPort ?: 0
        } catch (e: Exception) {
            e.printStackTrace()
        }

        // Setup WebView before exposing the bridge
        setupWebView()
        modelManager = ModelManager(this)
        modelBridge = ModelBridge(webView, modelManager)
        webView.addJavascriptInterface(modelBridge, "AndroidModelBridge")

        // Request permissions
        requestRequiredPermissions()

        // Load the orb interface via local HTTP server (not file://)
        if (serverPort > 0) {
            webView.loadUrl("http://127.0.0.1:$serverPort/")
        } else {
            // Fallback to file:// if server failed
            webView.loadUrl("file:///android_asset/public/index.html")
        }
    }

    private fun setupWebView() {
        webView = WebView(this)
        setContentView(webView)

        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.mediaPlaybackRequiresUserGesture = false
        settings.javaScriptCanOpenWindowsAutomatically = true
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        settings.allowFileAccessFromFileURLs = true
        settings.allowUniversalAccessFromFileURLs = true

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Inject model bridge into JavaScript (redundant but safe)
                injectModelBridge()
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest?) {
                request?.grant(request.resources)
            }
        }

        // Add JavaScript interface
        webView.addJavascriptInterface(modelBridge, "AndroidModelBridge")
    }

    private fun injectModelBridge() {
        // Make model bridge available to JavaScript
        webView.evaluateJavascript(
            """
            window.ModelBridge = {
                getAvailableModels: function() {
                    return AndroidModelBridge.getAvailableModels();
                },
                getModelStatus: function(modelId) {
                    return AndroidModelBridge.getModelStatus(modelId);
                },
                getAllModelStatuses: function() {
                    return AndroidModelBridge.getAllModelStatuses();
                },
                downloadModel: function(modelId) {
                    AndroidModelBridge.downloadModel(modelId);
                },
                loadModel: function(modelId) {
                    AndroidModelBridge.loadModel(modelId);
                },
                unloadModel: function() {
                    AndroidModelBridge.unloadModel();
                },
                deleteModel: function(modelId) {
                    AndroidModelBridge.deleteModel(modelId);
                },
                getStorageInfo: function() {
                    return AndroidModelBridge.getStorageInfo();
                },
                getLoadedModelId: function() {
                    return AndroidModelBridge.getLoadedModelId();
                },
                isModelLoaded: function() {
                    return AndroidModelBridge.isModelLoaded();
                }
            };
            """.trimIndent(), null)
    }

    private fun requestRequiredPermissions() {
        val permissions = mutableListOf<String>()

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.CAMERA)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.RECORD_AUDIO)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (permissions.isNotEmpty()) {
            ActivityCompat.requestPermissions(this,
                permissions.toTypedArray(),
                PERMISSION_REQUEST_CODE)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, @NonNull permissions: Array<out String>, @NonNull grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        if (requestCode == PERMISSION_REQUEST_CODE) {
            var allGranted = true
            for (result in grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false
                    break
                }
            }

            if (!allGranted) {
                Toast.makeText(this, "Camera and microphone permissions required for gestures and voice", Toast.LENGTH_LONG).show()
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        httpServer?.stop()
        webView.destroy()
    }
}