unexport PYTHONDONTWRITEBYTECODE
export PYTHONDONTWRITEBYTECODE=y

SHELL ?= sh

_PRJNAME := kernelconfig
_PRJROOT := $(patsubst %/,%,$(dir $(realpath $(lastword $(MAKEFILE_LIST)))))

S := $(_PRJROOT)
_PYMOD_DIRS := $(addprefix $(S:/=)/,$(_PRJNAME))
_SETUP_PY := $(S:/=)/setup.py

X_PEP8 = pep8
X_PYFLAKES = pyflakes
X_GREP = grep
GREP_CHECK_OPTS = -n --color



PHONY += all
all:
	false


PHONY += clean
clean:
	true

PHONY += pyclean
pyclean:
	find $(_PYMOD_DIRS) -name '*.py[co]' -delete -print

PHONY += distclean
distclean: clean pyclean

# ~int _f_grep_check_recursive ( pattern, dirlist )
define _f_grep_check_recursive
	$(X_GREP) -rIE $(GREP_CHECK_OPTS) -- '$(strip $(1))' $(2)
endef

# @may-exit void f_grep_check_recursive ( bad_pattern )
define f_grep_check_recursive
	$(call _f_grep_check_recursive,$(1),$(_PYMOD_DIRS)) && exit 1 || true
endef

PHONY += check
check:
# name it Kconfig, or kconfig where lowercase is appropriate
	$(call f_grep_check_recursive,[kK]C[oO][nN][fF][iI][gG])
# and the usual suspects
# setup.py does not need to be pep8-compliant
	$(X_PEP8) $(_PYMOD_DIRS)
	$(X_PYFLAKES) $(_SETUP_PY) $(_PYMOD_DIRS)


FORCE:

.PHONY: $(PHONY)
