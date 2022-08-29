Alternative cpp compiler
/opt/homebrew/bin/gcc-12

---------------------------

How to make clion to use it:
Option 1:

- config.

Option 2:

- make parameters

---------------------------
How to add

1) brew?

- add to cmake file like on stackoverflow

2) what is the path?

- use - add to cmake file
  this path?
  /opt/homebrew/bin/sdl2-config

----------------
So the solution was

- install SDL with brew

I) run
sdl2-config --cflags
-I/opt/homebrew/include/SDL2 -D_THREAD_SAFE
(dev) ➜ particles git:(master) ✗ sdl2-config --libs
-L/opt/homebrew/lib -lSDL2

II)
Add "-L/opt/homebrew/lib"
to set(CMAKE_CXX_FLAGS.. line in the CMakeLists
'-lSDL2' is already there from some other search/target lib lines

Where to add
-I/opt/homebrew/include/SDL2 -D_THREAD_SAFE?
is this already here?

III) And defaul (clang) version complains that -L/opt/homebrew/lib is unused