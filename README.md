# ConvertSEP
To generate [tufte-book](https://tufte-latex.github.io/tufte-latex/) style document for SEP entries.
## Dependencies
* XeLaTeX 
* [pandoc](http://pandoc.org/) and its python wrapper pypandoc
* [Inkscape](https://inkscape.org/): if `.svg` images are used in the entry

You may need to add the paths to the `PATH` environment variable, such that `inkscape` and `xelatex` can be called directly from your command-line.

## Usage
```
 python ConvertSEPHTML.py <URL to the entry> [<output.tex>]
```
For example:
```
python ConvertSEPHTML.py  https://plato.stanford.edu/entries/comte/ comte.tex
```
or
```
python ConvertSEPHTML.py  https://plato.stanford.edu/entries/comte/
```
which will save the tex output to `output.tex`. Manual adjustment may be required, e.g. <*offset*> argument of `\sidenote`. XeLaTeX can then be used to compile the output:
```
xelatex comte.tex
xelatex comte.tex # second run to generate the TOC
```
