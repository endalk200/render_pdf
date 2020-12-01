#!/usr/bin/env python3

"""
This is the main script that renders any source code to pdf format with syntax
highlighting and line number and more. It has support for downloading and rendering
any online source code using requests and BeautifulSoup.
"""

from signal import SIGINT, signal
signal(SIGINT, lambda signum, frame: sys.exit(1))

import os
import re
import sys
import requests
import termcolor

from argparse import ArgumentParser
from backports.shutil_get_terminal_size import get_terminal_size
from braceexpand import braceexpand
from bs4 import BeautifulSoup
from copy import copy
from glob import glob
from natsort import natsorted, ns
from pkg_resources import DistributionNotFound, get_distribution
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename, guess_lexer
from pygments.lexers.special import TextLexer
from PyPDF2 import PdfFileReader, PdfFileWriter
from requests.exceptions import RequestException
from tempfile import mkstemp
from textwrap import fill
from traceback import print_exception
from urllib.parse import urljoin
from warnings import filterwarnings


# Require Python 3.6+
if sys.version_info < (3, 6):
    sys.exit("You have an old version of python. Install version 3.6 or higher.")

# Get version
try:
    d = get_distribution("render50")
except DistributionNotFound:
    __version__ = "UNKNOWN"
else:
    __version__ = d.version


