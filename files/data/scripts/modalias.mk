# This Makefile creates and install files necessary
# for modalias-based hardware detection.
#
# To realize this, a throw-away "make allmodconfig && make modules" run
# compiles all modules and then depmod is run to create the modules.alias file
# (and some other files).
#
# Usage:
#   make ... all && make ... install
# or
#   make ... compress-modalias && make ... install-tar
#
# Consider adding "-j" to the make command.
# Most variables are passed as-is to the kernel make commands,
# so specifying ARCH=<arch> should work.
#
# This makefile relies on a temporary directory,
# which must be cleaned up by the caller.
# Also, it should (but does not have to) be created by the caller.
#
# The following vars must be passed to this Makefile:
#
# * T       temporary working dir, not cleaned up by this mkfile
# * D       modalias install dir (i.e. cache dir)
#            files in this directory get overwritten when "installing"
#            Theoretically, only necessary for the "install" target -- COULDFIX
# * KSRC    kernel srctree
#            should be in a clean state
#            the modules are compiled out-of-tree (O=<T>/...)
#
# The following vars should be passed to this Makefile:
#
# * DEPMOD  path to depmod
#             since depmod usually resides in /sbin/depmod
#             and this mkfile is run as normal user,
#             it can be necessary to set this manually
#
# Other vars of interest:
#
# * KERNELCONFIG_CONFTARGET:  the config target used for building the modules
#                             Defaults to "allmodconfig".
#                             For testing, "defconfig" should suffice.
#
# Targets:
# * all:          build modules, run depmod
# * install:      install modules.alias and related files to D
# * install-tar:  install the tarfile variant to D (D/data.txz, D/kernelrelease)
#
# Phase targets (later targets include previous ones):
#
# * config:             create the kernel configuration
# * modules:            build the kernel modules
# * modules_install:    run depmod
# * compress-modalias:  create a tar archive of the created modalias files
#

# by default, export all variables (e.g. ARCH) to sub-makes
export

ifeq ("","$(DEPMOD)")
DEPMOD := $(shell which depmod 2>/dev/null)
endif
ifeq ("","$(DEPMOD)")
$(error path to depmod DEPMOD is not set)
endif
unexport DEPMOD

ifeq ("","$(T)")
$(error tmpdir T is not set)
endif

ifeq ("","$(KSRC)")
$(error kernel srctree KSRC is not set)
endif

ifeq ("","$(D)")
$(error modules destdir D is not set)
endif

KERNELCONFIG_KBUILD         := $(T:/=)/build
KERNELCONFIG_KINST          := $(T:/=)/inst
KERNELCONFIG_KINST_MOD      := $(KERNELCONFIG_KINST)/mod
KERNELCONFIG_KINST_MODALIAS := $(KERNELCONFIG_KINST)/modalias
KERNELCONFIG_STAMPD         := $(T:/=)

# for testing purposes, this can be set to a "lighter" target, e.g. defconfig
KERNELCONFIG_CONFTARGET := allmodconfig

# this is a checklist of files that must exist after running depmod
#  All files whose name starts with "modules.*" get copied.
#
KERNELCONFIG_MODALIAS_FILES :=
KERNELCONFIG_MODALIAS_FILES += modules.alias modules.alias.bin
KERNELCONFIG_MODALIAS_FILES += modules.builtin modules.builtin.bin
KERNELCONFIG_MODALIAS_FILES += modules.dep modules.dep.bin
KERNELCONFIG_MODALIAS_FILES += modules.softdep
KERNELCONFIG_MODALIAS_FILES += modules.symbols modules.symbols.bin


unexport T
unexport KSRC
unexport D
unexport KERNELCONFIG_KBUILD
unexport KERNELCONFIG_KINST
unexport KERNELCONFIG_KINST_MOD
unexport KERNELCONFIG_KINST_MODALIAS
unexport KERNELCONFIG_KINST
unexport KERNELCONFIG_STAMPD
unexport KERNELCONFIG_CONFTARGET
unexport KERNELCONFIG_MODALIAS_FILES

