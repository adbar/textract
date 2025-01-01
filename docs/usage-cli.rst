On the command-line
===================

.. meta::
    :description lang=en:
        Trafilatura offers a robust CLI. Learn how to download and extract text from HTML web pages without writing code, including parallel processing and data mining capabilities.


Introduction
------------

Trafilatura offers a robust command-line interface and can be conveniently used without writing code.

For the very first steps:

- Multilingual `Introduction to the command-line interface <https://tutorial.djangogirls.org/en/intro_to_command_line/>`_
- Section of the `Introduction to Cultural Analytics & Python <https://melaniewalsh.github.io/Intro-Cultural-Analytics/01-Command-Line/01-The-Command-Line.html>`_


Quickstart
----------

All instructions for the terminal window are followed by pressing the enter key.


URLs can be used directly (``-u/--URL``):

.. code-block:: bash

    # outputs main content and comments as plain text ...
    $ trafilatura -u "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"

    # outputs main text with basic XML structure ...
    $ trafilatura --xml --URL "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"

    # displays help message
    $ trafilatura -h


You can also pipe a HTML document (and response body) to trafilatura:

.. code-block:: bash

    # use the contents of an already existing file
    $ cat myfile.html | trafilatura

    # alternative syntax
    $ < myfile.html trafilatura

    # use a custom download utility and pipe it to trafilatura
    $ wget -qO- "https://de.creativecommons.org/index.php/was-ist-cc/" | trafilatura


Extraction parameters
---------------------


Choice of HTML elements
~~~~~~~~~~~~~~~~~~~~~~~

Several elements can be included or discarded (see list of options below):

- Text elements
   - Comments and tables are extracted by default.
   - ``--no-comments`` and ``--no-tables`` deactivate these settings.

- Structural elements
   ``--formatting``
      Keep structural elements related to formatting (``<b>``/``<strong>``, ``<i>``/``<emph>`` etc.)
   ``--links``
      Keep link targets (in ``href="..."``), converting relative URLs to absolute where possible
   ``--images``
      Keep track of images along with their targets (``<img>`` attributes: alt, src, title)

.. note::
    Certain elements are only visible in the output if the chosen format allows it (e.g. images and XML). Including extra elements works best with conversion to XML/XML-TEI.

    The heuristics used by the main algorithm change according to the presence of certain elements in the HTML. If the output seems odd, try removing a constraint (e.g. formatting) to improve the result.


Output format
~~~~~~~~~~~~~

Output as TXT without metadata is the default, another format can be selected in two different ways:

-  ``--csv``, ``--html``, ``--json``, ``--markdown``, ``--xml`` or ``--xmltei``
-  ``--output-format`` {csv,json,html,markdown,txt,xml,xmltei}

.. hint::
    Combining TXT, CSV and JSON formats with certain structural elements (e.g. formatting or links) triggers output in Markdown format. Selecting Markdown automatically includes text formatting.

*HTML output is available from version 1.11, Markdown from version 1.9 onwards.*


Filename Customization
~~~~~~~~~~~~~~~~~~~~~~

Use ``--filename-template`` to control how output filenames are generated based on the URL and content. Supported variables:

- {domain}: Website domain
- {path}: URL path segments, joined by underscores
- {path_dirs}: URL path segments, joined by directory separators
- {params}: URL query parameters
- {hash}: Hash of extracted content
- {ext}: File extension
- {lang}: Identified language

Example: ``--filename-template "{domain}/{hash}.{ext}"``

Use ``--max-length`` to set the maximum total path length, including any directories. It defaults to 250 characters.

If the generated path would exceed this limit, it is intelligently truncated:
1. Individual directory and file components are preserved as long as possible.
2. The file component is reduced to a minimum of {hash}.{ext}.
3. The --output-dir is omitted from length calculations.

Example: ``--max-length 200``

Invalid template variables or unsafe path characters will raise an error.


Optimizing for precision and recall
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The arguments ``--precision`` or ``--recall`` can be passed to adjust the focus of the extraction process.

- If your results contain too much noise, prioritize precision to focus on the most central and relevant elements.
- If parts of your documents are missing, try this preset to take more elements into account.
- If parts of the contents are still missing, see `troubleshooting <troubleshooting.html>`_.


Language identification
~~~~~~~~~~~~~~~~~~~~~~~

Passing the argument ``--target-language`` along with a 2-letter code (ISO 639-1) will trigger language filtering of the output if the identification component has been `installed <installation.html>`_ and if the target language is available.

.. note::
    Additional components are required: ``pip install trafilatura[all]``.
    This feature currently uses the `py3langid package <https://github.com/adbar/py3langid>`_ and is dependent on language availability and performance of the original model.



Changing default settings
~~~~~~~~~~~~~~~~~~~~~~~~~

See `documentation page on settings <settings.html>`_.



Process files locally
---------------------

In case web pages have already been downloaded and stored, it is possible to process single files or directories as a whole. It can be especially helpful to separate download and extraction to circumvent blocking mechanisms, either by scrambling IPs used to access the pages or by using web browser automation software to bypass issues related to cookies and paywalls.

