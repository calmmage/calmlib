//
// Created by Petr Lavrov on 29.08.2022.
//

#include "physics_engine.h"
#include <cmath>

namespace particle_simulator {

const float ENGINE_TIME_STEP = 0.01; // todo: make a proper config - Engine constructor / config file?
const float ACCELERATION_COEFFICIENT = 10;
const float ANGULAR_ACCELERATION_COEFFICIENT = 0.1;

PhysicsEngine::PhysicsEngine(PhysicsEngineConfig config) :
    config_(config), mt(rd()),
    dist(-1.f, 1.f) {};

void PhysicsEngine::simulateFrame(AssetManager &asset_manager) {
  // todo: support all particle types. How? Can I do cross-type particle interaction?
  //  export to a function, templated. Then call for types 1 by 1.
  switch (config_.engine_type) {
    case KINEMATIC_1:
      for (auto &particle : asset_manager.kinetic_polar_particles_) {

        // todo: support different physics
        //  Need a config for that. How exacly? Per-
        particle.x += particle.speed * cos(particle.direction) * ENGINE_TIME_STEP;
        particle.y += particle.speed * sin(particle.direction) * ENGINE_TIME_STEP;

        // todo: smooth over the movement somehow.
        particle.speed += dist(mt) * ACCELERATION_COEFFICIENT;
        particle.direction += dist(mt) * ANGULAR_ACCELERATION_COEFFICIENT;
      }
      break;
    case DYNAMIC_1:break;
    case DYNAMIC_2:break;
  }



  ////////////////////////////////////


  // todo: process trails
  asset_manager.trail_update_frame++;
  asset_manager.trail_update_frame %= asset_manager.trail_update_frequency_;
  if (!asset_manager.trail_update_frame) {
    for (auto &trail : asset_manager.trails_) {
      // todo: support updating trails not every frame
      // todo: support storing trail frame state and passing it to Canvas for interpolation
      //  canvas.trail_update_frame
//      trail.positions.push_front(trail.tracked_particle); // need to cast the tracked particle to a simple location herer
      if (trail.positions.size() > asset_manager.trail_depth) {
        trail.positions.pop_back();
      }
    }
  }


  ////////////////////////////////////


  // todo: support connected particles. e.g. that cloth model..


  ////////////////////////////////////


  // todo: store and visualize particle forces / accelerations (configurable?)
};

} // particle_simulator