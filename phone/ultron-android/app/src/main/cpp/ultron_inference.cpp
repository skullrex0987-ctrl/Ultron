// ULTRON Android - JNI Bridge
// C++ implementation connecting Kotlin to llama.cpp

#include <jni.h>
#include <string>
#include <memory>
#include <android/log.h>

#include "llama.h"
#include "common/common.h"
#include "common/sampling.h"

#define LOG_TAG "UltronInference"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

struct InferenceContext {
    llama_model* model = nullptr;
    llama_context* ctx = nullptr;
    gpt_params params;
    std::vector<llama_chat_message> messages;
    
    ~InferenceContext() {
        if (ctx) llama_free(ctx);
        if (model) llama_model_free(model);
    }
};

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeCreate(JNIEnv* env, jobject /* this */) {
    auto* ctx = new InferenceContext();
    LOGI("Inference engine created");
    return reinterpret_cast<jlong>(ctx);
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeDestroy(JNIEnv* env, jobject /* this */, jlong handle) {
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    delete ctx;
    LOGI("Inference engine destroyed");
}

JNIEXPORT jboolean JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeLoadModel(
    JNIEnv* env, jobject /* this */, jlong handle, jstring path) {
    
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (!ctx) return JNI_FALSE;
    
    const char* modelPath = env->GetStringUTFChars(path, nullptr);
    LOGI("Loading model: %s", modelPath);
    
    ctx->params.model = modelPath;
    ctx->params.n_ctx = 4096;
    ctx->params.n_gpu_layers = 99; // Use GPU if available
    ctx->params.cpuparams.n_threads = 4;
    ctx->params.cpuparams_batch.n_threads = 4;
    
    auto mparams = llama_model_default_params();
    ctx->params.hf_file = "";
    ctx->params.hf_repo = "";
    ctx->params.prompt = "";
    ctx->params.use_jinja = true;
    
    llama_backend_init();
    llama_numa_init(ctx->params.numa);
    
    auto lparams = llama_context_default_params();
    lparams.n_ctx = ctx->params.n_ctx;
    lparams.n_batch = ctx->params.n_batch;
    lparams.n_ubatch = ctx->params.n_ubatch;
    lparams.n_gpu_layers = ctx->params.n_gpu_layers;
    lparams.main_gpu = ctx->params.main_gpu;
    lparams.split_mode = ctx->params.split_mode;
    lparams.tensor_split = ctx->params.tensor_split;
    lparams.use_mmap = ctx->params.use_mmap;
    lparams.use_mlock = ctx->params.use_mlock;
    lparams.flash_attn = ctx->params.flash_attn;
    lparams.kv_unified = ctx->params.kv_unified;
    lparams.overrides = ctx->params.overrides;
    lparams.n_threads = ctx->params.cpuparams.n_threads;
    lparams.cpuparams = ctx->params.cpuparams;
    lparams.cpuparams_batch = ctx->params.cpuparams_batch;
    
    ctx->model = llama_model_load_from_file(modelPath, mparams);
    env->ReleaseStringUTFChars(path, modelPath);
    
    if (!ctx->model) {
        LOGE("Failed to load model");
        return JNI_FALSE;
    }
    
    ctx->ctx = llama_init_from_model(ctx->model, lparams);
    if (!ctx->ctx) {
        llama_model_free(ctx->model);
        ctx->model = nullptr;
        LOGE("Failed to create context");
        return JNI_FALSE;
    }
    
    LOGI("Model loaded successfully");
    return JNI_TRUE;
}

JNIEXPORT jstring JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeInfer(
    JNIEnv* env, jobject /* this */, jlong handle, jstring prompt) {
    
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (!ctx || !ctx->ctx) {
        return env->NewStringUTF("Error: No model loaded");
    }
    
    const char* promptStr = env->GetStringUTFChars(prompt, nullptr);
    LOGI("Inference prompt: %s", promptStr);
    
    std::string response;
    
    try {
        // Simple inference
        const int n_ctx = llama_n_ctx(ctx->ctx);
        const int n_ctx_train = llama_model_n_ctx_train(ctx->model);
        
        std::vector<llama_token> tokens_list = ::llama_tokenize(ctx->ctx, promptStr, true, true);
        
        if (tokens_list.size() > n_ctx) {
            response = "Error: Prompt too long for context size";
        } else {
            // Create batch and decode
            llama_batch batch = llama_batch_init(512, 0, 1);
            
            // Add tokens
            for (size_t i = 0; i < tokens_list.size(); i++) {
                llama_batch_add(batch, tokens_list[i], i, {0}, false);
            }
            
            // Generate response
            std::string generated;
            while (generated.size() < 512) {
                if (llama_decode(ctx->ctx, batch) != 0) {
                    response = "Error: Inference failed";
                    break;
                }
                
                // Sample next token
                auto* logits = llama_get_logits_ith(ctx->ctx, batch.n_tokens - 1);
                auto n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(ctx->model));
                
                llama_token new_token_id = 0;
                // Simple greedy sampling
                float max_logit = -INFINITY;
                for (int i = 0; i < n_vocab; i++) {
                    if (logits[i] > max_logit) {
                        max_logit = logits[i];
                        new_token_id = i;
                    }
                }
                
                // Check for EOS
                if (llama_vocab_is_eog(llama_model_get_vocab(ctx->model), new_token_id)) {
                    break;
                }
                
                // Decode token
                char buf[32];
                int n = llama_token_to_piece(llama_model_get_vocab(ctx->model), new_token_id, buf, sizeof(buf), 0, true);
                if (n > 0) {
                    generated.append(buf, n);
                }
                
                // Prepare next batch
                llama_batch_clear(batch);
                llama_batch_add(batch, new_token_id, batch.n_tokens, {0}, true);
            }
            
            llama_batch_free(batch);
            response = generated.empty() ? "No response generated" : generated;
        }
        
    } catch (const std::exception& e) {
        response = std::string("Error: ") + e.what();
        LOGE("Inference exception: %s", e.what());
    }
    
    env->ReleaseStringUTFChars(prompt, promptStr);
    LOGI("Response: %s", response.c_str());
    return env->NewStringUTF(response.c_str());
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeStop(JNIEnv* env, jobject /* this */, jlong handle) {
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (ctx && ctx->ctx) {
        llama_stop(ctx->ctx);
    }
}

JNIEXPORT jint JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeGetContextSize(JNIEnv* env, jobject /* this */, jlong handle) {
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (!ctx || !ctx->ctx) return 0;
    return llama_n_ctx(ctx->ctx);
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeSetContextSize(JNIEnv* env, jobject /* this */, jlong handle, jint size) {
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (!ctx || !ctx->ctx) return;
    llama_set_n_ctx(ctx->ctx, size);
}

JNIEXPORT jint JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeGetGpuLayers(JNIEnv* env, jobject /* this */, jlong handle) {
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (!ctx || !ctx->ctx) return 0;
    return llama_n_gpu_layers(ctx->ctx);
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeSetGpuLayers(JNIEnv* env, jobject /* this */, jlong handle, jint layers) {
    // Note: GPU layers can only be set at model load time
    auto* ctx = reinterpret_cast<InferenceContext*>(handle);
    if (ctx) {
        ctx->params.n_gpu_layers = layers;
    }
}

} // extern "C"