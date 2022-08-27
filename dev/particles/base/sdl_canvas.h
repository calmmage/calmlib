//
// Created by Petr Lavrov on 26.08.2022.
//

#ifndef PARTICLES_SDL_CANVAS_H
#define PARTICLES_SDL_CANVAS_H

#include <SDL2/SDL.h>
#include <SDL2/SDL_image.h>
#include <SDL2/SDL_timer.h>

class SdlCanvas {
public:
    SdlCanvas(int width, int height);

    ~SdlCanvas();

    void run();

    virtual void handle_events() = 0;

    virtual void render_image() = 0;

    virtual void run_logic() = 0;

    SDL_Renderer *rend;

protected:
    // controls animation loop
    int close;
private:
    SDL_Window *win;
    Uint32 render_flags;
};


#endif //PARTICLES_SDL_CANVAS_H
