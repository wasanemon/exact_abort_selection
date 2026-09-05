cmake_minimum_required(VERSION 3.2)
project(aria)

#set(CMAKE_BUILD_TYPE Debug)
#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -Wall -Wno-long-long -Wno-unused-variable -Wno-variadic-macros -pedantic")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -Wall -Wno-long-long -Wno-unused-variable -Wno-variadic-macros -pedantic -O2")
set(CMAKE_CXX_STANDARD 14)

find_library(jemalloc_lib jemalloc) # jemalloc 5.0

# additional target to perform clang-format run, requires clang-format

# get all project files
file(GLOB_RECURSE ALL_SOURCE_FILES benchmark/*.h common/*.h core/*.h protocol/*.h bench*.cpp)

add_custom_target(
        format
        COMMAND clang-format
        -style=LLVM
        -i
        -sort-includes
        ${ALL_SOURCE_FILES}
)

include_directories(${CMAKE_SOURCE_DIR})

file(GLOB_RECURSE COMMON_SOURCE_FILES common/*.cpp)
add_library(common STATIC ${COMMON_SOURCE_FILES})

if(APPLE)
    find_package(glog REQUIRED)
    find_package(gflags REQUIRED)
    target_link_libraries(common ${jemalloc_lib} glog::glog gflags)
else()
    target_link_libraries(common ${jemalloc_lib} glog gflags)
endif()

add_executable(bench_tpcc bench_tpcc.cpp)
target_link_libraries(bench_tpcc common)

add_executable(bench_ycsb bench_ycsb.cpp)
target_link_libraries(bench_ycsb common)

# The historical targets and defaults above are unchanged.
option(ARIA_BUILD_EAS "Build the local Exact Abort Selection experiment" OFF)
set(EAS_SANITIZER "" CACHE STRING "EAS-only sanitizer: address,undefined or thread")
if(ARIA_BUILD_EAS)
    enable_testing()
    add_library(eas_selector STATIC eas/Selector.cpp eas/Oracle.cpp)
    add_library(eas_engine STATIC eas/Engine.cpp)
    if(APPLE)
        target_link_libraries(eas_engine eas_selector glog::glog)
    else()
        # Avoid jemalloc interposition in sanitizer targets.
        target_link_libraries(eas_engine eas_selector glog)
    endif()
    add_executable(bench_eas bench_eas.cpp)
    target_link_libraries(bench_eas eas_engine)
    add_executable(eas_selector_test tests/eas_selector_test.cpp)
    target_link_libraries(eas_selector_test eas_selector)
    add_executable(eas_integration_test tests/eas_integration_test.cpp)
    target_link_libraries(eas_integration_test eas_engine)
    add_executable(policy_comparison_test tests/policy_comparison_test.cpp)
    target_link_libraries(policy_comparison_test eas_selector)
    if(EAS_SANITIZER)
        foreach(target eas_selector eas_engine bench_eas eas_selector_test eas_integration_test policy_comparison_test)
            target_compile_options(${target} PRIVATE -g -fno-omit-frame-pointer -fsanitize=${EAS_SANITIZER})
            set_property(TARGET ${target} APPEND_STRING PROPERTY LINK_FLAGS " -fsanitize=${EAS_SANITIZER}")
        endforeach()
    endif()
    add_test(NAME eas_selector COMMAND eas_selector_test --failure-dir ${CMAKE_SOURCE_DIR}/experiments/eas/validation)
    add_test(NAME eas_integration COMMAND eas_integration_test)
    add_test(NAME policy_comparison COMMAND policy_comparison_test)
endif()
