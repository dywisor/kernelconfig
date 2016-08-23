EXEMODE ?= 0755
INSMODE ?= 0644
DIRMODE ?= 0755

INSTALL  = install
DODIR    = $(INSTALL) -d -m $(DIRMODE)
DOEXE    = $(INSTALL) -D -m $(EXEMODE)
DOINS    = $(INSTALL) -D -m $(INSMODE)
DOSYM    = $(LN) -f -s

# _f_install_files_recursive(ins_mode, src_root, dst_root)
define _f_install_files_recursive
	( cd '$(2:/=)/' && find ./ -type f; ) | sed -e 's=^[.]/==' | \
		xargs -r -n 1 -I '{}' \
			$(INSTALL) -D -m '$(1)' --  '$(2:/=)/{}' '$(3:/=)/{}'
endef

# f_install_files_recursive(ins_mode, src_root, dst_root)
f_install_files_recursive = $(call \
	_f_install_files_recursive,$(strip $(1)),$(strip $(2)),$(strip $(3)))

doins_recursive = $(call f_install_files_recursive,$(INSMODE),$(1),$(2))

# _f_install_files_norecur(ins_mode, src_root, dst_root)
define _f_install_files_norecur
	( cd '$(2:/=)/' && find ./ -mindepth 1 -maxdepth 1 -type f; ) | \
		sed -e 's=^[.]/==' | \
		xargs -r -n 1 -I '{}' \
			$(INSTALL) -D -m '$(1)' --  '$(2:/=)/{}' '$(3:/=)/{}'
endef

# f_install_files_norecur(ins_mode, src_root, dst_root)
f_install_files_norecur = $(call \
	_f_install_files_norecur,$(strip $(1)),$(strip $(2)),$(strip $(3)))

doins_norecur = $(call f_install_files_norecur,$(INSMODE),$(1),$(2))


SED_EDIT_EXPRV_INSTALL = \
	-e s=@prj_sysconfdir@=$(PRJ_SYSCONFDIR)=g \
	-e s=@prj_datadir@=$(PRJ_DATADIR)=g \
	-e /@prj_localconfdir@/d \
	-e /@prj_localdatadir@/d

# dup of <filesdir>/installinfo/standalone.py
SED_EDIT_EXPRV_STANDALONE = \
	-e s=@prj_sysconfdir@=$(_PRJROOT:/=)/config=g \
	-e s=@prj_datadir@=$(_PRJROOT:/=)/files/data=g \
	-e s=@prj_localconfdir@=$(PRJ_LOCALDIR:/=)/config=g \
	-e s=@prj_localdatadir@=$(PRJ_LOCALDIR:/=)/data=g

# _f_sed_edit_mode (mode_exprv, infile, outfile)
__f_sed_edit_mode = $(SED) -r $(1) < '$(2)' > '$(3)'
_f_sed_edit_mode = $(call __f_sed_edit_mode,$(1),$(strip $(2)),$(strip $(3)))

# f_sed_edit_<mode> (infile, outfile)
#  f_sed_edit_install(...)
#  f_sed_edit_standalone(...)
f_sed_edit_install = $(call _f_sed_edit_mode,$(SED_EDIT_EXPRV_INSTALL),$(1),$(2))
f_sed_edit_standalone = $(call _f_sed_edit_mode,$(SED_EDIT_EXPRV_STANDALONE),$(1),$(2))
