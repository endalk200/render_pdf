# Render PDF

render_pdf is python script based on weasyprint that converts any source code to pdf file. 

## Showcase
> Single Code Base
![Rendered source code](https://github.com/endalk200/render_pdf/blob/master/example/render.png?raw=true)

> Two Source Codes Side By Side
![Side By Side Rendered Source Code](https://github.com/endalk200/render_pdf/blob/master/example/render_side_by_side.png?raw=true)

## Features

This script has the following features.

* syntax highlighting for any source code using pygments.
* line number for the source code.
* rendering any online materials or source code by downloading it.

## Installation

You can install this package from the pypi index using the following commands.

> For Linux Based OS
```bash
pip install render_pdf
```

> For windows
```bash
python -m pip install render_pdf
```

## Usage

This script can be used in variety of ways. The following examples and the results are stored in the example directory
in this repository.

* rendering single source code from local directory

```bash
render ./example/render.py -o ./example/render.pdf
```

* rendering multiple source codes from local directory

```bash
render ./setup.py ./example/render.py -o ./example/render.pdf
```

### rendering two source codes side by side for comparison.

```bash
render -y ./setup.py ./example/render.py -o ./example/render.pdf
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
