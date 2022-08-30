//
// Created by Petr Lavrov on 27.08.2022.
//

#include "sdl_interactive_canvas_square.h"

SdlInteractiveCanvasSquare::SdlInteractiveCanvasSquare(int height, int width, const char *file)
        : SdlCanvas(width, height), dest() {
    // please provide a path for your image
    surface = IMG_Load(file);
    // loads image to our graphics hardware memory.
    tex = SDL_CreateTextureFromSurface(rend, surface);
    // clears main-memory
    SDL_FreeSurface(surface);

    // connects our texture with dest to control position
    SDL_QueryTexture(tex, NULL, NULL, &dest.w, &dest.h);

    // adjust height and width of our image box.
    dest.w /= 6;
    dest.h /= 6;

    // sets initial x-position of object
    dest.x = (width - dest.w) / 2;

    // sets initial y-position of object
    dest.y = (height - dest.h) / 2;

    speed = 300;
}

SdlInteractiveCanvasSquare::~SdlInteractiveCanvasSquare() {
    // destroy texture
    SDL_DestroyTexture(tex);
}


void SdlInteractiveCanvasSquare::handle_events() {
    SDL_Event event;
    // Events management
    while (SDL_PollEvent(&event)) {
        switch (event.type) {

            case SDL_QUIT:
                // handling of close button
                close = 1;
                break;

            case SDL_KEYDOWN:
                // keyboard API for key pressed
                switch (event.key.keysym.scancode) {
                    case SDL_SCANCODE_W:
                    case SDL_SCANCODE_UP:
                        dest.y -= speed / 30;
                        break;
                    case SDL_SCANCODE_A:
                    case SDL_SCANCODE_LEFT:
                        dest.x -= speed / 30;
                        break;
                    case SDL_SCANCODE_S:
                    case SDL_SCANCODE_DOWN:
                        dest.y += speed / 30;
                        break;
                    case SDL_SCANCODE_D:
                    case SDL_SCANCODE_RIGHT:
                        dest.x += speed / 30;
                        break;
                    default:
                        break;
                }
        }
    }

    run_logic();
}

void SdlInteractiveCanvasSquare::render_image() {
    SDL_RenderCopy(rend, tex, NULL, &dest);
}

void SdlInteractiveCanvasSquare::run_logic() {
    // right boundary
    if (dest.x + dest.w > 1000)
        dest.x = 1000 - dest.w;

    // left boundary
    if (dest.x < 0)
        dest.x = 0;

    // bottom boundary
    if (dest.y + dest.h > 1000)
        dest.y = 1000 - dest.h;

    // upper boundary
    if (dest.y < 0)
        dest.y = 0;
}