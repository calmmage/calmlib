cmake_minimum_required(VERSION 3.23)
project(particle_simulator)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x -L/opt/homebrew/lib")

find_package(SDL2 REQUIRED)
include_directories(particle_simulator ${SDL2_INCLUDE_DIRS})

add_executable(particle_simulator
        main.cpp
        config.h

        core/asset_types.h
        core/asset_manager.cpp core/asset_manager.h

        core/canvas.cpp core/canvas.h

        core/physics_engine.cpp core/physics_engine.h
        ../config_menu/main.cpp)

INCLUDE(FindPkgConfig)

PKG_SEARCH_MODULE(SDL2 REQUIRED sdl2)
PKG_SEARCH_MODULE(SDL2IMAGE REQUIRED SDL2_image>=2.0.0)
#
INCLUDE_DIRECTORIES(${SDL2_INCLUDE_DIRS} ${SDL2IMAGE_INCLUDE_DIRS})
TARGET_LINK_LIBRARIES(${PROJECT_NAME} ${SDL2_LIBRARIES} ${SDL2IMAGE_LIBRARIES})


