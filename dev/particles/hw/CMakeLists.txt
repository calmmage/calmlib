cmake_minimum_required(VERSION 3.23)
project(hw)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x")

add_executable(hw
        main.cpp)