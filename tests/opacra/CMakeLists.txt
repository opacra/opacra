# Opacra consensus regression tests (no external test framework).
#   make opacra_consensus_tests && ./bin/opacra_consensus_tests
add_executable(opacra_consensus_tests opacra_consensus_tests.cpp)
target_link_libraries(opacra_consensus_tests
  PRIVATE
    cryptonote_core
    randomx
    cryptonote_basic
    hardforks
    cncrypto
    common
    epee
    ${Boost_CHRONO_LIBRARY}
    ${Boost_FILESYSTEM_LIBRARY}
    ${Boost_PROGRAM_OPTIONS_LIBRARY}
    ${Boost_REGEX_LIBRARY}
    ${Boost_SERIALIZATION_LIBRARY}
    ${Boost_SYSTEM_LIBRARY}
    ${Boost_THREAD_LIBRARY}
    ${CMAKE_THREAD_LIBS_INIT}
    ${EXTRA_LIBRARIES})
target_include_directories(opacra_consensus_tests PRIVATE ${RANDOMX_INCLUDE})
set_property(TARGET opacra_consensus_tests PROPERTY RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

# Difficulty fuzz harness (driven by contrib/sim/difficulty_fuzz.py):
#   make opacra_difficulty_fuzz && python3 contrib/sim/difficulty_fuzz.py
add_executable(opacra_difficulty_fuzz difficulty_fuzz.cpp)
target_link_libraries(opacra_difficulty_fuzz
  PRIVATE
    cryptonote_basic
    cncrypto
    common
    epee
    ${Boost_SYSTEM_LIBRARY}
    ${Boost_THREAD_LIBRARY}
    ${CMAKE_THREAD_LIBS_INIT}
    ${EXTRA_LIBRARIES})
set_property(TARGET opacra_difficulty_fuzz PROPERTY RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