Trafilatura will work as well provided web pages (HTML documents) are used as input. Two major command line arguments are necessary:

-  ``--input-dir`` to select a directory to read files from
-  ``-o`` or ``--output-dir`` to define a directory to eventually store the results


.. note::
    In case no directory is selected, results are printed to standard output (*STDOUT*, e.g. in the terminal window).



Process a list of links
-----------------------

.. note::
    Beware that there should be a tacit scraping etiquette and that a server may block you after the download of a certain number of pages from the same website/domain in a short period of time.

    In addition, some websites may block the ``requests`` `user-agent <https://en.wikipedia.org/wiki/User_agent>`_. Thus, *trafilatura* waits a few seconds per default between requests.

    For more information see the `page on downloads <downloads.html>`_.


Two major command line arguments are necessary here:

-  ``-i`` or ``--input-file`` to select an input list to read links from.

   This option allows for bulk download and processing of a list of URLs from a file listing one link per line. The input list will be read sequentially, only lines beginning with a valid URL will be read, the file can thus contain other information which will be discarded.

-  ``-o`` or ``--output-dir`` to define a directory to eventually store the results.

   The output directory can be created on demand, but it must be writable.


.. code-block:: bash

    $ trafilatura -i list.txt -o txtfiles/		# output as raw text
    $ trafilatura --xml -i list.txt -o xmlfiles/	# output in XML format


.. hint::
    Backup of HTML sources can be useful for archival and further processing:

    ``$ trafilatura --input-file links.txt --output-dir converted/ --backup-dir html-sources/ --xml``


Internet Archive
~~~~~~~~~~~~~~~~

Using the option ``--archived`` will trigger queries to the `Internet Archive <https://web.archive.org/>`_ for web pages which could not be downloaded.

There is a fair chance to find archived versions for larger websites, whereas pages of lesser-known websites may not have been preserved there. The retrieval process is slow as it depends on a single web portal only, it is best performed for a relatively small number of URLs.


Link discovery
--------------

Link discovery can be performed over `web feeds <https://en.wikipedia.org/wiki/Web_feed>`_ (Atom and RSS, mostly for fresh content), `sitemaps <https://en.wikipedia.org/wiki/Sitemaps>`_ for exhaustivity (all potential pages as listed by the owners), and discovery by web crawling (i.e. by following the internal links, more experimental).

Both the homepage and a particular page can be used as input depending on the selected options (e.g. a sitemap or feed URL).

The ``--list`` option is useful to list URLs prior to processing. This option can be combined with an input file (``-i``) containing a list of sources which will then be processed in parallel.

For more information please refer to the `tutorial on content discovery <tutorial0.html#content-discovery>`_.

Feeds
~~~~~

.. code-block:: bash

    # automatically detecting feeds starting from the homepage
    $ trafilatura --feed "https://www.dwds.de/" --list

    # already known feed
    $ trafilatura --feed "https://www.dwds.de/api/feed/themenglossar/Corona" --list

    # processing a list in parallel
    $ trafilatura -i mylist.txt --feed --list


.. raw:: html

    <iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/NW2ISdOx08M?start=406" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


Youtube tutorial: `Extracting links from web feeds <https://www.youtube.com/watch?v=NW2ISdOx08M&list=PL-pKWbySIRGMgxXQOtGIz1-nbfYLvqrci&index=2&t=398s>`_


Sitemaps
~~~~~~~~

.. code-block:: bash

    # run link discovery through a sitemap for sitemaps.org and store the resulting links in a file
    $ trafilatura --sitemap "https://www.sitemaps.org/" --list > mylinks.txt

    # using an already known sitemap URL
    $ trafilatura --sitemap "https://www.sitemaps.org/sitemap.xml" --list

    # targeting webpages in German
    $ trafilatura --sitemap "https://www.sitemaps.org/" --list --target-language "de"


For more information on sitemap use and filters for lists of links see this blog post: `Using sitemaps to crawl websites <https://adrien.barbaresi.eu/blog/using-sitemaps-crawl-websites.html>`_.


.. raw:: html

    <iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/uWUyhxciTOs?start=330" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


Youtube tutorial: `Listing all website contents with sitemaps <https://www.youtube.com/watch?v=uWUyhxciTOs&list=PL-pKWbySIRGMgxXQOtGIz1-nbfYLvqrci&index=3&t=330s>`_


Web crawling
~~~~~~~~~~~~

Selecting the ``--crawl`` option automatically looks for pages by following a fixed number of internal links on the website, starting from the given URL and returning a list of links.

See the `page on web crawling <crawls.html>`_ for more information.


URL inspection prior to download and processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: bash

    $ trafilatura --sitemap "https://www.sitemaps.org/" --list --url-filter "https://www.sitemaps.org/de"
    $ trafilatura --sitemap "https://www.sitemaps.org/" --list --url-filter "protocol"

Using a subpart of the site also acts like a filter, for example ``--sitemap "https://www.sitemaps.org/de/"``.

