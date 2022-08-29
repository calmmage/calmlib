//
// Created by Petr Lavrov on 29.08.2022.
//

#include "canvas.h"
#include <cmath>
#include <vector>

namespace particle_simulator {

void Canvas::displayAssets(const AssetManager &assetManager) {
  // clears the screen
  SDL_SetRenderDrawColor(rend, 0, 0, 0, 0);
  SDL_RenderClear(rend);


  ////////////////////////////////////


  // todo: support per-particle-type display (extract to separate func)
  int x, y;
  auto &cc = canvas_config_;
  auto &sc = cc.sprite_color;
  switch (cc.sprite_type) {
    case HOLLOW_SQUARE:SDL_SetRenderDrawColor(rend, sc.r, sc.g, sc.b, sc.opacity);
      for (const auto &particle : assetManager.kinetic_polar_particles_) {
        x = (int) lround(particle.x);
        y = (int) lround(particle.y);
        //  SDL_RenderDrawPoint(rend, x, y);
        SDL_Rect rect{x, y, cc.sprite_size, cc.sprite_size};
        SDL_RenderDrawRect(rend, &rect);
      }
      break;
    case HOLLOW_CIRCLE:break;
  }


  ////////////////////////////////////


  // todo: process trails.
  //  version 1: display as is
  //  version 2: interpolate intermediary state


  ////////////////////////////////////


  // triggers the double buffers
  // for multiple rendering
  SDL_RenderPresent(rend);
};

Canvas::Canvas(int width, int height, CanvasConfig canvas_config) : canvas_config_(canvas_config) {

  // returns zero on success else non-zero
  if (SDL_Init(SDL_INIT_EVERYTHING) != 0) {
    printf("error initializing SDL: %s\n", SDL_GetError());
  }
  win = SDL_CreateWindow("GAME", // creates a window
                         SDL_WINDOWPOS_CENTERED,
                         SDL_WINDOWPOS_CENTERED,
                         width, height, 0);

  // triggers the program that controls
  // your graphics hardware and sets flags
  render_flags = SDL_RENDERER_ACCELERATED;

  // creates a renderer to render our images
  rend = SDL_CreateRenderer(win, -1, render_flags);
}

Canvas::~Canvas() {

  // destroy renderer
  SDL_DestroyRenderer(rend);

  // destroy window
  SDL_DestroyWindow(win);

  // close SDL
  SDL_Quit();
}

bool Canvas::poll_event(SDL_Event &event) {
  bool result = SDL_PollEvent(&event);
  if (result) {
    switch (event.type) {
      case SDL_QUIT:
        // handling of close button
        closed = true;
        break;
    }
  }
  return result;
}

} // particle_simulator