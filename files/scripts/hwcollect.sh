#!/bin/sh
#  This script collects information about hardware of the current system
#  by querying files in /sys.
#
#  The result is a text file in JSON format that is written to stdout.
#
#  Note: the JSON file produced by this script uses null/empty sentinel values
#        to work around trailing commas
#        Parsers should ignore empty values at the end of string lists.
#
#  This script is meant to be run on minimal/embedded systems,
#  so compatibility with busybox applets (and its shell) is important.
#
#  Below is a list of applets that are required for running this script:
#
#  * sh/ash
#  * basename
#  * printf
#  * sed    with -r
#  * sort   with -u
#  * find   with -name, -print0
#  * xargs  with -n
#
# Additionally, /sys and /proc need to be mounted.
#
set -u

export LC_ALL=C
export LC_COLLATE=C
export LANG=C

# one level if whitespace indent is 3 spaces:
I="   "


SYSFS_PATH=/sys

# @nostderr find_sysfs (...)
find_sysfs() {
    2>/dev/null find "${SYSFS_PATH}/" "${@}"
}


# @stdio json_strlistify(indent="")
#
#  stdio filter for json_strlist_attr().
#  Converts strings from stdin to list items, written to stdout.
#
json_strlistify() {
    # char conversions:
    #   \ -> \\
    #   " -> \"
    # the rest (^, $) is pretty-printing
    sed -r \
        -e 's=\\\\=\\=' -e 's="=\\"=g' \
        -e "s=^=${1-}\"=" -e "s=\$=\",="
}


# json_strlist_attr ( name, func, *args )
#
#  Creates a name X list attribute
#  where the list items are strings written to stdout by func(*args)
#  (one item per line, no newline in string items supported).
#
json_strlist_attr() {
    local name
    name="${1:?}"; shift

    printf '%s\n' "${I}\"${name}\": ["
    "${@}" | json_strlistify "${I}${I}"
    printf '%s\n' "${I}${I}\"\""
    printf '%s\n' "${I}],"
}


# json_scalar_attr ( name, value_str )
#
#  Creates a name X value_str attribute, value_str must already be quoted
#  (if applicable).
#
json_scalar_attr() {
    printf '%s\n' "${I}\"${1:?}\": ${2:?},"
}


# hwcollect_modules_driver_symlink()
#
#  Scans /sys for "driver" symlinks and writes a deduplicated list
#  of associated kernel module names to stdout (one item per line).
#
hwcollect_modules_driver_symlink() {
    find_sysfs -name driver -print0 | \
        xargs -0 readlink | \
        xargs -n 1 basename | \
        sort -u
}


# hwcollect_modules_lsmod()
#
#  Reads /proc/modules and writes a list of module names to stdout
#  (one item per line).
#
hwcollect_modules_lsmod() {
    local mod_name
    local dont_care

    # /proc/modules does not exist when non-modular kernel is booted
    [ -r /proc/modules ] || return 0

    while read -r mod_name dont_care; do
        [ -z "${mod_name-}" ] || printf '%s\n' "${mod_name}"
    done < /proc/modules | sort
}


# hwcollect_modules_modalias()
#
#  Scans /sys for "modalias" files and writes a deduplicated list
#  of module alias identfiers to stdout (one item per line).
#
#  (This function will read all modalias files in /sys.)
#
hwcollect_modules_modalias() {
    # "xargs -0 sort" does not necessarily receive all modalias files,
    # so make sure of deduplication with a second sort -u
    find_sysfs -name modalias -print0 | xargs -0 sort -u | sort -u
}


# hwcollect_filesystem_types_mounted()
#
#  Reads the types of mounted filesystems from /proc/self/mounts
#  and writes them to stdout. (one item per line, deduplicated)
#
#  Note that this source is unreliable when running hwcollect
#  on a live system (e.g. "/" mounted as aufs/overlayfs union).
#
hwcollect_filesystem_types_mounted() {
    local fs mp fstype dont_care

    [ -r /proc/self/mounts ] || return 1

    while read -r fs mp fstype dont_care; do
        [ -z "${fstype-}" ] || printf '%s\n' "${fstype}"
    done < /proc/self/mounts | sort -u
}


# hwcollect_json_init ( version )
#
#  Starts the json output file (a json object).
#
hwcollect_json_init() {
    # object header
    printf '%s\n' "{"

    # version of the file format,
    #    tells kernelconfig what info/structure to expect
    json_scalar_attr  "version"   1
}


# hwcollect_json_fini()
#
#  Terminates the json output file.
#
hwcollect_json_fini() {
    # object footer
    # Putting "version" at the end of the file would be an option for working
    # around trailing commas, too, but it'd poor in terms of readability,
    # so a dummy attr is used instead.
    printf '%s\n' "${I}\"__null__\": null"
    printf '%s\n' "}"
}

# hwcollect_main()
#
#   Creates the JSON file.
#
hwcollect_main() {
    hwcollect_json_init 1

    # kernel modules currently used by devices
    json_strlist_attr "driver"    hwcollect_modules_driver_symlink

    # loaded modules
    json_strlist_attr "lsmod"     hwcollect_modules_lsmod

    # module alias identifiers
    json_strlist_attr "modalias"  hwcollect_modules_modalias

    # types of mounted filesystems
    json_strlist_attr "fsmount"   hwcollect_filesystem_types_mounted

    hwcollect_json_fini
}


hwcollect_main "${@}"
