// ULTRON Android - InferenceManager.kt
// Manages local LLM inference via llama.cpp JNI

package com.ultron.orb.inference

import android.content.Context
import android.util.Log
import java.io.File

class InferenceManager(private val context: Context) {
    private var nativeHandle: Long = 0
    private var currentModelPath: String? = null
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

        // Unload current model if any
        if (isModelLoaded) {
            unloadModel()
        }

        val success = nativeLoadModel(nativeHandle, path)
        if (success) {
            currentModelPath = path
            isModelLoaded = true
            Log.d(TAG, "Model loaded: $path (${file.length() / 1024 / 1024}MB)")
        } else {
            Log.e(TAG, "Failed to load model")
        }
        return success
    }

    fun unloadModel() {
        if (nativeHandle != 0L && isModelLoaded) {
            nativeUnload(nativeHandle)
            currentModelPath = null
            isModelLoaded = false
            Log.d(TAG, "Model unloaded")
        }
    }

    fun infer(prompt: String): String {
        if (!isModelLoaded || nativeHandle == 0L) {
            return "Error: No model loaded"
        }
        return nativeInfer(nativeHandle, prompt)
    }

    fun isModelLoaded(): Boolean = isModelLoaded

    fun getCurrentModelPath(): String? = currentModelPath

    fun release() {
        unloadModel()
        if (nativeHandle != 0L) {
            nativeDestroy(nativeHandle)
            nativeHandle = 0
        }
    }

    // Native methods
    private external fun nativeCreate(): Long
    private external fun nativeDestroy(handle: Long)
    private external fun nativeLoadModel(handle: Long, path: String): Boolean
    private external fun nativeUnload(handle: Long)
    private external fun nativeInfer(handle: Long, prompt: String): String
}