cmake_minimum_required(VERSION 3.16)
project(agri_rough_canary_runner LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT DEFINED F2C_SOURCE_DIR OR NOT IS_DIRECTORY "${F2C_SOURCE_DIR}")
  message(FATAL_ERROR "F2C_SOURCE_DIR must name the runtime Fields2Cover checkout")
endif()
add_subdirectory("${F2C_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/fields2cover" EXCLUDE_FROM_ALL)
add_executable(agri_f2c_runner src/agri_f2c_runner.cpp)
target_link_libraries(agri_f2c_runner PRIVATE Fields2Cover)

# Sidecar bound probe; production runner remains unchanged.
add_executable(agri_f2c_bound_probe src/agri_f2c_bound_probe.cpp)
target_link_libraries(agri_f2c_bound_probe PRIVATE Fields2Cover)

# MST-only sidecar probe.
add_executable(agri_f2c_mst_probe src/agri_f2c_mst_probe.cpp)
target_link_libraries(agri_f2c_mst_probe PRIVATE Fields2Cover)

# Degree-relaxation sidecar probe.
add_executable(agri_f2c_degree_probe src/agri_f2c_degree_probe.cpp)
target_link_libraries(agri_f2c_degree_probe PRIVATE Fields2Cover)
