
import setuptools
import pathlib

BASE_DIR = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (BASE_DIR / 'README.md').read_text(encoding='utf-8')


from setuptools import setup

setup(
    name="render_pdf",
    version="0.1.8",
    url="https://github.com/endalk200/render_pdf",

    author="Endalkachew Biruk",
    author_email="eb808826@gmail.com",

    classifiers=[
        "Intended Audience :: Education",
        "Programming Language :: Python :: 3",
        "Topic :: Education",
        "Topic :: Utilities"
    ],
    description="This is render50, with which you can render source code as PDFs.",
    long_description=long_description,
    long_description_content_type="text/markdown",

    install_requires=[
        "backports.shutil_get_terminal_size", 
        "backports.shutil_which", 
        "braceexpand", 
        "beautifulsoup4", 
        "natsort", 
        "Pygments>=2.7.1", 
        "PyPDF2", 
        "requests", 
        "six>=1.10.0", 
        "termcolor", 
        "WeasyPrint>=51"],
    python_requires='>=3.3',

    scripts=["./scripts/render"],

    keywords=["render", "render_pdf"]
)