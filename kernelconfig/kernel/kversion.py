# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import re

from ..util import fileio


__all__ = ["KernelVersion", "KernelVersionMkVarRedefinition"]


class KernelVersionMkVarRedefinition(AssertionError):
    pass


class KernelVersion(object):
    """A kernel version.

    @ivar version:
    @type version:       C{int}
    @ivar patchlevel:
    @type patchlevel:    C{int}
    @ivar sublevel:
    @type sublevel:      C{int}
    @ivar extraversion:
    @type extraversion:  C{str} or C{None}
    @ivar name:
    @type name:          C{str} or C{None}
    """

    @classmethod
    def read_makefile_vars(cls, varnames, makefile, **read_kwargs):
        """Reads variables from the kernel sources' Makefile.

        Note: this method is not suitable for parsing arbitrary Makefiles!
              For instance, it does not evaluate "$(VAR)",
              and raises an exception if a requested var gets reset.

        @raises KernelVersionMkVarRedefinition: if a var gets set twice

        @param varnames:     iterable containing names
        @type  varnames:     iterable of C{str}
        @param makefile:     path to Makefile (or file object)
        @type  makefile:     fileobj or C{str}
        @param read_kwargs:  additional keyword arguments
                             for read_text_file_lines()
        @type read_kwargs:   C{dict} :: C{str} => _

        @return: generates 2-tuples (varname, value)
        @rtype:  2-tuple (C{str}, C{str})
        """
        varnames_missing = set(varnames)
        mk_vassign_regexp = re.compile(
            (
                r'(?P<varname>{varnames})'
                r'\s*(?:[:]?[=])\s*'
                r'(?P<value>(?:(?:\S.*)*\S))?'
                r'\s*$'
            ).format(varnames='|'.join(map(re.escape, varnames_missing)))
        )

        for lino, line in (
            fileio.read_text_file_lines(makefile, **read_kwargs)
        ):
            vmatch = mk_vassign_regexp.match(line)
            if vmatch is not None:
                varname = vmatch.group("varname")
                try:
                    varnames_missing.remove(varname)
                except KeyError:
                    # duplicate entry for varname
                    #  because we abort after having read each var once,
                    #  it doesn't make sense to yield duplicates
                    #  (other dups might get by unnoticed)
                    raise KernelVersionMkVarRedefinition(varname) from None
                else:
                    yield (varname, vmatch.group("value"))
                    # break loop if all vars found
                    if not varnames_missing:
                        break
                    # --
                # -- end try
            # -- end if vmatch?
        # -- end for line
    # --- end of read_makefile_vars (...) ---

    @classmethod
    def new_from_makefile(cls, makefile, **read_kwargs):
        """Creates a new kernel version object with information
        read from a Makefile.

        @raises ValueError: if Makefile lacks essential vars
        @raises ValueError: propagated from set_<attr>()
        @raises KernelVersionMkVarRedefinition: if a var gets set twice

        @param makefile:     path to Makefile (or file object)
        @type  makefile:     fileobj or C{str}

        @return:  kernel version object
        @rtype:   L{KernelVersion}
        """
        kver = cls()

        for varname, value in cls.read_makefile_vars(
            ["VERSION", "PATCHLEVEL", "SUBLEVEL", "EXTRAVERSION", "NAME"],
            makefile, **read_kwargs
        ):
            attr_setter = getattr(kver, "set_%s" % varname.lower())
            attr_setter(value)
        # --

        if not kver.is_complete():
            # or AssertionError
            raise ValueError("incomplete version from Makefile")
        # --
        return kver
    # --- end of new_from_makefile (...) ---

    def __init__(
        self,
        version=None, patchlevel=None, sublevel=None, extraversion=None,
        name=None
    ):
        super().__init__()
        self.version = version
        self.patchlevel = patchlevel
        self.sublevel = sublevel
        self.extraversion = extraversion
        self.name = name
    # --- end of __init__ (...) ---

    def is_complete(self):
        """Checks whether the essential parts of the kernel version are set.

        A kernel version is considered complete
        if its version, patchlevel and sublevel are set to a non-None value.

        @return:  "complete or not?" -- True or False
        @rtype:   C{bool}
        """
        return all((
            v is not None for v in (
                self.version, self.patchlevel, self.sublevel
            )
        ))
    # --- end of is_complete (...) ---

    def set_version(self, arg):
        """Sets the 'version' component of this kernel version."""
        self.version = int(arg)

    def set_patchlevel(self, arg):
        """Sets the 'patchlevel' component of this kernel version."""
        self.patchlevel = int(arg)

    def set_sublevel(self, arg):
        """Sets the 'sublevel' component of this kernel version."""
        self.sublevel = int(arg)

    def set_extraversion(self, arg):
        """Sets the 'extraversion' component of this kernel version."""
        self.extraversion = arg

    def set_name(self, arg):
        """Sets the name of this kernel version."""
        self.name = arg

    def __str__(self):
        assert self.is_complete()
        return "{ver!s}.{plvl!s}.{slvl!s}{ever!s}".format(
            ver=self.version,
            plvl=self.patchlevel,
            slvl=self.sublevel,
            ever=(self.extraversion or "")
        )

    def __repr__(self):
        try:
            version_str = str(self)
        except AssertionError:
            version_str = "???"
        # --
        return "{c.__qualname__}({!r}".format(version_str, c=self.__class__)
    # --- end of __repr__ (...) ---

# --- end of KernelVersion ---
