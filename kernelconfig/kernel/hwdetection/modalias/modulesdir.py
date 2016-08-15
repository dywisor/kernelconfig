# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os.path
import re
import tarfile


from ....abc import loggable
from ....util import fs
from ....util import subproc
from ....util import tmpdir


__all__ = ["NullModulesDir", "ModulesDir"]


def _get_first_file(
    dirpath, candidate_names, *, f_check=os.path.isfile,
    _osp_join=os.path.join
):
    for cand_name in candidate_names:
        cand_path = _osp_join(dirpath, cand_name)
        if f_check(cand_path):
            return (cand_name, cand_path)

    return (None, None)
# ---


class ModulesDirCreationError(RuntimeError):
    pass


class AbstractModulesDir(loggable.AbstractLoggable, fs.AbstractFsView):
    __slots__ = []

    # files that get opened when running kmod.Kmod().lookup(),
    # gathered from strace output:
    KMOD_ESSENTIAL_FILES = frozenset({
        "modules.softdep",
        "modules.dep.bin",
        "modules.alias.bin",
        "modules.symbols.bin",
        "modules.builtin.bin"
    })

    def check_dirpath_available(self, dirpath):
        return dirpath and all((
            os.path.isfile(os.path.join(dirpath, candidate))
            for candidate in self.KMOD_ESSENTIAL_FILES
        ))
    # --- end of check_dirpath_available (...) ---

    def is_available(self):
        return self.check_dirpath_available(self.get_path())
    # --- end of is_available (...) ---

    @abc.abstractmethod
    def is_ready(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def create(self):
        raise NotImplementedError()

    def prepare(self):
        if not self.is_ready():
            self.create()
        return self.is_available()
    # --- end of prepare (...) ---

# --- end of AbstractModulesDir ---


class NullModulesDir(AbstractModulesDir):
    __slots__ = []

    def __repr__(self):
        return "{cls.__name__s}()".format(cls=self.__class__)

    def __str__(self):
        return str(None)

    def get_path(self):
        raise TypeError()

    def is_available(self):
        return False

    def is_ready(self):
        return True

    def create(self):
        pass

# --- end of NullModulesDir ---


class ModulesDir(AbstractModulesDir):
    __slots__ = ["source", "path", "_tmpdir"]

    def __init__(self, source, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.path = None
        self._tmpdir = None

    def __repr__(self):
        return "{cls.__name__!s}({arg!r})".format(
            arg=(self.path or self.source), cls=self.__class__
        )

    def __str__(self):
        return str(self.source or self.path or "")

    def get_path(self):
        return self.path

    def is_ready(self):
        path = self.get_path()
        return path and os.path.isdir(path)

    def _check_tarfile(self, filepath, tarfile_fh):
        """
        @return:  list of members that may be unpacked, possibly empty
        @rtype:   C{list}
        """
        # bad path: use w/ re.search()
        #  tar members whose name is accepted by this regexp
        #  should not be unpacked.
        #
        #  This includes absolute paths and paths containing os.path.pardir.
        #
        re_bad_path = re.compile(
            r'(?:^/|(?:^|/){pardir}(?:$|/))'.format(
                pardir=re.escape(os.path.pardir)
            )
        )

        def check_member_allowed(member):
            # (1) must be a regular file, dir or hard-/symlink
            # (2) must have a relative path without parent dir refs ("..")
            # (3) if it is a link, the link dst must also follow rule (2)

            if re_bad_path.search(member.name):
                self.logger.warning(
                    "Ignoring tar member due to bad name: %s", member.name
                )
                return False
            # --

            if member.issym() or member.islnk():
                if not member.linkname or re_bad_path.search(member.linkname):
                    self.logger.warning(
                        "Ignoring link tar member to bad dst: %s (-> %s)",
                        member.name, member.linkname
                    )
                    return False
                # --

            elif member.isfile():
                pass

            elif member.isdir():
                pass

            else:
                self.logger.warning(
                    "Ignoring tar member due to bad type: %s", member.name
                )
                return False
            # --

            self.logger.debug("tar member ok: %s", member.name)
            return True
        # ---

        return [m for m in tarfile_fh.getmembers() if check_member_allowed(m)]
    # ---

    def _create_from_tarball(self, filepath):
        assert self._tmpdir is None
        unpack_tmpdir = tmpdir.Tmpdir(suffix=".kernelconfig")
        tmp_path = unpack_tmpdir.get_path()

        self.logger.debug(
            "Unpacking modules/modalias tar file %s to temporary directory",
            filepath
        )

        tarfile_fh = None
        try:
            # same as tarfile.is_tarfile(), but also keep opened file open
            try:
                tarfile_fh = tarfile.open(filepath, "r")
            except tarfile.TarError:
                tarfile_fh = None  # nop
            # --

            if tarfile_fh is not None:
                self.logger.debug("Using 'tarfile' module for unpacking")
                #
                tar_members = self._check_tarfile(filepath, tarfile_fh)
                if not tar_members:
                    # then no members, or only 'malicious' members
                    raise ModulesDirCreationError("tarfile has no members")
                # --

                # COULDFIX: reduce tar_members to what the modalias lookup
                #           class needs (i.e. kmod)
                tarfile_fh.extractall(tmp_path, members=tar_members)

            else:
                self.logger.debug("Trying 'tar' prog for unpacking")
                with subproc.SubProc(
                    [
                        "tar", "xa",
                        "-C", tmp_path,
                        "-f", os.path.abspath(filepath)
                    ],
                    tmpdir=tmp_path, logger=self.logger
                ) as proc:
                    if not proc.join(return_success=True):
                        raise ModulesDirCreationError(
                            "failed to unpack tar archive w/ tar"
                        )
            # -- end if tarfile_fh

            # unlikely, but reassure that self._tmpdir has not been set
            assert self._tmpdir is None
            self._tmpdir = unpack_tmpdir
            self.path = tmp_path

        finally:
            if tarfile_fh is not None:
                tarfile_fh.close()
        # -- end with autoclose tarfile
    # --- end of _create_from_tarball (...) ---

    def create(self):
        source = self.source

        if os.path.isfile(source):
            # then assume tar file
            self.logger.debug("%s is -probably- a tar file source", source)
            self._create_from_tarball(source)

        elif os.path.isdir(source):
            # then probe,
            #  could contain a data.txz tar file or could be just a dir

            # is_available() gets checked twice this way
            if self.check_dirpath_available(source):
                self.logger.debug("%s is a directory source", source)
                self.path = source

            else:
                fname, fpath = _get_first_file(source, ["data.txz"])
                if fpath:
                    # tarfile found
                    self.logger.debug("%s is a tar file source", source)
                    self._create_from_tarball(fpath)

                else:
                    raise ModulesDirCreationError(
                        "{} is not a valid modalias source".format(source)
                    )

        else:
            raise ModulesDirCreationError(
                "{} is not a valid modalias source".format(source)
            )
    # --- end of create (...) ---

# --- end of ModulesDir ---
