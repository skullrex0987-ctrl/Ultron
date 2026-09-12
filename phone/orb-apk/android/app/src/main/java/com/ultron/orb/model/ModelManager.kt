// ULTRON Android - ModelManager.kt
// Manages GGUF model downloads, storage, loading, and unloading

package com.ultron.orb.model

import android.content.Context
import android.content.SharedPreferences
import android.os.Environment
import android.util.Log
import com.ultron.orb.inference.InferenceManager
import kotlinx.coroutines.*
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

data class ModelInfo(
    val id: String,
    val name: String,
    val size: String,
    val sizeBytes: Long,
    val url: String,
    val filename: String,
    val quantization: String,
    val contextSize: Int
)

data class ModelStatus(
    val info: ModelInfo,
    val isDownloaded: Boolean,
    val isLoaded: Boolean,
    val downloadProgress: Float = 0f,
    val filePath: String = ""
)

class ModelManager(private val context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("ultron_models", Context.MODE_PRIVATE)
    private val modelsDir: File = File(context.getExternalFilesDir(null), "models")
    private val inferenceManager = InferenceManager(context)
    
    companion object {
        private const val TAG = "ModelManager"
        private const val KEY_LOADED_MODEL = "loaded_model"
        
        val AVAILABLE_MODELS = listOf(
            ModelInfo(
                id = "qwen3_0.6b",
                name = "Qwen3 0.6B",
                size = "0.5GB",
                sizeBytes = 536870912L,
                url = "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf",
                filename = "qwen3-0.6b-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "qwen2.5_0.5b",
                name = "Qwen2.5 0.5B",
                size = "0.4GB",
                sizeBytes = 429496729L,
                url = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                filename = "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "gemma_2b",
                name = "Gemma 2B",
                size = "1.5GB",
                sizeBytes = 1610612736L,
                url = "https://huggingface.co/google/gemma-2b-it-GGUF/resolve/main/gemma-2b-it-q4_k_m.gguf",
                filename = "gemma-2b-it-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 8192
            ),
            ModelInfo(
                id = "qwen3_0.8b",
                name = "Qwen3 0.8B",
                size = "0.7GB",
                sizeBytes = 751619276L,
                url = "https://huggingface.co/Qwen/Qwen3-0.8B-GGUF/resolve/main/Qwen3-0.8B-Q4_K_M.gguf",
                filename = "qwen3-0.8b-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "qwen3_1.7b",
                name = "Qwen3 1.7B",
                size = "1.2GB",
                sizeBytes = 1288490188L,
                url = "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf",
                filename = "qwen3-1.7b-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 32768
            ),
            ModelInfo(
                id = "llama_3.2_1b",
                name = "Llama 3.2 1B",
                size = "0.8GB",
                sizeBytes = 858993459L,
                url = "https://huggingface.co/llama-factory/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
                filename = "llama-3.2-1b-instruct-q4_k_m.gguf",
                quantization = "Q4_K_M",
                contextSize = 8192
            ),
            ModelInfo(
                id = "phi_3.5_mini",
                name = "Phi-3.5 Mini",
                size = "2.5GB",
                sizeBytes = 2684354560L,
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
    
    fun getModelsDir(): String = modelsDir.absolutePath
    
    fun getAvailableModels(): List<ModelInfo> = AVAILABLE_MODELS
    
    fun getModelPath(modelId: String): String? {
        val model = AVAILABLE_MODELS.find { it.id == modelId } ?: return null
        return File(modelsDir, model.filename).absolutePath
    }
    
    fun modelExists(modelId: String): Boolean {
        val path = getModelPath(modelId) ?: return false
        val file = File(path)
        return file.exists() && file.length() > 0
    }
    
    fun getDownloadedModels(): List<ModelInfo> {
        return AVAILABLE_MODELS.filter { modelExists(it.id) }
    }
    
    fun getModelStatus(modelId: String): ModelStatus {
        val info = AVAILABLE_MODELS.find { it.id == modelId } ?: return ModelStatus(
            info = ModelInfo("", "", "", 0, "", "", "", 0),
            isDownloaded = false,
            isLoaded = false
        )
        val downloaded = modelExists(modelId)
        val loaded = getLoadedModelId() == modelId
        return ModelStatus(
            info = info,
            isDownloaded = downloaded,
            isLoaded = loaded,
            filePath = getModelPath(modelId) ?: ""
        )
    }
    
    fun getAllModelStatuses(): List<ModelStatus> {
        return AVAILABLE_MODELS.map { getModelStatus(it.id) }
    }
    
    fun getLoadedModelId(): String? {
        return prefs.getString(KEY_LOADED_MODEL, null)
    }
    
    fun getLoadedModelPath(): String? {
        val modelId = getLoadedModelId() ?: return null
        return getModelPath(modelId)
    }
    
    fun isModelLoaded(): Boolean {
        return getLoadedModelPath() != null && modelExists(getLoadedModelId() ?: "")
    }
    
    suspend fun downloadModel(modelId: String, onProgress: (Float) -> Unit): Result<String> {
        return withContext(Dispatchers.IO) {
            try {
                val model = AVAILABLE_MODELS.find { it.id == modelId }
                    ?: return@withContext Result.failure(Exception("Model not found"))
                
                val outputFile = File(modelsDir, model.filename)
                val tempFile = File(modelsDir, "${model.filename}.tmp")
                
                Log.d(TAG, "Downloading ${model.name} from ${model.url}")
                
                val url = URL(model.url)
                val connection = url.openConnection() as HttpURLConnection
                connection.connectTimeout = 30000
                connection.readTimeout = 60000
                connection.setRequestProperty("User-Agent", "ULTRON/1.0")
                connection.connect()
                
                if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                    return@withContext Result.failure(Exception("HTTP ${connection.responseCode}"))
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
                    
                    val progress = if (contentLength > 0) {
                        totalBytesRead.toFloat() / contentLength.toFloat()
                    } else {
                        -1f
                    }
                    onProgress(progress)
                    
                    // Yield to avoid blocking
                    if (totalBytesRead % (1024 * 1024) < 8192) {
                        yield()
                    }
                }
                
                outputStream.close()
                inputStream.close()
                
                // Verify download succeeded
                if (tempFile.length() > 0) {
                    if (outputFile.exists()) outputFile.delete()
                    tempFile.renameTo(outputFile)
                    Log.d(TAG, "Download complete: ${outputFile.length()} bytes")
                    Result.success(outputFile.absolutePath)
                } else {
                    tempFile.delete()
                    Result.failure(Exception("Download failed: empty file"))
                }
                
            } catch (e: Exception) {
                Log.e(TAG, "Download error", e)
                Result.failure(e)
            }
        }
    }
    
    suspend fun loadModel(modelId: String): Result<String> {
        return withContext(Dispatchers.IO) {
            try {
                if (!modelExists(modelId)) {
                    return@withContext Result.failure(Exception("Model not downloaded"))
                }
                
                val path = getModelPath(modelId) ?: return@withContext Result.failure(Exception("Invalid model path"))
                
                // Unload current model if any
                unloadModelInternal()
                
                // Load new model via inference manager
                val success = inferenceManager.loadModel(path)
                
                if (success) {
                    prefs.edit().putString(KEY_LOADED_MODEL, modelId).apply()
                    Log.d(TAG, "Model loaded: $modelId")
                    Result.success(path)
                } else {
                    Result.failure(Exception("Failed to load model into memory"))
                }
                
            } catch (e: Exception) {
                Log.e(TAG, "Load error", e)
                Result.failure(e)
            }
        }
    }
    
    suspend fun unloadModel(): Result<Boolean> {
        return withContext(Dispatchers.IO) {
            try {
                unloadModelInternal()
                prefs.edit().remove(KEY_LOADED_MODEL).apply()
                Log.d(TAG, "Model unloaded")
                Result.success(true)
            } catch (e: Exception) {
                Log.e(TAG, "Unload error", e)
                Result.failure(e)
            }
        }
    }
    
    private fun unloadModelInternal() {
        inferenceManager.unloadModel()
    }
    
    suspend fun deleteModel(modelId: String): Result<Boolean> {
        return withContext(Dispatchers.IO) {
            try {
                // Unload if loaded
                if (getLoadedModelId() == modelId) {
                    unloadModelInternal()
                    prefs.edit().remove(KEY_LOADED_MODEL).apply()
                }
                
                val path = getModelPath(modelId) ?: return@withContext Result.failure(Exception("Model not found"))
                val file = File(path)
                
                if (file.exists()) {
                    val deleted = file.delete()
                    if (deleted) {
                        Log.d(TAG, "Model deleted: $modelId")
                        Result.success(true)
                    } else {
                        Result.failure(Exception("Failed to delete file"))
                    }
                } else {
                    Result.success(true) // Already deleted
                }
                
            } catch (e: Exception) {
                Log.e(TAG, "Delete error", e)
                Result.failure(e)
            }
        }
    }
    
    fun getStorageUsed(): Long {
        return modelsDir.listFiles()?.sumOf { it.length() } ?: 0
    }
    
    fun getStorageAvailable(): Long {
        return modelsDir.freeSpace
    }
    
    fun getStorageTotal(): Long {
        return modelsDir.totalSpace
    }
}