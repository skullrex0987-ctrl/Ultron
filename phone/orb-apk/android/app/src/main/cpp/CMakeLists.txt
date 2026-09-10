cmake_minimum_required(VERSION 3.22.1)
project("ultron-inference")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_library(log-lib log)
find_library(android-lib android)

set(LLAMA_DIR ${CMAKE_SOURCE_DIR}/../../llama.cpp)

if(EXISTS ${LLAMA_DIR}/include/llama.h)
    message(STATUS "llama.cpp found - building with local inference")
    
    set(BUILD_SHARED_LIBS OFF)
    
    add_library(ggml STATIC
        ${LLAMA_DIR}/ggml/src/ggml.c
        ${LLAMA_DIR}/ggml/src/ggml-alloc.c
        ${LLAMA_DIR}/ggml/src/ggml-backend.c
        ${LLAMA_DIR}/ggml/src/ggml-quants.c
        ${LLAMA_DIR}/ggml/src/ggml-cpu.c
    )
    target_include_directories(ggml PUBLIC ${LLAMA_DIR}/ggml/include)
    
    add_library(llama STATIC
        ${LLAMA_DIR}/src/llama.cpp
        ${LLAMA_DIR}/src/llama-vocab.cpp
        ${LLAMA_DIR}/src/llama-grammar.cpp
        ${LLAMA_DIR}/src/llama-sampling.cpp
        ${LLAMA_DIR}/src/llama-chat.cpp
        ${LLAMA_DIR}/src/unicode.cpp
        ${LLAMA_DIR}/src/unicode-data.cpp
    )
    target_include_directories(llama PUBLIC ${LLAMA_DIR}/include ${LLAMA_DIR}/ggml/include)
    target_link_libraries(llama PUBLIC ggml)
    
    add_library(ultron-inference SHARED ultron_inference.cpp)
    target_include_directories(ultron-inference PRIVATE ${LLAMA_DIR}/include ${LLAMA_DIR}/ggml/include)
    target_link_libraries(ultron-inference llama ggml ${log-lib} ${android-lib})
else()
    message(STATUS "llama.cpp not found - building stub")
    add_library(ultron-inference SHARED ultron_inference_stub.cpp)
    target_link_libraries(ultron-inference ${log-lib} ${android-lib})
endif()
