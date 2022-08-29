//
// Created by Petr Lavrov on 29.08.2022.
//

#ifndef PARTICLES_ENGINE_PHYSICS_ENGINE_H
#define PARTICLES_ENGINE_PHYSICS_ENGINE_H

#include <random>
#include "asset_manager.h"

namespace particle_simulator {

// Config

enum EngineType {
  KINEMATIC_1, // random acceleration
  DYNAMIC_1, // todo: simple particle interaction
  DYNAMIC_2 // todo: vector fields.. ? rain? (random re-appear)
};

struct PhysicsEngineConfig {
  EngineType engine_type = KINEMATIC_1;
};


////////////////////////////////////


class PhysicsEngine {
 public:
  explicit PhysicsEngine(PhysicsEngineConfig config);
  void simulateFrame(AssetManager &asset_manager);
 private:
  PhysicsEngineConfig config_;

  std::random_device rd;
  std::mt19937 mt;
  std::uniform_real_distribution<float> dist;
};

} // particle_simulator

#endif //PARTICLES_ENGINE_PHYSICS_ENGINE_H
