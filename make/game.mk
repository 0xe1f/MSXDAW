# Shared recipes for an MSXDAW game Makefile.
# The game Makefile sets SRC, OUT, SHA1FILE and includes this file.
#
#   include tools/workbench/make/game.mk

ASM      ?= tools/sjasmplus --longptr
SHA1SUM  ?= $(shell command -v sha1sum 2>/dev/null || echo "shasum -a 1")
WB       := $(dir $(lastword $(MAKEFILE_LIST)))..

.PHONY: all verify clean coverage

all: $(SRC)
	$(ASM) $(SRC)

verify: all
	@$(SHA1SUM) -c $(SHA1FILE)

coverage:
	python3 "$(WB)/msx/coverage.py" --badges generated/badges

clean:
	rm -f $(OUT)
	rm -f banks/*.bin segments/seg*.bin
