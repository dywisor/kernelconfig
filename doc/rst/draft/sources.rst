Sources
=======

This is a draft on the upcoming *configuration basis* feature.


What is a Source?
-----------------

A kernel configuration file that serves as basis
for generating the custom config file.

In the broader sense,
a source stands for means to get such a *configuration basis*.



What type of sources exist in kernelconfig?
-------------------------------------------

* local file

  a input ``.config`` file that is already available on the system running
  kernelconfig

  * absolute path

  * relative path, looked up in ``<settings dirs>/sources/files``

* remote file

  a input ``.config`` file that can be retrieved via http(s) or ftp

* command

  A command that creates the input ``.config`` file,
  and either writes it to stdout
  or to a file specified by ``--outfile <file>``.

* make target

  A subtype of *command*,
  which is run the kernel sources directory and creates ``<srctree>/.config``.

* (embedded) script

  A extended variant of *command*.
  Instead of running a single command,
  runs the text as script, interpreted by ``sh``.

* *curated source*

  A mix of source definition file and/or a script file.

  The definition file contains a detailed description of the *source*,
  e.g. supported architectures and variants.

  Simple *curated sources* (e.g. ``wget <file>``)
  can be defined with this file only.
  More complex tasks need to be offloaded to the script file,
  which can be written in any language
  (``sh`` and ``python`` preferred)

  It is also possible, though not encouraged for "official" *curated sources*,
  to use a script file only.



From the implementation point of view, there are only two types,

* *static sources*, which are files

* *dynamic sources* which consist of

  * a description,
    either implicit (command, script, curated source w/o def)
    or explicit (make target, curated source w/ definition file)

  * a command or script,
    either implicit (make target, curated source w/ definition file),
    or explciit (all other types)


How to configure sources?
-------------------------

In the ``[source]`` section of the settings file

* absolute path to local file::

    [source]
    /path/to/file

  Possibly subject to Python string formatting (``/path/tp/{arch}/file``).

* relative path to local file (or overly explicit absolute path)::

    [source]
    file <file>
    #file file://<file>

  Possibly subject to Python string formatting.

* remote file::

    [source]
    file http://
    file https://
    file ftp://

* command::

    [source]
    command [...] <command> [<arg>...]
    #cmd [...] <command> [<arg>...]

  The command line is subject to Python string formatting,
  make sure to escape ``{`` and ``}`` braces accordingly (``{{``, ``}}``).

* make target::

    [source]
    make <target> [<arg>...]

* curated source::

    [source]
    <name> [<arg>...]

  alternatively ``source <name> [<arg>...]``.

  Plus a source definition file and/or a script in
  $$some$$ subdirectory of the settings directories.

* script::

    [source]
    sh [...]
    ...

  The script is possibly subject to Python string formatting.
  This would allow to infer some details from the script,
  e.g. whether a temporary directory is required,
  and whether the script writes to stdout or a file.


Curated Source Definition File
------------------------------

An ini file that is parsed with ``configparser.?``.

Section and option names are case-insensitive.


.. code:: ini

    [Source]
    Name          = ...
    Description   = ...
    Type          = file|script
    Path          = http://...|script name|empty
    Architectures = ...
    Features      = ...
    Cacheable     = yes|no

    [Arch:A]
    ...

    [Feature:F]
    ...


.. table::

    +-----------------+---------------+-----------+---------------------------------------+
    | field name      | value type    | required  | description                           |
    +=================+===============+===========+=======================================+
    | Name            | str           | *default* | name of the curated source            |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to name of the definition    |
    |                 |               |           | file with suffix removed              |
    +-----------------+---------------+-----------+---------------------------------------+
    | Description     | str           | no        | description of the curated source,    |
    |                 |               |           | for informational purposes            |
    +-----------------+---------------+-----------+---------------------------------------+
    | Type            | str           | **yes**   | the type of the source                |
    +-----------------+---------------+-----------+---------------------------------------+
    | Path            | format str    | *depends* | path to the input ``.config``,        |
    |                 |               |           | or path to the script                 |
    +-----------------+---------------+-----------+---------------------------------------+
    | Architectures   | str-list      | no        | supported architectures               |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to *all*.                    |
    +-----------------+---------------+-----------+---------------------------------------+
    | Features        | str-list      | no        | source variants                       |
    +-----------------+---------------+-----------+---------------------------------------+
    | Cacheable       | bool          | no        | whether the config file can be        |
    |                 |               |           | reused subsequent runs (*true*),      |
    |                 |               |           | or needs to be recreated each time    |
    |                 |               |           | (*false*)                             |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to *false*.                  |
    +-----------------+---------------+-----------+---------------------------------------+
    | CacheKey        | format str    | no        | [partial] file name used for caching  |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to maybe                     |
    |                 |               |           | ``{name}-{arch}-{kver}-{features}``?  |
    +-----------------+---------------+-----------+---------------------------------------+


