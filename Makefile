PHONY += all
all:
	true


__MAIN_MK_FILE := $(realpath $(lastword $(MAKEFILE_LIST)))
__MAIN_MK_DIR  := $(patsubst %/,%,$(dir $(__MAIN_MK_FILE)))

include $(__MAIN_MK_DIR)/mk/prj.mk
include $(__MAIN_MK_DIR)/mk/prj_doc.mk
include $(__MAIN_MK_DIR)/mk/progs.mk
include $(__MAIN_MK_DIR)/mk/install.mk
include $(__MAIN_MK_DIR)/mk/installfuncs.mk

PYTHON = python

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
WGET_OPTS = -q
X_GIT = git
GIT_OPTS = --no-pager
GIT_COMMIT_OPTS =

PRJ_LKC_SRC = $(S)/src/lkc
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



PHONY += build-py
build-py: $(_BUILD_DIR:/=)/installinfo.py
	$(PYTHON) $(_SETUP_PY) build


PHONY += clean
clean::
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
distclean:: clean pyclean
	true

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


PHONY += prepare-installinfo
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

PHONY += install-py
install-py: | $(dir $(PYSETUP_RECORD_FILE))
	$(PYTHON) $(_SETUP_PY) install \
		--skip-build \
		--root '/$(DESTDIR:/=)' \
		--prefix '$(PREFIX)' \
		--exec-prefix '$(EXEC_PREFIX)' \
		--record '$(PYSETUP_RECORD_FILE)'

PHONY += install-data
install-data:
	$(DODIR) -- '$(DESTDIR)$(PRJ_DATADIR)'
	$(DODIR) -- '$(DESTDIR)$(PRJ_DATADIR)/scripts'

	$(DOINS) -- '$(SRC_FILESDIR)/data/scripts/modalias.mk' \
		'$(DESTDIR)$(PRJ_DATADIR)/scripts/modalias.mk'

	$(call doins_recursive,$(SRC_CONFDIR)/sources,$(DESTDIR)$(PRJ_DATADIR)/sources)

PHONY += install-config
install-config:
	$(DODIR) -- '$(DESTDIR)$(PRJ_SYSCONFDIR)'

	$(call doins_norecur,$(SRC_CONFDIR),$(DESTDIR)$(PRJ_SYSCONFDIR))
	$(call doins_recursive,$(SRC_CONFDIR)/include,$(DESTDIR)$(PRJ_SYSCONFDIR)/include)

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


$(PRJ_LKC_SRC):
	$(MKDIRP) -- '$(@)'

PHONY += import-lkc
ifeq ("","$(LK_SRC)")
import-lkc:
	$(error LK_SRC is not set)

else
import-lkc: $(LK_SRC) $(PRJ_LKC_SRC)
	$(CPV) -- '$(<)/COPYING' '$(PRJ_LKC_SRC)/COPYING'
	{ set -e; \
		for fname in $(LKC_FILE_NAMES); do \
			$(CPV) -- "$(<)/scripts/kconfig/$${fname}" \
				"$(PRJ_LKC_SRC)/$${fname%_shipped}"; \
		done; \
	}
endif

PHONY += fetch-lkc
ifeq ("","$(LK_SRC_URI)")
fetch-lkc:
	$(error LK_SRC_URI is not set)

else

$(PRJ_LKC_SRC)/COPYING: $(PRJ_LKC_SRC) FORCE
	$(X_WGET) $(WGET_OPTS) '$(LK_SRC_URI)/COPYING' -O '$(@)'

# make sure to fetch COPYING first by depending on it
$(addprefix $(PRJ_LKC_SRC)/,$(LKC_FILE_NAMES)): \
	$(PRJ_LKC_SRC)/%: $(PRJ_LKC_SRC)/COPYING FORCE

	$(X_WGET) $(WGET_OPTS) '$(LK_SRC_URI)/scripts/kconfig/$(*)' -O '$(@)'

$(patsubst %_shipped,%,\
	$(addprefix $(PRJ_LKC_SRC)/,$(filter %_shipped,$(LKC_FILE_NAMES)))): \
	$(PRJ_LKC_SRC)/%: $(PRJ_LKC_SRC)/%_shipped

	$(CP) -- '$(<)' '$(@)'

fetch-lkc: $(patsubst %_shipped,%,\
	$(addprefix $(PRJ_LKC_SRC)/,COPYING $(LKC_FILE_NAMES)))

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


PHONY += commit-bundle-lkc
commit-bundle-lkc: bundle-lkc
	$(X_GIT) $(GIT_OPTS) add -A -- '$(PRJ_LKC_SRC_BUNDLED)/'

	if $(X_GIT) $(GIT_OPTS) status --porcelain \
		-- '$(PRJ_LKC_SRC_BUNDLED)/' | $(X_GREP) -q -- '^[MADRCU]'; \
	then \
		$(X_GIT) $(GIT_OPTS) commit $(GIT_COMMIT_OPTS) \
			-m "update bundled lkc files" \
			-m "Automated commit." \
			-- "$(PRJ_LKC_SRC_BUNDLED)/" || exit 5; \
	fi


