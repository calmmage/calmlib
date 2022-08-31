//
// Created by Petr Lavrov on 30.08.2022.
//

#ifndef PARTICLES_ENGINE_PARTICLES_SIMULATOR_CONFIG_H_
#define PARTICLES_ENGINE_PARTICLES_SIMULATOR_CONFIG_H_

#include "core/asset_types.h"

namespace particle_simulator {


// preset 1 -
//static const int SPRITE_SIZE = 2;
//static const int NUM_PARTICLES = 3; // todo: make constructor parameter and config
//static const int TRAIL_DEPTH = 450;
//static const int TRAIL_VARIATION_LIMIT = 450; // coordinate with trail depth and mult
//static const int TRAIL_UPDATE_FREQUENCY = 1;
//static const TrailType TRAIL_TYPE = LINEAR_SQUARE_TRAIL;
////static const double TRAIL_VARIATION_MULT = 0.5; // trail size diff multiplier. Consider negative values!
//static const double TRAIL_VARIATION_MULT = 0.5; // trail size diff multiplier. Consider negative values!



// preset 2
//static const int SPRITE_SIZE = 2;
//static const int NUM_PARTICLES = 3; // todo: make constructor parameter and config
//static const int TRAIL_DEPTH = 450;
//static const int TRAIL_VARIATION_LIMIT = 450; // coordinate with trail depth and mult
//static const int TRAIL_UPDATE_FREQUENCY = 1;
//static const TrailType TRAIL_TYPE = LINEAR_SQUARE_TRAIL;
////static const double TRAIL_VARIATION_MULT = 1; // trail size diff multiplier. Consider negative values!
//static const double TRAIL_VARIATION_MULT = -0.5; // trail size diff multiplier. Consider negative values!


// preset 3 - dragons //
static const int SPRITE_SIZE = 60;
static const int NUM_PARTICLES = 10; // todo: make constructor parameter and config
static const int TRAIL_DEPTH = 100;
static const int TRAIL_VARIATION_LIMIT = 60; // coordinate with trail depth and mult
static const int TRAIL_UPDATE_FREQUENCY = 1;
// chineese dragons
//static const TrailType TRAIL_TYPE = LINEAR_SQUARE_TRAIL;
//static const double TRAIL_VARIATION_MULT = 0.5; // trail size diff multiplier. Consider negative values!

// sandclock dragons
//static const TrailType TRAIL_TYPE = PERIODIC_SQUARE_TRAIL;
//static const double TRAIL_VARIATION_MULT = 2; // trail size diff multiplier. Consider negative values!
//static const TrailType TRAIL_TYPE = LINEAR_VERTICAL_RECTANGLE;
//static const TrailType TRAIL_TYPE = LINEAR_HORIZONTAL_RECTANGLE;
static const double TRAIL_VARIATION_MULT = 2.5; // trail size diff multiplier. Consider negative values!
static const TrailType TRAIL_TYPE = PERIODIC_VERTICAL_RECTANGLE;
//static const TrailType TRAIL_TYPE = PERIODIC_HORIZONTAL_RECTANGLE;
//static const double TRAIL_VARIATION_MULT = 0.5; // trail size diff multiplier. Consider negative values!


// preset 4 - sperm
//static const int SPRITE_SIZE = 10;
//static const int NUM_PARTICLES = 100; // todo: make constructor parameter and config
//static const int TRAIL_DEPTH = 20;
//static const int TRAIL_VARIATION_LIMIT = 450; // coordinate with trail depth and mult
//static const int TRAIL_UPDATE_FREQUENCY = 1;
//static const TrailType TRAIL_TYPE = LINEAR_SQUARE_TRAIL;
//static const double TRAIL_VARIATION_MULT = 1; // trail size diff multiplier. Consider negative values!


//////////////////////////////////////////////
// play arond with
// todo: remove. This doesn't work as expected..
static const int SCREEN_REFRESH_FREQUENCY = 1; // how often to clean the screen
//static const int SCREEN_REFRESH_FREQUENCY = 1; // how often to clean the screen

//static const int BOUNDARY_OVERFLOW = -200;
static const int BOUNDARY_OVERFLOW = -10; // particle size?
//static const int BOUNDARY_OVERFLOW = 100;

static const float ACCELERATION_COEFFICIENT = 20;
static const float ANGULAR_ACCELERATION_COEFFICIENT = 0.1;

//////////////////////////////////////////////
static const int PHYSICS_FPS_MULT = 1; // todo: move to a proper class, add to config.
static const int WIN_WIDTH = 1800, WIN_HEIGHT = 1000; // todo: move to a proper class, add to config.
//static const int NUM_PARTICLES = 3; // todo: make constructor parameter and config
//static const int NUM_PARTICLES = 200; // todo: make constructor parameter and config
//static const int NUM_PARTICLES = 20; // todo: make constructor parameter and config
static const int FPS = 120; // todo: make constructor parameter and config
//static const int SCREEN_REFRESH_FREQUENCY = 1; // how often to clean the screen


//////////////////////////////////////////////
// Trail

//static const int TRAIL_DEPTH = 450;
//static const int TRAIL_DEPTH = 6; // todo: config per particle

//static const int TRAIL_UPDATE_FREQUENCY = 1;
//static const int TRAIL_UPDATE_FREQUENCY = 20; // each n-th frame
//static const int TRAIL_UPDATE_FREQUENCY = 10; // each n-th frame

//static const double TRAIL_VARIATION_MULT = 1; // trail size diff multiplier. Consider negative values!
//static const double TRAIL_VARIATION_MULT = 3;
//static const double TRAIL_VARIATION_MULT = -1;
//static const int TRAIL_VARIATION_LIMIT = 60; // coordinate with trail depth and mult

static const int TRAIL_MIN_SIZE = 1; // min size of trail sprite.
static const int TRAIL_MAX_SIZE = 110; // min size of trail sprite.
//static const TrailType TRAIL_TYPE = LINEAR_SQUARE_TRAIL;


//////////////////////////////////////////////
// Engine configs

static const float ENGINE_TIME_STEP = 0.01; // todo: make a proper config - Engine constructor / config file?
//static const float ACCELERATION_COEFFICIENT = 20;
//static const float ANGULAR_ACCELERATION_COEFFICIENT = 0.1;


//////////////////////////////////////////////
// Canvas configs

//static const int SPRITE_SIZE = 100;
//static const int SPRITE_SIZE = 10;
static const SDL_Color SPRITE_COLOR = {255, 255, 255, 255};
//SDL_Color SPRITE_COLOR = {216, 216, 216, 255};
static const SpriteType SPRITE_TYPE = HOLLOW_SQUARE;

static const SDL_Color CANVAS_COLOR = {0, 0, 0, 255}; // black
//SDL_Color CANVAS_COLOR = {255, 255, 255, 255}; // white

static const SpriteColorScheme SPRITE_COLOR_SCHEME = PLAIN_COLOR_SCHEME;

//////////////////////////////////////////////
// New configs
static const bool TRAIL_FADE = true; // TODO: add to visualizer
static const int TRAIL_FADE_AMOUNT = 5;
static const Uint8 TRAIL_FADE_MIN = 50;

} // particle_simulator

#endif //PARTICLES_ENGINE_PARTICLES_SIMULATOR_CONFIG_H_
