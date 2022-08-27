//
// Created by Petr Lavrov on 27.08.2022.
//

#ifndef PARTICLES_SDL_CANVAS_PARTICLES_2D_RANDOM_H
#define PARTICLES_SDL_CANVAS_PARTICLES_2D_RANDOM_H

#include "../base/sdl_canvas.h"
#include <vector>
#include <random>

using namespace std;

class Particle {
public:
    Particle() : x(0.), y(0.), speed(0.), direction(0.) {};

    Particle(float x, float y, float speed, float direction) : x(x), y(y), speed(speed), direction(direction) {};

    float x;
    float y;
    float speed;
    float direction;
};

//class SdlInteractiveCanvasSquare: public SdlCanvas {
//public:
//    SdlInteractiveCanvasSquare(int height, int width, const char* file);
//    ~SdlInteractiveCanvasSquare();
//    void handle_events() override;
//    void render_image() override;
//
//private:
//    // creates a surface to load an image into the main memory
//    SDL_Surface* surface;
//    // let us control our image position
//    // so that we can move it with our keyboard.
//    SDL_Rect dest;
//    SDL_Texture* tex;
//    // speed of box
//    int speed;
//};


class SdlCanvasParticles2dRandom : public SdlCanvas {
public:
    SdlCanvasParticles2dRandom(int height, int width, int num_particles);
//    ~SdlCanvasParticles2dRandom();

    void handle_events() override;

    void render_image() override;

    void run_logic() override;

private:
    vector<Particle> particles;

    std::random_device rd;
    std::mt19937 mt;
    std::uniform_real_distribution<float> dist;
};


#endif //PARTICLES_SDL_CANVAS_PARTICLES_2D_RANDOM_H
