Quickstart
==========


Trafilatura is a tool that simplifies the process of turning raw HTML into structured, meaningful data. This quickstart guide will walk you through the main functions of the software package using Python or the command-line.


To get started, install Trafilatura using a Python package manager: ``pip install trafilatura``. For more details, see the `installation documentation <installation.html>`_. You can then import it into your Python script or code.


With Python
-----------

Basic extraction
^^^^^^^^^^^^^^^^

One of Trafilatura's main functions is extracting text from a web page. The only required argument is the input document (here a downloaded HTML file), the rest is optional.

This code snippet demonstrates the basic extraction process, where we fetch a URL and process the content.


.. code-block:: python

    # import the necessary functions
    >>> from trafilatura import fetch_url, extract

    # grab a HTML file to extract data from
    >>> downloaded = fetch_url('https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/')

    # output main content and comments as plain text
    >>> result = extract(downloaded)
    >>> print(result)


This will extract the text from the specified URL and print it to the console.


Customizing output
^^^^^^^^^^^^^^^^^^

To tailor the output to your specific requirements, Trafilatura allows you to convert the extracted data into various formats. Here are a couple of examples:

.. code-block:: python

    # change the output format to XML (allowing for preservation of document structure)
    >>> result = extract(downloaded, output_format="xml")

    # discard potential comments, extract metadata and change the output to JSON
    >>> extract(downloaded, output_format="json", include_comments=False)

    # set the output to Markdown and extract metadata
    >>> extract(downloaded, output_format="markdown", with_metadata=True)



Fast mode
^^^^^^^^^

You can bypass the use of fallback algorithms in fast mode. This can improve performance, but may affect the accuracy of the extraction:

.. code-block:: python

    # faster mode without backup extraction
    >>> result = extract(downloaded, no_fallback=True)


For a full list of options see `Python usage <usage-python.html>`_.


Extracting all text content
^^^^^^^^^^^^^^^^^^^^^^^^^^^

While the previous examples focused on extracting the main text from a webpage, Trafilatura also offers a function to extract all text content in a ``html2txt`` manner:

.. code-block:: python

    >>> from trafilatura import html2txt
    >>> html2txt(downloaded)


Metadata
^^^^^^^^

The tool can also extract specific information from a web page, such as the title, author, or publication date. You can use the ``extract_metadata`` function to do this:

.. code-block:: python

    >>> from trafilatura import fetch_url, extract_metadata
    >>> downloaded = fetch_url('https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/')
    >>> extract_metadata(downloaded)


On the command-line
-------------------


You can use URLs directly with the ``-u`` or ``--URL`` option:

.. code-block:: bash

    # outputs main content and comments as plain text
    $ trafilatura -u "https://github.blog/2019-03-29-leader-spotlight-erin-spiceland/"


For a detailed overview of available options, you can display the help message by running ``trafilatura -h``.


Additionally, you can pipe the HTML document (including the response body) to Trafilatura for extraction:

.. code-block:: bash

    $ cat myfile.html | trafilatura # use the contents of an already existing file
    $ < myfile.html trafilatura # same here


Extraction options are also available on the command-line and they can be combined:

.. code-block:: bash

    $ < myfile.html trafilatura --json --no-tables

Use ``--filename-template`` to control how output filenames are generated based on the URL and content.

.. code-block:: bash

    $ trafilatura -u "https://example.com/path/dirs" --filename-template "{domain}/{path_dirs}/{hash}.{ext}" --markdown -o output/

this will produce a file named ``example.com/path/dirs/uOHdo6wKo4IK0pkL.md`` in the ``output`` directory.

Further steps
-------------


For more information please refer to `usage documentation <usage.html>`_ and `tutorials <tutorials.html>`_.

.. hint::
     Explore Trafilatura's features interactively with this Python Notebook: `Trafilatura overview <https://github.com/adbar/trafilatura/blob/master/docs/Trafilatura_Overview.ipynb>`_
