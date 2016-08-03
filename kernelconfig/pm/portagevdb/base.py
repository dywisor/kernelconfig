# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import portage
import re


from ...abc import loggable
from . import pkginfo


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

    # lax expr
    #  FIXME: does not really belong to this class (also parse_config_check)
    RE_CONFIG_CECK_ITEM = re.compile(
        r'^(?P<prefix>[\@\!\~]+)?(?P<config_option>[a-zA-Z0-9\_]+)$'
    )

    __hash__ = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # There is no point in lazy-loading these portage objects.
        # At the time an object this class (PortageInterface) is created,
        # it should have already been decided to do some portage queries.
        #
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
        """
        @return:  dict of config option name X want config option enabled
        @rtype:   dict :: C{str} => C{bool}
        """
        #  FIXME: does not really belong to this class

        def parse_inner(config_check_str):
            match_config_check_word = self.RE_CONFIG_CECK_ITEM.match

            for word in config_check_str.split():
                match = match_config_check_word(word)
                if not match:
                    self.logger.warning(
                        "Could not parse CONFIG_CHECK item %r", word
                    )

                else:
                    prefix = match.group("prefix")

                    if "@" in prefix:
                        # "reworkmodules" -- undocumented, no example found
                        self.logger.warning(
                            "Skipping 'reworkmodules' CONFIG_CHECK item %r",
                            word
                        )
                    else:
                        yield (
                            match.group("config_option"),
                            ("!" not in prefix)
                        )
        # --- end of parse_inner (...) ---

        config_options = collections.OrderedDict()
        for config_option, want_enabled in parse_inner(config_check_str):
            if config_option in config_options:
                # conflict!
                # if want_enabled matches the value of the existing entry: ok
                # otherwise: error, cannot recommended both
                #            CONFIG_A=ym and CONFIG_A=n at the same time
                self.logger.info(
                    "config option appears twice in CONFIG_CHECK: %s",
                    config_option
                )

                if config_options[config_option] == want_enabled:
                    pass
                else:
                    raise NotImplementedError(
                        "conflict in CONFIG_CHECK", config_option
                    )

            else:
                config_options[config_option] = want_enabled
            # --
        # --

        return config_options
    # --- end of parse_config_check (...) ---

# --- end of PortageInterface ---