def main():

    # Exit on ctrl-c
    def handler(signum, frame):
        cprint("")
        cancel(1)

    # Register handler
    signal(SIGINT, handler)

    # Parse command-line arguments
    parser = ArgumentParser(description="A command-line tool that renders source code as a PDF.")
    parser.add_argument("-b", "--browser", action="store_true", help="render as a browser would")
    parser.add_argument("-f", "--force", action="store_true", default=False, help="overwrite existing files without prompting")
    parser.add_argument("-C", "--no-color", action="store_true", help="disable syntax highlighting")
    parser.add_argument("-i", "--include", action="append", help="pattern to include")
    parser.add_argument("-o", "--output", help="file to output", required=True)
    parser.add_argument("-P", "--no-path", action="store_true", default=False, help="omit paths in headers")
    parser.add_argument("-r", "--recursive", action="store_true", help="recurse into directories")
    parser.add_argument("-s", "--size", help="size of page, per https://developer.mozilla.org/en-US/docs/Web/CSS/@page/size")
    parser.add_argument("-x", "--exclude", action="append", help="pattern to exclude")
    parser.add_argument("-y", "--side-by-side", action="store_true", help="render inputs side by side")
    parser.add_argument("INPUT", help="file or URL to render", nargs="*")
    parser.add_argument("-V", "--version", action="version", version="%(prog)s {}".format(__version__))
    args = parser.parse_args(sys.argv[1:])

    # Ensure output ends in .pdf
    output = args.output
    if not output.lower().endswith(".pdf"):
        output += ".pdf"

    # Check for input
    if args.INPUT:
        inputs = args.INPUT
    else:
        inputs = [line.strip() for line in sys.stdin.readlines()]

    # Check for includes
    includes = []
    if args.include:
        for i in args.include:
            includes.append(re.escape(i).replace("\*", ".*"))

    # Check for excludes
    excludes = []
    if args.exclude:
        for x in args.exclude:
            excludes.append(re.escape(x).replace("\*", ".*"))

    # Check stdin for inputs else command line
    patterns = []
    if len(inputs) == 1 and inputs[0] == "-":
        patterns = sys.stdin.read().splitlines()
    else:
        patterns = inputs

    # Glob patterns lest shell (e.g., Windows) or stdin not have done so, ignoring empty patterns
    paths = []
    for pattern in patterns:
        if pattern.startswith(("http", "https")):
            paths += [pattern]
        if pattern:
            for expression in list(braceexpand(pattern)):
                paths += natsorted(glob(expression, recursive=True), alg=ns.IGNORECASE)

    # Candidates to render
    candidates = []
    for path in paths:
        if os.path.isfile(path) or path.startswith(("http", "https")):
            candidates.append(path)
        elif os.path.isdir(path):
            files = []
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    files.append(os.path.join(dirpath, filename))
            files = natsorted(files, alg=ns.IGNORECASE)
            candidates += files
        else:
            raise RuntimeError("Could not recognize {}.".format(path))

    # Filter candidates
    queue = []
    for candidate in candidates:

        # Skip implicit exclusions
        if includes and not re.search(r"^" + r"|".join(includes) + "$", candidate):
            continue

        # Skip explicit exclusions
        if excludes and re.search(r"^" + r"|".join(excludes) + "$", candidate):
            continue

        # Queue candidate for rendering
        queue.append(candidate)

    # If side-by-side
    if args.side_by_side:

        # Expect 2 or 3 inputs
        if len(queue) < 2:
            raise RuntimeError("Too few files to render side by side.")
        elif len(queue) > 3:
            raise RuntimeError("Too many files to render side by side.")

    # If rendering as browser would
    if args.browser:

        # Expect 1 input
        if len(queue) != 1:
            raise RuntimeError("Can only render one input as browser would.")


    # Prompt whether to overwrite output
    if not args.force and os.path.exists(output):
        if not args.INPUT:  # If using stdin for inputs
            raise RuntimeError("Output exists.")
        while True:
            s = input("Overwrite {}? ".format(output))
            if s.lower() in ["y", "yes"]:
                break
            elif s.lower() in ["n", "no"]:
                cancel()

    # Create parent directory as needed
    dirname = os.path.dirname(os.path.realpath(output))
    if not os.path.isdir(dirname):
        while True:
            s = input("Create {}? ".format(dirname)).strip()
            if s.lower() in ["n", "no"]:
                cancel()
            elif s.lower() in ["y", "yes"]:
                try:
                    os.makedirs(dirname)
                except Exception:
                    raise RuntimeError("Could not create {}.".format(dirname))

    # Determine size
    # https://developer.mozilla.org/en-US/docs/Web/CSS/@page/size
    if not args.size:
        if args.browser:
            size = "letter portrait"
        else:
            size = "letter landscape"
    else:
        size = args.size.strip()
        if not re.search(r"^[A-Za-z0-9\- ]+$", size):
            raise RuntimeError("Invalid size.")
        if size in ["A5", "A4", "A3", "B5", "B4", "JIS-B5", "JIS-B4", "letter", "legal", "ledger"]:
            size = "{} landscape".format(size)

    # Render input as browser would, effectively screenshotting page
    if args.browser:

        # frameset
        try:
            page = get(queue[0])
            soup = BeautifulSoup(page, "html.parser")
            framesets = soup.find_all(
                "frameset", {"cols": re.compile("(50%,\s*50%|33%,\s*33%,\s*33%)")})
            assert len(framesets) == 1
            frames = framesets[0].find_all("frame")
            assert 2 <= len(frames) <= 3
            if not args.size:
                size = "letter landscape"
            args.side_by_side = True
            queue = [join(queue[0], frame.attrs["src"]) for frame in frames]

        # noframes
        except:

            # Render input
            document = render(queue[0], browser=True, size=size)
            if not document:
                cancel(1)

            # Write rendered output
            if not write(output, [document]):
                cancel(1)
            cprint("Rendered {}.".format(output), "green")
            sys.exit(0)

    # Render inputs side by side
    if args.side_by_side:

        # Divide width
        document = blank(size)
        width = int(document.pages[0].width / len(queue))
        height = int(document.pages[0].height)
        size = "{}px {}px".format(width, height)

        # temporary files
        temps = []

        # Render first input
        temps.append(mkstemp())
        document = render(queue[0], browser=args.browser, color=not args.no_color,
                        fontSize="8pt", margin=".5in .25in .5in .5in", path=not args.no_path, relative=False, size=size)
        if not document:
            cancel(1)
        write(temps[0][1], [document], False)

        # Render second input
        temps.append(mkstemp())
        margin = ".5in .5in .5in .25in" if len(queue) == 2 else ".5in .375in .5in .375in"
        document = render(queue[1], browser=args.browser, color=not args.no_color,
                        fontSize="8pt", margin=margin, path=not args.no_path, relative=False, size=size)
        if not document:
            cancel(1)
        write(temps[1][1], [document], False)

        # Render third input, if any
        if len(queue) == 3:
            temps.append(mkstemp())
            document = render(queue[2], browser=args.browser, color=not args.no_color,
                            fontSize="8pt", margin=".5in .5in .5in .25in", path=not args.no_path, relative=False, size=size)
            if not document:
                cancel(1)
            write(temps[2][1], [document], False)

        # Concatenate inputs
        concatenate(output, list(map(lambda f: f[1], temps)))

        # Remove temporary files
        map(lambda f: os.close(f[0]), temps)
        map(lambda f: os.remove(f[1]), temps)

        # Rendered
        cprint("Rendered {}.".format(output), "green")
        sys.exit(0)

    # Render queued files
    documents = []
    for queued in queue:
        document = render(queued, color=not args.no_color, path=not args.no_path, size=size)
        if document:
            documents.append(document)

    # Write rendered files
    if not write(output, documents):
        cancel(1)


