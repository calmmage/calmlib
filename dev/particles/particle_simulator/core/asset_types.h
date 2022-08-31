//
// Created by Petr Lavrov on 30.08.2022.
//

#ifndef PARTICLES_ENGINE_PARTICLES_SIMULATOR_ASSET_TYPES_H_
#define PARTICLES_ENGINE_PARTICLES_SIMULATOR_ASSET_TYPES_H_

#include <SDL2/SDL_timer.h>
#include <SDL2/SDL_image.h>
#include <SDL2/SDL.h>
//#include "asset_manager.h"
#include "../config.h"
#include <deque>
#include <vector>

namespace particle_simulator {

//////////////////////////////////////////////
// Assets
struct SimpleCartesianParticle {
  float x; //
  float y; //
};
struct SimplePolarParticle {
  float r;
  float phi;
};
struct KineticCartesianParticle : SimpleCartesianParticle {
  float v_x; // horizontal speed component
  float v_y; // vertical speed component
};
struct KineticPolarParticle : SimpleCartesianParticle {
  float speed;
  float direction;
};
struct DynamicCartesianParticle : KineticCartesianParticle {
  float a_x; // horizontal acceleration component
  float a_y; // vertical acceleration component
};
struct DynamicParticle : KineticCartesianParticle {
  float m; // mass
};
struct Trail {
  explicit Trail(const unsigned short trail_depth, KineticPolarParticle *particle) : tracked_particle(particle) {
//    positions.resize(trail_depth);
  };
  // todo
  std::deque<SimpleCartesianParticle> positions; // how to specify depth?
//  SimpleCartesianParticle *tracked_particle;
  KineticPolarParticle *tracked_particle;
};


//////////////////////////////////////////////
// Canvas


enum SpriteType {
  HOLLOW_SQUARE,
  HOLLOW_CIRCLE
};

enum TrailType {
  LINEAR_SQUARE_TRAIL, // adjust square size linearly
  PERIODIC_SQUARE_TRAIL,
  LINEAR_VERTICAL_RECTANGLE,
  LINEAR_HORIZONTAL_RECTANGLE,
  PERIODIC_VERTICAL_RECTANGLE,
  PERIODIC_HORIZONTAL_RECTANGLE,
};

enum SpriteColorScheme {
  PLAIN_COLOR_SCHEME, // color = SPRITE_COLOR
  SPEED_COLOR_SCHEME,
  DIRECTION_COLOR_SCHEME, //
  RANDOM_COLOR_SCHEME, // Fixed Random color per particle, but fixed?
  RAINBOW_COLOR_SCHEME, // Changing random color for each
  // todo: how to generate random colors beautifully, gradually?

  // todo: consider. make trail change colors over time?. random color per particle
  // need to add color to SimpleCartesianParticle

};

//struct SDLColor {
//  unsigned short r = 0;
//  unsigned short g = 0;
//  unsigned short b = 0;
//  unsigned short opacity = 255;
//};
// todo: make a proper config. How are configs done in C++?
struct CanvasConfig {
  SpriteType sprite_type = HOLLOW_SQUARE;
  int sprite_size = 1;
  // int sprite_width = 1; // todo: rect
  // int sprite_height = 1; // todo: rect
  SDL_Color sprite_color = {255, 255, 255, 255};
};

} // particle_simulator

#endif //PARTICLES_ENGINE_PARTICLES_SIMULATOR_ASSET_TYPES_H_