For more information on sitemap use and filters for lists of links see this blog post: `Using sitemaps to crawl websites <https://adrien.barbaresi.eu/blog/using-sitemaps-crawl-websites.html>`_ and this `tutorial on link filtering <tutorial0.html#link-filtering>`_.


Deprecations
------------

The following arguments have been deprecated since inception:

- ``--nocomments`` and ``--notables`` → ``--no-comments`` and ``--no-tables``
- ``--inputfile``, ``--inputdir``, and ``--outputdir`` → ``--input-file``, ``--input-dir``, and ``--output-dir``
- ``-out`` → ``--output-format``
- ``--hash-as-name`` → hashes used by default
- ``--with-metadata`` (include metadata) had once the effect of today's ``--only-with-metadata`` (only documents with necessary metadata)



Further information
-------------------


.. hint::
    See also `how to modify the default settings <settings.html>`_.


For all usage instructions see ``trafilatura -h``:

.. code-block:: bash

    trafilatura [-h] [-i INPUTFILE | --input-dir INPUTDIR | -u URL]
                   [--parallel PARALLEL] [-b BLACKLIST] [--list]
                   [-o OUTPUTDIR] [--backup-dir BACKUP_DIR] [--keep-dirs]
                   [--filename-template FILENAME_TEMPLATE] [--max-length MAX_LENGTH]
                   [--feed [FEED] | --sitemap [SITEMAP] | --crawl [CRAWL] |
                   --explore [EXPLORE] | --probe [PROBE]] [--archived]
                   [--url-filter URL_FILTER [URL_FILTER ...]] [-f]
                   [--formatting] [--links] [--images] [--no-comments]
                   [--no-tables] [--only-with-metadata] [--with-metadata]
                   [--target-language TARGET_LANGUAGE] [--deduplicate]
                   [--config-file CONFIG_FILE] [--precision] [--recall]
                   [--output-format {csv,json,html,markdown,txt,xml,xmltei} |
                   --csv | --html | --json | --markdown | --xml | --xmltei]
                   [--validate-tei] [-v] [--version]


Command-line interface for Trafilatura

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         increase logging verbosity (-v or -vv)
  --version             show version information and exit

Input:
  URLs, files or directories to process

  -i INPUT_FILE, --input-file INPUT_FILE
                        name of input file for batch processing
  --input-dir INPUT_DIR
                        read files from a specified directory (relative path)
  -u URL, --URL URL     custom URL download
  --parallel PARALLEL   specify a number of cores/threads for downloads and/or
                        processing
  -b BLACKLIST, --blacklist BLACKLIST
                        file containing unwanted URLs to discard during
                        processing

Output:
  Determines if and how files will be written

  --list                display a list of URLs without downloading them
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        write results in a specified directory (relative path)
  --backup-dir BACKUP_DIR
                        preserve a copy of downloaded files in a backup
                        directory
  --keep-dirs           keep input directory structure and file names
  --filename-template FILENAME_TEMPLATE
                        template for generating filenames (e.g.
                        {domain}/{path}-{hash}.{ext})
  --max-length MAX_LENGTH
                        maximum length for generated file paths

Navigation:
  Link discovery and web crawling

.. code-block:: bash

  --feed [FEED]         look for feeds and/or pass a feed URL as input
  --sitemap [SITEMAP]   look for sitemaps for the given website and/or enter a sitemap URL
  --crawl [CRAWL]       crawl a fixed number of pages within a website starting from the given URL
  --explore [EXPLORE]   explore the given websites (combination of sitemap and crawl)
  --probe [PROBE]       probe for extractable content (works best with target language)
  --archived            try to fetch URLs from the Internet Archive if downloads fail
  --url-filter URL_FILTER [URL_FILTER ...] only process/output URLs containing these patterns (space-separated strings)

Extraction:
  Customization of text and metadata processing

  -f, --fast            fast (without fallback detection)
  --formatting          include text formatting (bold, italic, etc.)
  --links               include links along with their targets (experimental)
  --images              include image sources in output (experimental)
  --no-comments         don't output any comments
  --no-tables           don't output any table elements
  --only-with-metadata  only output those documents with title, URL and date
  --with-metadata       extract and add metadata to the output
  --target-language TARGET_LANGUAGE
                        select a target language (ISO 639-1 codes)
  --deduplicate         filter out duplicate documents and sections
  --config-file CONFIG_FILE
                        override standard extraction parameters with a custom
                        config file
  --precision           favor extraction precision (less noise, possibly less
                        text)
  --recall              favor extraction recall (more text, possibly more
                        noise)

Format:
  Selection of the output format

.. code-block:: bash

  --output-format {csv,json,html,markdown,txt,xml,xmltei}
                        determine output format
  --csv                 shorthand for CSV output
  --html                shorthand for HTML output
  --json                shorthand for JSON output
  --markdown            shorthand for MD output
  --xml                 shorthand for XML output
  --xmltei              shorthand for XML TEI output
  --validate-tei        validate XML TEI output