def blank(size):
    """Render blank page of specified size."""
    return HTML(string="").render(stylesheets=[CSS(string="@page {{ size: {}; }}".format(size))])


def cancel(code=0):
    """Report cancellation, exiting with code"""
    cprint("Rendering cancelled.", "red")
    sys.exit(code)


def concatenate(output, inputs):
    """Concatenate (PDF) inputs side by side."""

    # Read files
    readers = list(map(PdfFileReader, inputs))

    # Render blank page, inferring size from first input's first page
    temp = mkstemp()
    size = "{}pt {}pt".format(readers[0].getPage(0).mediaBox[2], readers[0].getPage(0).mediaBox[3])
    write(temp[1], [blank(size)], False)
    page = PdfFileReader(temp[1]).getPage(0)

    # Concatenate files side by side
    writer = PdfFileWriter()

    # Concatenate pages
    for i in range(max(map(lambda r: r.getNumPages(), readers))):

        # Leftmost page
        left = copy(readers[0].getPage(i)) if i < readers[0].getNumPages() else copy(page)

        # Rightmost pages
        for reader in readers[1:]:
            right = copy(reader.getPage(i)) if i < reader.getNumPages() else copy(page)
            left.mergeTranslatedPage(right, left.mediaBox[2], 0, expand=True)

        # Add pages to output
        writer.addPage(left)

    # Ouput PDF
    with open(output, "wb") as file:
        writer.write(file)

    # Remove temporary files
    os.close(temp[0]), os.remove(temp[1])


def cprint(text="", color=None, on_color=None, attrs=None, end="\n"):
    """Colorize text (and wraps to terminal's width)."""

    # Assume 80 in case not running in a terminal
    columns, _ = get_terminal_size()
    if columns == 0:
        columns = 80

    # Print text, flushing output
    termcolor.cprint(fill(text, columns, drop_whitespace=False, replace_whitespace=False),
                    color=color, on_color=on_color, attrs=attrs, end=end)
    sys.stdout.flush()


def excepthook(type, value, tb):
    """Report an exception."""
    excepthook.ignore = False
    if type is RuntimeError and str(value):
        cprint(str(value), "yellow")
    else:
        cprint("Sorry, something's wrong! Let sysadmins@cs50.harvard.edu know!", "yellow")
        print_exception(type, value, tb)
    cancel(1)


sys.excepthook = excepthook


def get(file):
    """Gets contents of file locally or remotely."""

    # Check if URL
    if file.startswith(("http", "https")):

        # Get from raw.githubusercontent.com
        matches = re.search(r"^(https?://github.com/[^/]+/[^/]+)/blob/(.+)$", file)
        if matches:
            file = "{}/raw/{}".format(matches.group(1), matches.group(2))
        matches = re.search(r"^(https?://gist.github.com/[^/]+/[^/#]+/?)(?:#file-(.+))?$", file)
        if matches:
            file = "{}/raw".format(matches.group(1))
            if matches.group(2):
                file += "/{}".format(matches.group(2))

        # Get file
        req = requests.get(file)
        if req.status_code == 200:
            return req.text
        else:
            cprint("\033[2K", end="\r")
            raise RuntimeError("Could not GET {}.".format(file))

    # Read file
    else:
        try:
            with open(file, "rb") as f:
                return f.read().decode("utf-8", "ignore")
        except Exception as e:
            cprint("\033[2K", end="\r")
            if type(e) is FileNotFoundError:
                raise RuntimeError("Could not find {}.".format(file))
            else:
                raise RuntimeError("Could not read {}.".format(file))


def join(a, b):
    """Join a and b, where each is a URL, an absolute path, or a relative path."""

    # If b is a URL, don't join
    if b.startswith(("http://", "https://")):
        return b

    # if a is a URL (and b is not), join with b
    if a.startswith(("http://", "https://")):
        return urljoin(a, b)

    # if a is an absolute or a relative path, join with b
    else:
        return os.path.normpath(os.path.join(os.path.dirname(a), b))


