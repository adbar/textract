Troubleshooting
===============

.. meta::
    :description lang=en:
        This page explains how to solve common issues about content extraction and downloads.
        They include missing content, paywalls, cookies, and networks.



.. hint::
    Trafilatura evolves over time, make sure you have the latest version to benefit from all documentation pages. The software is thoroughly tested but rare problems remain difficult to replicate as they are linked to a particular setting/OS/IP. For the rest, see the `list of open issues <https://github.com/adbar/trafilatura/issues>`_


Content extraction
------------------

Something is missing
^^^^^^^^^^^^^^^^^^^^

The extractor uses several fallbacks to make sure enough text is returned. Content extraction is a tradeoff between precision and recall, that is between desired and undesirable content. Being ready to accept more unwanted text makes it easier to gather more of the relevant text in the output. Here are ways to tackle the issue:

- Opting for ``favor_recall`` (Python) or ``--recall`` (CLI)
- Changing the minimum acceptable length in the settings
- Using the more basic `baseline <corefunctions.html#baseline>`_ or `html2txt <corefunctions.html#html2txt>`_ functions instead (which is also faster)


.. note::
    Trafilatura is geared towards article pages, blog posts, main text parts, etc. Results vary wildly on link lists, galleries or catalogs.


Beyond raw HTML
^^^^^^^^^^^^^^^

While downloading and processing raw HTML documents is much faster, it can be necessary to fully render the web page before further processing, e.g. because a page makes exhaustive use of JavaScript or because content is injected from multiple sources.

In such cases the way to go is to use a browser automation library like Playwright. For available alternatives see this `list of headless browsers <https://github.com/dhamaniasad/HeadlessBrowsers>`_.

For more refined masking and automation methods, see the `nodriver <https://github.com/ultrafunkamsterdam/nodriver>`_ and `browserforge <https://github.com/daijro/browserforge>`_ packages.



Bypassing paywalls
^^^^^^^^^^^^^^^^^^

A browser automation library can also be useful to bypass issues related to cookies and paywalls as it can be combined with a corresponding browser extension, e.g. iamdamdev's bypass-paywalls-chrome and available alternatives.



Downloads
---------

HTTP library
^^^^^^^^^^^^

In the default settings Trafilatura identifies itself in the `User-Agent header <https://en.wikipedia.org/wiki/User-Agent_header>`_. It may have been compromised by others on certain websites and thus blocked, see `this discussion <https://www.webmasterworld.com/search_engine_spiders/5090863.htm>`_.

For various reasons, it is also possible that the standard download utility doesn't come through. Using another one is then an option (see ``pycurl`` with Python and ``wget`` or ``curl`` on the command-line).

- Installing the additional download utility ``pycurl`` manually or using ``pip3 install trafilatura[all]`` can alleviate the problem: another download library is used, leading to different results.
- Several alternatives are available on the command-line, e.g. ``wget -O - "my_url" | trafilatura`` instead of ``trafilatura -u "my_url"``.
- Emulating a browser is also possible, see the information on headless browsing above.

Asynchronous processing can be more efficient than a multiprocessing in certain context, see for instance the ``aiohttp`` library.


.. note::
    Downloads may fail because your IP or user agent are blocked. Trafilatura's crawling and download capacities do not bypass such restrictions.


Managing cookies
^^^^^^^^^^^^^^^^

The standard library `cookiejar <https://docs.python.org/3/library/http.cookiejar.html>`_ can be used along ``urllib3`` in order to use cookies along with HTTP requests, see this `documentation pull request <https://github.com/urllib3/urllib3/pull/2474/files>`_.

Alternatively, cookies can be manually specified in a ``settings.cfg`` config file, separated by semicolons, e.g. ``COOKIE = yummy_cookie=choco; tasty_cookie=strawberry``.


Unavailable pages and link rot
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download issues can be addressed by retrieving the files somewhere else, i.e. from already existing internet archives like the Internet Archive or the CommonCrawl.

On the command-line you can use ``--archived`` to use the Internet Archive to retrieve pages for which download failed. A corresponding function in Python could look as follows:

.. code-block:: python

    # url is the target
    # downloaded is the result of the download
    # also needs a function fetch_url() or equivalent
    if downloaded is None:
        new_url = "https://web.archive.org/web/20/" + url
        downloaded = fetch_url(new_url)

This approach is generic as it fetches the last available snapshot from the archive.


Download first and extract later
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Since the they have distinct characteristics it can be useful to separate the infrastructure needed for download from the extraction. Using a custom IP or network infrastructure can also prevent your usual IP from getting banned.

For an approach using files from the Common Crawl and Trafilatura, see the external tool `datatrove/process_common_crawl_dump.py <https://github.com/huggingface/datatrove/blob/main/examples/process_common_crawl_dump.py>`_.


Invalid template variables and filenames
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you see an error about invalid template variables, check that your ``--filename-template`` string only uses supported values like ``{domain}``, ``{hash}``, etc.
Refer to the filename.py source for a complete list.

An error about unsafe characters in the filename template means that characters like ``<>``, ``:``, ``"`` were used outside of ``{variable}`` sections.
Make sure to only use alphanumeric characters, underscores, dashes and forward slashes in static parts of the template.