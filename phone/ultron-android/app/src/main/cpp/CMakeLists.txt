# ULTRON Android - CMakeLists.txt
# JNI bridge to llama.cpp for local inference

cmake_minimum_required(VERSION 3.31.6)
project("ultron-inference")

# Find Android NDK components
find_library(log-lib log)
find_library(android-lib android)

# Add llama.cpp as a subdirectory
set(LLAMA_BUILD_COMMON ON CACHE BOOL "" FORCE)
set(LLAMA_BUILD_APP OFF CACHE BOOL "" FORCE)
set(LLAMA_OPENSSL OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL ON CACHE BOOL "" FORCE)
set(GGML_CPU_ALL_VARIANTS ON CACHE BOOL "" FORCE)
set(GGML_LLAMAFILE OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)

# Add llama.cpp
add_subdirectory(${CMAKE_SOURCE_DIR}/../../../../llama.cpp ${CMAKE_BINARY_DIR}/llama.cpp)

# Create our JNI library
add_library(
    ultron-inference
    SHARED
    ultron_inference.cpp
)

target_link_libraries(
    ultron-inference
    llama
    common
    ${log-lib}
    ${android-lib}
)

target_include_directories(
    ultron-inference
    PRIVATE
    ${CMAKE_SOURCE_DIR}/../../../../llama.cpp/include
    ${CMAKE_SOURCE_DIR}/../../../../llama.cpp/common
)