# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections


from . import _base


__all__ = ["ModaliasCache"]


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

# --- end of ModaliasCacheEntrySimilaritySortKey ---


class ModaliasCache(_base.ModaliasCacheBase):
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
