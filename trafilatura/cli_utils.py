"""
Functions dedicated to command-line processing.
"""

try:
    import gzip
    HAS_GZIP = True
except ImportError:
    HAS_GZIP = False

import logging
import random
import re
import string
import sys
import traceback

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import partial
from os import makedirs, path, stat, walk
from threading import RLock
from typing import Any, Generator, List, Optional, Set, Tuple

from courlan import UrlStore, extract_domain, get_base_url  # validate_url

from trafilatura import spider
from trafilatura.filename import FilenameTemplate, generate_hash_filename

from .baseline import html2txt
from .core import extract
from .downloads import (
    Response,
    add_to_compressed_dict,
    buffered_downloads,
    buffered_response_downloads,
    load_download_buffer
)
from .feeds import find_feed_urls
from .meta import reset_caches
from .settings import (
    Extractor,
    FILENAME_LEN,
    MAX_FILES_PER_DIRECTORY,
    args_to_extractor,
)
from .sitemaps import sitemap_search
from .utils import (
    LANGID_FLAG,
    URL_BLACKLIST_REGEX,
    is_acceptable_length,
    language_classifier,
    make_chunks,
)


LOGGER = logging.getLogger(__name__)

random.seed(345)  # make generated file names reproducible
CHAR_CLASS = string.ascii_letters + string.digits

STRIP_DIR = re.compile(r"[^/]+$")
STRIP_EXTENSION = re.compile(r"\.[a-z]{2,5}$")

INPUT_URLS_ARGS = ["URL", "crawl", "explore", "probe", "feed", "sitemap"]

EXTENSION_MAPPING = {
    "csv": ".csv",
    "json": ".json",
    "markdown": ".md",
    "xml": ".xml",
    "xmltei": ".xml",
}


def load_input_urls(args: Any) -> List[str]:
    "Read list of URLs to process or derive one from command-line arguments."
    input_urls: List[str] = []

    if args.input_file:
        try:
            # optional: errors='strict', buffering=1
            with open(args.input_file, mode="r", encoding="utf-8") as inputfile:
                input_urls.extend(line.strip() for line in inputfile)
        except UnicodeDecodeError:
            sys.exit("ERROR: system, file type or buffer encoding")
    else:
        for arg in INPUT_URLS_ARGS:
            if getattr(args, arg):
                input_urls = [getattr(args, arg)]
                break

    if not input_urls:
        LOGGER.warning("No input provided")

    # uniq URLs while preserving order (important)
    return list(dict.fromkeys(input_urls))


def load_blacklist(filename: str) -> Set[str]:
    "Read list of unwanted URLs."
    with open(filename, "r", encoding="utf-8") as inputfh:
        # if validate_url(url)[0] is True:
        blacklist = {URL_BLACKLIST_REGEX.sub("", line.strip()) for line in inputfh}
    return blacklist


def load_input_dict(args: Any) -> UrlStore:
    "Read input list of URLs to process and build a domain-aware dictionary."
    inputlist = load_input_urls(args)
    # deduplicate, filter and convert to dict
    return add_to_compressed_dict(
        inputlist,
        blacklist=args.blacklist,
        compression=(args.sitemap and not args.list),
        url_filter=args.url_filter,
        verbose=args.verbose,
    )


def check_outputdir_status(directory: str) -> bool:
    "Check if the output directory is within reach and writable."
    # check the directory status
    if not path.exists(directory) or not path.isdir(directory):
        try:
            makedirs(directory, exist_ok=True)
        except OSError:
            # maybe the directory has already been created
            # sleep(0.25)
            # if not path.exists(directory) or not path.isdir(directory):
            sys.stderr.write(
                "ERROR: Destination directory cannot be created: " + directory + "\n"
            )
            # raise OSError()
            return False
    return True


def determine_counter_dir(dirname: str, c: int) -> str:
    "Return a destination directory based on a file counter."
    c_dir = str(int(c / MAX_FILES_PER_DIRECTORY) + 1) if c >= 0 else ""
    return path.join(dirname, c_dir)


