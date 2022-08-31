//
// Created by Petr Lavrov on 29.08.2022.
//

#ifndef PARTICLES_ENGINE_ASSET_MANAGER_H
#define PARTICLES_ENGINE_ASSET_MANAGER_H

#include <vector>
#include <deque>
#include "../config.h"
#include "asset_types.h"

namespace particle_simulator {

// todo: Dynamic particle
//  Version 1: x,y, vx, vy, ax, ay
//  Version 2: x,y, vx, vy,  m / q (optional?)

// todo: Connected Particles
//  ignore for now.
//  Version 1: Just do 1 type for now.. e.g. KineticCartesian.
//  Version 2: can I do a templated collection? Make Particles inherit from common class?
//  Version 3:

class AssetManager { // Class for storing and managing the assets loaded into the simulator
 public:
//    AssetManager(); // Do I need the constructor at all?

  // containers //todo: make private. Figure out how to provide access to engine? protected?
  std::vector<SimpleCartesianParticle> simple_cartesian_particles_;
  std::vector<SimplePolarParticle> simple_polar_particles_;
  std::vector<KineticCartesianParticle> kinetic_cartesian_particles_;
  std::vector<KineticPolarParticle> kinetic_polar_particles_;
  std::vector<DynamicCartesianParticle> dynamic_cartesian_particles_;
  std::vector<DynamicParticle> dynamic_particles_;

  std::vector<Trail> trails_;
  const int trail_update_frequency_ = TRAIL_UPDATE_FREQUENCY; // todo: consider changing to (FPS / trail_depth)
  int trail_update_frame = 0;
  const unsigned short trail_depth = TRAIL_DEPTH; // todo: store in config?
};

} // particle_simulator

#endif //PARTICLES_ENGINE_ASSET_MANAGER_H
