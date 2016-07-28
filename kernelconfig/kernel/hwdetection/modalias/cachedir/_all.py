# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import logging
import os
import re
import shutil
import stat
import tempfile

from .....abc import loggable
from .....util import fs
from .....util import fspath
from .....util import misc
from .....util import objcache
from .....util import osmisc
from .....util import subproc
from .....util import tmpdir

from .... import kversion

from . import exc


__all__ = ["ModaliasCacheBuilder"]


def _create_kernelversion_noerr(
    version_string, *,
    constructor=kversion.KernelVersion.new_from_version_str
):
    try:
        return constructor(version_string)
    except ValueError:
        return None
# ---


class MakeArgs(list):
    # TODO: config sources mk.py would be a potential consumer of this class

    def fmt_var(self, name, value):
        return "{0!s}={1!s}".format(name, value)

    def add(self, name, value):
        self.append(self.fmt_var(name, value))

    def addv(self, iterable):
        for name, value in iterable:
            self.add(name, value)
# ---


_ModaliasCacheEntrySimilaritySortKey = collections.namedtuple(
    "ModaliasCacheEntrySimilaritySortKey",
    "archiness arch kv_numcommon kv_dist_neg kver"
)


class ModaliasCacheEntrySimilaritySortKey(
    _ModaliasCacheEntrySimilaritySortKey
):

    @property
    def kv_dist(self):
        return -(self.kv_dist_neg)


_ModaliasCacheKey = collections.namedtuple(
    "ModaliasCacheKey", "kernelversion arch"
)


_ModaliasCacheEntryInfo = collections.namedtuple(
    "ModaliasCacheEntryInfo", "filepath is_file cache_key"
)


class ModaliasCacheEntryInfo(_ModaliasCacheEntryInfo):

    @property
    def arch(self):
        return self.cache_key.arch

    @property
    def kernelversion(self):
        return self.cache_key.kernelversion

# ---


class ModaliasCacheKey(_ModaliasCacheKey):

    KVER_OBJ_CACHE = objcache.ObjectCache()

    @classmethod
    def decode(cls, key_str):
        key_components = key_str.split("__")

        if key_components:
            arch_key = None
            if len(key_components) > 1:
                arch_key = key_components.pop()

            kernelversion = cls.KVER_OBJ_CACHE.get(
                _create_kernelversion_noerr, key_components.pop()
            )

            # other key components are ignored

            if kernelversion:
                return cls(arch=arch_key, kernelversion=kernelversion)
        # --

        return None
    # --- end of decode (...) ---

    def encode(self):
        forbidden_seq = re.compile(r'(?:__)|(?:/)')

        def strconvert(arg):
            str_val = str(arg)
            if forbidden_seq.search(str_val):
                raise exc.ModaliasCacheError(
                    "invalid cache key element", str_val
                )
            return str_val
        # ---

        return "__".join((
            strconvert(self.kernelversion),
            strconvert(self.arch)
        ))
    # ---

    def __str__(self):
        return self.encode()

# ---