def get_writable_path(destdir: str, extension: str) -> Tuple[str, str]:
    "Find a writable path and return it along with its random file name."
    output_path = None
    while output_path is None or path.exists(output_path):
        # generate a random filename of the desired length
        filename = "".join(random.choice(CHAR_CLASS) for _ in range(FILENAME_LEN))
        output_path = path.join(destdir, filename + extension)
    return output_path, filename


def determine_output_path(
    args: Any,
    orig_filename: str,
    content: str,
    counter: int = -1,
    new_filename: Optional[str] = None,
) -> Tuple[str, str]:
    "Pick a directory based on selected options and a file name based on output type."
    # determine extension, TXT by default
    extension = EXTENSION_MAPPING.get(args.output_format, ".txt")

    if hasattr(args, "filename_template") and args.filename_template:
        # Initialize template with configuration
        template = FilenameTemplate(
            template=args.filename_template,
            max_length=args.max_length,
            output_dir=args.output_dir,
            lang=args.target_language,
            ext=extension,
        )

        try:
            output_path, destination_dir = template.generate(
                content=content,
                url=args.URL,
                filename=new_filename or orig_filename
            )
            return output_path, destination_dir

        except ValueError as e:
            # Log the error and fall back to hash-based filename
            LOGGER.warning("Template generation failed: %s. Falling back to hash-based name.", str(e))
            filename = generate_hash_filename(content)
            full_path = path.join(args.output_dir, filename + extension)
            return args.output_dir, full_path

    else:
        # Original behavior for backward compatibility
        if args.keep_dirs:
            # strip directory
            original_dir = STRIP_DIR.sub("", orig_filename)
            destination_dir = path.join(args.output_dir, original_dir)
            # strip extension
            filename = STRIP_EXTENSION.sub("", orig_filename)
        else:
            destination_dir = determine_counter_dir(args.output_dir, counter)
            # use cryptographic hash on file contents to define name
            filename = new_filename or generate_hash_filename(content)

        output_path = path.join(destination_dir, filename + extension)
        return output_path, destination_dir


def archive_html(htmlstring: str, args: Any, counter: int = -1) -> str:
    "Write a copy of raw HTML in backup directory."
    destination_directory = determine_counter_dir(args.backup_dir, counter)
    output_path, filename = get_writable_path(destination_directory, ".html.gz")
    # check the directory status
    if check_outputdir_status(destination_directory) is True and HAS_GZIP:
        # write
        with gzip.open(output_path, "wb") as outputfile:
            outputfile.write(htmlstring.encode("utf-8"))
    return filename


def write_result(
    result: Optional[str],
    args: Any,
    orig_filename: str = "",
    counter: int = -1,
    new_filename: Optional[str] = None,
) -> None:
    """Deal with result (write to STDOUT or to file)"""
    if result is None:
        return
    if args.output_dir is None:
        sys.stdout.write(result + "\n")
    else:
        destination_path, destination_dir = determine_output_path(
            args, orig_filename, result, counter, new_filename
        )
        # check the directory status
        if check_outputdir_status(destination_dir) is True:
            with open(destination_path, mode="w", encoding="utf-8") as outputfile:
                outputfile.write(result)


def generate_filelist(inputdir: str) -> Generator[str, None, None]:
    "Walk the directory tree and output all file names."
    for root, _, inputfiles in walk(inputdir):
        for fname in inputfiles:
            yield path.join(root, fname)


def file_processing(
    filename: str, args: Any, counter: int = -1, options: Optional[Extractor] = None
) -> None:
    "Aggregated functions to process a file in a list."
    if not options:
        options = args_to_extractor(args)
    options.source = filename

    with open(filename, "rb") as inputf:
        htmlstring = inputf.read()

    file_stat = stat(filename)
    ref_timestamp = min(file_stat.st_ctime, file_stat.st_mtime)
    options.date_params["max_date"] = datetime.fromtimestamp(ref_timestamp).strftime(
        "%Y-%m-%d"
    )

    result = examine(htmlstring, args, options=options)
    write_result(result, args, filename, counter, new_filename=None)


