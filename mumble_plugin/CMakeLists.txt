cmake_minimum_required(VERSION 3.15)
project(koverlay_mumble
    VERSION "1.1.0"
    DESCRIPTION "KOverlay Mumble Plugin"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(koverlay_mumble SHARED
    koverlay_mumble.cpp
)

target_include_directories(koverlay_mumble PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

set_target_properties(koverlay_mumble PROPERTIES
    PREFIX ""
    OUTPUT_NAME "koverlay_mumble"
)

if(WIN32)
    target_link_libraries(koverlay_mumble PRIVATE ws2_32)
    install(TARGETS koverlay_mumble
        RUNTIME DESTINATION "$ENV{APPDATA}/Mumble/Plugins"
    )
else()
    install(TARGETS koverlay_mumble
        LIBRARY DESTINATION "$ENV{HOME}/.local/share/Mumble/Mumble/Plugins"
    )
endif()
