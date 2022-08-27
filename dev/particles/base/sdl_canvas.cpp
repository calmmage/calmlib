//
// Created by Petr Lavrov on 26.08.2022.
//

#include "sdl_canvas.h"

SdlCanvas::SdlCanvas(int width, int height) {

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

    // Animation loop active
    close = 0;
}

SdlCanvas::~SdlCanvas() {

    // destroy renderer
    SDL_DestroyRenderer(rend);

    // destroy window
    SDL_DestroyWindow(win);

    // close SDL
    SDL_Quit();
}

void SdlCanvas::run() {

    // animation loop
    while (!close) {
        handle_events();

        // clears the screen
        SDL_SetRenderDrawColor(rend, 0, 0, 0, 0);
        SDL_RenderClear(rend);

        render_image();

        // triggers the double buffers
        // for multiple rendering
        SDL_RenderPresent(rend);

        // calculates to 60 fps
        SDL_Delay(1000 / 60);
    }
}