class _ModaliasCacheBase(loggable.AbstractLoggable):

    CACHE_DIR_RELPATH = "modalias/tmp"

    def iter_cache_dir_entries(self, *, cache_search_dirs=None):
        def iter_candidates():
            nonlocal cache_search_dirs

            for fname, filepath, stat_info in (
                cache_search_dirs.iglob_stat("*__*")
            ):
                # files end with ".txz"
                #  -- this can be adjusted to allow other tarballs,
                #     e.g. tarfile.is_tarfile() (which would open the file)

                if stat.S_ISREG(stat_info.st_mode) and fname.endswith(".txz"):
                    fbasename = fname.rpartition(".")[0]
                    yield (True, fbasename, filepath)

                elif stat.S_ISDIR(stat_info.st_mode):
                    yield (False, fname, filepath)
            # --
        # --- end of iter_candidates (...) ---

        if cache_search_dirs is None:
            cache_search_dirs = self.get_cache_search_dirs()

        for is_file, fbasename, filepath in iter_candidates():
            cache_key = ModaliasCacheKey.decode(fbasename)
            if cache_key is not None:
                yield ModaliasCacheEntryInfo(
                    filepath=filepath, is_file=is_file, cache_key=cache_key
                )
    # --- end of iter_cache_dir_entries (...) ---

    def __init__(self, install_info, source_info, **logger_kwargs):
        super().__init__(**logger_kwargs)
        self.install_info = install_info
        self.source_info = source_info
        self._cache_key_str = None
    # --- end of __init__ (...) ---

    def zap(self):
        self._cache_key_str = None

    def get_cache_file_path(self):
        return self.get_cache_dir_path("%s.txz" % self.get_cache_key_str())

    def get_cache_dirs(self, relpath=None):
        return self.install_info.get_cache_dirs(
            fspath.join_relpath(self.CACHE_DIR_RELPATH, relpath)
        )

    def get_cache_dir_path(self, relpath=None):
        return self.get_cache_dirs(relpath).get_path()

    def get_cache_search_dirs(self, relpath=None, check_exist=False):
        return self.install_info.get_cache_search_dirs(
            fspath.join_relpath(self.CACHE_DIR_RELPATH, relpath),
            check_exist=check_exist
        )

    def get_arch_keys(self):
        return misc.iter_dedup(
            filter(
                # skip unset arch attrs,
                # and also "usermode" archs
                lambda w: (w and w != "um"),
                (
                    self.source_info.arch,
                    self.source_info.subarch,
                    self.source_info.karch
                )
            )
        )
    # ---

    def get_cache_key_components(self):
        """
        Returns the 'ideal' cache key for the modalias info source as list.

        @return:  cache key components
        @rtype:   C{list} of C{object}
        """
        def get_arch_key():
            for arch_key in self.get_arch_keys():
                return arch_key
            raise exc.ModaliasCacheError("no arch cache key")
        # ---

        # the cache key consists of
        # * the kernel version
        # * the target arch, see get_arch_key() above
        return ModaliasCacheKey(
            kernelversion=self.source_info.kernelversion,
            arch=get_arch_key()
        )
    # --- end of get_cache_key_components (...) ---

    def _get_cache_key_str(self):
        """Returns the 'ideal' cache key for the modalias info source.
        This is mostly useful for storing new info sources.

        @return:  cache key (can be interpreted as relative fs path)
        @rtype:   C{str}
        """
        return self.get_cache_key_components().encode()
    # --- end of _get_cache_key_str (...) ---

    def get_cache_key_str(self):
        """See _get_cache_key_str(). This method adds result caching."""
        cache_key_str = self._cache_key_str
        if cache_key_str is None:
            cache_key_str = self._get_cache_key_str()
            self._cache_key_str = cache_key_str
        return cache_key_str
    # --- end of get_cache_key_str (...) ---

# --- end of _ModaliasCacheBase ---


