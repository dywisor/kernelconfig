unexport PYTHONDONTWRITEBYTECODE
export PYTHONDONTWRITEBYTECODE=y

SHELL ?= sh

__PRJ_MK_FILE := $(realpath $(lastword $(MAKEFILE_LIST)))
__PRJ_MK_DIR  := $(patsubst %/,%,$(dir $(__PRJ_MK_FILE)))

_PRJNAME := kernelconfig
_PRJROOT := $(abspath $(__PRJ_MK_DIR)/..)
PN := $(_PRJNAME)

S := $(_PRJROOT)
O := $(S)
SRC_FILESDIR := $(S:/=)/files
SRC_DOCDIR := $(S:/=)/doc
SRC_CONFDIR := $(S:/=)/config
SRC_CONFSOURCEDIR := $(SRC_CONFDIR:/=)/sources

_BUILD_DIR := $(O:/=)/build
_PYMOD_DIRS := $(addprefix $(S:/=)/,$(_PRJNAME))
_SETUP_PY := $(S:/=)/setup.py
_EPYDOC_DIR = $(SRC_DOCDIR:/=)/epydoc

PYSETUP_RECORD_FILE := $(_BUILD_DIR)/$(PN)_pysetup_files.list