MKDIR = mkdir
MKDIRP = $(MKDIR) -p
CP = cp
CPV = $(CP) -v
MV = mv
MVV = $(MV) -v
RM = rm
RMF = $(RM) -f
SED = sed
TOUCH = touch
TAR = tar
# the compression is controlled by the modalias.txz rule
TAR_CREATE_OPTS =
# try to reduce the information leak
TAR_CREATE_OPTS += --numeric-owner --owner=root --group=root
TAR_CREATE_OPTS += --no-acls
TAR_CREATE_OPTS += --no-xattrs


unexport MKDIR
unexport MKDIRP
unexport CP
unexport CPV
unexport MV
unexport MVV
unexport RM
unexport RMF
unexport SED
unexport TOUCH
unexport TAR
unexport TAR_CREATE_OPTS

unexport PHONY

PHONY += all
all: modules_install

PHONY += compress-modalias
compress-modalias: $(KERNELCONFIG_KINST)/modalias.txz

PHONY += install
install:
# modules_install must be run before this target
# (and "install" should not trigger compilation)
	test -e '$(KERNELCONFIG_STAMPD)/.stamp_modules_install'

# copy the files
	$(MKDIRP) -- '$(D)'
	$(CPV) -dR -- '$(KERNELCONFIG_KINST_MODALIAS)/.' '$(D)/.'


PHONY += install-tar
install-tar:
# modules_install must be run before this target
# (and "install" should not trigger compilation)
	test -e '$(KERNELCONFIG_STAMPD)/.stamp_modules_install'

	$(MKDIRP) -- '$(D)'
	$(CPV) -- '$(KERNELCONFIG_KINST_MODALIAS)/kernelrelease' '$(D)/kernelrelease'
	$(CPV) -- '$(KERNELCONFIG_KINST)/modalias.txz' '$(D)/data.txz'


# declare phony config, modules targets, which rely on a stamp file
KERNELCONFIG__MK_PHASES := config modules modules_install
unexport KERNELCONFIG__MK_PHASES

PHONY += $(KERNELCONFIG__MK_PHASES)
$(KERNELCONFIG__MK_PHASES): %: $(KERNELCONFIG_STAMPD)/.stamp_%


# mkdir targets
$(KERNELCONFIG_KBUILD) $(KERNELCONFIG_KINST) \
$(KERNELCONFIG_KINST_MOD) $(KERNELCONFIG_KINST_MODALIAS):
	$(MKDIRP) -- '$(@)'

ifneq ("","$(KERNELCONFIG_STAMPD)")
# T=/ will probably not work.
$(KERNELCONFIG_STAMPD):
	$(MKDIRP) -- '$(@)'
endif


# func: delete a previous stamp file (when running "make -B")
define stamp_rule_init
	$(RMF) -- '$(@)'
endef
unexport stamp_rule_init

# func: create a stamp file
define stamp_rule_fini
	$(TOUCH) -- '$(@)'
endef
unexport stamp_rule_fini

# configure the kernel:
$(KERNELCONFIG_STAMPD)/.stamp_config: %/.stamp_config: \
	| $(KSRC) $(KERNELCONFIG_KBUILD) %
# prepare
	$(call stamp_rule_init)

# configure the kernel
	$(info *** Creating base config: $(KERNELCONFIG_CONFTARGET))
	$(MAKE) -C '$(KSRC)' 'O=$(KERNELCONFIG_KBUILD)' \
		'$(KERNELCONFIG_CONFTARGET)' < /dev/null

