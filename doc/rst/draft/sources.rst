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

  * relative path, looked up in ``<settings dirs>/source/files``

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

  Possibly subject to Python string formatting.

* command::

    [source]
    cmd [...] <command> [<arg>...]

  The command line is subject to Python string formatting,
  make sure to escape ``{`` and ``}`` braces accordingly (``{{``, ``}}``).

* make target::

    [source]
    make <target> [<arg>...]

* curated source::

    [source]
    <name> [<arg>...]

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
