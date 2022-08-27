//
// Created by Petr Lavrov on 26.08.2022.
//
#include "sdl_interactive_canvas_square.h"

int main(int argc, char *argv[]) {
    printf("Hello World SDL!! \n");

    SdlInteractiveCanvasSquare canvas = SdlInteractiveCanvasSquare(1000, 1000,
                                                                   "/Users/calm/home/calmlib/dev/particles/hw_sdl/rect.jpg");
    canvas.run();

    return 0;
}