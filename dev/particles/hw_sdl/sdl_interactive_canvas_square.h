//
// Created by Petr Lavrov on 27.08.2022.
//

#ifndef PARTICLES_SDL_INTERACTIVE_CANVAS_SQUARE_H
#define PARTICLES_SDL_INTERACTIVE_CANVAS_SQUARE_H


#include "../base/sdl_canvas.h"

class SdlInteractiveCanvasSquare : public SdlCanvas {
public:
    SdlInteractiveCanvasSquare(int height, int width, const char *file);

    ~SdlInteractiveCanvasSquare();

    void handle_events() override;

    void render_image() override;

    void run_logic() override;

private:
    // creates a surface to load an image into the main memory
    SDL_Surface *surface;
    // let us control our image position
    // so that we can move it with our keyboard.
    SDL_Rect dest;
    SDL_Texture *tex;
    // speed of box
    int speed;
};


#endif //PARTICLES_SDL_INTERACTIVE_CANVAS_SQUARE_H