# deactivate some options (w/o dep check)
	$(info *** Editing config)
	$(SED) -r \
		-e 's,^(CONFIG_MODULE_SIG.*)=.*$$,# \\1 is not set,' \
		-i '$(KERNELCONFIG_KBUILD)/.config'

	{ \
		set -e; \
		for cfg_opt in \
			CONFIG_MODULE_SIG \
		; do \
			if ! grep -qE -- \
				"(^$${cfg_opt}=)|(^#\\s+$${cfg_opt}\\s+is)" \
				'$(KERNELCONFIG_KBUILD)/.config' \
			; then \
				printf '# %s is not set\n' "$${cfg_opt}" \
					>> '$(KERNELCONFIG_KBUILD)/.config'; \
			fi; \
		done; \
	}

# oldconfig
	$(info *** Checking config w/ silentoldconfig)
	$(MAKE) -C '$(KSRC)' 'O=$(KERNELCONFIG_KBUILD)' 'silentoldconfig' < /dev/null

# done
	$(call stamp_rule_fini)



# build the modules:
$(KERNELCONFIG_STAMPD)/.stamp_modules: %/.stamp_modules: \
	%/.stamp_config | $(KSRC) %

# prepare
	$(call stamp_rule_init)

# build
	$(info *** Building modules)
	$(MAKE) -C '$(KSRC)' 'O=$(KERNELCONFIG_KBUILD)' modules < /dev/null

# done
	$(call stamp_rule_fini)


# install the modules to the temporary directory:
$(KERNELCONFIG_STAMPD)/.stamp_modules_install: %/.stamp_modules_install: \
	%/.stamp_modules | $(KSRC) $(KERNELCONFIG_KINST_MOD) %

# prepare
	$(call stamp_rule_init)

# install
	$(info *** Installing modules to temporary directory)
	$(MAKE) -C '$(KSRC)' 'O=$(KERNELCONFIG_KBUILD)' \
		INSTALL_MOD_PATH='$(KERNELCONFIG_KINST_MOD)' \
		modules_install

# depmod
	$(info *** Getting kernelrelease)
	$(eval MY_$@_KVER := $(shell \
		$(MAKE) -s -C '$(KSRC)' 'O=$(KERNELCONFIG_KBUILD)' kernelrelease))

	$(info *** kernelrelease = $(MY_$@_KVER))

	test -d '$(KERNELCONFIG_KINST_MOD)/lib/modules/$(MY_$@_KVER)'

	$(info *** Running depmod)
	$(DEPMOD) --basedir '$(KERNELCONFIG_KINST_MOD)' '$(MY_$@_KVER)'

# pick modalias files-related files and move them to .../modalias
	$(MKDIRP) -- '$(KERNELCONFIG_KINST_MODALIAS)'

#   KERNELCONFIG_MODALIAS_FILES first
	{ \
		set -e; \
		src_dir="$(KERNELCONFIG_KINST_MOD)/lib/modules/$(MY_$@_KVER)"; \
		for f in $(KERNELCONFIG_MODALIAS_FILES); do \
			$(MVV) \
				"$${src_dir}/$${f}" \
				"$(KERNELCONFIG_KINST_MODALIAS)/$${f}"; \
		done; \
	}

#   then all other files w/ name "modules.*"
	find '$(KERNELCONFIG_KINST_MOD)/lib/modules/$(MY_$@_KVER)' \
		-type f -name 'modules.*' \
		-exec $(MVV) -t '$(KERNELCONFIG_KINST_MODALIAS)/' '{}' +

#   then create a kernelrelease file
	printf '%s\n' '$(MY_$@_KVER)' \
		> '$(KERNELCONFIG_KINST_MODALIAS)/kernelrelease'

# done
	$(call stamp_rule_fini)

$(KERNELCONFIG_KINST)/modalias.txz: \
	$(KERNELCONFIG_STAMPD)/.stamp_modules_install | $(KERNELCONFIG_KINST)

	$(TAR) c -C '$(KERNELCONFIG_KINST_MODALIAS)/' \
		./ -J -f '$(@)' $(TAR_CREATE_OPTS)



.PHONY: $(PHONY)
