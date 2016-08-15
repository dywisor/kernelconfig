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

PRJ_SYSCONFDIR = $(SYSCONFDIR:/=)/$(PN)
PRJ_DATADIR    = $(DATADIR:/=)/$(PN)
