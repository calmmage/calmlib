//
// Created by Petr Lavrov on 29.08.2022.
//

#ifndef PARTICLES_ENGINE_CANVAS_H
#define PARTICLES_ENGINE_CANVAS_H

#include "asset_manager.h"
#include <SDL2/SDL.h>
#include <SDL2/SDL_image.h>
#include <SDL2/SDL_timer.h>

namespace particle_simulator {

enum SpriteType {
  HOLLOW_SQUARE,
  HOLLOW_CIRCLE
};

struct SpriteColor {
  u_short r = 0;
  u_short g = 0;
  u_short b = 0;
  u_short opacity = 255;
};

// todo: make a proper config. How are configs done in C++?
struct CanvasConfig {
  SpriteType sprite_type = HOLLOW_SQUARE;
  int sprite_size = 1;
  SpriteColor sprite_color = {255, 255, 255, 255};
};


////////////////////////////////////


class Canvas {
 public:
  Canvas(int width, int height, CanvasConfig canvas_config);
//    Canvas();
  ~Canvas();

  SDL_Renderer *rend;

  void displayAssets(const AssetManager &assetManager);
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
