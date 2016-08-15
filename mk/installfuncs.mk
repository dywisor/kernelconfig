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