def process_result(
    htmlstring: str, args: Any, counter: int, options: Optional[Extractor]
) -> int:
    "Extract text and metadata from a download webpage and eventually write out the result."
    # backup option
    fileslug = archive_html(htmlstring, args, counter) if args.backup_dir else ""
    # process
    result = examine(htmlstring, args, options=options)
    write_result(
        result, args, orig_filename=fileslug, counter=counter, new_filename=fileslug
    )
    # increment written file counter
    if counter >= 0 and result:
        counter += 1
    return counter


def download_queue_processing(
    url_store: UrlStore, args: Any, counter: int, options: Extractor
) -> Tuple[List[str], int]:
    "Implement a download queue consumer, single- or multi-threaded."
    errors = []
    sleep_time = options.config.getfloat("DEFAULT", "SLEEP_TIME")

    while not url_store.done:
        bufferlist, url_store = load_download_buffer(url_store, sleep_time)
        # process downloads
        for url, result in buffered_downloads(
            bufferlist, args.parallel, options=options
        ):
            # handle result
            if result and isinstance(result, str):
                options.url = url
                counter = process_result(result, args, counter, options)
            else:
                LOGGER.warning("No result for URL: %s", url)
                errors.append(url)
    return errors, counter


def cli_discovery(args: Any) -> int:
    "Group CLI functions dedicated to URL discovery."
    url_store = load_input_dict(args)
    input_urls = url_store.dump_urls()
    if args.list:
        url_store.reset()

    options = args_to_extractor(args)
    func = partial(
        find_feed_urls if args.feed else sitemap_search,
        target_lang=args.target_language,
        external=options.config.getboolean("DEFAULT", "EXTERNAL_URLS"),
        sleep_time=options.config.getfloat("DEFAULT", "SLEEP_TIME"),
    )
    lock = RLock()

    # link discovery and storage
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = (executor.submit(func, url) for url in input_urls)
        # process results from the parallel threads and add them
        # to the compressed URL dictionary for further processing
        for future in as_completed(futures):
            if future.result() is not None:
                url_store.add_urls(future.result())
                # empty buffer in order to spare memory
                if args.list and len(url_store.get_known_domains()) >= args.parallel:
                    with lock:
                        url_store.print_unvisited_urls()
                        url_store.reset()
                        reset_caches()

    # process the (rest of the) links found
    exit_code = url_processing_pipeline(args, url_store)

    # activate site explorer
    if args.explore:
        # add to compressed dict and crawl the remaining websites
        control_dict = build_exploration_dict(url_store, input_urls, args)
        cli_crawler(args, url_store=control_dict, options=options)

    return exit_code


def build_exploration_dict(
    url_store: UrlStore, input_urls: List[str], args: Any
) -> UrlStore:
    "Find domains for which nothing has been found and add info to the crawl dict."
    input_domains = {extract_domain(u) for u in input_urls}
    still_to_crawl = input_domains - {
        extract_domain(u) for u in url_store.get_known_domains()
    }
    new_input_urls = [u for u in input_urls if extract_domain(u) in still_to_crawl]
    return add_to_compressed_dict(
        new_input_urls,
        blacklist=args.blacklist,
        url_filter=args.url_filter,
        verbose=args.verbose,
    )


def cli_crawler(
    args: Any,
    n: int = 30,
    url_store: Optional[UrlStore] = None,
    options: Optional[Extractor] = None,
) -> None:
    """Start a focused crawler which downloads a fixed number of URLs within a website
    and prints the links found in the process."""
    options = options or args_to_extractor(args)
    sleep_time = options.config.getfloat("DEFAULT", "SLEEP_TIME")
    param_dict = {}

    # load input URLs
    if url_store is None:
        spider.URL_STORE.add_urls(load_input_urls(args))
    else:
        spider.URL_STORE = url_store

    # load crawl data
    for hostname in spider.URL_STORE.get_known_domains():
        if spider.URL_STORE.urldict[hostname].tuples:
            startpage = spider.URL_STORE.get_url(hostname, as_visited=False)
            if startpage:
                param_dict[hostname] = spider.init_crawl(
                    startpage, lang=args.target_language
                )
            # update info
            # TODO: register changes?
            # if base_url != hostname:
            # ...

    # iterate until the threshold is reached
    while not spider.URL_STORE.done:
        bufferlist, spider.URL_STORE = load_download_buffer(
            spider.URL_STORE, sleep_time
        )
        for url, result in buffered_response_downloads(
            bufferlist, args.parallel, options=options
        ):
            if result and isinstance(result, Response):
                spider.process_response(result, param_dict[get_base_url(url)])
        # early exit if maximum count is reached
        if any(c >= n for c in spider.URL_STORE.get_all_counts()):
            break

    print("\n".join(u for u in spider.URL_STORE.dump_urls()))


