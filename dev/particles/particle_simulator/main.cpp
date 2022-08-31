//
// Created by Petr Lavrov on 29.08.2022.
//

#include <iostream>
#include <random>
#include "core/asset_manager.h"
#include "core/canvas.h"
#include "core/physics_engine.h"
#include "config.h"
#include "core/asset_types.h"

using namespace particle_simulator;

void run_logic(AssetManager &asset_manager) {
  // todo: convert to a proper boundary handling, all types of boundaries (through Asset Manager?)
  for (auto &particle : asset_manager.kinetic_polar_particles_) {

    // right boundary
    if (particle.x > WIN_WIDTH + BOUNDARY_OVERFLOW) {
      particle.x = WIN_WIDTH + BOUNDARY_OVERFLOW - 1;
      particle.direction = M_PI - particle.direction; // bounce right boundary
    }

    // left boundary
    if (particle.x < 0 - BOUNDARY_OVERFLOW) {
      particle.x = 0.f - BOUNDARY_OVERFLOW + 1;
      particle.direction = M_PI - particle.direction; // bounce left boundary
    }

    // bottom boundary
    if (particle.y > WIN_HEIGHT + BOUNDARY_OVERFLOW) {
      particle.y = WIN_HEIGHT + BOUNDARY_OVERFLOW - 1;
      particle.direction = -particle.direction; // bounce bottom boundary
    }

    // upper boundary
    if (particle.y < 0 - BOUNDARY_OVERFLOW) {
      particle.y = 0.f - BOUNDARY_OVERFLOW + 1;
      particle.direction = -particle.direction; // bounce upper boundary
    }
  }
};

int main() { // App
  std::cout << "Launching particle simulator. Version 1: randomized kinematics\n";

  // Load assets
  AssetManager assetManager;
  // populate particles
  assetManager.kinetic_polar_particles_.resize(NUM_PARTICLES);
  // todo: init particle coordinates? to zeros? to random?. Do I even need this?
//    KineticPolarParticle value{.direction=0,.speed=0,.x=0,.y=0};
//    KineticPolarParticle value{0,0,0,0};
//    KineticPolarParticle value{};
//    value.x = 0;
//    value.y = 0;
//    value.direction = 0;
//    value.speed = 0;
//    fill(assetManager.kinetic_polar_particles_.begin(), assetManager.kinetic_polar_particles_.end(), value);

  std::random_device rd;
  std::mt19937 mt(rd());
  std::uniform_real_distribution<float> dist_x(0.f, (float) WIN_WIDTH);
  std::uniform_real_distribution<float> dist_y(0.f, (float) WIN_HEIGHT);

  for (auto &particle : assetManager.kinetic_polar_particles_) {
    particle.x = dist_x(mt);
    particle.y = dist_y(mt);
    particle.speed = 0;
    particle.direction = 0;
  }

  // populate trails
  for (int i = 0; i < NUM_PARTICLES; i++) {
    Trail trail(assetManager.trail_depth, &assetManager.kinetic_polar_particles_[i]);
    assetManager.trails_.push_back(trail);
  }


  ////////////////////////////////////

  // Physics engine - config
  PhysicsEngineConfig engine_config{};
  PhysicsEngine physicsEngine(engine_config);


  // Canvas - config
  CanvasConfig canvas_config{
      .sprite_type = SPRITE_TYPE,
      .sprite_size = SPRITE_SIZE,
      .sprite_color = SPRITE_COLOR // {216, 216, 216}
      // todo: support PLAIN_COLOR_SCHEME
  };
  Canvas canvas(WIN_WIDTH, WIN_HEIGHT, canvas_config);
  // todo: config particle sprite. Enums
//    std::vector<SDL_Event> events;
  SDL_Event event;

  int frame_count = 0;
  //Run event loop
  while (!canvas.closed) {
    // poll events
    // todo: handle_events();
    //  add config adjustments, menu etc.. - buttons, scrollbars, options for config parameters.

    while (canvas.poll_event(event)) {
      // todo: store and pass events to simulateFrame
      // events.push_back(event)
    }


    // run physics
    for (int i = 0; i < PHYSICS_FPS_MULT; i++) {
      physicsEngine.simulateFrame(assetManager); // events
    }

    // Hack: process boundaries in a crude way..
    // todo: do it more gracefully. Store in Asset manager and generalize. Collisions?
    run_logic(assetManager);


    ////////////////////////////////////


    // draw
    canvas.DisplayAssets(assetManager, frame_count);


    ////////////////////////////////////


    // FPS
    SDL_Delay(1000 / FPS);
    // todo: advanced fps handling - disentangle physics engine from drawing
    //  (replace PHYSICS_FPS_MULT)
  }

  return 0;
};