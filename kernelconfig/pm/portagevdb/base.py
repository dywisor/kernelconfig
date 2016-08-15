# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import portage
import re


from ...abc import loggable
from . import pkginfo
from . import util


__all__ = ["PortageInterface"]


class PortageInterface(loggable.AbstractLoggable):
    """
    Interface for querying information relevant
    for CONFIG_CHECK-based pm integration via the portage API.

    @ivar settings:    portage config
    @ivar port_db:     portage db
    @ivar vartree:     portage vartree
    @ivar vdb:         portage vdb
    """

    __hash__ = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # There is no point in lazy-loading these portage objects.
        # At the time an object this class (PortageInterface) is created,
        # it should have already been decided to do some portage queries.
        #

        # pylint: disable=E1101
        self.settings = portage.settings
        self.port_db = portage.db[portage.root]
        self.vartree = self.port_db["vartree"]
        self.vdb = self.vartree.dbapi
    # --- end of __init__ (...) ---

    def zipmap_get_var(self, cpv_iterable, varname):
        """
        Generator that retrieves a single var
        from vdb//environment.bz2 for a sequence of packages
        and returns (cpv, value) pairs.

        @param cpv_iterable:  package cpv list (or iterable)
        @type  cpv_iterable:  iterable of cpv
        @param varname:       name of the variable
        @type  varname:       C{str}

        @return:  2-tuples (cpv, var_value)
        @rtype:   2-tuples (cpv, C{str})
        """
        vdb = self.vdb
        wants = [varname]

        for cpv in cpv_iterable:
            yield (cpv, vdb.aux_get(cpv, wants)[0])
    # --- end of zipmap_get_var (...) ---

    def get_package_info(self, cpv):
        """
        Creates a package info object for the given cpv,
        which contains additional information from vdb
        for re-evaluating CONFIG_CHECK.

        @param cpv:  package cpv

        @return:  package info object
        @rtype:   L{PackageInfo}
        """
        vdb = self.vdb
        vartree = self.vartree

        (repo_name, ) = vdb.aux_get(cpv, ["repository"])

        return pkginfo.PackageInfo(
            cpv=cpv,
            repo_name=repo_name,
            ebuild_file=vartree.getebuildpath(cpv)
        )
    # --- end of get_package_info (...) ---

    def get_repo_config(self, repo_name):
        """
        @raises KeyError:  if repo not found

        @param repo_name:  name of the repository, e.g. "gentoo"
        @type  repo_name:  C{str}

        @return:  repo config object
        @rtype:   (portage.repository.config.RepoConfig)
        """
        return self.settings.repositories[repo_name]
    # --- end of get_repo_config (...) ---

    def find_all_cpv_inheriting_expr(self, eclass_name_expr):
        """
        Generator that queries portage's vdb for packages inheriting
        the given eclass(es), given as regexp str.

        @return:  cpv
        @rtype:   genexpr of cpv
        """
        if isinstance(eclass_name_expr, str):
            re_inherited_filter = re.compile(eclass_name_expr)
        else:
            re_inherited_filter = eclass_name_expr
        # --

        vdb = self.vdb
        for cpv in vdb.cpv_all():
            inherited = vdb.aux_get(cpv, ["INHERITED"])[0]

            if re_inherited_filter.search(inherited):
                yield cpv
            # --
        # -- end for cpv
    # --- end of find_all_cpv_inheriting_expr (...) ---

    def find_all_cpv_inheriting(self, eclass_name):
        """
        Generator that queries portage's vdb for packages inheriting
        the given eclass, given by its name.

        @return:  cpv
        @rtype:   genexpr of cpv
        """
        # match <eclass_name>, but not e.g. <eclass_name>-r2
        return self.find_all_cpv_inheriting_expr(
            r'(?:^|\s)(?:{})(?:$|\s)'.format(re.escape(eclass_name))
        )
    # --- end of find_all_cpv_inheriting (...) ---

    def find_all_cpv_inheriting_linux_info(self):
        """
        Generator that queries portage's vdb for packages inheriting
        the "linux-info" eclass.

        @return:  cpv
        @rtype:   genexpr of cpv
        """
        return self.find_all_cpv_inheriting("linux-info")
    # --- end of find_all_cpv_inheriting_linux_info (...) ---

    def parse_config_check(self, config_check_str):
        return util.parse_config_check(config_check_str, logger=self.logger)
    # --- end of parse_config_check (...) ---

# --- end of PortageInterface ---
