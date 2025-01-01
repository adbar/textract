# Trafilatura: Discover and Extract Text Data on the Web

<br/>

<img alt="Trafilatura Logo" src="https://raw.githubusercontent.com/adbar/trafilatura/master/docs/trafilatura-logo.png" align="center" width="60%"/>

<br/>

[![Python package](https://img.shields.io/pypi/v/trafilatura.svg)](https://pypi.python.org/pypi/trafilatura)
[![Python versions](https://img.shields.io/pypi/pyversions/trafilatura.svg)](https://pypi.python.org/pypi/trafilatura)
[![Documentation Status](https://readthedocs.org/projects/trafilatura/badge/?version=latest)](http://trafilatura.readthedocs.org/en/latest/?badge=latest)
[![Code Coverage](https://img.shields.io/codecov/c/github/adbar/trafilatura.svg)](https://codecov.io/gh/adbar/trafilatura)
[![Downloads](https://static.pepy.tech/badge/trafilatura/month)](https://pepy.tech/project/trafilatura)
[![Reference DOI: 10.18653/v1/2021.acl-demo.15](https://img.shields.io/badge/DOI-10.18653%2Fv1%2F2021.acl--demo.15-blue)](https://aclanthology.org/2021.acl-demo.15/)

<br/>

<img alt="Demo as GIF image" src="https://raw.githubusercontent.com/adbar/trafilatura/master/docs/trafilatura-demo.gif" align="center" width="80%"/>

<br/>


## Introduction

Trafilatura is a cutting-edge **Python package and command-line tool**
designed to **gather text on the Web and simplify the process of turning
raw HTML into structured, meaningful data**. It includes all necessary
discovery and text processing components to perform **web crawling,
downloads, scraping, and extraction** of main texts, metadata and
comments. It aims at staying **handy and modular**: no database is
required, the output can be converted to commonly used formats.

Going from HTML bulk to essential parts can alleviate many problems
related to text quality, by **focusing on the actual content**,
**avoiding the noise** caused by recurring elements like headers and footers
and by **making sense of the data and metadata** with selected information.
The extractor strikes a balance between limiting noise (precision) and
including all valid parts (recall). It is **robust and reasonably fast**.

Trafilatura is [widely used](https://trafilatura.readthedocs.io/en/latest/used-by.html)
and integrated into [thousands of projects](https://github.com/adbar/trafilatura/network/dependents>)
by companies like HuggingFace, IBM, and Microsoft Research as well as institutions like
the Allen Institute, Stanford, the Tokyo Institute of Technology, and
the University of Munich.


### Features

- Advanced web crawling and text discovery:
   - Support for sitemaps (TXT, XML) and feeds (ATOM, JSON, RSS)
   - Smart crawling and URL management (filtering and deduplication)

- Parallel processing of online and offline input:
   - Live URLs, efficient and polite processing of download queues
   - Previously downloaded HTML files and parsed HTML trees

- Robust and configurable extraction of key elements:
   - Main text (common patterns and generic algorithms like jusText and readability)
   - Metadata (title, author, date, site name, categories and tags)
   - Formatting and structure: paragraphs, titles, lists, quotes, code, line breaks, in-line text formatting
   - Optional elements: comments, links, images, tables

- Multiple output formats:
   - TXT and Markdown
   - CSV
   - JSON
   - HTML, XML and [XML-TEI](https://tei-c.org/)

- Flexible output file naming:
   - Template-based filename generation with variables like {domain}, {path}, {hash}
   - Path length control and automatic truncation
   - Safe character handling and URL component parsing

- Optional add-ons:
   - Language detection on extracted content
   - Speed optimizations

- Actively maintained with support from the open-source community:
   - Regular updates, feature additions, and optimizations
   - Comprehensive documentation

### Evaluation and alternatives

Trafilatura consistently outperforms other open-source libraries in text
extraction benchmarks, showcasing its efficiency and accuracy in
extracting web content. The extractor tries to strike a balance between
limiting noise and including all valid parts.

For more information see the [benchmark section](https://trafilatura.readthedocs.io/en/latest/evaluation.html)
and the [evaluation readme](https://github.com/adbar/trafilatura/blob/master/tests/README.rst)
to run the evaluation with the latest data and packages.


#### Other evaluations:

- Most efficient open-source library in *ScrapingHub*'s [article extraction benchmark](https://github.com/scrapinghub/article-extraction-benchmark)
- Best overall tool according to [Bien choisir son outil d'extraction de contenu à partir du Web](https://hal.archives-ouvertes.fr/hal-02768510v3/document)
  (Lejeune & Barbaresi 2020)
- Best single tool by ROUGE-LSum Mean F1 Page Scores in [An Empirical Comparison of Web Content Extraction Algorithms](https://webis.de/downloads/publications/papers/bevendorff_2023b.pdf)
  (Bevendorff et al. 2023)


## Usage and documentation

[Getting started with Trafilatura](https://trafilatura.readthedocs.io/en/latest/quickstart.html)
is straightforward. For more information and detailed guides, visit
[Trafilatura's documentation](https://trafilatura.readthedocs.io/):

- [Installation](https://trafilatura.readthedocs.io/en/latest/installation.html)
- Usage:
  [On the command-line](https://trafilatura.readthedocs.io/en/latest/usage-cli.html),
  [With Python](https://trafilatura.readthedocs.io/en/latest/usage-python.html),
  [With R](https://trafilatura.readthedocs.io/en/latest/usage-r.html)
- [Core Python functions](https://trafilatura.readthedocs.io/en/latest/corefunctions.html)
- Interactive Python Notebook: [Trafilatura Overview](docs/Trafilatura_Overview.ipynb)
- [Tutorials and use cases](https://trafilatura.readthedocs.io/en/latest/tutorials.html)

Youtube playlist with video tutorials in several languages:

- [Web scraping tutorials and how-tos](https://www.youtube.com/watch?v=8GkiOM17t0Q&list=PL-pKWbySIRGMgxXQOtGIz1-nbfYLvqrci)


## License

This package is distributed under the [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0.html).

Versions prior to v1.8.0 are under GPLv3+ license.


### Contributing

Contributions of all kinds are welcome. Visit the [Contributing
page](https://github.com/adbar/trafilatura/blob/master/CONTRIBUTING.md)
for more information. Bug reports can be filed on the [dedicated issue
page](https://github.com/adbar/trafilatura/issues).

Many thanks to the
[contributors](https://github.com/adbar/trafilatura/graphs/contributors)
who extended the docs or submitted bug reports, features and bugfixes!


## Context

This work started as a PhD project at the crossroads of linguistics and
NLP, this expertise has been instrumental in shaping Trafilatura over
the years. Initially launched to create text databases for research purposes
at the Berlin-Brandenburg Academy of Sciences (DWDS and ZDL units),
this package continues to be maintained but its future depends on community support.

**If you value this software or depend on it for your product, consider
sponsoring it and contributing to its codebase**. Your support
[on GitHub](https://github.com/sponsors/adbar) or [ko-fi.com](https://ko-fi.com/adbarbaresi)
will help maintain and enhance this popular package.

*Trafilatura* is an Italian word for [wire
drawing](https://en.wikipedia.org/wiki/Wire_drawing) symbolizing the
refinement and conversion process. It is also the way shapes of pasta
are formed.

### Author

Reach out via ia the software repository or the [contact
page](https://adrien.barbaresi.eu/) for inquiries, collaborations, or
feedback. See also social networks for the latest updates.

-   Barbaresi, A. [Trafilatura: A Web Scraping Library and Command-Line
    Tool for Text Discovery and
    Extraction](https://aclanthology.org/2021.acl-demo.15/), Proceedings
    of ACL/IJCNLP 2021: System Demonstrations, 2021, p. 122-131.
-   Barbaresi, A. "[Generic Web Content Extraction with Open-Source
    Software](https://hal.archives-ouvertes.fr/hal-02447264/document)",
    Proceedings of KONVENS 2019, Kaleidoscope Abstracts, 2019.
-   Barbaresi, A. "[Efficient construction of metadata-enhanced web
    corpora](https://hal.archives-ouvertes.fr/hal-01371704v2/document)",
    Proceedings of the [10th Web as Corpus Workshop
    (WAC-X)](https://www.sigwac.org.uk/wiki/WAC-X), 2016.


### Citing Trafilatura

Trafilatura is widely used in the academic domain, chiefly for data
acquisition. Here is how to cite it:

[![Reference DOI: 10.18653/v1/2021.acl-demo.15](https://img.shields.io/badge/DOI-10.18653%2Fv1%2F2021.acl--demo.15-blue)](https://aclanthology.org/2021.acl-demo.15/)
[![Zenodo archive DOI: 10.5281/zenodo.3460969](https://zenodo.org/badge/DOI/10.5281/zenodo.3460969.svg)](https://doi.org/10.5281/zenodo.3460969)

``` shell
@inproceedings{barbaresi-2021-trafilatura,
  title = {{Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction}},
  author = "Barbaresi, Adrien",
  booktitle = "Proceedings of the Joint Conference of the 59th Annual Meeting of the Association for Computational Linguistics and the 11th International Joint Conference on Natural Language Processing: System Demonstrations",
  pages = "122--131",
  publisher = "Association for Computational Linguistics",
  url = "https://aclanthology.org/2021.acl-demo.15",
  year = 2021,
}
```


### Software ecosystem

Jointly developed plugins and additional packages also contribute to the
field of web data extraction and analysis:

<img alt="Software ecosystem" src="https://raw.githubusercontent.com/adbar/htmldate/master/docs/software-ecosystem.png" align="center" width="65%"/>

Corresponding posts can be found on [Bits of
Language](https://adrien.barbaresi.eu/blog/tag/trafilatura.html).

Impressive, you have reached the end of the page: Thank you for your
interest!
