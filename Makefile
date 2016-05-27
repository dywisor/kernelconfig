unexport PYTHONDONTWRITEBYTECODE
export PYTHONDONTWRITEBYTECODE=y

SHELL ?= sh

_PRJNAME := kernelconfig
_PRJROOT := $(patsubst %/,%,$(dir $(realpath $(lastword $(MAKEFILE_LIST)))))

S := $(_PRJROOT)
_PYMOD_DIRS := $(addprefix $(S:/=)/,$(_PRJNAME))
_SETUP_PY := $(S:/=)/setup.py

MKDIR = mkdir
MKDIRP = $(MKDIR) -p
CP = cp
CPV = $(CP) -v

X_PEP8 = pep8
X_PYFLAKES = pyflakes
X_GREP = grep
GREP_CHECK_OPTS = -n --color

PRJ_LKC_SRC = $(_PRJROOT)/src/lkc

# a list of files to import from the kernel sources
LKC_FILE_NAMES  = $(addsuffix .h,expr list lkc lkc_proto)
LKC_FILE_NAMES += $(addsuffix .c,confdata expr menu symbol util)
LKC_FILE_NAMES += $(addsuffix .c,$(addprefix zconf.,tab hash lex))



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


PHONY += print-lkc-files
print-lkc-files:
	@{ \
		$(foreach n,$(LKC_FILE_NAMES),printf '%s\n' '$(n)';) \
		printf '%s\n' 'COPYING'; \
	} | sort



PHONY += import-lkc
ifeq ("","$(LK_SRC)")
import-lkc:
	$(error LK_SRC is not set)

else
import-lkc: $(LK_SRC)
	$(MKDIRP) -- $(PRJ_LKC_SRC)
	$(CPV) -- '$(LK_SRC)/COPYING' '$(PRJ_LKC_SRC)/COPYING'
	{ set -e; \
		for fname in $(LKC_FILE_NAMES); do \
			$(CPV) -- "$(LK_SRC)/scripts/kconfig/$${fname}" \
				"$(PRJ_LKC_SRC)/$${fname}"; \
		done; \
	}
endif


PHONY += help
help:
	@echo  'Helper targets:'
	@echo  '  check                      - perform some basic code checks (pep8, pyflakes)'
	@echo  '  import-lkc [LK_SRC=...]    - import lkc files from linux kernel '
	@echo  '                               source tree LK_SRC'
	@echo  ''
	@echo  'Cleanup Targets:'
	@echo  '  clean                      - does nothing'
	@echo  '  pyclean                    - remove pyc files'
	@echo  '  distclean                  - all clean targets'


FORCE:

.PHONY: $(PHONY)
