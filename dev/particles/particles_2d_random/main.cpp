//
// Created by Petr Lavrov on 26.08.2022.
//

#include "sdl_canvas_particles_2d_random.h"

int main(int argc, char *argv[]) {
    printf("Hello World SDL!! \n");
    int HEIGHT = 1000;
    int WIDTH = 1000;
    SdlCanvasParticles2dRandom canvas(HEIGHT, WIDTH, 100);
    canvas.run();

    return 0;
}