def probe_homepage(args: Any) -> None:
    "Probe websites for extractable content and print the fitting ones."
    input_urls = load_input_urls(args)
    options = args_to_extractor(args)

    for url, result in buffered_downloads(
        input_urls, args.parallel, options=options
    ):
        if result is not None:
            result = html2txt(result)
            if (
                result
                and len(result) > options.min_extracted_size  # type: ignore[attr-defined]
                and any(c.isalpha() for c in result)
            ):
                if (
                    not LANGID_FLAG
                    or not args.target_language
                    or language_classifier(result, "") == args.target_language
                ):
                    print(url, flush=True)


def _define_exit_code(errors: List[str], total: int) -> int:
    """Compute exit code based on the number of errors:
    0 if there are no errors, 126 if there are too many, 1 otherwise."""
    ratio = len(errors) / total if total > 0 else 0

    if ratio > 0.99:
        return 126
    if errors:
        return 1
    return 0


def url_processing_pipeline(args: Any, url_store: UrlStore) -> int:
    "Aggregated functions to show a list and download and process an input list."
    if args.list:
        url_store.print_unvisited_urls()  # and not write_result()
        return False  # and not sys.exit(0)

    options = args_to_extractor(args)
    url_count = url_store.total_url_number()
    counter = 0 if url_count > MAX_FILES_PER_DIRECTORY else -1

    # download strategy
    errors, counter = download_queue_processing(url_store, args, counter, options)
    LOGGER.debug("%s / %s URLs could not be found", len(errors), url_count)

    if args.archived is True:
        url_store = UrlStore()
        url_store.add_urls(["https://web.archive.org/web/20/" + e for e in errors])
        if len(url_store.find_known_urls("https://web.archive.org")) > 0:
            archived_errors, _ = download_queue_processing(
                url_store, args, counter, options
            )
            LOGGER.debug(
                "%s archived URLs out of %s could not be found",
                len(archived_errors),
                len(errors),
            )
            # pass information along if URLs are missing
            return _define_exit_code(archived_errors, url_store.total_url_number())

    return _define_exit_code(errors, url_count)


def file_processing_pipeline(args: Any) -> None:
    "Define batches for parallel file processing and perform the extraction."
    filecounter = -1
    options = args_to_extractor(args)
    timeout = options.config.getint("DEFAULT", "EXTRACTION_TIMEOUT")

    # max_tasks_per_child available in Python >= 3.11
    with ProcessPoolExecutor(max_workers=args.parallel) as executor:
        # chunk input: https://github.com/python/cpython/issues/74028
        for filebatch in make_chunks(
            generate_filelist(args.input_dir), MAX_FILES_PER_DIRECTORY
        ):
            if filecounter < 0 and len(filebatch) >= MAX_FILES_PER_DIRECTORY:
                filecounter = 0
            worker = partial(
                file_processing, args=args, counter=filecounter, options=options
            )
            executor.map(worker, filebatch, chunksize=10, timeout=timeout)
            # update counter
            if filecounter >= 0:
                filecounter += len(filebatch)


def examine(
    htmlstring: Optional[Any],
    args: Any,
    url: Optional[str] = None,
    options: Optional[Extractor] = None,
) -> Optional[str]:
    "Generic safeguards and triggers around extraction function."
    result = None
    if not options:
        options = args_to_extractor(args, url)
    # safety check
    if htmlstring is None:
        sys.stderr.write("ERROR: empty document\n")
    elif not is_acceptable_length(len(htmlstring), options):
        sys.stderr.write("ERROR: file size\n")
    # proceed
    else:
        try:
            result = extract(htmlstring, options=options)
        # ugly but efficient
        except Exception as err:
            sys.stderr.write(f"ERROR: {str(err)}\n{traceback.format_exc()}\n")
    return result
