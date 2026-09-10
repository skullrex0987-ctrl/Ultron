// ULTRON Android - ModelManager.kt
// Downloads and manages GGUF models from HuggingFace

package com.ultron.orb.model

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

data class ModelInfo(
    val id: String,
    val displayName: String,
    val size: String,
    val url: String,
    val filename: String,
    val quantization: String,
    val contextSize: Int
)

class ModelManager(private val context: Context) {
    private val modelsDir = File(context.filesDir, "models")
    private val prefs = context.getSharedPreferences("ultron_models", Context.MODE_PRIVATE)

    companion object {
        private const val TAG = "ModelManager"
        
        val AVAILABLE_MODELS = listOf(
            ModelInfo(
                id = "qwen3_0.6b",
                displayName = "Qwen3 0.6B",
                size = "~0.5GB",
                url = "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf",
                filename = "qwen3-0.6b-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "qwen2.5_0.5b",
                displayName = "Qwen2.5 0.5B",
                size = "~0.4GB",
                url = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                filename = "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "gemma_2b",
                displayName = "Gemma 2B",
                size = "~1.5GB",
                url = "https://huggingface.co/google/gemma-2b-it-GGUF/resolve/main/gemma-2b-it-q4_k_m.gguf",
                filename = "gemma-2b-it-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 8192
            ),
            ModelInfo(
                id = "qwen3_0.8b",
                displayName = "Qwen3 0.8B",
                size = "~0.7GB",
                url = "https://huggingface.co/Qwen/Qwen3-0.8B-GGUF/resolve/main/Qwen3-0.8B-Q4_K_M.gguf",
                filename = "qwen3-0.8b-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "qwen3_1.7b",
                displayName = "Qwen3 1.7B",
                size = "~1.2GB",
                url = "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf",
                filename = "qwen3-1.7b-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "llama_3.2_1b",
                displayName = "Llama 3.2 1B",
                size = "~0.8GB",
                url = "https://huggingface.co/llama-factory/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
                filename = "llama-3.2-1b-instruct-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 8192
            ),
            ModelInfo(
                id = "phi_3.5_mini",
                displayName = "Phi-3.5 Mini",
                size = "~2.5GB",
                url = "https://huggingface.co/microsoft/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
                filename = "phi-3.5-mini-instruct-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 4096
            )
        )
    }

    init {
        if (!modelsDir.exists()) {
            modelsDir.mkdirs()
        }
    }

    fun getAvailableModels(): List<ModelInfo> = AVAILABLE_MODELS

    fun getModelPath(modelId: String): String? {
        val model = AVAILABLE_MODELS.find { it.id == modelId } ?: return null
        return File(modelsDir, model.filename).absolutePath
    }

    fun modelExists(modelId: String): Boolean {
        val path = getModelPath(modelId) ?: return false
        return File(path).exists() && File(path).length() > 0
    }

    fun getDownloadedModels(): List<ModelInfo> {
        return AVAILABLE_MODELS.filter { modelExists(it.id) }
    }

    fun downloadModel(model: ModelInfo, callback: (Boolean) -> Unit) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val outputFile = File(modelsDir, model.filename)
                val tempFile = File(modelsDir, "${model.filename}.tmp")

                Log.d(TAG, "Downloading ${model.displayName} from ${model.url}")

                val url = URL(model.url)
                val connection = url.openConnection() as HttpURLConnection
                connection.connectTimeout = 30000
                connection.readTimeout = 60000
                connection.connect()

                if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                    Log.e(TAG, "Download failed: HTTP ${connection.responseCode}")
                    callback(false)
                    return@launch
                }

                val contentLength = connection.contentLength.toLong()
                val inputStream = BufferedInputStream(connection.inputStream)
                val outputStream = FileOutputStream(tempFile)

                val buffer = ByteArray(8192)
                var totalBytesRead = 0L
                var bytesRead: Int

                while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                    outputStream.write(buffer, 0, bytesRead)
                    totalBytesRead += bytesRead

                    // Progress logging every 10MB
                    if (totalBytesRead % (10 * 1024 * 1024) < 8192) {
                        val progress = if (contentLength > 0) {
                            (totalBytesRead * 100 / contentLength).toInt()
                        } else {
                            (totalBytesRead / 1024 / 1024).toInt()
                        }
                        Log.d(TAG, "Download progress: $progress%")
                    }
                }

                outputStream.close()
                inputStream.close()

                // Verify download succeeded
                if (tempFile.length() > 0) {
                    if (outputFile.exists()) outputFile.delete()
                    tempFile.renameTo(outputFile)
                    Log.d(TAG, "Download complete: ${outputFile.length()} bytes")
                    callback(true)
                } else {
                    tempFile.delete()
                    Log.e(TAG, "Download failed: empty file")
                    callback(false)
                }

            } catch (e: Exception) {
                Log.e(TAG, "Download error", e)
                callback(false)
            }
        }
    }

    fun deleteModel(modelId: String): Boolean {
        val path = getModelPath(modelId) ?: return false
        return File(path).delete()
    }

    fun getModelSize(modelId: String): Long {
        val path = getModelPath(modelId) ?: return 0
        val file = File(path)
        return if (file.exists()) file.length() else 0
    }

    fun setLastUsedModel(modelId: String) {
        prefs.edit().putString("last_used_model", modelId).apply()
    }

    fun getLastUsedModel(): String? {
        return prefs.getString("last_used_model", null)
    }

    fun isModelDownloaded(modelId: String): Boolean = modelExists(modelId)

    fun getStorageUsed(): Long {
        return modelsDir.listFiles()?.sumOf { it.length() } ?: 0
    }

    fun getStorageAvailable(): Long {
        return modelsDir.freeSpace
    }
}