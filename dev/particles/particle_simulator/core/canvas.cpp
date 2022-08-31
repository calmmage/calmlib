//
// Created by Petr Lavrov on 29.08.2022.
//

#include "canvas.h"
#include <cmath>
#include <vector>
#include "../config.h"
#include "asset_types.h"

namespace particle_simulator {

int linear_variation(int trail_count) {
  int variation;
  variation = (int) (TRAIL_VARIATION_MULT * trail_count);
  variation = std::min(variation, TRAIL_VARIATION_LIMIT);
  return variation;
};

int periodic_variation(int trail_count) {
  int variation;
  variation = trail_count + TRAIL_VARIATION_LIMIT / 2;
  variation %= TRAIL_VARIATION_LIMIT;
  variation -= TRAIL_VARIATION_LIMIT / 2;
  variation = std::abs(variation);
  variation = (int) (variation * TRAIL_VARIATION_MULT);
  variation = std::min(variation, TRAIL_VARIATION_LIMIT);
  return variation;

};

SDL_Color mix_colors(const SDL_Color &color_1, const SDL_Color &color_2, double alpha) {
  // todo: assert 0 < alpha < 1;
  alpha = std::max(std::min(alpha, 1.), 0.);
  SDL_Color result;
  result.r = (Uint8) ((1 - alpha) * color_1.r + alpha * color_2.r);
  result.g = (Uint8) ((1 - alpha) * color_1.g + alpha * color_2.g);
  result.b = (Uint8) ((1 - alpha) * color_1.b + alpha * color_2.b);
  result.a = (Uint8) ((1 - alpha) * color_1.a + alpha * color_2.a);
  return result;
}

void Canvas::DisplayAssets(const AssetManager &asset_manager, int frame_count) {
  // clears the screen
  if (frame_count % SCREEN_REFRESH_FREQUENCY == 0) {
    SDL_SetRenderDrawColor(rend, CANVAS_COLOR.r, CANVAS_COLOR.g, CANVAS_COLOR.b, CANVAS_COLOR.a);
    SDL_RenderClear(rend);
  }


  ////////////////////////////////////


  auto &cc = canvas_config_;
  for (const auto &particle : asset_manager.kinetic_polar_particles_) {
    display_sprite(particle, cc.sprite_type, cc.sprite_color, cc.sprite_size, cc.sprite_size);
  }


  ////////////////////////////////////

  int trail_count, width, height, size, sprite_opacity;
  SDL_Color color;
  // todo: export to separate method
  for (auto &trail : asset_manager.trails_) {
    trail_count = 0;
    for (auto &trail_particle : trail.positions) {
      trail_count++;
      switch (TRAIL_TYPE) { // todo: config per-particle
        case LINEAR_SQUARE_TRAIL: // adjust square size linearly
          size = cc.sprite_size;
          // linear variation
          size -= linear_variation(trail_count);
          size = std::max(size, TRAIL_MIN_SIZE);
          size = std::min(size, TRAIL_MAX_SIZE);
          width = height = size;
          break;
        case PERIODIC_SQUARE_TRAIL:size = cc.sprite_size;
          size -= periodic_variation(trail_count);
          size = std::max(size, TRAIL_MIN_SIZE);
          size = std::min(size, TRAIL_MAX_SIZE);
          width = height = size;
          break;
        case LINEAR_VERTICAL_RECTANGLE:size = cc.sprite_size;
          // linear variation
          size -= linear_variation(trail_count);
          size = std::max(size, TRAIL_MIN_SIZE);
          size = std::min(size, TRAIL_MAX_SIZE);
          width = cc.sprite_size;
          height = size;
          break;
        case LINEAR_HORIZONTAL_RECTANGLE:size = cc.sprite_size;
          // linear variation
          size -= linear_variation(trail_count);
          size = std::max(size, TRAIL_MIN_SIZE);
          size = std::min(size, TRAIL_MAX_SIZE);
          width = size;
          height = cc.sprite_size;
          break;
        case PERIODIC_VERTICAL_RECTANGLE:width = height = size;
          size = cc.sprite_size;
          // periodic variation
          size -= periodic_variation(trail_count);
          size = std::max(size, TRAIL_MIN_SIZE);
          size = std::min(size, TRAIL_MAX_SIZE);
          width = cc.sprite_size;
          height = size;
          break;
        case PERIODIC_HORIZONTAL_RECTANGLE:width = height = size;
          size = cc.sprite_size;
          // periodic variation
          size -= periodic_variation(trail_count);
          size = std::max(size, TRAIL_MIN_SIZE);
          size = std::min(size, TRAIL_MAX_SIZE);
          width = size;
          height = cc.sprite_size;
          break;
      }
      double alpha;
      switch (SPRITE_COLOR_SCHEME) { // todo: config per-particle
        case PLAIN_COLOR_SCHEME: // color = SPRITE_COLOR
          color = SPRITE_COLOR;
          break;
        case SPEED_COLOR_SCHEME: //
          // todo: change tracked particle back to SimpleKineticParticle
          alpha = std::abs(trail.tracked_particle->speed / FAST_SPEED);
          color = mix_colors(SLOW_SPEED_COLOR, FAST_SPEED_COLOR, alpha);

          // todo: make particle types interchangeable,
          //  considering vx,vy vs speed, direction
          break;
        case DIRECTION_COLOR_SCHEME: //
          break;
        case RANDOM_COLOR_SCHEME: // Fixed Random color per particle, but fixed?
          break;
        case RAINBOW_COLOR_SCHEME: // Changing random color for each
          break;
      }
      if (TRAIL_FADE) {
        sprite_opacity = color.a;
        sprite_opacity -= trail_count * TRAIL_FADE_AMOUNT;
        color.a = std::max(sprite_opacity, (int) TRAIL_FADE_MIN);
      }

      display_sprite(
          trail_particle,
          cc.sprite_type, // todo: custom sprite type per particle? config: use custom sprite type, then decide here.
          color,
          width,
          height
      );
    }
  }

  // version 1: display as is
  // todo: version 2: interpolate intermediary state, process trails.


  ////////////////////////////////////


  // triggers the double buffers
  // for multiple rendering
  SDL_RenderPresent(rend);
};

void Canvas::display_sprite(const SimpleCartesianParticle &particle,
                            SpriteType type,
                            SDL_Color color,
                            int height,
                            int width) const {
  // todo: support per-particle-type display
  SDL_Rect rect;
  switch (type) {
    case HOLLOW_SQUARE:SDL_SetRenderDrawColor(rend, color.r, color.g, color.b, color.a);
      //  SDL_RenderDrawPoint(rend, x, y);
      rect = {
          (int) lround(particle.x) - height / 2,
          (int) lround(particle.y) - width / 2,
//          (int) lround(particle.x),
//          (int) lround(particle.y),
          height, // h
          width // w
      };
      SDL_RenderDrawRect(rend, &rect);
      break;
    case HOLLOW_CIRCLE:break;
  }
}

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
  SDL_SetRenderDrawBlendMode(rend, SDL_BLENDMODE_BLEND);
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