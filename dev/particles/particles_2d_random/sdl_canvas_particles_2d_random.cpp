//
// Created by Petr Lavrov on 27.08.2022.
//

#include "sdl_canvas_particles_2d_random.h"
#include <cmath>
#include <vector>
#include <random>

SdlCanvasParticles2dRandom::SdlCanvasParticles2dRandom(int height, int width, int num_particles)
        : SdlCanvas(width, height), mt(rd()), dist(0.f, (float) height) {

    particles = vector<Particle>(num_particles);
    for (auto &particle: particles) {
        // init random
        particle.x = dist(mt);
        particle.y = dist(mt);
    }

//
//    // please provide a path for your image
//    surface = IMG_Load(file);
//    // loads image to our graphics hardware memory.
//    tex = SDL_CreateTextureFromSurface(rend, surface);
//    // clears main-memory
//    SDL_FreeSurface(surface);
//
//    // connects our texture with dest to control position
//    SDL_QueryTexture(tex, NULL, NULL, &dest.w, &dest.h);
//
//    // adjust height and width of our image box.
//    dest.w /= 6;
//    dest.h /= 6;
//
//    // sets initial x-position of object
//    dest.x = (width - dest.w) / 2;
//
//    // sets initial y-position of object
//    dest.y = (height - dest.h) / 2;
//
//    speed = 300;
}

//SdlCanvasParticles2dRandom::~SdlCanvasParticles2dRandom() {
//    // destroy texture
//    SDL_DestroyTexture(tex);
//}


void SdlCanvasParticles2dRandom::handle_events() {
    SDL_Event event;
    // Events management
    while (SDL_PollEvent(&event)) {
        switch (event.type) {

            case SDL_QUIT:
                // handling of close button
                close = 1;
                break;

//        case SDL_KEYDOWN:
        }
    }

    run_logic();
}

void SdlCanvasParticles2dRandom::render_image() {
//    SDL_RenderCopy(rend, tex, NULL, &dest);
    SDL_SetRenderDrawColor(rend, 255, 255, 255, 255);
    for (const auto &particle: particles) {
        SDL_RenderDrawPoint(rend, lround(particle.x), lround(particle.y));
//        SDL_Rect()
        SDL_Rect rect{(int) lround(particle.x), (int) lround(particle.y), 10, 10};
        SDL_RenderDrawRect(rend, &rect);
    }
}

void SdlCanvasParticles2dRandom::run_logic() {
    // Update particles location
    float dt = 0.01;

    for (auto &particle: particles) {
        particle.x += particle.speed * cos(particle.direction) * dt;
        particle.y += particle.speed * sin(particle.direction) * dt;
        particle.speed += (dist(mt) - 500) / 100;
        particle.direction += (dist(mt) - 500) / 5000;

        // right boundary
        if (particle.x > 1000) {
            particle.x = 1000.f - 1;
            particle.direction = M_PI - particle.direction; // bounce right boundary
        }

        // left boundary
        if (particle.x < 0) {
            particle.x = 0.f + 1;
            particle.direction = M_PI - particle.direction; // bounce left boundary
        }

        // bottom boundary
        if (particle.y > 1000) {
            particle.y = 1000.f - 1;
            particle.direction = -particle.direction; // bounce bottom boundary
        }

        // upper boundary
        if (particle.y < 0) {
            particle.y = 0.f + 1;
            particle.direction = -particle.direction; // bounce upper boundary
        }
    }
}