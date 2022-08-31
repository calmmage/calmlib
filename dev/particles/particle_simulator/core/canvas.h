//
// Created by Petr Lavrov on 29.08.2022.
//

#ifndef PARTICLES_ENGINE_CANVAS_H
#define PARTICLES_ENGINE_CANVAS_H

#include "asset_manager.h"
#include "asset_types.h"
#include <SDL2/SDL.h>
#include <SDL2/SDL_image.h>
#include <SDL2/SDL_timer.h>

namespace particle_simulator {


////////////////////////////////////


class Canvas {
 public:
  Canvas(int width, int height, CanvasConfig canvas_config);
//    Canvas();
  ~Canvas();

  SDL_Renderer *rend;

  void DisplayAssets(const AssetManager &asset_manager, int frame_count);
  void display_sprite(const SimpleCartesianParticle &particle,
                      SpriteType type,
                      SDL_Color color,
                      int height,
                      int width) const;
  bool poll_event(SDL_Event &event);

  // controls animation loop
  bool closed = false;
//protected:
 private:
  SDL_Window *win;
  Uint32 render_flags;

  CanvasConfig canvas_config_;
};

} //particle_simulator

#endif //PARTICLES_ENGINE_CANVAS_H
