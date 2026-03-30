## Body LED Persistence

Goal: add a real persistent primitive for `left/center/right` body LEDs on Nabaztag/tag.

### Reverse engineering summary

- `CH`/choreography is transient only.
- The stock firmware clears body LEDs at choreography start and returns control to idle afterwards.
- In idle, body LEDs are driven by `infoRun` from `info.mtl`.
- `nose` and `bottom` are already persistent through `AmbientPacket`.
- A true persistent arbitrary RGB primitive for body LEDs therefore requires either:
  - patching bootcode, or
  - accepting the limited stock `infoRun` service animations/palette.

### Bootcode patch prepared

Patch intent:

- add persistent body LED state in `info.mtl`
- add commands in `main.mtl`:
  - `BL <rgb-decimal>`: left
  - `BM <rgb-decimal>`: center
  - `BR <rgb-decimal>`: right
  - `BO`: all off, while staying in override mode
  - `BI`: disable override and return to stock `infoRun`
- apply the override after `infoRun`, so idle keeps the requested colors

### Compiler blocker

The OpenJabNab MTL compiler is effectively 32-bit.

Observed behavior on both macOS and Debian x86_64:

- after minimal pointer-cast fixes, the compiler builds
- but `mtl_comp -s bootcode.mtl bootcode.bin` segfaults at startup

ASAN trace on Debian x86_64:

- crash in `Memory::tabset(...)`
- called from `Compiler::createpackage(...)`
- root cause: VM values are still stored in `int`, so tagged pointers are truncated on 64-bit

Implication:

- a reliable bootcode rebuild needs a real 32-bit build/runtime environment
- or a larger port of the compiler VM from `int` to `intptr_t`/`long`

### Files investigated

- OpenJabNab bootcode:
  - `bootcode/sources/main.mtl`
  - `bootcode/sources/info.mtl`
  - `bootcode/sources/palette.mtl`
- OpenJabNab compiler:
  - `bootcode/compiler/mtl_linux/vcomp/memory.h`
  - `bootcode/compiler/mtl_linux/vcomp/compiler.cpp`
  - `bootcode/compiler/mtl_linux/vcomp/memory.cpp`
  - `bootcode/compiler/mtl_linux/Makefile`

### Next practical step

Build the patched bootcode inside a 32-bit Linux environment, then:

1. replace `deploy/assets/bootcode.default`
2. update `apps/portal/portal_app/device_protocol.py` to emit `BL/BM/BR/BO/BI`
3. redeploy and retest body LED persistence on `Lapinou`
