DESTDIR       =
PREFIX        = /usr/local
EXEC_PREFIX   = $(PREFIX)
BINDIR        = $(EXEC_PREFIX:/=)/bin
SBINDIR       = $(EXEC_PREFIX:/=)/sbin
LIBDIR_NAME   = lib
LIBDIR        = $(EXEC_PREFIX:/=)/$(LIBDIR_NAME)
DATAROOTDIR   = $(PREFIX:/=)/share
DATADIR       = $(DATAROOTDIR)
SYSCONFDIR    = $(PREFIX:/=)/etc
LOCALSTATEDIR = $(PREFIX:/=)/var

EXEMODE ?= 0755
INSMODE ?= 0644
DIRMODE ?= 0755

INSTALL  = install
DODIR    = $(INSTALL) -d -m $(DIRMODE)
DOEXE    = $(INSTALL) -D -m $(EXEMODE)
DOINS    = $(INSTALL) -D -m $(INSMODE)
DOSYM    = $(LN) -f -s

PRJ_SYSCONFDIR = $(SYSCONFDIR:/=)/$(PN)
PRJ_DATADIR    = $(DATADIR:/=)/$(PN)

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