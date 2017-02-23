# ConvertSEP
To generate [tufte-book](https://tufte-latex.github.io/tufte-latex/) style document for SEP entries.
## Dependencies
* XeLaTeX 
* [pandoc](http://pandoc.org/) and its python wrapper pypandoc

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
which will save the tex output to `output.tex`. XeLaTeX can then be used to compile the output:
```
xelatex comte.tex
xelatex comte.tex # second run to generate the TOC
```
