// ULTRON Android - JNI Stub
// Placeholder for llama.cpp integration (full version in v1.1)

#include <jni.h>
#include <string>
#include <android/log.h>

#define LOG_TAG "UltronInference"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeCreate(JNIEnv* env, jobject /* this */) {
    LOGI("Inference engine created (stub)");
    return 1;
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeDestroy(JNIEnv* env, jobject /* this */, jlong handle) {
    LOGI("Inference engine destroyed");
}

JNIEXPORT jboolean JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeLoadModel(
    JNIEnv* env, jobject /* this */, jlong handle, jstring path) {
    LOGI("Model loading stub - llama.cpp integration in v1.1");
    return JNI_TRUE;
}

JNIEXPORT jstring JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeInfer(
    JNIEnv* env, jobject /* this */, jlong handle, jstring prompt) {
    const char* promptStr = env->GetStringUTFChars(prompt, nullptr);
    std::string response = "ULTRON v1.0 - Local LLM integration coming in v1.1. ";
    response += "For now, please use cloud providers (OpenRouter, Claude, GPT, DeepSeek). ";
    response += "Your prompt was: \"";
    response += promptStr;
    response += "\"";
    env->ReleaseStringUTFChars(prompt, promptStr);
    return env->NewStringUTF(response.c_str());
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeStop(JNIEnv* env, jobject /* this */, jlong handle) {
    LOGI("Inference stopped");
}

JNIEXPORT jint JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeGetContextSize(JNIEnv* env, jobject /* this */, jlong handle) {
    return 4096;
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeSetContextSize(JNIEnv* env, jobject /* this */, jlong handle, jint size) {
}

JNIEXPORT jint JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeGetGpuLayers(JNIEnv* env, jobject /* this */, jlong handle) {
    return 0;
}

JNIEXPORT void JNICALL
Java_com_ultron_orb_inference_InferenceManager_nativeSetGpuLayers(JNIEnv* env, jobject /* this */, jlong handle, jint layers) {
}

}