class ModaliasCache(_ModaliasCacheBase):
    """
    @cvar KVER_DIST_WARN_THRESHOLD:    when picking a cache entry,
                                       warn if its kv distance is equal
                                       or greater than this value
                                       Disabled if set to None,
                                       has no effect if >= unsafe threshold,
    @type KVER_DIST_WARN_THRESHOLD:    C{int} or C{None}

    @cvar KVER_DIST_UNSAFE_THRESHOLD:  when picking a cache entry,
                                       warn if its kv distance is equal
                                       or greater than this value,
                                       and also consider the entry as unsafe.
                                       Disabled if set to None.
    @type KVER_DIST_UNSAFE_THRESHOLD:  C{int} or C{None}
    """

    KVER_DIST_WARN_THRESHOLD = 0x100      # patchlevel +- 1
    KVER_DIST_UNSAFE_THRESHOLD = 0x800    # patchlevel +- 8

    def _locate_cache_entry_iter_candidates(self):
        """
        Iterates over all cache entries,
        determines which entries are usable,
        and yields them alongside with a key
        for sorting by similarity to self.source_info.

        @return:  2-tuples (sort key, cache entry)
        @rtype:   2-tuples (C{tuple}, L{ModaliasCacheEntryInfo})
        """

        def common_list_prefix(*iterables):
            def iter_common_list_prefix(iterables):
                for a, b in zip(*iterables):
                    if a == b:
                        yield a
                    else:
                        break
            # ---

            return list(iter_common_list_prefix(iterables))
        # ---

        def get_archiness(arch_key):
            nonlocal source_info

            # rate the "archiness", arch similarity
            # a higher score indicates a higher degree of similarity,
            # and a score < 0 means "not similar"
            #
            # * arch_key matches karch           (1 points)
            # * arch_key matches subarch         (2 points)
            # * arch_key matches arch            (3 points)
            # * subarch(arch_key) matches karch  (0 points)
            # * otherwise -1 point
            #
            #  Since source_info.arch could contain the target kernel arch,
            #  comparing starts with the 'lowest' direct match (subarch).
            #
            if arch_key == source_info.karch:
                return 1

            elif arch_key == source_info.subarch:
                return 2

            elif arch_key == source_info.arch:
                return 3

            elif (
                source_info.calculate_subarch(arch_key) == source_info.subarch
            ):
                return 0

            else:
                return -1
        # ---

        source_info = self.source_info
        kver = source_info.kernelversion
        kver_parts = kver.get_version_parts()
        kver_vcode = kver.get_version_code()

        for cache_entry in self.iter_cache_dir_entries():
            cache_kver = cache_entry.kernelversion
            cache_arch = cache_entry.arch

            # major version must match, don't mix 3.x <> 4.x <> 5.x
            #
            # also, if the version is < 3.0, then the first three version
            # components must be equal (e.g. 2.6.32)
            #
            #  rc versions are accepted - that's up to sorting
            #

            if kver.version != cache_kver.version:
                # filtered out
                pass

            elif (
                cache_kver.version < 3
                and (
                    cache_kver.patchlevel != kver.patchlevel
                    or cache_kver.sublevel != kver.sublevel
                )
            ):
                # filtered out
                pass

            else:
                # yield the entry and its sort key

                # the "archiness", see above
                archiness = get_archiness(cache_arch)

                # continue even if there is no "archiness"

                # how many version component parts are equal?
                #  (starting from kver.version and
                #  stopping at first mismatch)
                #
                #    TODO: maybe (len(kver_parts) - kv_numcommon)
                #          would be more interesting?
                kv_numcommon = len(
                    common_list_prefix(
                        kver_parts, cache_kver.get_version_parts()
                    )
                )

                # the version distance
                kv_dist = abs(kver_vcode - cache_kver.get_version_code())

                # COULDFIX:
                #       kv_dist does not include -rc level distance,
                #       causing get_locate_cache_entries() to prefer
                #       non-"-rc" versions over "-rc" versions.
                #       This shouldn't be an issue, but in case it is,
                #       add a "rc dist" element to the sort key.

                # now build the key for sorting
                #  * in case of equal kv_dist (4.3 < _4.4_ < 4.5),
                #    compare the version
                #  * lower kv_dist is better, so multiple w/ -1
                #  * to avoid randomness when picking entries with
                #    no archiness, sort by arch (after archiness)

                sort_key = ModaliasCacheEntrySimilaritySortKey(
                    archiness, cache_arch, kv_numcommon, -kv_dist, cache_kver
                )

                yield (sort_key, cache_entry)
            # -- end if
        # -- end for
    # --- end of _locate_cache_entry_iter_candidates (...) ---

    def get_locate_cache_entries(self):
        return sorted(
            self._locate_cache_entry_iter_candidates(),
            key=lambda item: item[1]
        )

    def locate_cache_entry(self, unsafe=False):
        log_unsafe = self.logger.warning if unsafe else self.logger.debug

        self.logger.debug("Locating suitable cached modalias files")
        candidates = self.get_locate_cache_entries()

        if not candidates:
            self.logger.debug("No modalias cache files found")
            return None

        # pick the best entry -- the candidates are already sorted
        sort_key, cache_entry = candidates[-1]

        if sort_key.archiness < 0:
            # then no arch similarity
            # and also no other candidates with better similarity
            # (guaranteed by sorting)
            #
            log_unsafe(
                (
                    "No modalias cache entry found for target arch %s,"
                    "but there is one for %s"
                ),
                ", ".join(self.get_arch_keys()),
                sort_key.arch
            )

            if unsafe:
                log_unsafe(
                    "Picking this entry since 'unsafe' mode is enabled"
                )
            else:
                log_unsafe("Not picking this entry due to 'safe' mode")
                return None
        # --

        # if the kver distance is too high, warn about
        kv_diff_is_unsafe = (
            self.KVER_DIST_UNSAFE_THRESHOLD is not None
            and sort_key.kv_dist >= self.KVER_DIST_UNSAFE_THRESHOLD
        )
        kv_diff_want_warn = kv_diff_is_unsafe or (
            self.KVER_DIST_WARN_THRESHOLD is not None
            and sort_key.kv_dist >= self.KVER_DIST_WARN_THRESHOLD
        )

        if kv_diff_want_warn:
            self.logger.warning(
                (
                    "kernel version of the cached modalias info "
                    "does not match the kernel sources version exactly, "
                    "this could result in incorrect config options"
                    " (%s <> %s)"
                ),
                self.source_info.kernelversion, sort_key.kver
            )
        # --

        if kv_diff_is_unsafe:
            log_unsafe(
                (
                    "modalias cache entry is unsafe, "
                    "kernelversion differs too much"
                )
            )
            if not unsafe:
                log_unsafe("Not picking this entry due to 'safe' mode")
                return None
        # --

        self.logger.info(
            "Picking modalias info for kver=%s, arch=%s from cache",
            sort_key.kver, sort_key.arch
        )
        return cache_entry.filepath
    # --- end of locate_cache_entry (...) ---