def render(filename, size, browser=False, color=True, fontSize="10pt", margin=".5in", path=True, relative=True):
    """Render file with filename as HTML page(s) of specified size."""

    # Rendering
    cprint("Rendering {}...".format(filename), end="")

    # Render as a browser would
    if browser:

        # Styles for document
        stylesheets = [
            CSS(string="@page {{ margin: {}; size: {}; }}".format(margin, size)),
            CSS(string="html {{ font-size: {}; }}".format(fontSize))]

        # Render document
        try:

            # Parse HTML
            soup = BeautifulSoup(get(filename), "html.parser")

            # Remove relative links (for side-by-side outputs, for which we concatenate PDFs page-wise)
            if not relative:
                for a in soup.find_all("a"):
                    if a["href"].startswith("#"):
                        del a["href"]

            # Re-parse HTML
            document = HTML(base_url=os.path.dirname(filename),
                            string=str(soup)).render(stylesheets=stylesheets)

        except Exception as e:
            cprint("\033[2K", end="\r")
            if type(e) in [RequestException, URLFetchingError]:
                raise RuntimeError("Could not GET {}.".format(filename))
            else:
                raise RuntimeError("Could not read {}.".format(filename))

    # Syntax-highlight instead
    else:

        # Get code from file
        code = get(filename)

        # Check whether binary file
        if "\x00" in code:
            cprint("\033[2K", end="\r")
            cprint("Could not render {} because binary.".format(filename), "yellow")
            return None

        # Highlight code unless file is empty, using inline line numbers to avoid
        # page breaks in tables, https://github.com/Kozea/WeasyPrint/issues/36
        if code.strip() and color:
            try:
                lexer = get_lexer_for_filename(filename)
            except:
                try:
                    assert code.startswith("#!")  # else, e.g., a .gitignore file with a dotfile is mistaken by GasLexer
                    lexer = guess_lexer(code.splitlines()[0])
                except:
                    lexer = TextLexer()
            string = highlight(code, lexer, HtmlFormatter(linenos="inline", nobackground=True))
        else:
            string = highlight(code, TextLexer(), HtmlFormatter(
                linenos="inline", nobackground=True))

        # Styles for document
        title = filename if path else os.path.basename(filename)
        stylesheets = [
            CSS(string="@page {{ border-top: 1px #808080 solid; margin: {}; padding-top: 1em; size: {}; }}".format(margin, size)),
            CSS(string="@page {{ @top-right {{ color: #808080; content: '{}'; padding-bottom: 1em; vertical-align: bottom; }} }}".format(
                title.replace("'", "\'"))),
            CSS(string="* {{ font-family: monospace; font-size: {}; margin: 0; overflow-wrap: break-word; white-space: pre-wrap; }}".format(fontSize)),
            CSS(string=HtmlFormatter().get_style_defs('.highlight')),
            CSS(string=".highlight { background: initial; }"),
            CSS(string="span.linenos { background-color: inherit; color: #808080; }"),
            CSS(string="span.linenos:after { content: '  '; }")]

        # Render document
        document = HTML(string=string).render(stylesheets=stylesheets)

    # Bookmark document
    document.pages[0].bookmarks = [(1, title, (0, 0), "closed")]

    # Rendered
    cprint("\033[2K", end="\r")
    cprint("Rendered {}.".format(filename))
    return document


def write(output, documents, echo=True):
    """
    Write documents to output as PDF.
    https://github.com/Kozea/WeasyPrint/issues/212#issuecomment-52408306
    """
    if documents:
        pages = [page for document in documents for page in document.pages]
        documents[0].copy(pages).write_pdf(output)
        if echo:
            cprint("Rendered {}.".format(output), "green")
        return True
    else:
        return False


# Check for dependencies
# http://weasyprint.readthedocs.io/en/latest/install.html
try:
    # Ignore warnings about outdated Cairo and Pango (on Ubuntu 14.04, at least)
    filterwarnings("ignore", category=UserWarning, module="weasyprint")
    from weasyprint import CSS, HTML
    from weasyprint.urls import URLFetchingError
except OSError as e:
    if "pangocairo" in str(e):
        raise RuntimeError("Missing dependency. Install Pango.")
    elif "cairo" in str(e):
        raise RuntimeError("Missing dependency. Install cairo.")
    else:
        raise RuntimeError(str(e))


if __name__ == "__main__":
    main()