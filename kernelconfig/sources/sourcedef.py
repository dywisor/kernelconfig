# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import argparse
import collections.abc
import configparser
import shlex
import re

from ..abc import loggable
from ..util import argutil
from .abc import exc
from . import sourcetype


__all__ = ["CuratedSourceDef"]


class CuratedSourceArgFeatureNotSupportedAction(argparse.Action):
    """
    This action replaces the original action of a "feature" argparse parameter
    if the feature is inactive, i.e. not supported by the target arch.

    If the feature option is encountered in the parsed argv,
    an ConfigurationSourceFeatureNotSupported exception will be raised.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string:
            err_msg = "{} ({})".format(self.dest, option_string)
        else:
            err_msg = self.dest

        raise exc.ConfigurationSourceFeatureNotSupported(err_msg)

# ---


class CuratedSourceArgParser(argutil.NonExitingArgumentParser):
    """
    @cvar DEFAULT_EXIT_EXC_TYPE:  exception that is raised instead of exiting
    @type DEFAULT_EXIT_EXC_TYPE:  C{type} e, e is subclass of Exception

    @cvar RE_FEAT_SPLIT:          regexp for preprocessing feature names

                                  Each char sequence matched by the regexp
                                  will be replaced with a single dash char "-",
                                  and leading/ending dash chars are removed.
                                  The resulting string is then used as base
                                  for the feature argument's long option name.
                                  (and must not be empty)
    @type RE_FEAT_SPLIT:          compiled regexp


    @ivar source_params:          parameter group names (readonly property)
    @type source_params:          iterable of C{str}

    @ivar _source_params:         mapping from parameter group name
                                  to None or 2-tuple (arg group, mut~arg group)

                                  A parameter group is a group of arguments
                                  that race for the same dest in the parsed
                                  args namespace.
                                  For that reason, they are made mutually
                                  exclusive. This attr keeps track of
                                  which protected arg "dests" exist, and
                                  "dest" name dual as parameter group names.

    @type _source_params:         C{dict} :: C{str}
                                          => None or 2-tuple (
                                               argparse arg group,
                                               argparse mutually exclusive grp
                                             )

    @ivar accept_unknown_args:    whether to allow unknown args in parse_args()
    @type accept_unknown_args:    C{bool}
    """

    DEFAULT_EXIT_EXC_TYPE = exc.ConfigurationSourceFeatureUsageError

    RE_FEAT_SPLIT = re.compile(r'[^a-zA-Z0-9]+')

    @property
    def source_params(self):
        return iter(self._source_params)

    def __init__(
        self, source_name,
        description=None, epilog=None, accept_unknown_args=False
    ):
        # keep track of all arch/feature parameters
        #  there are ways to re-use what argparse.ArgumentParser already has,
        #  but this is more explicit and just works
        self._source_params = {}

        self.accept_unknown_args = accept_unknown_args

        super().__init__(
            prog=source_name,
            description=description,
            epilog=epilog,
            add_help=False,
        )

    def register_empty_source_parameter_group(self, name):
        """
        Registers a new parameter group that contains exactly one argument,
        and therefore does not need to keep track of its argument group
        (and likely there is no group anyway).

        @raises KeyError:  name already registered

        @param name:  parameter group name
        @type  name:  C{str}

        @return:  None (implicit)
        """
        if name in self._source_params:
            raise KeyError("duplicate entry for {}".format(name))

        # empty group
        self._source_params[name] = None
    # --- end of register_empty_source_parameter_group (...) ---

    def get_source_parameter_group(self, name):
        """
        Returns the argparse argument group for the given parameter group.
        Creates a new group if necessary,
        otherwise the existing group is returned.

        An exception is raised if the existing group is a "one argument group".
        @raises KeyError:  name already registered as single-arg "group"

        @param name:  parameter group name
        @type  name:  C{str}

        @return:  argparse argument group
        """
        if name in self._source_params:
            source_param_tuple = self._source_params[name]

            if not source_param_tuple:
                # already registered as single-arg
                raise KeyError("duplicate entry for {}".format(name))

            return source_param_tuple[-1]

        else:
            arg_group = self.add_argument_group(
                title="{} options".format(name)
            )
            arg_mut_group = arg_group.add_mutually_exclusive_group()

            self._source_params[name] = (arg_group, arg_mut_group)
            return arg_mut_group
    # --- end of get_source_parameter_group (...) ---

    def parse_args(self, argv, **kwargs):
        """
        @return:  2-tuple (parsed args namespace, unknown args or None)
        @rtype:   2-tuple (argparse namespace, C{None} or C{list} of C{str})
        """
        if self.accept_unknown_args:
            return self.parse_known_args(argv, **kwargs)
        else:
            parsed = super().parse_args(argv, **kwargs)
            return (parsed, None)
    # ---

    def add_feature(self, feat_name, feat_node, is_active):
        """
        Creates and adds an argparse argument
        from a source def feature name and data dict.

        The data dict may not contain arbitrary entries,
        only the following keys are accepted:

        * name           --  feature name override (instead of feat_name)
                             The name is used as default longopt "--<~name>",
                             and as default arg dest "<~~name>".
                             (after applying a few str transformations)
        * dest           --  optional arg dest override (instead of ~~name)
        * description    --  optional arg help (otherwise: None)
        * type           --  arg type,
                             one of "const", "optin", "optout", "arg".
                             Defaults to "const".
        * value          --  value for "const"-type args
        * default        --  default arg value,
                             the default default is type-specific
        * architectures  --  ignored.

        Unknown keys lead to an exception.
        @raises ConfigurationSourceInvalidParameterDef: unknown feat-node key

        @param feat_name:  the feature's name,
                           which is transformed into a (long) option name
                           in absence of an explicit option name

        @param feat_node:  the feature's data dict
        @type  feat_node:  C{dict} :: C{str} => C{object}

        @param is_active:  whether the feature is active or not

                           An active feature can be specified as parameter
                           and behaves as configured.
                           An inactive feature raises an exception
                           if it is specified as parameter.
        @type  is_active:  C{bool}
        """

        feat_opts = set()    # --feat-name
        # feat_args will be set from feat_opts just before creating the arg
        feat_kwargs = {}     # kw-args for add_argument()

        # feat_node keys that have been processed,
        #  towards the end of this method, it is checked whether any keys
        #  were not processed, in which case an exception is raised.
        #
        #  "architectures" is not of interest here, mark it as processed
        #
        keys_processed = {"architectures", }

        def feat_pseudo_pop(key):
            """
            Retrieves an item referenced by its key from feat_node
            and marks it as processed.

            Returns None if feat_node does not contain the requested key.
            """
            nonlocal feat_node
            nonlocal keys_processed

            try:
                item = feat_node[key]
            except KeyError:
                return None
            else:
                keys_processed.add(key)
                return item
        # ---

        def create_feat_action():
            """
            Creates a dict containing the action-related argparse kw-args
            for add_argument().
            """
            # for now, feat_node is always parsed completely
            #
            #  action-related config should be stored in feat_action,
            #  which is merged with feat_kwargs if the feature is "active".
            #
            #  Otherwise, feat_action gets (mostly) discarded,
            #  and a "feature disabled" action will be set up.
            #
            nonlocal feat_arg_name
            nonlocal feat_longopt
            nonlocal feat_node
            nonlocal feat_pseudo_pop

            feat_action = {}
            arg_type = (feat_pseudo_pop("type") or "const").lower()

            if arg_type == "const":
                # then use action=store_const,
                # * "default" holds the default str value (optional)
                #     may be empty, defaults to ""
                # * "value" holds the const str value     (optional)
                #     may be empty, defaults to feat_longopt
                #
                if "value" in feat_node:
                    feat_action["const"] = feat_pseudo_pop("value")
                else:
                    feat_action["const"] = feat_longopt
                # --

                feat_action["action"] = "store_const"
                feat_action["default"] = feat_pseudo_pop("default") or ""

            elif arg_type in {"optin", "optout"}:
                # then use action=store_const,
                # * default is ""  (optin) or "y" (optout)
                # * const   is "y"         or ""

                is_optin = arg_type[-1] == "n"

                feat_action["action"] = "store_const"
                feat_action["default"] = "" if is_optin else "y"
                feat_action["const"] = "y" if is_optin else ""

            elif arg_type == "arg":
                # then use action=store
                feat_action["action"] = "store"
                feat_action["default"] = feat_pseudo_pop("default") or ""
                feat_action["metavar"] = "<{}>".format(feat_arg_name)

            else:
                raise exc.ConfigurationSourceInvalidParameterDef(
                    "unknown argument type {} for {}".format(
                        arg_type, feat_name
                    )
                )
            # -- end if arg type

            return feat_action
        # --- end of create_feat_action (...) ---

        # feat_name is already lowercase
        feat_arg_name = feat_pseudo_pop("name") or feat_name
        # feat_key: preprocessed feat name parts that can be reassembled
        #           to create a longopt or arg dest name
        feat_key = [
            w for w in self.RE_FEAT_SPLIT.split(feat_arg_name.lower()) if w
        ]
        if not feat_key:
            raise exc.ConfigurationSourceInvalidParameterDef(
                "empty feature key for {}".format(feat_name)
            )
        # --

        # longopt
        feat_longopt = "--{}".format("-".join(feat_key))
        feat_opts.add(feat_longopt)

        # dest
        feat_dest = feat_pseudo_pop("dest")
        if feat_dest:
            feat_dest = feat_dest.lower()
        else:
            feat_dest = "_".join(feat_key).lower()

        feat_kwargs["dest"] = feat_dest

        # help
        feat_kwargs["help"] = feat_pseudo_pop("description") or None

        # action, const, default, metavar, ...
        feat_action = create_feat_action()

        if is_active:
            feat_kwargs.update(feat_action)
        else:
            # default from feat_action or None?
            #
            #  default from feat_action:
            #     pretend that the feature has not been enabled
            #     * fmt vars will contain param_x = <default>
            #     * env vars will contain PARAM_X = <default>
            #
            #  default None:
            #     pretend that the feature does not exist
            #     * fmt vars will contain param_x = ""  (for convenience)
            #     * env vars will not contain PARAM_X,
            #       (PARAM_X will be removed from the env vars)
            #
            feat_kwargs["default"] = None
            feat_kwargs["action"] = CuratedSourceArgFeatureNotSupportedAction

            # the nargs=0 'hack' is necessary,
            # otherwise the parser expects a value after --<feature>
            feat_kwargs["nargs"] = feat_action.get("nargs") or 0
        # --

        # check for unknown keys in feat_node
        keys_unprocessed = set(feat_node) - keys_processed
        if keys_unprocessed:
            raise exc.ConfigurationSourceInvalidParameterDef(
                "unknown parameter options", keys_unprocessed
            )
        # --

        # create and add the argparse arg
        feat_args = sorted(feat_opts, key=len)

        # TODO: check for conflicting defaults in group
        feat_group = self.get_source_parameter_group(feat_dest)
        return feat_group.add_argument(*feat_args, **feat_kwargs)
    # --- end of add_feature_argument (...) ---

# --- end of CuratedSourceArgParser ---


class CuratedSourceDef(loggable.AbstractLoggable, collections.abc.Mapping):
    """
    @ivar name:                 name of the configuration source,
                                as passed to __init__()
                                (not read from the source def file)
    @type name:                 C{str}

    @ivar senv:                 shared configuration source environment
    @type senv:                 L{ConfigurationSourcesEnv}

    @ivar data:                 parsed source def data
    @type data:                 C{dict} :: C{str} => _  (nested dict)

    @ivar default_script_file:  path to the source's default script file
                                as determined by file lookups prior
                                to initializing this object.
                                It is possibly used as fallback script path.
    @type default_script_file:  C{str} or C{None}

    @ivar _def_file:            path to the loaded source def file or None,
                                may also be True if file unknown but loaded
    @type _def_file:            C{None} or C{str} or C{bool}

    @ivar has_definition_file:  whether the source def was constructed
                                from a definition file (True)
                                or is script-only (False)
    @type has_definition_file:  C{bool}

    @ivar arch:                 target architecture node,
                                extracted from the source definition data
    @type arch:                 C{dict} :: C{str} => _  (nested dict)

    @ivar feat:                 node of features supported for the target arch,
                                extracted from the source definition data
    @type feat:                 C{dict} :: C{str} => _  (nested dict)
    """

    @classmethod
    def new_from_ini(
        cls,
        conf_source_env, name,
        source_def_file=None, source_script_file=None, *,
        parent_logger=None, logger=None, logger_name=None
    ):
        """

        @param   conf_source_env:     shared configuration sources environment
        @type    conf_source_env:     L{ConfigurationSourcesEnv}

        @param   name:                name of the configuration source
        @type    name:                C{str}

        @keyword source_def_file:     None or path to the source def ini file
        @type    source_def_file:     C{None} or C{str}

        @keyword source_script_file:  None or path to the source's script file
        @type    source_script_file:  C{None} or C{str}

        @keyword parent_logger:
        @keyword logger:
        @keyword logger_name:         defaults to name

        @return:  source def object
        @rtype:   L{CuratedSourceDef}
        """
        # This is a convenience method that should only be used
        # for initializing a SourceDef object.
        # For that reason, it is bound to cls and not self.
        #
        source_def = cls(
            conf_source_env, name, default_script_file=source_script_file,
            parent_logger=parent_logger,
            logger=logger, logger_name=logger_name
        )

        if source_def_file:
            # forward-ref CuratedSourceDefIniParser
            parser = CuratedSourceDefIniParser(
                logger=source_def.get_child_logger("parser")
            )
            parser.read_filepath(source_def_file)
            source_def.load_ini_data(
                parser.get_source_def_raw_dict(), source=source_def_file
            )
        # --

        source_def.autoset()
        return source_def
    # --- end of new_from_ini (...) ---

    @property
    def has_definition_file(self):
        return bool(self._def_file)

    def __init__(
        self, conf_source_env, name, *, default_script_file=None,
        parent_logger=None, logger=None, logger_name=None
    ):
        super().__init__(
            parent_logger=parent_logger,
            logger=logger, logger_name=(logger_name or name),
        )
        self.senv = conf_source_env
        self.name = name
        self.data = {}  # gets replaced by a new dict in load_*()

        self.default_script_file = default_script_file
        self._def_file = None

        self.arch = None
        self.feat = None
    # --- end of __init__ (...) ---

    def get_source_type(self):
        source_type_name = self.data.get("type")
        if not source_type_name:
            # then _autodetect_type() could not detect the source type
            raise exc.ConfigurationSourceMissingType()
        # --

        return sourcetype.get_source_type(source_type_name)
    # --- end of get_source_type (...) ---

    def __bool__(self):
        return bool(self.data)

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def gen_parser_description(self):
        """
        Generator that yields text lines describing the source,
        meant for creating the argument parser's description.

        This method expects that the def data have already been initialized.

        @return:  text line(s) w/o newline
        @rtype:   C{str}  (genexpr)
        """
        archs = self.data["architectures"]
        yield "Supported architectures: {}.".format(
            (
                ", ".join(sorted(archs)) if archs
                else "unknown (no restrictions)"
            )
        )

    def build_parser(self):
        """Builds the argument parser for the config source.

        This method expects that the def data have already been initialized.

        @return: a non-exiting argument parser
                 with a 2-tuple returning parse_args() method
        @rtype:  L{CuratedSourceArgParser}
        """
        parser = CuratedSourceArgParser(
            self.name,
            description="\n".join(self.gen_parser_description()),
            accept_unknown_args=self.get("passunknownargs"),
            epilog=self.data.get("description")
        )

        arch_value = (
            (self.arch.get("value") if self.arch else None)
            or (self.senv.get_format_vars().get("arch"))
        )
        if arch_value:
            parser.set_defaults(arch=arch_value)
            parser.register_empty_source_parameter_group("arch")

        active_features = set(self.feat) if self.feat else set()
        for feat_name, feat_node in self.data["features"].items():
            parser.add_feature(
                feat_name, feat_node, (feat_name in active_features)
            )

        return parser
    # --- end of build_parser (...) ---

    def load_ini_data(self, data, source=None):
        """Replaces the current source data with a new dict.

        autoset() should be called after this method.

        @param   data:
        @type    data:    C{dict} :: C{str} => _  (nested dict)
        @keyword source:
        @type    source:  C{None} or C{str} or C{bool}

        @return:  None (implicit)
        """
        self.data = data
        if source:
            self._def_file = (True if source is None else source)

    def autoset(self):
        """
        Fills up self.data and sets self.arch, self.feat accordingly.

        This method should be called after loading self.data.

        @return:  None (implicit)
        """
        self._fillup_data()

    def _fillup_data(self):
        """
        @return:  None (implicit)
        """
        self._add_missing_entries()
        self._autodetect_type()
        self._link_arch_x_feat()
        self._pick_arch()

    def _add_missing_entries(self):
        """Adds default entries for missing nodes in self.data:

          * Architectures  -- default: empty node
          * Features       -- default: empty node

          (entry names are lowercase)

        @return:  None (implicit)
        """
        for key in "architectures", "features":
            if key not in self.data:
                self.data[key] = {}
    # ---

    def _autodetect_type(self):
        """
        Defaults the source's type and also a few type-related vars:

          * Type
          * Path
          * PassUnknownArgs

          (entry names are lowercase)

        @return:  None (implicit)
        """
        type_name = self.data.get("type") or None

        if type_name:
            pass

        elif self.data.get("path"):
            type_name = "script"

        elif self.data.get("command"):
            # either a command or a script
            str_formatter = self.senv.get_str_formatter()
            fvars = set(
                str_formatter.iter_referenced_vars_v(self.data["command"])
            )

            if "script_file" in fvars:
                type_name = "script"
            else:
                type_name = "command"

        # elif ...

        elif self.default_script_file:
            type_name = "script"
        # --

        self.data["type"] = type_name  # possibly None

        if type_name in {"script", "pym"}:
            if self.default_script_file and not self.data.get("path"):
                self.data["path"] = self.default_script_file
        # --

        self.data.setdefault(
            "passunknownargs", (not self.has_definition_file)
        )
    # --- end of _autodetect_type (...) ---

    def _link_arch_x_feat(self):
        """Completes the "architectures" and "features" nodes in self.data.

        @return:  None (implicit)
        """

        def cross_iter(pair):
            """
            >>> list(cross_iter([a, b]))
            [(a, b), (b, a)]

            @param pair:   object pair
            @type  pair:   2-tuple (object, object)   (or similar)

            @return:  2-tuples (object, object)
            """
            # return itertools.permutations(pair)
            yield (pair[0], pair[1])
            yield (pair[1], pair[0])
        # ---

        source_def = self.data

        # "link" features/architectures
        #
        #  step 1: prepare feat, arch
        #           replace feat/arch str list with a set of values
        #
        #   for node in source_def["architectures"].values():
        #      replace features entry with new node, data type set
        #      also check whether features are known
        #
        #   for node in source_def["features"].values():
        #      replace architectures entry with new node, data type set
        #      also check whether architectures are known
        #
        cross_pair = ["architectures", "features"]

        unknown = {k: set() for k in cross_pair}
        for key, oth_key in cross_iter(cross_pair):
            all_values = set()
            for node in source_def[key].values():
                try:
                    strlist = node[oth_key]
                except KeyError:
                    vset = set()
                else:
                    vset = set(strlist.split())
                # --

                all_values.update(vset)
                node[oth_key] = vset
            # -- end for node

            unknown[oth_key].update(all_values - set(source_def[oth_key]))
        # --

        if any(unknown.values()):
            raise ValueError(unknown)

        #  step 2: balance feat<>arch references
        #
        #    for arch->name that lists feat
        #       add arch->name to feat->arch
        #
        #    for feat->name that lists arch
        #       add feat->name to arch->feat
        #
        #  feat_nodes = source_def["features"]
        #  for arch, arch_node in source_def["architectures"].items():
        #     for feat in arch_node["features"]:
        #        feat_nodes[feat]["architectures"].add(arch)
        #  end for
        #
        for key, oth_key in cross_iter(cross_pair):
            oth_nodes = source_def[oth_key]

            for name, node in source_def[key].items():
                for oth_name in node[oth_key]:
                    oth_nodes[oth_name][key].add(name)
        # --

        #  step 3: identify unlinked features,
        #           add them to all archs and establish backrefs
        #
        #   for feat->name that does not list any arch
        #      add feat->name to arch->feat of all archs

        # create a helper dict with refs to source_def
        #   arch's name => arch's set of features
        arch_feat_sets = {
            arch_name: arch_node["features"]
            for arch_name, arch_node in source_def["architectures"].items()
        }

        for feat_name, feat_node in source_def["features"].items():
            feat_archs = feat_node["architectures"]
            if not feat_archs:
                # then add to all archs
                for arch_name, arch_feat_set in arch_feat_sets.items():
                    feat_archs.add(arch_name)     # add to feat->arch
                    arch_feat_set.add(feat_name)  # add to arch->feat
                # --
        # -- end for feature name,node
    # --- end of _link_arch_x_feat (...) ---

    def _pick_arch(self):
        """
        Sets self.arch to the architecture node of the first-matching
        target arch (source_info.iter_target_arch_dedup()),
        and sets self.feat accordingly.

        If the "architectures" node in self.data is empty
        (that is, no architectures defined), a mostly empty arch node is
        created and all features are added to it.

        @return:  None (implicit)
        """
        source_def = self.data

        # create "arch", "feat" entries for the arch being configured
        #  they will be None if the arch is not supported,
        #  but an empty dict should not be interpreted as "not supported"
        #
        assert "arch" not in source_def
        assert "feat" not in source_def

        self.arch = None
        self.feat = None

        try:
            architectures = source_def["architectures"]
            features = source_def["features"]
        except KeyError:
            raise AssertionError("no data loaded")

        if not architectures:
            self.arch = {"features": set(features)}
            self.feat = features
            # not adding arch to feat->arch

        else:
            # for each possible arch str (from most specific to most generic)
            #    if arch str appears in architectures:
            #       pick this arch and associated features
            #       BREAK LOOP
            #
            for arch_source_ident, arch_candidate in (
                self.senv.source_info.iter_target_arch_dedup()
            ):
                # lower(): architectures contains lowercase names only
                arch_candlow = arch_candidate.lower()

                if arch_candlow in architectures:
                    arch_node = architectures[arch_candidate]
                    self.arch = arch_node
                    self.feat = {
                        feat_name: features[feat_name]
                        for feat_name in arch_node["features"]
                    }

                    # == BREAK LOOP ==
                    break
                # -- end if arch candidate matches
            # --- end for arch candidate
        # -- end if source def defines architectures?
    # --- end of _pick_arch (...) ---

# --- end of CuratedSourceDef ---


class CuratedSourceDefIniParser(configparser.ConfigParser):
    """Curated source definition .ini file parser.

    @cvar OPTION_RENAME_MAP:  option name unalias map,
                              keys and values must be lowercase strings
    @type OPTION_RENAME_MAP:  C{dict} :: C{str} => C{str}

    @ivar logger:
    """

    OPTION_RENAME_MAP = {
        "arch":         "architectures",
        "archs":        "architectures",
        "architecture": "architectures",

        "feat":         "features",
        "feats":        "features",
        "feature":      "features",

        "desc":         "description",

        "cmd":          "command",
    }

    def __init__(
        self, logger, *,
        allow_no_value=False,
        delimiters="=",
        comment_prefixes="#",
        strict=True,
        empty_lines_in_values=False,
        interpolation=None,
        **kwargs
    ):
        self.logger = logger
        super().__init__(
            allow_no_value=allow_no_value,
            delimiters=delimiters,
            comment_prefixes=comment_prefixes,
            strict=strict,
            empty_lines_in_values=empty_lines_in_values,
            interpolation=interpolation,
            **kwargs
        )

    def optionxform(self, option):
        olow = option.lower()
        return self.OPTION_RENAME_MAP.get(olow, olow)

    def read_filepath(self, filepath):
        with open(filepath, "rt", encoding="utf-8") as fh:
            self.read_file(fh, source=filepath)

    def get_source_def_raw_dict(self):
        """
        Creates a "raw" source definition data dict from the parsed ini data.

        It is a nested dict containing the data read from the ini file(s).
        Option names are already unaliased/renamed and lowercase-converted,
        and values are preprocessed (depending on the section/option name).

        Its overall structure is the same as what CuratedSourceDef will use
        later on, but the dict nodes may be incomplete,
        especially the "architectures" and "features" sub-dicts.

        An exception is raised if the parsed ini data contain unknown sections.
        @raises ValueError:   unknown sections

        @return:  raw source def data dict
        @rtype:   C{dict} :: C{str} => _  (nested dict, max depth: 3 keys)
        """
        # set of section names that accumulate in a dict-like fashion
        dict_sects = {"architectures", "features"}

        # set section names that are added as sub dicts to the output dict
        #  They must not appear as options in the main section.
        passthrough_sub_sects = {"config", }

        # (main section:) options whose value should be interpreted as bool
        source_bool_opts = {"passunknownargs", }

        # (main section:) options whose value is subject to shlex.split()
        shlex_options = {"command", }

        sdef_raw = {}

        # sections :: normalized section name => section name
        sections = {w.lower(): w for w in self.sections()}
        sections_processed = set()

        # load the main section, if it exists
        if "source" in sections:
            for option, input_value in self.items(sections["source"]):

                # convert input_value depending on option name
                if option in dict_sects:
                    value = {
                        w.lower(): {"name": w}
                        for w in set(input_value.split())
                    }

                elif option in passthrough_sub_sects:
                    raise ValueError(
                        "reserved sub-section field name: {}".format(option)
                    )

                elif option in source_bool_opts:
                    value = self.getboolean(sections["source"], option)

                elif option.endswith("_str"):
                    raise ValueError("reserved field name: {}".format(option))

                elif option in shlex_options:
                    value_str = input_value.strip()
                    value = shlex.split(value_str)
                    sdef_raw[option + "_str"] = value_str

                else:
                    # strip leading/ending whitespace from all options
                    value = input_value.strip()
                # --

                sdef_raw[option] = value
            # --

            #  Add processed sections to sections_processed
            #  so that unknown sections can be identified later on.
            sections_processed.add("source")
        # --

        # add empty arch/feature sections
        #  if the main section did not define them
        for sect in dict_sects:
            if sect not in sdef_raw:
                sdef_raw[sect] = {}
        # --

        # add pass-through sub-sections as-is  (but preprocess value)
        for sect in passthrough_sub_sects:
            if sect in sections:
                sdef_raw[sect] = {
                    option: value.strip()
                    for option, value in self.items(sections[sect])
                }
                sections_processed.add(sect)
        # --

        # process remaining sections,
        #   * architectures:<arch>
        #   * features:<feat>
        #
        #  Multiple ":" chars are accepted and get ignored,
        #  and so do leading/ending ":" chars.
        #
        #  The first component of the colon-separated list gets option-renamed.
        #  Since it is already in lowercase,
        #  the OPTION_RENAME_MAP lookup is sufficient.
        #
        for sect, sect_name in sections.items():
            sect_parts = [w for w in sect.split(":") if w]

            if sect_parts and len(sect_parts) == 2:
                sect_key = self.OPTION_RENAME_MAP.get(
                    sect_parts[0], sect_parts[0]
                )

                if sect_key in dict_sects:
                    sect_subkeys = [
                        w for w
                        in (s.strip() for s in sect_parts[1].split(",")) if w
                    ]

                    for sect_subkey in sect_subkeys:
                        parent_node = sdef_raw[sect_key]

                        try:
                            node = parent_node[sect_subkey]
                        except KeyError:
                            self.logger.debug(
                                "Implicit declaration of %r in %s",
                                sect_subkey, sect_key
                            )
                            node = {}
                            parent_node[sect_subkey] = node
                        # --

                        node.update(self.items(sect_name))
                    # -- end for subkey

                    #  Add processed sections to sections_processed
                    #  so that unknown sections can be identified later on.
                    sections_processed.add(sect)
                # -- end if dict_sects key
            # -- end if sect_parts
        # --

        sections_unprocessed = set(sections) - sections_processed
        if sections_unprocessed:
            raise ValueError("unknown sections", sections_unprocessed)

        return sdef_raw
    # --- end of get_source_def_raw_dict (...) ---

# --- end of CuratedSourceDefIniParser (...) ---
