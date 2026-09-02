# __GAME__ (MSXDAW) disassembly build.
#
#   make            assemble __GAME__.asm -> __GAME__.rom
#   make verify     SHA-1 check against __GAME__.sha1
#   make banks      extract leftover 8 KiB bins / drop migrated ones
#
# Prerequisite: tools/sjasmplus (tools/workbench/bin/install-sjasmplus)

include tools/workbench/make/game.mk

SRC      := __GAME__.asm
OUT      := __GAME__.rom
SHA1FILE := __GAME__.sha1

.PHONY: banks
banks:
	tools/workbench/msx/split-rom.sh
