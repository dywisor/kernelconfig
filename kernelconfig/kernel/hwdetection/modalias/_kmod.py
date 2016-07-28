# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

try:
    import kmod
except ImportError:
    HAVE_KMOD = False
else:
    HAVE_KMOD = True


from .abc import lookup as _lookup_abc


__all__ = ["KmodModaliasLookup"]


if HAVE_KMOD:

    class KmodModaliasLookup(_lookup_abc.AbstractModaliasLookup):

        AVAILABLE = HAVE_KMOD

        def iter_lookup_v(self, modaliases):
            # lazy-init kmod interface
            kmod_iface = self.get_kmod()

            # iterate over modaliases, using <kmod interface>.lookup
            for modalias in modaliases:
                # flags like "apply blacklist" are irrelevant when looking
                # up module names for a config currently being created
                for result in kmod_iface.lookup(modalias, flags=0):
                    yield result.name
        # --- end of iter_lookup_v (...) ---

        def get_kmod(self):
            """
            Lazy-initializes the kmod interfaces,
            which in turn may lazy-initialize the modules dir.

            @return:  kmod interface
            @rtype:   kmod.Kmod
            """
            kmod_iface = self._kmod
            if kmod_iface is None:
                kmod_iface = self._init_kmod()
                assert kmod_iface is not None
                self._kmod = kmod_iface
            # --
            return kmod_iface
        # --- end of get_kmod (...) ---

        def __init__(self, mod_dir, **kwargs):
            super().__init__(**kwargs)
            self._mod_dir = mod_dir
            self._kmod = None
        # --- end of __init__ (...) ---

        def _init_kmod(self):
            if not self._init_mod_dir():
                raise RuntimeError("could not initialize modules dir")

            mod_dir_path = self.get_mod_dir_path()
            self.logger.debug(
                "Initializing kmod-based modalias lookup, using files from %s",
                (repr(mod_dir_path) if mod_dir_path else "<default>")
            )

            # TODO: find out how config from /etc can interfere with
            #       modalias lookup, and turn it off where appropriate
            #       (flags get already set to 0)
            return kmod.Kmod(mod_dir=self._convert_to_bytes(mod_dir_path))
        # --- end of _init_kmod (...) ---

        def lazy_init(self):
            return self._init_mod_dir()
        # --- end of lazy_init (...) ---

        def get_mod_dir_path(self):
            mod_dir = self._mod_dir

            if not mod_dir:
                return mod_dir

            elif isinstance(mod_dir, (str, bytes)):
                return mod_dir

            else:
                return mod_dir.get_path()
        # --- end of get_mod_dir_path (...) ---

        def _init_mod_dir(self):
            mod_dir = self._mod_dir
            if mod_dir is None:
                # None  -->  usable, but discouraged,
                #            since /lib/modules/$(uname -r) is an unreliable
                #            source
                self.logger.warning(
                    (
                        "Using /lib/modules for modalias lookup,"
                        " this is an unreliable info source."
                    )
                )
                return True

            elif not mod_dir:
                # False, ""  -->  not usable
                return False

            elif isinstance(mod_dir, (str, bytes)):
                # non-empty str/bytes  -->  usable
                return True

            else:
                # modules dir obj  -->  return from prepare()
                if mod_dir is True:
                    raise AssertionError(
                        "auto-set modules dir must be done at an upper level"
                    )
                # --

                return mod_dir.prepare()
        # --- end of _init_mod_dir (...) ---

        @classmethod
        def _convert_to_bytes(cls, seq):
            if seq is None:
                return seq
            elif isinstance(seq, bytes):
                return seq
            elif isinstance(seq, str):
                return seq.encode("ascii")
            else:
                raise ValueError(seq)

    # --- end of KmodModaliasLookup ----

else:
    KmodModaliasLookup = _lookup_abc.UnavailableModaliasLookup
# -- end if HAVE_KMOD?
