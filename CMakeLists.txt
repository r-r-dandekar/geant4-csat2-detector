#----------------------------------------------------------------------------
# Particle-detector Geant4 simulation -- build configuration.
#----------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.16 FATAL_ERROR)
project(detector_sim)

#----------------------------------------------------------------------------
# Find Geant4 (with all UI/Vis drivers by default).
#----------------------------------------------------------------------------
option(WITH_GEANT4_UIVIS "Build with Geant4 UI and Vis drivers" ON)
if(WITH_GEANT4_UIVIS)
  find_package(Geant4 REQUIRED ui_all vis_all)
else()
  find_package(Geant4 REQUIRED)
endif()

include(${Geant4_USE_FILE})
include_directories(${PROJECT_SOURCE_DIR}/include)

#----------------------------------------------------------------------------
# Sources and headers.
#----------------------------------------------------------------------------
file(GLOB sources ${PROJECT_SOURCE_DIR}/src/*.cc)
file(GLOB headers ${PROJECT_SOURCE_DIR}/include/*.hh)

#----------------------------------------------------------------------------
# Executable.
#----------------------------------------------------------------------------
add_executable(dsim payload.cc ${sources} ${headers})
target_link_libraries(dsim ${Geant4_LIBRARIES})

#----------------------------------------------------------------------------
# Copy the macro files next to the executable so they can be found at runtime.
#----------------------------------------------------------------------------
set(MACRO_FILES
  init_vis.mac
  vis.mac
  run.mac
  )
foreach(_macro ${MACRO_FILES})
  configure_file(
    ${PROJECT_SOURCE_DIR}/macros/${_macro}
    ${PROJECT_BINARY_DIR}/macros/${_macro}
    COPYONLY
    )
endforeach()
