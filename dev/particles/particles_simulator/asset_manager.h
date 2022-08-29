//
// Created by Petr Lavrov on 29.08.2022.
//
#include <vector>
#include <deque>

#ifndef PARTICLES_ENGINE_ASSET_MANAGER_H
#define PARTICLES_ENGINE_ASSET_MANAGER_H

namespace particle_simulator {

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

// todo: Dynamic particle
//  Version 1: x,y, vx, vy, ax, ay
//  Version 2: x,y, vx, vy,  m / q (optional?)

struct DynamicCartesianParticle : KineticCartesianParticle {
  float a_x; // horizontal acceleration component
  float a_y; // vertical acceleration component
};

struct DynamicParticle : KineticCartesianParticle {
  float m; // mass
};

// todo: Trails
//  Version 1: Add a Trail to Particle class.
//  Version 2: Create a class-agnostic

// todo: Connected Particles
//  ignore for now.
//  Version 1: Just do 1 type for now.. e.g. KineticCartesian.
//  Version 2: can I do a templated collection? Make Particles inherit from common class?
//  Version 3:

struct Trail {
  explicit Trail(const short trail_depth) {
    positions.resize(trail_depth);
  };
  // todo
  std::deque<SimpleCartesianParticle> positions; // how to specify depth?
  SimpleCartesianParticle *tracked_particle;
};

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
  const int trail_update_frequency_ = 20; // todo: consider changing to (FPS / trail_depth)
  int trail_update_frame = 0;
  const int trail_depth = 6; // todo: store in config?
};

} // particle_simulator

#endif //PARTICLES_ENGINE_ASSET_MANAGER_H
