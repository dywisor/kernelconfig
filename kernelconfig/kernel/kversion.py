# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import re

from . import _kversion_base
from ..util import fileio


__all__ = [
    "kver_sort_key",
    "KernelVersion", "KernelExtraVersion",
    "KernelVersionMkVarRedefinition"
]


def kver_sort_key(kver_obj):
    """Returns the sort key of a kernel version object."""
    return kver_obj.get_sort_key()
# --- end of kver_sort_key (...) ---


class KernelVersionMkVarRedefinition(AssertionError):
    pass


class KernelVersionRegexp(object):
    __slots__ = []

    _REGEXP_EXTRAVERSION_STR = r'''
        (?P<extraversion_str>
            (?:[.](?P<extraversion_subsublevel>{d}(?:[.]{d})*))?
            (?:[-]rc(?P<extraversion_rclevel>{d}))?
            (?P<extraversion_dirty>[+])?
            (?P<extraversion_localversion>.+)?
        )
    '''.format(d=r'(?:[0-9]+)')

    _REGEXP_VERSION_STR = r'''
        (?P<version>{d})
            (?:
                [.](?P<patchlevel>{d})
                (?:
                    [.](?P<sublevel>{d})
                    (?:{ever})
                )?
            )?
    '''.format(d=r'(?:$|[0-9]+)', ever=_REGEXP_EXTRAVERSION_STR)

    RE_EXTRAVERSION_STR = re.compile(
        r'^%s$' % _REGEXP_EXTRAVERSION_STR, flags=re.VERBOSE
    )

    RE_VERSION_STR = re.compile(
        r'^%s$' % _REGEXP_VERSION_STR, flags=re.VERBOSE
    )

    @classmethod
    def match_version_str(cls, s):
        return cls.RE_VERSION_STR.match(s)

    @classmethod
    def match_extraversion_str(cls, s):
        return cls.RE_EXTRAVERSION_STR.match(s)

    @classmethod
    def get_version_regexp_str(cls):
        return cls._REGEXP_VERSION_STR

# ---


class KernelExtraVersion(_kversion_base.KernelVersionBaseObject):
    """The EXTRAVERSION part of a kernel version.

    @ivar subsublevel:   tuple of additional int version components
                         (for pre 3.x.y versions, e.g. 2.x.y.z,
                         where the "z" part ends up in subsublevel)
    @type subsublevel:   C{None} or tuple of C{int}

    @ivar rclevel:       the "-rc<LEVEL>" part of the extraversion
                         An extra version with an rclevel is considered
                         to be "less than" anything without an rclevel
    @type rclevel:       C{None} or C{int}

    @ivar dirty:         whether the extraversion has a "+" flag
                         Does not contribute to comparison results.
    @type dirty:         C{bool}

    @ivar localversion:  str remainder of the extraversion
                         Does not contribute to comparison results.
    @type localversion:  C{None} or C{str}
    """

    __slots__ = ["subsublevel", "rclevel", "dirty", "localversion"]

    @classmethod
    def new_from_match_vars(cls, match_vars):

        if match_vars["extraversion_subsublevel"]:
            subsublevel = tuple((
                int(w)
                for w in match_vars["extraversion_subsublevel"].split(".")
            ))
        else:
            subsublevel = None
        # --

        rclevel = None
        if match_vars["extraversion_rclevel"]:
            rclevel = int(match_vars["extraversion_rclevel"])
        # --

        dirty = bool(match_vars["extraversion_dirty"])

        localversion = match_vars["extraversion_localversion"] or None

        return cls(
            subsublevel=subsublevel, rclevel=rclevel,
            dirty=dirty, localversion=localversion
        )
    # --- end of new_from_match_vars (...) ---

    @classmethod
    def new_from_str(cls, extraversion_str):
        match = KernelVersionRegexp.match_extraversion_str(extraversion_str)
        if not match:
            raise ValueError(extraversion_str)

        return cls.new_from_match_vars(match.groupdict())
    # --- end of new_from_str (...) ---

    def __init__(
        self, subsublevel=None, rclevel=None, dirty=False, localversion=None
    ):
        super().__init__()
        self.subsublevel = subsublevel
        self.rclevel = rclevel
        self.dirty = dirty
        self.localversion = localversion
    # ---

    @classmethod
    def get_none_sort_key(cls):
        return ((), 0, 0, "")
    # --- end of get_none_sort_key (...) ---

    def get_sort_key(self):
        return (
            self.subsublevel or (),
            -self.rclevel if self.rclevel is not None else 0,
            1 if self.dirty else 0,
            self.localversion or ""
        )
    # --- end of get_sort_key (...) ---

    def _cmp_none(self):
        return 1 if (self.rclevel is None) else -1

    def _cmp_iter(self, other):
        yield (True, self.subsublevel, other.subsublevel)
        yield (False, self.rclevel, other.rclevel)

    def gen_str(self):
        if self.subsublevel:  # is not None
            yield "."
            yield ".".join(map(str, self.subsublevel))
        # --

        if self.rclevel is not None:
            yield "-rc%d" % self.rclevel
        # --

        if self.dirty:
            yield "+"
        # --

        if self.localversion is not None:
            yield str(self.localversion)
        # --
    # --- end of gen_str (...) ---

