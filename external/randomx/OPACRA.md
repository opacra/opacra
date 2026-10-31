# RandomX in Opacra

This is RandomX v1.2.2 (tevador/RandomX, commit 6c4340b), vendored into the Opacra
tree instead of used as a git submodule, with one change: `RANDOMX_ARGON_SALT` in
`src/configuration.h` is `"RandomOPCA\x01"` instead of Monero's `"RandomX\x03"`.

RandomX's documentation (`doc/configuration.md`) says every implementation should
choose a unique salt. Changing only the salt makes every hash differ from Monero's
`rx/0` while keeping the algorithm's design, memory requirements, program size and
security analysis exactly as audited for Monero. Miners need an Opacra build of their
mining software (see `contrib/xmrig/` in the Opacra repository); the miner built into
`opacrad` uses it automatically.
