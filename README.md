# render_pdf

render_pdf is python script based on weasyprint that converts any source code to pdf file. 

## Features

This script has the following features.

* syntax highlighting for any source code using pygments.
* line number for the source code.
* rendering any online materials or source code by downloading it.

## Installation

You can install this package from the pypi index using the following commands.
<br>
For Linux
```bash
pip install render_pdf
```

For windows
```bash
python -m pip install render_pdf
```

## Usage

This script can be used in variety of ways.

* rendering single source code from local directory

```bash
render ./setup.py -o setup.pdf
```

* rendering multiple source codes from local directory

```bash
render ./setup.py ./render.py -o render.pdf
```

### rendering two source codes side by side for comparison.

```bash
render -y ./setup.py ./render.py -o render.pdf
```

### rendering source code by downloading from the internet.

To render the [setup.py](https://raw.githubusercontent.com/endalk200/render_pdf/main/setup.py) file
from this repository by downloading it from github server.
P
```bash
render https://raw.githubusercontent.com/endalk200/render_pdf/main/setup.py -o setup.pdf
```

## Source Code

You can see the source code by cloning the repository as follows.
```bash
git clone https://github.com/endalk200/render_pdf.git
```