# ---


class KernelVersion(_kversion_base.KernelVersionBaseObject):
    """A kernel version.

    @ivar kv:            version string up to the next-to-last int version
                         component if the kernel version is not an "-rc"
                         version, and the full kernel version str otherwise
                         examples:
                           4.7.0-r1 => 4.7.0-r1,
                           3.5.1 => 3.5,
                           2.6.32.32 => 2.6.32
    @type kv:            C{str}  (readonly property)

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

    @ivar subsublevel:   tuple of additional int version components (readonly)
    @type subsublevel:   C{None} or tuple of C{int}
    @ivar rclevel:       the rclevel of the kernel version,
                         or None if it is not a -rc version (readonly)
    @type rclevel:       C{None} or C{int}
    """
    __slots__ = [
        "version", "patchlevel", "sublevel", "extraversion", "name"
    ]

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

    @classmethod
    def decode_version_code(cls, vcode):
        return (
            (vcode >> 16),
            ((vcode >> 8) & 0xff),
            (vcode & 0xff)
        )
    # --- end of decode_version_code (...) ---

    @classmethod
    def encode_version_code(cls, version, patchlevel, sublevel):
        return sum((
            (version or 0) << 16,
            (patchlevel or 0) << 8,
            (sublevel or 0)
        ))

    @classmethod
    def new_from_version_code(cls, vcode, name=None):
        version, patchlevel, sublevel = cls.decode_version_code(vcode)
        return cls(version, patchlevel, sublevel, name=name)
    # --- end of new_from_version_code (...) ---

    @classmethod
    def parse_version_str(cls, version_str):
        vmatch = KernelVersionRegexp.match_version_str(version_str)
        if vmatch is None:
            raise ValueError(version_str)

        vm_vars = vmatch.groupdict()

        _get_int = lambda w: int(w) if w else None
        get_int = lambda k, _mv=vm_vars: _get_int(_mv[k])

        if vm_vars["extraversion_str"]:
            extraversion = KernelExtraVersion.new_from_match_vars(vm_vars)
        else:
            extraversion = None

        return (
            get_int("version"),
            get_int("patchlevel"),
            get_int("sublevel"),
            extraversion
        )
    # ---

    @classmethod
    def new_from_version_str(cls, version_str, name=None):
        vcomp = cls.parse_version_str(version_str)

        return cls(
            version=vcomp[0], patchlevel=vcomp[1], sublevel=vcomp[2],
            extraversion=vcomp[3], name=name
        )
    # --- end of new_from_version_str (...) ---

    @classmethod
    def new_from_str(cls, seq, name=None):
        if not seq or seq[0] == "-":
            raise ValueError(seq)

        else:
            try:
                ival = int(seq, 0)
            except ValueError:
                ival = None

            if ival is None:
                return cls.new_from_version_str(seq, name=name)
            else:
                return cls.new_from_version_code(ival, name=name)
    # --- end of new_from_str (...) ---

    @property
    def subsublevel(self):
        ever = self.extraversion
        return None if ever is None else ever.subsublevel

    @property
    def rclevel(self):
        ever = self.extraversion
        return None if ever is None else ever.rclevel

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

    def get_version_code(self):
        return self.encode_version_code(
            self.version,
            self.patchlevel,
            self.sublevel
        )

    def _cmp_none(self):
        raise TypeError()

    def _cmp_iter(self, other):
        yield (True, self.version, other.version)
        yield (True, self.patchlevel, other.patchlevel)
        yield (True, self.sublevel, other.sublevel)
        yield (None, self.extraversion, other.extraversion)

    def get_sort_key(self):
        negative_none = lambda k: (-1 if k is None else k)

        return (
            negative_none(self.version),
            negative_none(self.patchlevel),
            negative_none(self.sublevel),
            (
                KernelExtraVersion.get_none_sort_key()
                if self.extraversion is None
                else self.extraversion.get_sort_key()
            )
        )
    # --- end of get_sort_key (...) ---

    def is_complete(self):
        """Checks whether the essential parts of the kernel version are set.

        A kernel version is considered complete
        if its version, patchlevel and sublevel are set to a not-None value.

        @return:  "complete or not?" -- True or False
        @rtype:   C{bool}
        """
        return all((
            v is not None for v in (
                self.version, self.patchlevel, self.sublevel
            )
        ))
    # --- end of is_complete (...) ---

    def is_partially_complete(self):
        """Checks whether the kernel version is at least partially complete.

        A kernel version is considered partially complete
        if its version is set to a not-None value and
        its sublevel may only be not-None if its patchlevel is not-None.

        @return:  "partially complete or not?" -- True or False
        @rtype:   C{bool}
        """
        if self.version is None:
            return False
        elif self.sublevel is not None:
            return self.patchlevel is not None
        else:
            return True
    # ---

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
        if isinstance(arg, str):
            self.extraversion = KernelExtraVersion.new_from_str(arg)
        else:
            self.extraversion = arg

    def set_name(self, arg):
        """Sets the name of this kernel version."""
        self.name = arg

    def gen_str(self):
        assert self.is_partially_complete()

        yield "%s" % self.version

        if self.patchlevel is not None:
            yield ".%s" % self.patchlevel

            if self.sublevel is not None:
                yield ".%s" % self.sublevel
        # --

        if self.extraversion is not None:
            yield "%s" % self.extraversion
    # --

    def get_kv_str(self):
        assert self.is_partially_complete()
        if (
            self.extraversion is not None
            and self.extraversion.rclevel is not None
        ):
            # -rc version: full version str
            return str(self)

        elif self.version is None:
            raise ValueError()

        elif self.patchlevel is None:
            return str(self.version)

        else:
            vparts = [self.version, self.patchlevel]

            if self.sublevel is not None:
                vparts.append(self.sublevel)
            # --

            if (
                self.extraversion is not None
                and self.extraversion.subsublevel
            ):
                assert self.sublevel is not None

                # subsublevel is a non-empty tuple if
                #  there are additional version components
                vparts.extend(self.extraversion.subsublevel)
            # --

            if len(vparts) > 2:
                # sublevel or subsublevel,
                #  chop one version component off
                vparts.pop()
            # --

            return ".".join(map(str, vparts))
    # --- end of get_kv_str (...) ---

    kv = property(get_kv_str)

    def iter_version_parts(self):
        for vpart in (
            self.version,
            self.patchlevel,
            self.sublevel
        ):
            if vpart is None:
                return

            yield vpart
        # --

        subsublevel = self.subsublevel
        if subsublevel:
            for vpart in subsublevel:
                yield vpart
    # --- end of iter_version_parts (...) ---

    def get_version_parts(self):
        return list(self.iter_version_parts())
    # --- end of get_version_parts (...) ---

# --- end of KernelVersion ---


if __name__ == "__main__":
    def main():
        import sys
        import itertools

        vobjlist = sorted(
            [KernelVersion.new_from_str(s) for s in sys.argv[1:]],
            key=kver_sort_key
        )

        for u, v in itertools.product(vobjlist, vobjlist):
            print(
                u, "X", v,
                "eq?", (u == v),
                "lt?", (u < v),
                "le?", (u <= v),
                "gt?", (u > v),
                "ge?", (u >= v)
            )
    # --

    main()
# --
