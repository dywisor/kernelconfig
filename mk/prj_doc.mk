# targets for generating doc files in HTML or PDF format
#
#  Warning: this Makefile relies on functionality from the top-level Makefile,
#           namely:
#           * f_sanity_check_output_dir()
#           * double-colon, phony clean/distclean targets
#           * prj.mk, progs.mk already included
#
#
# PRJ_DOCS is the list of documentation file names w/o the file suffix.
# It is initialized as empty list.
#
# Each doc file <name> must exist in $(SRC_DOCDIR_RST) as <name>.rst,
# and can be added to the PRJ_DOCS list with
#    PRJ_DOCS += <name>
#
# Additionally, its (html) document title should be set with
#    PRJ_DOC_TITLE_<name> := <title>
#
# Document-specific options for rst2html/rst2pdf can be set with
#    RST2HTML_OPTS_<name> += <opts>
#    RST2PDF_OPTS_<name> += <opts>
#
#
# It is then possible to build all HTML or PDF files with
#    $ make htmldoc
#    $ make pdfdoc
# or to build individual doc files with e.g.
#    $ make htmldoc-userguide
#
# Similarly, man pages are added to PRJ_MANPAGES,
# no other per-manpage variables exist.
#
# They can be created from doc/man/src/<name>.rst.in with
#    $ make man
#
# This will sed-edit @prj_@ vars in <name>.rst.in
# and create the man page with rst2man.
#
# There are no targets for installing the files,
# but they can be picked up from doc/man, doc/html and doc/pdf, respectively.
#

PRJ_DOCS :=

PRJ_DOCS += userguide
PRJ_DOC_TITLE_userguide := Generate Linux kernel configuration files
RST2PDF_OPTS_userguide := --break-level 2

PRJ_DOCS += devguide
PRJ_DOC_TITLE_devguide := Dev Guide

PRJ_DOCS += compatibility_rewrite_original
PRJ_DOC_TITLE_compatibility_rewrite_original = \
	Compatibility with the original project
RST2PDF_OPTS_compatibility_rewrite_original := --break-level 0

PRJ_MANPAGES :=
MANPAGE_BUILD_DIR := $(_BUILD_DIR)/man


# f_get_doc_title(name)
f_get_doc_title = $(strip $(PRJ_DOC_TITLE_$(1)))

# forward-referencing clean rules
clean-doc: $(addprefix clean-,htmldoc pdfdoc)
distclean:: clean-doc

# html
X_RST2HTML = rst2html.py
RST2HTML_OPTS = --date --section-numbering

_HTML_DOC_TARGETS := $(addprefix htmldoc-,$(PRJ_DOCS))

PHONY += htmldoc
htmldoc: $(_HTML_DOC_TARGETS)

PHONY += clean-htmldoc
clean-htmldoc:
	$(call f_sanity_check_output_dir,$(SRC_DOCDIR_HTML))
	$(RMF) -r -- $(SRC_DOCDIR_HTML)

PHONY += $(_HTML_DOC_TARGETS)
$(_HTML_DOC_TARGETS): htmldoc-%: $(SRC_DOCDIR_HTML)/%.html


$(SRC_DOCDIR_HTML):
	$(MKDIRP) -- '$(@)'

$(SRC_DOCDIR_HTML)/%.html: $(SRC_DOCDIR_RST)/%.rst | $(SRC_DOCDIR_HTML)
	$(X_RST2HTML) $(RST2HTML_OPTS) \
		--title '$(PN) - $(call f_get_doc_title,$*)' \
		$(RST2HTML_OPTS_$*) \
		'$(<)' '$(@)'


# pdf
X_RST2PDF = rst2pdf
RST2PDF_OPTS = --repeat-table-rows --break-level 1

_PDF_DOC_TARGETS := $(addprefix pdfdoc-,$(PRJ_DOCS))

PHONY += pdfdoc
pdfdoc: $(_PDF_DOC_TARGETS)

PHONY += clean-pdfdoc
clean-pdfdoc:
	$(call f_sanity_check_output_dir,$(SRC_DOCDIR_PDF))
	$(RMF) -r -- $(SRC_DOCDIR_PDF)

PHONY += $(_PDF_DOC_TARGETS)
$(_PDF_DOC_TARGETS): pdfdoc-%: $(SRC_DOCDIR_PDF)/%.pdf


$(SRC_DOCDIR_PDF):
	$(MKDIRP) -- '$(@)'

$(SRC_DOCDIR_PDF)/%.pdf: $(SRC_DOCDIR_RST)/%.rst | $(SRC_DOCDIR_PDF)

# --baseurl '$(SRC_DOCDIR_RST:/=)/' # raises ValueError / fails to resolve path
	$(X_RST2PDF) $(RST2PDF_OPTS) \
		$(RST2PDF_OPTS_$*) \
		'$(<)' '$(@)'


# man
X_RST2MAN = rst2man.py
RST2MAN_OPTS =

_MANPAGE_TARGETS := $(addprefix man-,$(PRJ_MANPAGES))

PHONY += man
man: $(_MANPAGE_TARGETS)

PHONY += $(_MANPAGE_TARGETS)
$(_MANPAGE_TARGETS): man-%: $(SRC_MANDIR)/% | $(SRC_MANDIR)


# no-target SRC_MANDIR
$(MANPAGE_BUILD_DIR):
	$(MKDIRP) -- '$(@)'

$(MANPAGE_BUILD_DIR)/%.rst: $(SRC_MANDIR)/src/%.rst.in | $(MANPAGE_BUILD_DIR)
	$(call f_sed_edit_install,$(<),$(@).make_tmp)
	$(MVF) -- '$(@).make_tmp' '$(@)'

$(SRC_MANDIR)/%: $(MANPAGE_BUILD_DIR)/%.rst | $(SRC_MANDIR)
	$(X_RST2MAN) $(RST2MAN_OPTS) '$(<)' '$(@)'
