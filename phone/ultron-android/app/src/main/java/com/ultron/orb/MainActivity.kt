// ULTRON Android - MainActivity.kt
// Standalone APK with local LLM inference (llama.cpp) + ORB + gestures

package com.ultron.orb

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.ultron.orb.databinding.ActivityMainBinding
import com.ultron.orb.inference.InferenceManager
import com.ultron.orb.ui.OrbView
import com.ultron.orb.gesture.GestureManager
import com.ultron.orb.model.ModelManager

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var orbView: OrbView
    private lateinit var inferenceManager: InferenceManager
    private lateinit var gestureManager: GestureManager
    private lateinit var modelManager: ModelManager

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.values.all { it }
        if (allGranted) {
            initializeApp()
        } else {
            Toast.makeText(this, "Permissions required for full functionality", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Initialize managers
        modelManager = ModelManager(this)
        inferenceManager = InferenceManager(this)
        orbView = OrbView(binding.orbContainer)
        gestureManager = GestureManager(this, orbView)

        // Check permissions
        checkPermissions()

        // Setup UI
        setupUI()
    }

    private fun checkPermissions() {
        val permissions = mutableListOf<String>()
        
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) 
            != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.RECORD_AUDIO)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) 
            != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.CAMERA)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) 
                != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (permissions.isNotEmpty()) {
            requestPermissionLauncher.launch(permissions.toTypedArray())
        } else {
            initializeApp()
        }
    }

    private fun initializeApp() {
        // Initialize llama.cpp native library
        inferenceManager.initialize()

        // Load default or last used model
        val lastModel = modelManager.getLastUsedModel()
        if (lastModel != null && modelManager.modelExists(lastModel)) {
            inferenceManager.loadModel(modelManager.getModelPath(lastModel))
        } else {
            // Show model download dialog on first launch
            showModelDownloadDialog()
        }

        // Start gesture recognition
        gestureManager.start()

        // Setup chat interface
        setupChat()
    }

    private fun setupUI() {
        // Model selector
        binding.btnModelSelector.setOnClickListener {
            showModelSelector()
        }

        // Settings
        binding.btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // Mic button for voice input
        binding.btnMic.setOnClickListener {
            toggleVoiceInput()
        }

        // Text input
        binding.btnSend.setOnClickListener {
            val text = binding.etInput.text.toString().trim()
            if (text.isNotEmpty()) {
                sendMessage(text)
            }
        }

        // Gesture button
        binding.btnGesture.setOnClickListener {
            gestureManager.toggleGestureMode()
        }
    }

    private fun setupChat() {
        orbView.setOnOrbClickListener {
            toggleVoiceInput()
        }
    }

    private fun sendMessage(text: String) {
        // Add user message to chat
        addMessage(text, isUser = true)
        binding.etInput.setText("")

        // Show thinking state
        orbView.setState(OrbView.State.THINKING)

        // Run inference
        inferenceManager.infer(text) { response ->
            runOnUiThread {
                addMessage(response, isUser = false)
                orbView.setState(OrbView.State.IDLE)
            }
        }
    }

    private fun addMessage(text: String, isUser: Boolean) {
        // Add message to RecyclerView
        val adapter = binding.rvChat.adapter as? ChatAdapter
        adapter?.addMessage(Message(text, isUser))
        binding.rvChat.scrollToPosition(adapter?.itemCount?.minus(1) ?: 0)
    }

    private fun toggleVoiceInput() {
        if (gestureManager.isListening()) {
            gestureManager.stopListening()
            orbView.setState(OrbView.State.IDLE)
        } else {
            gestureManager.startListening { text ->
                sendMessage(text)
            }
            orbView.setState(OrbView.State.LISTENING)
        }
    }

    private fun showModelDownloadDialog() {
        val dialog = ModelDownloadDialog(this) { model ->
            downloadModel(model)
        }
        dialog.show()
    }

    private fun showModelSelector() {
        val dialog = ModelSelectorDialog(this, modelManager.getAvailableModels()) { model ->
            loadModel(model)
        }
        dialog.show()
    }

    private fun downloadModel(model: ModelInfo) {
        orbView.setState(OrbView.State.THINKING)
        modelManager.downloadModel(model) { success ->
            runOnUiThread {
                if (success) {
                    loadModel(model)
                } else {
                    Toast.makeText(this, "Download failed", Toast.LENGTH_SHORT).show()
                    orbView.setState(OrbView.State.IDLE)
                }
            }
        }
    }

    private fun loadModel(model: ModelInfo) {
        orbView.setState(OrbView.State.THINKING)
        inferenceManager.loadModel(modelManager.getModelPath(model.id))
        modelManager.setLastUsedModel(model.id)
        binding.tvModelName.text = model.displayName
        orbView.setState(OrbView.State.IDLE)
        Toast.makeText(this, "Loaded ${model.displayName}", Toast.LENGTH_SHORT).show()
    }

    override fun onDestroy() {
        super.onDestroy()
        gestureManager.stop()
        inferenceManager.release()
    }
}