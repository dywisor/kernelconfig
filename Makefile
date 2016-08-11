__MAIN_MK_FILE := $(realpath $(lastword $(MAKEFILE_LIST)))
__MAIN_MK_DIR  := $(patsubst %/,%,$(dir $(__MAIN_MK_FILE)))

include $(__MAIN_MK_DIR)/mk/prj.mk
include $(__MAIN_MK_DIR)/mk/progs.mk
include $(__MAIN_MK_DIR)/mk/install.mk

X_PEP8 = pep8
PEP8_EXCLUDE = parsetab.py
X_PYFLAKES = pyflakes
PYFLAKES_EXTRA_FILES = $(wildcard $(SRC_FILESDIR)/installinfo/*.py)
X_GREP = grep
GREP_CHECK_OPTS = -n --color
X_EPYDOC = epydoc
EPYDOC_OPTS = --html -v --name '$(PN)'
X_PYREVERSE = pyreverse
PYREVERSE_OPTS = -p '$(_PRJNAME)' -fALL
X_DOT = dot
DOT_OPTS =
X_WGET = wget
WGET_OPTS =

PRJ_LKC_SRC = $(_PRJROOT)/src/lkc
PRJ_LKC_SRC_BUNDLED = $(PRJ_LKC_SRC)-bundled
LK_SRC_URI = https://raw.githubusercontent.com/torvalds/linux/master

# a list of files to import from the kernel sources
LKC_FILE_NAMES  = $(addsuffix .h,expr list lkc lkc_proto)
LKC_FILE_NAMES += $(addsuffix .c,confdata expr menu symbol util)
LKC_FILE_NAMES += $(addsuffix .c_shipped,$(addprefix zconf.,tab hash lex))

define _f_sanity_check_output_dir
	test -n '$(1)'
	test '$(1)' != '/'
	test '$(1)' != '$(S)'
endef
f_sanity_check_output_dir = $(call _f_sanity_check_output_dir,$(strip $(1)))

define __f_list_conf_sources_with_type
	test -n '$(1)' && \
	find '$(SRC_CONFSOURCEDIR)' \
		-type f -name '*.def' -not -path "*/skel/*" \
		-exec grep -lEi -- '^type\s*=\s*$(1)\s*$$' '{}' ';' \
		-print | sed -e 's=[.]def$$=='
endef

_f_list_conf_sources_with_type = $(shell \
	$(call __f_list_conf_sources_with_type,$(strip $(1))) | sort)

f_list_pym_conf_sources = $(call _f_list_conf_sources_with_type,pym)


PHONY += all
all:
	false


PHONY += clean
clean:
	true

PHONY += epydoc-clean
epydoc-clean:
	$(call f_sanity_check_output_dir,$(_EPYDOC_DIR))
	$(RMF) -r -- $(_EPYDOC_DIR)

PHONY += pyclean
pyclean:
	$(call f_sanity_check_output_dir,$(_PYMOD_DIRS))
	find $(_PYMOD_DIRS) -name '*.py[co]' -delete -print
	find $(_PYMOD_DIRS) -name '__pycache__' -type d -delete -print

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

PHONY += epydoc
epydoc: $(_EPYDOC_DIR)

$(_EPYDOC_DIR): epydoc-clean FORCE
	$(MKDIRP) -- $(@D)
	$(X_EPYDOC) $(EPYDOC_OPTS) -o $(@) $(_PYMOD_DIRS)


$(_BUILD_DIR)/pym/.stamp: $(_PYMOD_DIRS)
	$(RMF) -- $(@)
	$(MKDIRP) -- $(@D)
	{ set -e; \
		$(foreach p,$^,\
			$(RMF) -- $(@D)/$(notdir $(p)); \
			$(LNS) -- $(p) $(@D)/$(notdir $(p)); \
		) \
	}
	touch -- $(@)

$(_BUILD_DIR)/pym: %: %/.stamp

_UML_OUTFORMATS = dot png
uml: $(addprefix uml-,$(_UML_OUTFORMATS))

PHONY += $(addprefix uml-,$(_UML_OUTFORMATS))
uml-dot uml-png: uml-%: $(foreach t,classes packages,$(_BUILD_DIR)/uml/$(t)_$(_PRJNAME).%)

$(_BUILD_DIR)/uml/classes_$(_PRJNAME).dot: $(_BUILD_DIR)/pym
	$(MKDIRP) -- $(@D)
	cd '$(@D)' && \
		PYTHONPATH='$(<)' $(X_PYREVERSE) $(PYREVERSE_OPTS) -o dot $(_PRJNAME)

$(_BUILD_DIR)/uml/packages_$(_PRJNAME).dot: \
	%/packages_$(_PRJNAME).dot: | %/classes_$(_PRJNAME).dot
	# byproduct

$(_BUILD_DIR)/uml/%.png: $(_BUILD_DIR)/uml/%.dot
	$(MKDIRP) -- $(@D)
	$(X_DOT) $(DOT_OPTS) '-T$(patsubst .%,%,$(suffix $(@F)))' '$(<)' -o '$(@)'



PHONY += check-typo
check-typo:
# name it Kconfig, or kconfig where lowercase is appropriate
	$(call f_grep_check_recursive,[kK]C[oO][nN][fF][iI][gG])

PHONY += check-pep8
check-pep8:
# setup.py does not need to be pep8-compliant
	$(X_PEP8) \
		$(_PYMOD_DIRS) \
		$(call f_list_pym_conf_sources) \
		$(foreach x,$(PEP8_EXCLUDE),--exclude '$(x)')

PHONY += check-pyflakes
check-pyflakes:
	$(X_PYFLAKES) \
		$(_SETUP_PY) \
		$(_PYMOD_DIRS) \
		$(call f_list_pym_conf_sources) \
		$(PYFLAKES_EXTRA_FILES)

PHONY += check
check: $(addprefix check-,typo pep8 pyflakes)


prepare-installinfo: $(_BUILD_DIR:/=)/installinfo.py

$(_BUILD_DIR:/=)/installinfo.py:
	$(RMF) -- '$(@)' '$(@).make_tmp'

	$(MKDIRP) -- '$(@D)'
	{ set -e; \
		printf '%s = "%s"\n' sys_config_dir '$(PRJ_SYSCONFDIR)'; \
		printf '%s = "%s"\n' sys_data_dir   '$(PRJ_DATADIR)'; \
	} > '$(@).make_tmp'

	-$(X_PEP8) '$(@).make_tmp'
	$(X_PYFLAKES) '$(@).make_tmp'

	$(MV) -- '$(@).make_tmp' '$(@)'


PHONY += install-data
install-data:
	$(DODIR) -- '$(DESTDIR)$(PRJ_DATADIR)'
	$(DODIR) -- '$(DESTDIR)$(PRJ_DATADIR)/scripts'

	$(DOINS) -- '$(SRC_FILESDIR)/data/scripts/modalias.mk' \
		'$(DESTDIR)$(PRJ_DATADIR)/scripts/modalias.mk'

PHONY += install-config
install-config:
	$(DODIR) -- '$(DESTDIR)$(PRJ_SYSCONFDIR)'

	$(call doins_recursive,$(SRC_CONFDIR),$(DESTDIR)$(PRJ_SYSCONFDIR))

PHONY += install-hwcollect
install-hwcollect:
	$(DODIR) -- '$(DESTDIR)$(BINDIR)'

	$(DOEXE) -- '$(SRC_FILESDIR)/scripts/hwcollect.sh' \
		'$(DESTDIR)$(BINDIR)/$(PN)-hwcollect'


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
				"$(PRJ_LKC_SRC)/$${fname%_shipped}"; \
		done; \
	}
endif

PHONY += fetch-lkc
ifeq ("","$(LK_SRC_URI)")
fetch-lkc:
	$(error LK_SRC_URI is not set)

else
fetch-lkc:
	$(MKDIRP) -- $(PRJ_LKC_SRC)
	$(X_WGET) $(WGET_OPTS) '$(LK_SRC_URI)/COPYING' -O '$(PRJ_LKC_SRC)/COPYING'
	{ set -e; \
		for fname in $(LKC_FILE_NAMES); do \
			$(X_WGET) $(WGET_OPTS) "$(LK_SRC_URI)/scripts/kconfig/$${fname}" \
				-O "$(PRJ_LKC_SRC)/$${fname%_shipped}"; \
		done; \
	}
endif


PHONY += bundle-lkc
bundle-lkc: $(PRJ_LKC_SRC_BUNDLED)

$(PRJ_LKC_SRC_BUNDLED): FORCE | $(filter import-lkc fetch-lkc,$(MAKECMDGOALS))
	$(call f_sanity_check_output_dir,$(@))
	test ! -d '$(@)' || $(RM) -r -- '$(@)'

	$(MKDIRP) -- '$(@)'
	{ set -e; \
		for fname in COPYING $(patsubst %_shipped,%,$(LKC_FILE_NAMES)); do \
			$(CP) -- "$(PRJ_LKC_SRC)/$${fname}" "$(@)/$${fname}"; \
		done; \
	}


PHONY += help
help:
	@echo  'Helper targets:'
	@echo  '  check                      - perform some basic code checks (pep8, pyflakes)'
	@echo  '  import-lkc [LK_SRC=...]    - import lkc files from linux kernel'
	@echo  '                               source tree LK_SRC'
	@echo  '  fetch-lkc [LK_SRC_URI=...] - download lkc files'
	@echo  '  bundle-lkc                 - update the bundled lkc files'
	@echo  '                               with newly imported files'
	@echo  ''
	@echo  'Cleanup Targets:'
	@echo  '  clean                      - does nothing'
	@echo  '  pyclean                    - remove pyc files'
	@echo  '  distclean                  - all clean targets'


FORCE:

.PHONY: $(PHONY)
