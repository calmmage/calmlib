cmake_minimum_required(VERSION 3.23)
project(particles_engine)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x -L/opt/homebrew/lib")

find_package(SDL2 REQUIRED)
include_directories(particles ${SDL2_INCLUDE_DIRS})

add_executable(particles_engine
        main.cpp asset_manager.cpp asset_manager.h physics_engine.cpp physics_engine.h canvas.cpp canvas.h)

INCLUDE(FindPkgConfig)

PKG_SEARCH_MODULE(SDL2 REQUIRED sdl2)
PKG_SEARCH_MODULE(SDL2IMAGE REQUIRED SDL2_image>=2.0.0)
#
INCLUDE_DIRECTORIES(${SDL2_INCLUDE_DIRS} ${SDL2IMAGE_INCLUDE_DIRS})
TARGET_LINK_LIBRARIES(${PROJECT_NAME} ${SDL2_LIBRARIES} ${SDL2IMAGE_LIBRARIES})


