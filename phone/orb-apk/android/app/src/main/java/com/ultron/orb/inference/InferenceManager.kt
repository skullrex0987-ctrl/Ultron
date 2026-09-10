// ULTRON Android - InferenceManager.kt
// Manages local LLM inference via llama.cpp JNI

package com.ultron.orb.inference

import android.content.Context
import android.util.Log
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.Future

class InferenceManager(private val context: Context) {
    private var nativeHandle: Long = 0
    private val executor = Executors.newSingleThreadExecutor()
    private var currentFuture: Future<*>? = null
    private var isModelLoaded = false

    companion object {
        private const val TAG = "InferenceManager"
        
        init {
            try {
                System.loadLibrary("ultron-inference")
                Log.d(TAG, "Native library loaded successfully")
            } catch (e: UnsatisfiedLinkError) {
                Log.e(TAG, "Failed to load native library", e)
            }
        }
    }

    fun initialize() {
        nativeHandle = nativeCreate()
        Log.d(TAG, "Inference engine created: handle=$nativeHandle")
    }

    fun loadModel(path: String): Boolean {
        if (nativeHandle == 0L) {
            Log.e(TAG, "Engine not initialized")
            return false
        }
        
        val file = File(path)
        if (!file.exists()) {
            Log.e(TAG, "Model file not found: $path")
            return false
        }

        isModelLoaded = nativeLoadModel(nativeHandle, path)
        Log.d(TAG, "Model loaded: $isModelLoaded (${file.length() / 1024 / 1024}MB)")
        return isModelLoaded
    }

    fun infer(prompt: String, callback: (String) -> Unit) {
        if (!isModelLoaded) {
            callback("No model loaded. Please download a model first.")
            return
        }

        currentFuture?.cancel(true)
        currentFuture = executor.submit {
            try {
                val response = nativeInfer(nativeHandle, prompt)
                callback(response)
            } catch (e: Exception) {
                Log.e(TAG, "Inference error", e)
                callback("Error: ${e.message}")
            }
        }
    }

    fun stopInference() {
        currentFuture?.cancel(true)
        if (nativeHandle != 0L) {
            nativeStop(nativeHandle)
        }
    }

    fun release() {
        stopInference()
        if (nativeHandle != 0L) {
            nativeDestroy(nativeHandle)
            nativeHandle = 0
        }
        executor.shutdown()
    }

    fun isModelLoaded(): Boolean = isModelLoaded

    fun getContextSize(): Int = if (nativeHandle != 0L) nativeGetContextSize(nativeHandle) else 0

    fun setContextSize(size: Int) {
        if (nativeHandle != 0L) nativeSetContextSize(nativeHandle, size)
    }

    fun getGpuLayers(): Int = if (nativeHandle != 0L) nativeGetGpuLayers(nativeHandle) else 0

    fun setGpuLayers(layers: Int) {
        if (nativeHandle != 0L) nativeSetGpuLayers(nativeHandle, layers)
    }

    // Native methods (implemented in C++ via JNI)
    private external fun nativeCreate(): Long
    private external fun nativeDestroy(handle: Long)
    private external fun nativeLoadModel(handle: Long, path: String): Boolean
    private external fun nativeInfer(handle: Long, prompt: String): String
    private external fun nativeStop(handle: Long)
    private external fun nativeGetContextSize(handle: Long): Int
    private external fun nativeSetContextSize(handle: Long, size: Int)
    private external fun nativeGetGpuLayers(handle: Long): Int
    private external fun nativeSetGpuLayers(handle: Long, layers: Int)
}