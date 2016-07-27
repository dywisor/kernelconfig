# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os.path

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

    def get_path(self):
        return self.path

    def is_ready(self):
        path = self.get_path()
        return path and os.path.isdir(path)

    def _create_from_tarfile(self, tarfile):
        # TODO: use tarfile
        assert self._tmpdir is None
        self._tmpdir = tmpdir.Tmpdir(suffix=".kernelconfig")
        tmp_path = self._tmpdir.get_path()

        self.logger.debug(
            "Unpacking modules/modalias tar file %s to temporary directory",
            tarfile
        )
        with subproc.SubProc(
            ["tar", "xa", "-C", tmp_path, "-f", os.path.abspath(tarfile)],
            tmpdir=tmp_path, logger=self.logger
        ) as proc:
            if not proc.join(return_success=True):
                raise ModulesDirCreationError("failed to unpack tar archive")

        self.path = tmp_path
    # ---

    def create(self):
        source = self.source

        if os.path.isfile(source):
            # then assume tar file
            self.logger.debug("%s is -probably- a tar file source", source)
            self._create_from_tarfile(source)

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
                    self._create_from_tarfile(fpath)

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
