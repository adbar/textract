Settings and customization
==========================

.. meta::
    :description lang=en:
        Tailor Trafilatura to your needs. Its modular design and configuration options allow for
        extensive customization. See examples for Python and the command-line.


Tailor Trafilatura to your needs, its modular design and configuration options allow for extensive customization. In a nutshell, there are two main files which can be edited in order to modify the default download and extraction behavior:

1. ``settings.cfg`` (values designed to be adapted by the user)
2. ``settings.py`` (package-wide settings, advanced)


Configuration file
------------------

Text extraction can be parametrized by providing a custom configuration file which overrides the standard settings. Useful adjustments include download parameters, minimal extraction length, or de-duplication settings.


File structure
^^^^^^^^^^^^^^

The default file included in the package is `settings.cfg <https://github.com/adbar/trafilatura/blob/master/trafilatura/settings.cfg>`_ . Important values include:

- Download
   * ``DOWNLOAD_TIMEOUT = 30`` the time (in seconds) before requests are dropped
   * ``SLEEP_TIME = 5`` time between requests (higher is better to avoid detection)
   * ``USER_AGENTS`` and ``COOKIE`` are empty by default
- Input
   * ``MAX_FILE_SIZE = 20000000`` maximum acceptable size of input (in bytes)
   * ``MIN_FILE_SIZE = 10`` minimum acceptable size of input (in bytes)
- Extraction
   * ``MIN_EXTRACTED_SIZE = 250`` acceptable size in characters (used to trigger fallbacks)
   * ``MIN_OUTPUT_SIZE = 1`` absolute acceptable minimum for main text output
   * ``MIN_EXTRACTED_COMM_SIZE`` and ``MIN_OUTPUT_COMM_SIZE`` work the same for comment extraction
   * ``EXTRACTION_TIMEOUT = 30`` only active on the command-line: drop extraction after 30 seconds to prevent CPU usage due to erroneous or malicious files. Set to 0 if you see errors related to the ``signal`` module and/or use a module such as `defusedxml <https://github.com/tiran/defusedxml>`_
- Deduplication (not active by default)
   * ``MIN_DUPLCHECK_SIZE = 100`` minimum size in characters to run deduplication on
   * ``MAX_REPETITIONS = 2`` maximum number of duplicates allowed
- Metadata
   * ``EXTENSIVE_DATE_SEARCH = on`` set to ``off`` to deactivate ``htmldate``'s opportunistic search (lower recall, higher precision)
- Navigation
   * ``EXTERNAL_URLS = off`` do not take URLs from other websites in feeds and sitemaps (CLI mode)
   * ``MAX_REDIRECTS = 2``: maximum number of `URL redirections <https://en.wikipedia.org/wiki/URL_redirection>`_ to be followed. Set to 0 to not follow any redirection.


Using a custom file on the command-line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With the ``--config-file`` option, followed by the file name or path. All the required variables have to be present in the custom file.


Filename Generation
^^^^^^^^^^^^^^^^^^^^^
Two new options allow customizing how output filenames are generated:

--filename-template: Specify a template string for generating filenames, using variables like {domain}, {path}, {hash}, {ext}, etc. Example: --filename-template "{domain}/{hash}.{ext}"
--max-length: Set the maximum total path length, including directory components. The default is 250 characters. Example: --max-length 200

The filename template can include directory separators to preserve parts of the original URL's path structure. Unsafe characters are sanitized automatically. If the total path would exceed max-length, it is intelligently truncated while preserving key components.
Invalid variables or unsafe characters will raise an error.


Adapting settings in Python
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The standard `settings file <https://github.com/adbar/trafilatura/blob/master/trafilatura/settings.cfg>`_ can be modified, or a custom configuration file can be provided with the ``config`` parameter to the ``bare_extraction()`` and ``extract()`` functions.

In the following, a single default value is changed, which has an immediate effect on extraction. The resulting text is indeed too short and ends up being discarded. On the contrary, lowering default values can trigger a more opportunistic extraction.

.. code-block:: python

    # load necessary functions and data
    >>> from copy import deepcopy
    >>> from trafilatura import extract
    >>> from trafilatura.settings import DEFAULT_CONFIG

    # a very short HTML file
    >>> my_html = "<html><body><p>Text.</p></body></html>"

    # load the configuration and change the minimum output length
    >>> my_config = deepcopy(DEFAULT_CONFIG)
    >>> my_config['DEFAULT']['MIN_OUTPUT_SIZE'] = '1000'

    # apply new settings, extraction will fail
    >>> extract(my_html, config=my_config)
    >>>
    # default extraction works
    >>> extract(my_html)
    'Text.'


Alternatively, it is possible to override all standard settings by loading a new configuration file where all necessary values have been specified.

.. code-block:: python

    # load the required functions
    >>> from trafilatura import extract
    >>> from trafilatura.settings import use_config

    # load the new settings by providing a file name
    >>> newconfig = use_config("myfile.cfg")

    # use with a previously downloaded document
    >>> extract(downloaded, config=newconfig)

    # provide a file name directly (can be slower)
    >>> extract(downloaded, settingsfile="myfile.cfg")


.. note::
    Useful adjustments include download parameters, minimal extraction length, or de-duplication settings.
    User agent settings can also be specified in a custom ``settings.cfg`` file.


Package settings
----------------

For further configuration it is possible to edit package-wide variables contained in the `settings.py <https://github.com/adbar/trafilatura/blob/master/trafilatura/settings.py>`_ file provided with Trafilatura.

These settings notably include:

- Lists of HTML elements to accept or to discard
- Configuration of parallel processing
- Further download and deduplication settings
- Files written in CLI mode

Here is how to change them:

1. Find the locally installed version of the package or `clone the repository <https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository>`_
2. Edit ``settings.py``
3. Reinstall the package locally: ``pip install --no-deps -U .`` in the home directory of the cloned repository

These remaining variables greatly alter the functioning of the package!


.. hint::
    Starting from version 1.9, most extraction parameters and options can be defined in an object which is then passed to the extraction functions instead of the arguments and (in some cases) instead of the config file. See ``settings.py`` for an example.
