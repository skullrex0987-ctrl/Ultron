// ULTRON Android - JavaScript Bridge
// Connects JavaScript UI to native Kotlin ModelManager

package com.ultron.orb.bridge

import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.ultron.orb.model.ModelInfo
import com.ultron.orb.model.ModelManager
import com.ultron.orb.model.ModelStatus
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ModelBridge(
    private val webView: WebView,
    private val modelManager: ModelManager
) {
    private val scope = CoroutineScope(Dispatchers.Main)
    
    @JavascriptInterface
    fun getAvailableModels(): String {
        val models = modelManager.getAvailableModels()
        return models.joinToString(";") { "${it.id},${it.name},${it.size},${it.url}" }
    }
    
    @JavascriptInterface
    fun getModelStatus(modelId: String): String {
        val status = modelManager.getModelStatus(modelId)
        return "${status.isDownloaded},${status.isLoaded},${status.downloadProgress},${status.filePath}"
    }
    
    @JavascriptInterface
    fun getAllModelStatuses(): String {
        val statuses = modelManager.getAllModelStatuses()
        return statuses.joinToString("|") { status ->
            "${status.info.id},${status.info.name},${status.info.size},${status.isDownloaded},${status.isLoaded},${status.downloadProgress}"
        }
    }
    
    @JavascriptInterface
    fun downloadModel(modelId: String) {
        scope.launch {
            withContext(Dispatchers.IO) {
                modelManager.downloadModel(modelId) { progress ->
                    // Send progress back to JavaScript
                    val js = "javascript:window.onModelDownloadProgress('$modelId', $progress)"
                    webView.post { webView.evaluateJavascript(js, null) }
                }
            }
        }
    }
    
    @JavascriptInterface
    fun loadModel(modelId: String) {
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                modelManager.loadModel(modelId)
            }
            result.onSuccess {
                webView.post {
                    webView.evaluateJavascript("javascript:window.onModelLoaded('$modelId')", null)
                }
            }.onFailure { error ->
                webView.post {
                    webView.evaluateJavascript("javascript:window.onModelLoadError('$modelId', '${error.message}')", null)
                }
            }
        }
    }
    
    @JavascriptInterface
    fun unloadModel() {
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                modelManager.unloadModel()
            }
            result.onSuccess {
                webView.post {
                    webView.evaluateJavascript("javascript:window.onModelUnloaded()", null)
                }
            }
        }
    }
    
    @JavascriptInterface
    fun deleteModel(modelId: String) {
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                modelManager.deleteModel(modelId)
            }
            result.onSuccess {
                webView.post {
                    webView.evaluateJavascript("javascript:window.onModelDeleted('$modelId')", null)
                }
            }
        }
    }
    
    @JavascriptInterface
    fun getStorageInfo(): String {
        return "${modelManager.getStorageUsed()},${modelManager.getStorageAvailable()},${modelManager.getStorageTotal()}"
    }
    
    @JavascriptInterface
    fun getLoadedModelId(): String? {
        return modelManager.getLoadedModelId()
    }
    
    @JavascriptInterface
    fun isModelLoaded(): Boolean {
        return modelManager.isModelLoaded()
    }
}