# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections.abc
import configparser

from ..abc import loggable
from .abc import exc
from . import sourcetype


__all__ = ["CuratedSourceDef"]


class CuratedSourceDef(loggable.AbstractLoggable, collections.abc.Mapping):

    @classmethod
    def new_from_ini(
        cls,
        conf_source_env, name,
        source_def_file=None, source_script_file=None, *,
        parent_logger=None, logger=None, logger_name=None
    ):
        # This is a convenience method that should only be used
        # for initializing of the SourceDef object
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
            source_def.load_ini_data(parser.get_source_def_raw_dict())
        # --

        return source_def
    # --- end of new_from_ini (...) ---

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

    def setdefault(self, key, defaultvalue=None):
        if key not in self.data:
            self.data[key] = defaultvalue

    def load_ini_data(self, data):
        self.data = data
        self._fillup_data()

    def _fillup_data(self):
        self._autodetect_type()
        self._link_arch_x_feat()
        self._pick_arch()

    def _autodetect_type(self):
        if self.data.get("type"):
            return
        # --

        if self.data.get("scriptfile"):
            self.data["type"] = "script"

        # elif ...

        elif self.default_script_file:
            self.data["scriptfile"] = self.default_script_file
            self.data["type"] = "script"
    # --- end of _autodetect_type (...) ---

    def _link_arch_x_feat(self):
        def cross_iter(pair):
            """
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

    OPTION_RENAME_MAP = {
        "arch":         "architectures",
        "archs":        "architectures",
        "architecture": "architectures",

        "feat":         "features",
        "feats":        "features",
        "feature":      "features",

        "desc":         "description",
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
        # set of section names that accumulate in a dict-like fashion
        dict_sects = {"architectures", "features"}

        sdef_raw = {}

        # sections :: normalized section name => section name
        sections = {w.lower(): w for w in self.sections()}
        sections_processed = set()

        # load the main section, if it exists
        if "source" in sections:
            for option, input_value in self.items(sections["source"]):

                # convert input_value depending on option name
                if option in dict_sects:
                    value = {w: {} for w in set(input_value.split())}

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
                sect_subkey = sect_parts[1]

                if sect_key in dict_sects:
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