Source Environment
------------------

environment vars
++++++++++++++++

For ``script`` and ``command`` type config sources,
the following environment variables are set:

.. table:: environment variables

    +------------------+-------------------------------------------+
    | name             |  description                              |
    +==================+===========================================+
    | S                | path to the kernel sources                |
    +------------------+                                           |
    | SRCTREE          |                                           |
    +------------------+-------------------------------------------+
    | T                | private temporary directory               |
    |                  |                                           |
    +------------------+-------------------------------------------+
    | TMPDIR           | temporary directory                       |
    |                  |                                           |
    |                  | Do not rely on ``T == TMPDIR``            |
    |                  | or the contrary,                          |
    |                  | this might change in future.              |
    +------------------+-------------------------------------------+
    | ARCH             | target architecture as specified          |
    |                  | on the command line, or ``$(uname -m)``   |
    +------------------+-------------------------------------------+
    | KARCH            | target kernel architecture                |
    |                  |                                           |
    |                  | For instance, if ``ARCH`` is ``x86_64``,  |
    |                  | ``KARCH`` would be ``x86``.               |
    +------------------+-------------------------------------------+
    | SUBARCH          | *underlying kernel architecture*          |
    |                  |                                           |
    |                  | Usually equal to ``KARCH``.               |
    |                  | (Except for usermode builds ``KARCH=um``, |
    |                  | but it is not supported [yet?])           |
    +------------------+-------------------------------------------+
    | SRCARCH          | target kernel source architecture         |
    |                  |                                           |
    |                  | Usually equal to ``KARCH``.               |
    |                  | (due to how *kernelconfig* creates        |
    |                  | these vars)                               |
    +------------------+-------------------------------------------+
    | KVER             | full kernel version, e.g.                 |
    |                  | ``4.7.0-r1``, ``3.0.0``, ``4.5.1``        |
    +------------------+-------------------------------------------+
    | KV               | full kernel version without patchlevel    |
    |                  | unless it is an ``-rc`` version,          |
    |                  | e..g ``4.7.0-r1``, ``3.0``, ``4.5``       |
    +------------------+-------------------------------------------+
    | KMAJ             | kernel version,                           |
    |                  | e.g. ``4``, ``3``, ``4``                  |
    +------------------+-------------------------------------------+
    | KMIN             | kernel version sublevel,                  |
    |                  | e.g. ``7``, ``0``, ``5``                  |
    +------------------+-------------------------------------------+
    | KPATCH           | kernel version patchlevel,                |
    |                  | e.g. ``0``, ``0``, ``1``                  |
    +------------------+-------------------------------------------+


format variables
++++++++++++++++

All source types are subject to Python string formatting.

The available format variables are identical to the `environment vars`_,
except for ``TMPDIR`` (not set) and  ``T`` (special, see below).
Unlike the environment vars, the variable names are case-insensitive,
e.g. both ``{kv}`` and ``{KV}`` are accepted.

Additionally, the ``script`` and ``command`` type config sources
support *automatic format variables*,
which can be used to request additional tmpdirs/tmpfiles
and to tell kernelconfig where the output file(s) will be written to,
without having to specify a filesystem path.

These variables start with a keyword
and are optionally followed by an integer identifier.

The following *automatic format variables* exist:

``outconfig`` or ``out``
    Request a temporary file that will contain the input ``.config`` later on.

    The identifier can be used to request additional files.
    Note that ``{out}`` and ``{outconfig}`` will point to distinct files,
    and so do ``{out},  {out0}, {out00}, ..., {out9}, ...``.

    Example::

        [source]
        command wget 'http://...' -O '{outconfig}'

    (Note that a ``file``-type config
    source would be more appropriate in that case.)


``outfile``
    Similar to ``outconfig``, except that the temporary file
    will not be registered as input ``.config``.

    Example::

        [source]
        sh
        set -e
        wget 'http://...' -O '{outfile1}'
        wget 'http://...' -O '{outfile2}'
        cat '{outfile1}' '{outfile2}' > '{outconfig}'

``T``
    Request a temporary directory.

    If used without an identifier, request the default private tmpdir.

    If used with an identifier, creates a new one::

        [source]
        sh
        set -e
        wget 'http://.../file.tar' -O '{outfile}'        '
        tar x -C '{T0}' -f '{outfile}'
        ...



Getting Dynamic Sources
-----------------------

#. create output directory, temporary directory, if necessary

#. backup existing output file, if necessary

#. run script/command

   Set up environment variables
   \-- ``ARCH``, ``SUBARCH``, ``SRCARCH``, ``S``, ``T``

   * simple curated source: using builtin functions

   * python script: ``import`` and ``run(...)`` unless specified otherwise

   * other scripts, commands: ``subprocess.Popen(...)``

#. load or move the created config file

#. cache-copy the created config file

#. cleanup