# --- end of ModaliasCache ---


class ModaliasCacheBuilder(_ModaliasCacheBase):
    """
    This is the "Python side" of modalias info source creation.
    Basically, it wraps the modalias.mk Makefile,
    and adds tmpdir creation and storing the created files
    where kernelconfig can find them in subsequent runs.

    Two convenient creation modes are available via this class,

    * run_create()  --  creates a new modalias info source
                        and stores it in the cache dir

    * run_update()  --  checks whether a modalias info source
                        already exists and skips creation in that case.
                        Otherwise, identical to run_create().
                        *** NOT IMPLEMENTED ***

    The individual make targets of modalias.mk
    can also be run after calling prepare().

    Modalias info source creation depends on building all kernel modules.
    This requires some disk space (on x86_64, about ~1800MiB),
    which is taken into account when searching for a suitable tmpdir
    and controlled by the following two class-wide vars.
    Note that when a build directory is specified manually,
    these vars act just as recommendations.

    @cvar BUILD_ROOT_DIR_MIN_SIZE:  minimum size of free space a build root
                                    directory should have (in MiB)
    @type BUILD_ROOT_DIR_MIN_SIZE:  C{int}

    @cvar BUILD_ROOT_DIR_LOOKAHEAD_SIZE:  when auto-detecting the default
                                          build root directory,
                                          this size acts as upper bound
                                          when determining whether to peek
                                          at the next directory candidate
    @type BUILD_ROOT_DIR_LOOKAHEAD_SIZE:  C{int}

    When testing, "modalias.mk" might be edited while running a build,
    so this class offers copying modalias.mk to the build directory
    and running it from there:

    @cvar COPY_BUILD_SCRIPTS:  whether to copy build scripts (modalias.mk)
                               to the build directory and run them from there,
                               so that modifications to the build scripts
                               do not affect the already running build process.
                               For testing, set this True, and False otherwise.
    @type COPY_BUILD_SCRIPTS:  C{bool}

    Another class-wide var, CONF_TARGET, is only relevant for testing.
    It sets the base config for modalias info creation.
    Normally this should be None (modalias.mk then uses allmodconfig),
    for testing purposes it may be set to "defconfig".

    @cvar CONF_TARGET:         config target override
    @type CONF_TARGET:         C{None} or C{str}

    The usual install_info / source_info variables are used by instances
    of this class for accessing files and getting the kernel version / arch.

    @ivar install_info:
    @ivar source_info:

    Most of the instance-wide variables are only relevant when actually
    building and are set in prepare().
    Most of them are private and should not be accessed directly!

    @ivar outdir:               path to
    @type outdir:               C{str}
    @ivar outfile:              path to
    @type outfile:              C{str}

    @ivar _numjobs:             number of allowed make jobs
                                If set to a not-None value,
                                "-j <N>" is passed to make commands.
    @type _numjobs:             C{int} or C{None}

    @ivar _build_root_dir:      directory path under which the the temporary
                                build directory is created
                                This can be set manually with the
                                build_root_dir keyword passed to __init__,
                                otherwise a directory is set automatically
                                (either TMPDIR:=/tmp or /var/tmp).
    @type _build_root_dir:      C{str} (initially C{None})

    @ivar _build_tmpdir:        the temporary build directory
    @type _build_tmpdir:        L{Tmpdir}

    @ivar _mkscript:            path to modalias.mk,
                                which point to a file in a data dir,
                                or to a temporary file,
                                depending on COPY_BUILD_SCRIPTS
    @type _mkscript:            C{str} (initially C{None})
    @ivar _mkscript_base_cmdv:  make command for modalias.mk,
                                without args such as KSRC, T, D
    @type _mkscript_base_cmdv:  C{list} of C{str} (initially C{None})
    @ivar _mkscript_argv:       modalias.mk make args
    @type _mkscript_argv:       C{list} of C{str} (initially C{None})
    """

    COPY_BUILD_SCRIPTS = True   # FIXME: testing=>True, others=>False

    CONF_TARGET = "defconfig"   # FIXME: testing

    BUILD_ROOT_DIR_MIN_SIZE = 2000
    BUILD_ROOT_DIR_LOOKAHEAD_SIZE = BUILD_ROOT_DIR_MIN_SIZE + 200

    def run_create(self):
        if not self.prepare():
            return False

        if not self.make_compress_modalias():
            return False

        if not self.make_install_tar():
            return False

        if not self.install_outfile_to_cache():
            return False

        return True
    # ---

    def run_update(self):
        cache_file = self.get_cache_file_path()

        try:
            stat_info = os.stat(cache_file)
        except OSError:
            stat_info = None

        if stat_info is None:
            self.logger.info("Creating new modalias info source")
            return self.run_create()

        elif stat.S_ISREG(stat_info.st_mode):
            self.logger.info("modalias cache file exists, nothing to do.")
            return True

        else:
            self.logger.error(
                "Cache file %r exists but is not a file!", cache_file
            )
            return False
    # ---

    def install_outfile_to_cache(self):
        outfile = self._get_outfile()
        cache_file = self.get_cache_file_path()

        if fs.prepare_output_file(cache_file, move=True):
            self.logger.debug("Moved old modalias info file")

        self.logger.info(
            "Copying modalias info file %s to cache dir",
            os.path.basename(cache_file)
        )
        shutil.copyfile(outfile, cache_file)

        return True
    # --- end of install_outfile_to_cache (...) ---

    def _get_outfile(self):
        outfile = self.outfile
        if not outfile:
            raise exc.ModaliasCacheBuildInstallError(
                "outfile is not set - has prepare() been called?"
            )

        outfile_stat_info = os.lstat(outfile)  # raises OSError
        if not stat.S_ISREG(outfile_stat_info.st_mode):
            raise exc.ModaliasCacheBuildInstallError(
                "outfile is not a regular file", outfile
            )
        # --

        return outfile
    # --- end of _get_outfile (...) ---

    def prepare(self):
        log_debug = self.logger.debug
        log_info = self.logger.info

        # locate the modalias makefile
        mkscript = self._mkscript
        did_set_mkscript = False
        if not mkscript:
            log_debug("Trying to locate modalias make script")
            mkscript = self.install_info.get_script_file("modalias.mk")
            if not mkscript:
                raise exc.ModaliasCacheBuildPrepareError(
                    "could not locate modalias.mk script"
                )

            self._mkscript = mkscript
            did_set_mkscript = True
        # --
        log_debug("modalias make script: %s", mkscript)

        # find a suitable directory for building
        build_root_dir = self._build_root_dir
        if not build_root_dir:
            build_root_dir = self.get_default_build_root_dir()
            if not build_root_dir:
                raise exc.ModaliasCacheBuildPrepareError(
                    "could not find a suitable build root directory"
                )

            self._build_root_dir = build_root_dir
        # --
        log_debug("build root directory: %s", build_root_dir)

        # create the build dir
        build_tmpdir = self._build_tmpdir
        if not build_tmpdir:
            log_info(
                "Creating temporary build directory in %s", build_root_dir
            )
            build_tmpdir = tmpdir.Tmpdir(
                dir=build_root_dir, suffix=".kernelconfig"
            )
            self._build_tmpdir = build_tmpdir
        # --
        log_debug("build directory: %s", build_tmpdir.get_path())

        self.outdir = build_tmpdir.get_filepath("out")
        # the tarball created by modalias.mk -> install-tar
        self.outfile = os.path.join(self.outdir, "data.txz")
        log_debug("build outfile: %s", self.outfile)
        if fs.rmfile(self.outfile):
            log_debug("removed previous outfile: %s", self.outfile)
        # --

        # optionally copy the modalias makefile to build dir
        if self.COPY_BUILD_SCRIPTS:
            mkscript_orig = mkscript
            mkscript_tmp = build_tmpdir.get_filepath("modalias.mk")

            if did_set_mkscript or not os.access(mkscript_tmp, os.F_OK):
                log_debug("Copying modalias make script to tmpdir")
                shutil.copyfile(mkscript_orig, mkscript_tmp)
                mkscript = mkscript_tmp
                self._mkscript = mkscript_tmp
            else:
                log_debug("Not copying modalias make script to tmpdir: exists")
            # --

            log_debug("modalias make script (now in build dir): %s", mkscript)
        else:
            log_debug("Not copying modalias make script to tmpdir: disabled")
        # --

        # build the argument list that is passed to the modalias makefile cmd
        mkscript_argv = MakeArgs()

        #  source-info related vars (ARCH=...)
        #   not using iter_out_of_tree_build_make_vars() here,
        #   modalias.mk manages that itself
        mkscript_argv.addv(self.source_info.iter_make_vars())

        # * T: the tmpdir
        mkscript_argv.add("T", build_tmpdir.get_filepath("build"))

        # * D: the modalias install dir
        #    note that copying the modalias tarball is not really necessary,
        #    but otherwise more modalias.mk internals would have to be
        #    exposed here
        mkscript_argv.add("D", self.outdir)

        # * KSRC: kernel srctree
        mkscript_argv.add("KSRC", self.source_info.srctree)

        # * DEPMOD: adhere to environment var, but locate it otherwise
        depmod_prog = os.environ.get("DEPMOD") or osmisc.which_sbin("depmod")
        if not depmod_prog:
            raise exc.ModaliasCacheBuildPrepareError("Could not locate depmod")
        # --

        mkscript_argv.add("DEPMOD", depmod_prog)
        log_debug("depmod: %s", depmod_prog)

        if self.CONF_TARGET:
            mkscript_argv.add("KERNELCONFIG_CONFTARGET", self.CONF_TARGET)
            log_debug("config target: %s", self.CONF_TARGET)
        else:
            log_debug("config target: <default>")

        self._mkscript_argv = mkscript_argv
        log_debug("modalias mk args: %r", mkscript_argv)

        # the make command
        mkscript_base_cmdv = [
            "make",
            "-f", self._mkscript,
            "-C", build_tmpdir.get_path()
        ]

        numjobs = self._numjobs
        if numjobs:
            mkscript_base_cmdv.extend(("-j", str(numjobs)))
        # --

        self._mkscript_base_cmdv = mkscript_base_cmdv
        # no-log _mkscript_base_cmdv

        return True
    # --- end of prepare (...) ---

    def make_config(self, **kwargs):
        return self._make("config", **kwargs)

    def make_modules(self, **kwargs):
        return self._make("modules", **kwargs)

    def make_modules_install(self, **kwargs):
        return self._make("modules_install", **kwargs)

    def make_compress_modalias(self, **kwargs):
        return self._make("compress-modalias", **kwargs)

    def make_install_tar(self, **kwargs):
        return self._make("install-tar", **kwargs)

    def _get_make_cmdv(self, target, args_post=None, args_pre=None):
        cmdv = []
        cmdv.extend(self._mkscript_base_cmdv)

        if args_pre:
            cmdv.extend(args_pre)

        cmdv.extend(self._mkscript_argv)

        if args_post:
            cmdv.extend(args_post)

        if target:
            cmdv.append(target)

        return cmdv
    # --- end of _get_make_cmdv (...) ---

    def _create_subproc(self, cmdv):
        return subproc.SubProc(
            cmdv,
            tmpdir=self._build_tmpdir.dodir("tmp"),
            logger=self.logger
        )

    def _make(self, target, args=None, timeout=None, return_success=True):
        if not target:
            raise ValueError("no make target specified!")

        cmdv = self._get_make_cmdv(target=target, args_post=args)

        self.logger.info("Running 'make %s'", target)
        with self._create_subproc(cmdv) as proc:
            ret = proc.join(timeout=timeout, return_success=return_success)

        return ret
    # --- end of _make (...) ---

    def iter_pick_dir_candidate(self, candidates, min_size, lookahead_size):
        # candidates: iterable of 2-tuple (free_size, dirpath)
        for item in filter(lambda item: (item[0] >= min_size), candidates):
            yield item
            if item[0] >= lookahead_size:
                break
    # --- end of iter_pick_dir_candidate (...) ---

    def __init__(
        self, install_info, source_info,
        build_root_dir=None, numjobs=None, **logger_kwargs
    ):
        super().__init__(install_info, source_info, **logger_kwargs)

        self.outdir = None
        self.outfile = None

        self._numjobs = None
        self._build_root_dir = None
        self._build_tmpdir = None
        self._mkscript = None
        self._mkscript_base_cmdv = None
        self._mkscript_argv = None

        if numjobs:
            self.set_numjobs(numjobs)

        if build_root_dir:
            self.set_build_root_dir(build_root_dir)
    # --- end of __init__ (...) ---

    def set_numjobs(self, numjobs):
        self._numjobs = int(numjobs)
    # --- end of set_numjobs (...) ---

    def set_build_root_dir(self, build_root_dir):
        self._build_root_dir = build_root_dir
    # --- end of set_build_root_dir (...) ---

    def get_default_build_root_dir(self):
        def get_free_space_m_nofail(dirpath):
            try:
                return osmisc.get_free_space_m(dirpath)
            except OSError:
                return -1
        # ---

        want_debuglog = self.logger.isEnabledFor(logging.DEBUG)

        self.logger.debug(
            "Trying to find a suitable dir for building modalias files"
        )

        # build_root_candidates:
        #   list of directory paths which could be used as build root dir
        #   if
        #   (a) the dir exists
        #   (b) and enugh space is available
        #
        #   "upcoming" list transformations:
        #   * empty values are filtered out, too
        #   * convert to abspath
        #   * duplicates in this list are filtered out below
        #
        build_root_dir_candidates = [
            tempfile.gettempdir(),
            "/var/tmp",
        ]

        # transform as described above,
        # filter out non-existing dirs,
        # preserve order of dirpaths
        #
        shortlisted_build_root_dir_candidates = [
            (get_free_space_m_nofail(p), p)
            for p in filter(
                os.path.isdir,
                misc.iter_dedup(
                    map(
                        os.path.abspath,
                        filter(None, build_root_dir_candidates)
                    )
                )
            )
        ]

        if not shortlisted_build_root_dir_candidates:
            self.logger.warning("No build dir candidates available!")
            return None

        elif want_debuglog:
            self.logger.debug(
                "Build dir candidates: %s",
                ", ".join((
                    "{p!s} (free: {s:d}M)".format(p=item[1], s=item[0])
                    for item in shortlisted_build_root_dir_candidates
                ))
            )
        # --

        build_root_dir_item = None
        # pick the last item out of iter_pick_dir_candidate(),
        #  there will only be more than one if lookahead_size is effective
        for item in self.iter_pick_dir_candidate(
            shortlisted_build_root_dir_candidates,
            self.BUILD_ROOT_DIR_MIN_SIZE,
            self.BUILD_ROOT_DIR_LOOKAHEAD_SIZE
        ):
            build_root_dir_item = item
        # --

        if not build_root_dir_item:
            self.logger.warning("No build dir with enough free space found!")
            return None

        self.logger.debug(
            "Using build directory %s (free: %dM)",
            build_root_dir_item[1], build_root_dir_item[0]
        )

        return build_root_dir_item[1]
    # --- end of get_default_build_root_dir (...) ---

# --- end of ModaliasCacheBuilder ---
