"""
Unit tests for the command-line interface.
"""

import io
import logging
import os
import re
import subprocess
import sys

from contextlib import redirect_stdout
from datetime import datetime
from os import path
from tempfile import gettempdir
from unittest.mock import patch

import pytest

from courlan import UrlStore

from trafilatura import cli, cli_utils, spider, settings
from trafilatura.downloads import add_to_compressed_dict, fetch_url
from trafilatura.filename import generate_hash_filename
from trafilatura.utils import LANGID_FLAG

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
RESOURCES_DIR = path.join(path.abspath(path.dirname(__file__)), "resources")

settings.MAX_FILES_PER_DIRECTORY = 1


def test_parser():
    """test argument parsing for the command-line interface"""
    testargs = ["", "-fvv", "--xmltei", "--no-tables", "-u", "https://www.example.org"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert args.fast is True
    assert args.verbose == 2
    assert args.no_tables is False
    assert args.xmltei is True
    assert args.URL == "https://www.example.org"
    args = cli.map_args(args)
    assert args.output_format == "xmltei"
    testargs = ["", "--output-format", "csv", "--no-tables", "-u", "https://www.example.org"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert args.fast is False
    assert args.verbose == 0
    assert args.output_format == "csv"
    assert args.no_tables is False
    # test args mapping
    testargs = ["", "--markdown"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    args = cli.map_args(args)
    assert args.output_format == "markdown"
    testargs = ["", "--xml", "--no-comments", "--precision", "--recall"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    args = cli.map_args(args)
    assert args.output_format == "xml" and args.no_comments is False
    # combination possible (?)
    assert args.precision is True and args.recall is True
    args.xml, args.csv = False, True
    args = cli.map_args(args)
    assert args.output_format == "csv"
    args.csv, args.json = False, True
    args = cli.map_args(args)
    assert args.output_format == "json"
    testargs = ["", "--only-with-metadata"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    args = cli.map_args(args)
    assert args.only_with_metadata is True
    # process_args
    args.input_dir = "/dev/null"
    args.verbose = 1
    args.blacklist = path.join(RESOURCES_DIR, "list-discard.txt")
    cli.process_args(args)
    assert len(args.blacklist) == 3
    # filter
    testargs = [
        "",
        "-i",
        "resources/list-discard.txt",
        "--url-filter",
        "test1",
        "test2",
        "-vvv",
    ]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert args.input_file == "resources/list-discard.txt"
    assert args.url_filter == ["test1", "test2"]
    args.input_file = path.join(RESOURCES_DIR, "list-discard.txt")
    args.blacklist = path.join(RESOURCES_DIR, "list-discard.txt")
    f = io.StringIO()
    with redirect_stdout(f):
        cli.process_args(args)
    assert len(f.getvalue()) == 0
    # input directory
    testargs = ["", "--input-dir", "resources/test/"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    f = io.StringIO()
    with redirect_stdout(f):
        cli.process_args(args)
    assert len(f.getvalue()) == 0
    # version
    testargs = ["", "--version"]
    with pytest.raises(SystemExit) as e, redirect_stdout(f):
        with patch.object(sys, "argv", testargs):
            args = cli.parse_args(testargs)
    assert e.type == SystemExit
    assert e.value.code == 0
    assert re.match(
        r"Trafilatura [0-9]\.[0-9]+\.[0-9] - Python [0-9]\.[0-9]+\.[0-9]", f.getvalue()
    )


def test_climain(capfd):
    """test arguments and main CLI entrypoint"""
    # exit status required: 0
    # Windows platforms
    if os.name == "nt":
        trafilatura_bin = path.join(sys.prefix, "Scripts", "trafilatura")
    # other platforms
    else:
        trafilatura_bin = "trafilatura"
    # help display
    assert subprocess.run([trafilatura_bin, "--help"], check=True).returncode == 0
    # piped input
    empty_input = b"<html><body><article>" + b"<p>ABC</p>"*100 + b"</article></body></html>"
    result = subprocess.run([trafilatura_bin], input=empty_input, check=True)
    assert result.returncode == 0
    captured = capfd.readouterr()
    assert captured.out.strip().endswith("ABC")
    # input directory walking and processing
    env = os.environ.copy()
    if os.name == "nt":
        # Force encoding to utf-8 for Windows (seem to be a problem only in GitHub Actions)
        env["PYTHONIOENCODING"] = "utf-8"
    assert (
        subprocess.run(
            [trafilatura_bin, "--input-dir", RESOURCES_DIR], env=env, check=True
        ).returncode
        == 0
    )
    # compressed file
    with open(path.join(RESOURCES_DIR, "webpage.html.gz"), "rb") as inputf:
        compressed_input = inputf.read()
    assert subprocess.run([trafilatura_bin], input=compressed_input, check=True).returncode == 0
    captured = capfd.readouterr()
    assert captured.out.strip().endswith("in deep-red West Virginia.")


def test_input_type():
    """test input type errors"""
    testfile = "docs/trafilatura-demo.gif"
    testargs = ["", "-u", "http"]
    with patch.object(sys, "argv", testargs):
        assert cli.main() is None
    testargs = ["", "-v"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with open(testfile, "rb") as f:
        teststring = f.read(1024)
    assert cli.examine(teststring, args) is None
    assert cli.examine([1, 2, 3], args) is None
    testfile = "docs/usage.rst"
    with open(testfile, "r", encoding="utf-8") as f:
        teststring = f.read()
    assert cli.examine(teststring, args) is None
    # test file list
    assert 10 <= len(list(cli_utils.generate_filelist(RESOURCES_DIR))) <= 21


def test_sysoutput():
    """test command-line output with respect to CLI arguments"""
    testargs = ["", "--csv", "-o", "/root/forbidden/"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    filepath, destdir = cli_utils.determine_output_path(args, args.output_dir, "")
    assert len(filepath) >= 10 and filepath.endswith(".csv")
    assert destdir == "/root/forbidden/"
    # doesn't work the same on Windows
    if os.name != "nt":
        assert cli_utils.check_outputdir_status(args.output_dir) is False
    else:
        assert cli_utils.check_outputdir_status(args.output_dir) is True
    testargs = ["", "--xml", "-o", "/tmp/you-touch-my-tralala"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert cli_utils.check_outputdir_status(args.output_dir) is True
    # test fileslug for name
    filepath, destdir = cli_utils.determine_output_path(
        args, args.output_dir, "", new_filename="AAZZ"
    )
    assert filepath.endswith("AAZZ.xml")
    # test json output
    args2 = args
    args2.xml, args2.json = False, True
    args2 = cli.map_args(args2)
    filepath2, destdir2 = cli_utils.determine_output_path(
        args, args.output_dir, "", new_filename="AAZZ"
    )
    assert filepath2.endswith("AAZZ.json")
    assert "you-touch-my-tralala" in destdir2
    # test directory counter
    # doesn't work the same on Windows
    if os.name != "nt":
        assert cli_utils.determine_counter_dir("testdir", 0) == "testdir/1"
    else:
        assert cli_utils.determine_counter_dir("testdir", 0) == "testdir\\1"
    # test file writing
    testargs = ["", "--markdown", "-o", "/dev/null/", "-b", "/dev/null/"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    result = "DADIDA"
    cli_utils.write_result(result, args)
    args.output_dir = gettempdir()
    args.backup_dir = None
    cli_utils.write_result(result, args)
    # process with backup directory and no counter
    options = settings.args_to_extractor(args)
    assert options.format == "markdown" and options.formatting is True
    assert cli_utils.process_result("DADIDA", args, -1, options) == -1

    # with counter
    with open(
        path.join(RESOURCES_DIR, "httpbin_sample.html"), "r", encoding="utf-8"
    ) as f:
        teststring = f.read()
    assert cli_utils.process_result(teststring, args, 1, options) == 2

    # test keeping dir structure
    testargs = ["", "-i", "myinputdir/", "-o", "test/", "--keep-dirs"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    filepath, destdir = cli_utils.determine_output_path(args, "testfile.txt", "")
    assert filepath == "test/testfile.txt"
    # test hash as output file name
    assert args.keep_dirs is True
    args.keep_dirs = False
    filepath, destdir = cli_utils.determine_output_path(args, "testfile.txt", "")
    assert filepath == "test/uOHdo6wKo4IK0pkL.txt"


def test_download():
    """test page download and command-line interface"""
    assert cli_utils._define_exit_code([], 0) == 0
    assert cli_utils._define_exit_code(["a"], 1) == 126
    assert cli_utils._define_exit_code(["a"], 2) == 1

    testargs = ["", "-v"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert cli.examine(None, args) is None
    assert cli.examine(" ", args) is None
    assert cli.examine("0" * int(10e7), args) is None
    # url = 'https://httpbun.org/status/200'
    # teststring = fetch_url(url)
    # assert teststring is None  # too small
    # assert cli.examine(teststring, args, url) is None
    # url = 'https://httpbun.org/links/2/2'
    # teststring = fetch_url(url)
    # assert teststring is not None
    # assert cli.examine(teststring, args, url) is None
    url = "https://httpbun.com/html"
    teststring = fetch_url(url)
    assert teststring is not None
    assert cli.examine(teststring, args, url) is not None
    # test exit code for faulty URLs
    testargs = ["", "-u", "https://1234.yz/"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with pytest.raises(SystemExit) as e:
        cli.process_args(args)
    assert e.type == SystemExit and e.value.code == 126


# @patch('trafilatura.settings.MAX_FILES_PER_DIRECTORY', 1)
def test_cli_pipeline():
    """test command-line processing pipeline"""
    # Force encoding to utf-8 for Windows in future processes spawned by multiprocessing.Pool
    os.environ["PYTHONIOENCODING"] = "utf-8"

    # test URL listing
    testargs = ["", "--list"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert cli_utils.url_processing_pipeline(args, UrlStore()) is False

    # test inputlist + blacklist
    testargs = ["", "-i", path.join(RESOURCES_DIR, "list-process.txt")]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    my_urls = cli_utils.load_input_urls(args)
    assert my_urls is not None and len(my_urls) == 3
    testargs = [
        "",
        "-i",
        path.join(RESOURCES_DIR, "list-process.txt"),
        "--blacklist",
        path.join(RESOURCES_DIR, "list-discard.txt"),
        "--archived",
    ]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    assert args.blacklist is not None
    # test backoff between domain requests
    url_store = add_to_compressed_dict(my_urls, args.blacklist, None, None)
    reftime = datetime.now()
    cli_utils.url_processing_pipeline(args, url_store)
    delta = (datetime.now() - reftime).total_seconds()
    assert delta > 2
    # test blacklist and empty dict
    args.blacklist = cli_utils.load_blacklist(args.blacklist)
    assert len(args.blacklist) == 3
    url_store = add_to_compressed_dict(my_urls, args.blacklist, None, None)
    cli_utils.url_processing_pipeline(args, url_store)
    # test backup
    testargs = ["", "--backup-dir", "/tmp/"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    cli_utils.archive_html("00Test", args)
    # test date-based exclusion
    testargs = ["", "--output-format", "xml", "--only-with-metadata"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with open(
        path.join(RESOURCES_DIR, "httpbin_sample.html"), "r", encoding="utf-8"
    ) as f:
        teststring = f.read()
    assert cli.examine(teststring, args) is None
    testargs = ["", "--output-format", "xml", "--only-with-metadata", "--precision"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with open(
        path.join(RESOURCES_DIR, "httpbin_sample.html"), "r", encoding="utf-8"
    ) as f:
        teststring = f.read()
    assert cli.examine(teststring, args) is None
    # test JSON output
    testargs = ["", "--output-format", "json", "--recall"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with open(
        path.join(RESOURCES_DIR, "httpbin_sample.html"), "r", encoding="utf-8"
    ) as f:
        teststring = f.read()
    assert cli.examine(teststring, args) is not None
    # sitemaps: tested in --explore
    testargs = [
        "",
        "--sitemap",
        "https://sitemaps.org/sitemap.xml",
        "--list",
        "--parallel",
        "1",
    ]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    f = io.StringIO()
    with redirect_stdout(f):
        cli.process_args(args)
    assert f.getvalue().strip().endswith("https://www.sitemaps.org/zh_TW/terms.html")
    # CLI options
    testargs = ["", "--links", "--images"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with open(
        path.join(RESOURCES_DIR, "http_sample.html"), "r", encoding="utf-8"
    ) as f:
        teststring = f.read()
    result = cli.examine(teststring, args)
    assert "[link](testlink.html)" in result and "test.jpg" in result
    # HTML format as option
    testargs = ["", "--html"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    result = cli.examine(teststring, args)
    assert result.startswith("<html") and result.endswith("</html>")


def test_file_processing():
    "Test file processing pipeline on actual directories."
    backup = settings.MAX_FILES_PER_DIRECTORY
    settings.MAX_FILES_PER_DIRECTORY = 0

    # dry-run file processing pipeline
    testargs = ["", "--parallel", "1", "--input-dir", "/dev/null"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    cli_utils.file_processing_pipeline(args)
    # file processing pipeline on resources/
    args.input_dir = RESOURCES_DIR
    cli_utils.file_processing_pipeline(args)
    # test manually
    for f in cli_utils.generate_filelist(args.input_dir):
        cli_utils.file_processing(f, args)
    options = settings.args_to_extractor(args)
    args.output_dir = "/dev/null"
    for f in cli_utils.generate_filelist(args.input_dir):
        cli_utils.file_processing(f, args, options=options)

    settings.MAX_FILES_PER_DIRECTORY = backup


def test_cli_config_file():
    "Test if the configuration file is loaded correctly from the CLI."
    testargs = ["", "--input-dir", "/dev/null", "--config-file", "newsettings.cfg"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    with open(
        path.join(RESOURCES_DIR, "httpbin_sample.html"), "r", encoding="utf-8"
    ) as f:
        teststring = f.read()
    args.config_file = path.join(RESOURCES_DIR, args.config_file)
    options = settings.args_to_extractor(args)
    assert cli.examine(teststring, args, options=options) is None


def test_input_filtering():
    """test internal functions to filter urls"""
    testargs = [""]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    # load dictionary
    args.input_file = path.join(RESOURCES_DIR, "list-process.txt")
    url_store = cli.load_input_dict(args)
    assert len(url_store.find_known_urls("https://httpbin.org")) == 3
    args.input_file = path.join(RESOURCES_DIR, "list-process.txt")
    args.blacklist = {"httpbin.org/status/404"}
    url_store = cli.load_input_dict(args)
    assert len(url_store.find_known_urls("https://httpbin.org")) == 2

    # deduplication and filtering
    inputlist = [
        "https://example.org/1",
        "https://example.org/2",
        "https://example.org/2",
        "https://example.org/3",
        "https://example.org/4",
        "https://example.org/5",
        "https://example.org/6",
    ]
    args.blacklist = {"example.org/1", "example.org/3", "example.org/5"}
    url_store = add_to_compressed_dict(inputlist, blacklist=args.blacklist)
    assert url_store.find_known_urls("https://example.org") == [
        "https://example.org/2",
        "https://example.org/4",
        "https://example.org/6",
    ]

    # URL in blacklist
    args.input_file = path.join(RESOURCES_DIR, "list-process.txt")
    my_urls = cli_utils.load_input_urls(args)
    my_blacklist = cli_utils.load_blacklist(
        path.join(RESOURCES_DIR, "list-discard.txt")
    )
    url_store = add_to_compressed_dict(my_urls, blacklist=my_blacklist)
    assert len(url_store.dump_urls()) == 0
    # other method
    args.input_file = path.join(RESOURCES_DIR, "list-process.txt")
    args.blacklist = path.join(RESOURCES_DIR, "list-discard.txt")
    args.blacklist = cli_utils.load_blacklist(args.blacklist)
    url_store = cli_utils.load_input_dict(args)
    assert len(url_store.dump_urls()) == 0

    # URL filter
    args.input_file = path.join(RESOURCES_DIR, "list-process.txt")
    my_urls = cli_utils.load_input_urls(args)
    url_store = add_to_compressed_dict(
        my_urls, blacklist=None, url_filter=["status"], url_store=None
    )
    assert len(url_store.urldict) == 1
    url_store = add_to_compressed_dict(
        my_urls, blacklist=None, url_filter=["teststring"], url_store=None
    )
    assert len(url_store.urldict) == 0
    url_store = add_to_compressed_dict(
        my_urls, blacklist=None, url_filter=["status", "teststring"], url_store=None
    )
    assert len(url_store.urldict) == 1

    # malformed URLs
    url_store = add_to_compressed_dict(["123345", "https://www.example.org/1"])
    assert len(url_store.urldict) == 1

    # double URLs
    args.input_file = path.join(RESOURCES_DIR, "redundant-urls.txt")
    my_urls = cli_utils.load_input_urls(args)
    url_store = add_to_compressed_dict(my_urls)
    assert len(url_store.find_known_urls("https://example.org")) == 1

    # filter before exploration
    input_store = add_to_compressed_dict(
        ["https://example.org/1", "https://sitemaps.org/test"]
    )
    input_urls = ["https://example.org", "http://sitemaps.org/", "https://test.info/"]
    url_store = cli_utils.build_exploration_dict(input_store, input_urls, args)
    assert url_store.get_known_domains() == ["https://test.info"]


def test_crawling():
    "Test crawling and exploration functions."

    testargs = ["", "--crawl", ""]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    cli_utils.cli_crawler(args)

    testargs = ["", "--crawl", " "]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    cli_utils.cli_crawler(args)

    testargs = ["", "--crawl", "https://httpbun.com/html"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    f = io.StringIO()
    with redirect_stdout(f):
        cli.process_args(args)
    assert f.getvalue() == "https://httpbun.com/html\n"

    spider.URL_STORE = UrlStore(compressed=False, strict=False)
    # links permitted
    testargs = [
        "",
        "--crawl",
        "https://httpbun.com/links/1/1",
        "--list",
        "--parallel",
        "1",
    ]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    f = io.StringIO()
    with redirect_stdout(f):
        cli_utils.cli_crawler(args)
    # possibly a bug on Github actions, should be 2 URLs
    assert f.getvalue() in (
        "https://httpbun.com/links/1/1\nhttps://httpbun.com/links/1/0\n",
        "https://httpbun.com/links/1/1\n",
    )
    spider.URL_STORE = UrlStore(compressed=False, strict=False)
    # 0 links permitted
    args.crawl = "https://httpbun.com/links/4/4"
    f = io.StringIO()
    with redirect_stdout(f):
        cli_utils.cli_crawler(args, n=0)
    ## should be 6 (5 URLs as output), possibly a bug on Actions CI/CD
    assert len(f.getvalue().split("\n")) in (2, 6)
    spider.URL_STORE = UrlStore(compressed=False, strict=False)

    # Exploration (Sitemap + Crawl)
    testargs = ["", "--explore", "https://httpbun.com/html", "--list"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)
    f = io.StringIO()
    with redirect_stdout(f):
        cli.process_args(args)
    assert f.getvalue().strip() == "https://httpbun.com/html"


def test_probing():
    "Test webpage probing functions."
    url = "https://example.org/"
    conf = path.join(RESOURCES_DIR, "zerolength.cfg")
    testargs = ["", "--probe", url, "--target-language", "de", "--config-file", conf]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    f = io.StringIO()
    with redirect_stdout(f):
        cli.process_args(args)
    if LANGID_FLAG:
        assert f.getvalue().strip() == ""
        args.target_language = "en"
        f2 = io.StringIO()
        with redirect_stdout(f2):
            cli.process_args(args)
        assert f2.getvalue().strip() == url
    else:
        assert f.getvalue().strip() == url

def test_filename_template_cli_integration():
    """Test CLI integration with FilenameTemplate."""
    # Test hierarchical structure with no extension
    testargs = ["", "--filename-template", "{domain}/{path_dirs}", "--output-dir", "/tmp/test", "-u", "https://example.com/blog/post1"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    output_path, destination_dir = cli_utils.determine_output_path(args=args, orig_filename="", content="Test content 1")
    assert destination_dir == "/tmp/test/example.com/blog"
    assert output_path == "/tmp/test/example.com/blog/post1"

    # Test with markdown extension
    testargs = ["", "--filename-template", "{domain}/{path_dirs}.{ext}", "--output-dir", "/tmp/test", "--markdown", "-u", "https://example.com/blog/post1"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    output_path2, destination_dir2 = cli_utils.determine_output_path(args=args, orig_filename="", content="Test content 1")
    assert destination_dir2 == "/tmp/test/example.com/blog"
    assert output_path2 == "/tmp/test/example.com/blog/post1.md"

    # Test flattened structure
    testargs = ["", "--filename-template", "{domain}/{path}", "--output-dir", "/tmp/test", "-u", "https://example.com/articles/tech/news"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    output_path3, destination_dir3 = cli_utils.determine_output_path(args=args, orig_filename="", content="Test content 2")
    assert destination_dir3 == "/tmp/test/example.com"
    assert output_path3 == "/tmp/test/example.com/articles_tech_news"

    # Test with parameters
    testargs = ["", "--filename-template", "{domain}/{path_dirs}/{hash}-{params}", "--output-dir", "/tmp/test", "-u", "https://example.com/articles/tech?id=123&cat=news"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    output_path4, destination_dir4 = cli_utils.determine_output_path(args=args, orig_filename="", content="Test content 3")
    assert destination_dir4 == "/tmp/test/example.com/articles/tech"
    assert output_path4 == f"/tmp/test/example.com/articles/tech/{generate_hash_filename('Test content 3')}-cat-news_id-123"

@pytest.mark.usefixtures("caplog")
def test_filename_template_cli_errors(caplog):
    """Test error handling in CLI filename template integration."""
    # Test URL too long
    testargs = ["", "--filename-template", "{domain}/{path_dirs}", "--output-dir", "/tmp/test", "-u", "https://example.com/" + "a" * 100, "--max-length", "100"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    output_path, destination_dir = cli_utils.determine_output_path(args=args, orig_filename="", content="test content")
    assert "_ttt_" in output_path
    assert destination_dir == "/tmp/test/example.com"
    assert generate_hash_filename("test content") in output_path

    # Test no URL
    testargs = ["", "--filename-template", "{domain}/{path}", "--output-dir", "/tmp/test"]
    with patch.object(sys, "argv", testargs):
        args = cli.parse_args(testargs)

    caplog.set_level(logging.WARNING)
    output_path2, destination_dir2 = cli_utils.determine_output_path(args=args, orig_filename="", content="test content")
    assert "Template generation failed: URL is required for template variables" in caplog.text
    assert output_path2 == "/tmp/test"
    assert generate_hash_filename("test content") in destination_dir2

if __name__ == "__main__":
    test_parser()
    test_climain()
    test_input_type()
    test_input_filtering()
    test_sysoutput()
    test_cli_pipeline()
    test_file_processing()
    test_cli_config_file()
    test_crawling()
    test_download()
    test_probing()
    test_filename_template_cli_integration()
    test_filename_template_cli_errors()