PHONY += help
help:
	@echo  'Basic Targets:'
	@echo  '  all                        - does nothing'
	@echo  '  help                       - print this help message'
	@echo  ''
	@echo  'Build Targets:'
	@echo  '  prepare-installinfo        - create an installation info file'
	@echo  '                               (must be done prior to running setup.py build,'
	@echo  '                               with the same PREFIX,SYSCONFDIR as make install)'
	@echo  ''
	@echo  '  *** export LKCONFIG_SRC="src/lkc-bundled"  or see "lkc Targets" below,'
	@echo  '  *** then build with setup.py build, or'
	@echo  '  build-py                   - run PYTHON setup.py build,'
	@echo  '                               create installinfo if necessary'
	@echo  '                                 (PYTHON: $(PYTHON))'
	@echo  ''
	@echo 'Install Targets:'
	@echo  '  install-data               - install data files'
	@echo  '                               to DATADIR/$(PN) in DESTDIR'
	@echo  '                                 (DATADIR: $(DATADIR))'
	@echo  '  install-config             - install config files'
	@echo  '                               to SYSCONFDIR/$(PN) in DESTDIR'
	@echo  '                                 (SYSCONFDIR: $(SYSCONFDIR))'
	@echo  '  install-hwcollect          - install the hardware collector script'
	@echo  '                               to BINDIR in DESTDIR'
	@echo  '                                 (BINDIR: $(BINDIR))'
	@echo  ''
	@echo  '  *** install Python files with setup.py install, or'
	@echo  '  install-py                 - install Python files in DESTDIR,'
	@echo  '                               a list of installed files is written'
	@echo  '                               to build/$(notdir $(PYSETUP_RECORD_FILE))'
ifeq ("","$(DESTDIR)")
	@echo  '                                 (DESTDIR: /)'
else
	@echo  '                                 (DESTDIR: $(DESTDIR))'
endif
	@echo  '                                 (PYTHON: $(PYTHON))'
	@echo  ''
	@echo  'Cleanup Targets:'
	@echo  '  clean                      - does nothing'
	@echo  '  epydoc-clean               - remove generated epydoc files'
	@echo  '  pyclean                    - remove pyc files'
	@echo  '  distclean                  - all clean targets'
	@echo  ''
	@echo  'lkc Targets:'
	@echo  '  print-lkc-files            - print a list of required lkc files'
	@echo  '  import-lkc [LK_SRC=...]    - import lkc files from linux kernel'
	@echo  '                               source tree LK_SRC'
	@echo  '  fetch-lkc [LK_SRC_URI=...] - download lkc files from LK_SRC_URI'
	@echo  '  bundle-lkc                 - update the bundled lkc files'
	@echo  '                               with newly imported files'
	@echo  '                               (release/devel helper target)'
	@echo  '  commit-bundle-lkc          - bundle lkc and also git-commit'
	@echo  ''
	@echo  'Basic Code Check Targets:'
	@echo  '  check                      - perform some basic code checks (pep8, pyflakes)'
	@echo  '  check-typo                 - check for basic typos'
	@echo  '  check-pep8                 - run pep8 code check'
	@echo  '  check-pyflakes             - run pyflakes code check'
	@echo  ''
	@echo  'File Generation Targets:'
	@echo  '  epydoc                     - generate epydoc documentation'
	@echo  '                               (does not complete warning-free)'
	@echo  '  uml                        - generate packages and classes uml diagrams'
	@echo  '                               in dot and png format'
	@echo  '  uml-dot                    - ... in dot format only'
	@echo  '  uml-png                    - ... in png format only'
	@echo  ''
	@echo  ''
	@echo  'Variables:'
	@echo  '* S                          - project sources directory'
	@echo  '                               [$(S)]'
	@echo  '* PN                         - project name [$(PN)]'
	@echo  '* PYTHON                     - python prog used when running setup.py [$(PYTHON)]'
	@echo  ''
	@echo  '* PRJ_LKC_SRC                - path to the default lkc files'
	@echo  '                               [$(call f_subst_srcdir,$(PRJ_LKC_SRC))]'
	@echo  '* PRJ_LKC_SRC_BUNDLED        - path to the bundled lkc files'
	@echo  '                               [$(call f_subst_srcdir,$(PRJ_LKC_SRC_BUNDLED))]'
	@echo  '* LK_SRC_URI                 - uri for "fetch-lkc"'
	@echo  '                               [$(LK_SRC_URI)]'
	@echo  ''
	@echo  'Install-related Variables:'
	@echo  '* DESTDIR                    - [$(DESTDIR:/=)/]'
	@echo  '* PREFIX                     - [$(PREFIX)]'
	@echo  '* EXEC_PREFIX                - [$(EXEC_PREFIX)]'
	@echo  '* BINDIR                     - [$(BINDIR)]'
	@echo  '* SBINDIR                    - [$(SBINDIR)]'
	@echo  '* DATADIR                    - [$(DATADIR)]'
	@echo  '* PRJ_DATADIR                - DATADIR/$(PN) [$(PRJ_DATADIR)]'
	@echo  '* SYSCONFDIR                 - [$(SYSCONFDIR)]'
	@echo  '* PRJ_SYSCONFDIR             - SYSCONFDIR/$(PN) [$(PRJ_SYSCONFDIR)]'
	@echo  '* LOCALSTATEDIR              - [$(LOCALSTATEDIR)]'
	@echo  '* PYSETUP_RECORD_FILE        - setup.py install record file'
	@echo  '                               [$(call f_subst_srcdir,$(PYSETUP_RECORD_FILE))]'
	@echo  '* DIRMODE                    - mode for creating directories [$(DIRMODE)]'
	@echo  '* INSMODE                    - mode for installing files [$(INSMODE)]'
	@echo  '* EXEMODE                    - mode for installing scripts [$(EXEMODE)]'



FORCE:

.PHONY: $(PHONY)
