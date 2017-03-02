import sys
import os
import os.path
import re
import requests
import pypandoc
import demjson
import urllib
import tempfile
import shutil
import uuid
import subprocess 

from subprocess import call
from string import Template
from bs4 import BeautifulSoup, Comment
from urlparse import urljoin, urlparse

def ConvertMathJaX2TeX(mathjax_str):
  latex_str = re.sub(r'\\begin{align(\*?)}', r'\\begin{aligned}', mathjax_str)
  latex_str = re.sub(r'\\end{align(\*?)}', r'\\end{aligned}', latex_str)
  return latex_str

def CommentTeX(tex_src):
  return '\n'.join(['% ' + l for l in tex_src.strip().split('\n')])

def TeXWidth(tex_str, nowrap):
  script_template_fname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'get_width.template')
  if nowrap:
    script_template_fname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'get_width_nowrap.template')
  f = open(script_template_fname, 'r')
  script_template = Template(f.read())
  f.close()
  get_width_script = script_template.substitute(tex_to_measure=tex_str)
  
  DIR_CURRENT = os.getcwd()
  DIR_TEMP    = tempfile.mkdtemp()
  os.chdir(DIR_TEMP)
  script_id = str(uuid.uuid4())
  get_width_script_file = open(os.path.join(DIR_TEMP, script_id+'.tex'), "w")
  get_width_script_file.write(get_width_script.encode('utf8'))
  get_width_script_file.close()
  
  FNULL = open(os.devnull, 'w')
  call(['xelatex', '-interaction=batchmode', script_id], stdout=FNULL, stderr=subprocess.STDOUT)
  f_log = open(os.path.join(DIR_TEMP, script_id+'.log'), "r")
  tex_output = []
  for line in f_log:
    if re.match(r'^>', line):
      tex_output.append( line )
  f_log.close()
  os.chdir(DIR_CURRENT)
  shutil.rmtree(DIR_TEMP)
  
  if len(tex_output) == 2 :
     val = [float(re.sub('>\s*(.*)pt\.', r'\1', l)) for l in tex_output]
     return val[0]/val[1]
  else:
    return 0

def HTMLContentsWidth(contents, nowrap=False):
  if not contents:
    return 0
  listTeXWidth = []
  list_contents = []
  if contents:
    e_html = ''
    for e in contents:
      if isinstance(e, (str, unicode)):
        e_html += unicode(e)
      elif hasattr(e, 'name'):
        if e.name in ['h2', 'h3', 'h4',  'ul', 'ol', 'p', 'blockquote', 'div']:
          if e_html:
            if e_html.strip():
              latex_str = pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')
              listTeXWidth.append(TeXWidth(latex_str, nowrap))
            e_html     = ''
          listTeXWidth.append(TeXWidth(ConvertHTMLElement(e), nowrap))
          #  shouldn't really happen
        elif e.name == 'table':
          listTeXWidth.append( HTMLEntityWidth(e, nowrap) )
        else:
          e_html += unicode(e)
      else:
        e_html += unicode(e)
    if e_html:
      latex_str = pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')
      listTeXWidth.append(TeXWidth(latex_str, nowrap))
  return max(listTeXWidth)

def HTMLEntityWidth(html_entity, nowrap=False):
  MinCW=0
  tag = html_entity.name
  if tag == 'table':
    table_width_matrix = []
    for r in html_entity.children:
      if r.name == 'tr':
        row_width_vector = []
        for d in r.children:
          if d.name == 'td':
            colspan = 1
            rowspan = 1
            cell_nowrap  = False
            if d.has_attr('colspan'):
              colspan = int(d['colspan'])
            if d.has_attr('nowrap'):
              if d['nowrap'] == 'nowrap':
                cell_nowrap = True
            td_width = HTMLContentsWidth(d.contents, nowrap or cell_nowrap)
            row_width_vector.append(td_width)
        table_width_matrix.append(row_width_vector)
    MinCW = max([sum([wd for wd in wr]) for wr in table_width_matrix ])
    # print table_width_matrix
  else:
    MinCW = HTMLContentsMinWidth(html_entity.contents, nowrap)
  return MinCW

def HTMLContents2TeX(contents, TableEnv=False):
  latex_str = ''
  list_contents = []
  ignore = False
  if contents:
    e_html = ''
    for e in contents:
      if isinstance(e, (str, unicode)):
        if unicode(e) == 'pdf exclude begin':
          ignore=True
          # print 'HTMLContents2TeX: contents: str: pdf exclude begin'
          # clear e_html
          if e_html.strip():
            latex_str += pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')
          else:
            latex_str += '\n'
          latex_str += '% '
          latex_str += unicode(e)
          latex_str += '\n'
          e_html = ''
        elif unicode(e) == 'pdf exclude end':
          ignore=False
          # print 'HTMLContents2TeX: contents: str: pdf exclude end'
          # clear e_html
          if e_html.strip():
            latex_str += CommentTeX(pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash'))
          latex_str += '\n% '
          latex_str += unicode(e)
          latex_str += '\n'
          e_html = ''
        elif re.match(r'pdf include.*pdf include', unicode(e), flags=re.MULTILINE|re.DOTALL):
          e_contents = BeautifulSoup(re.sub(r'pdf include(.*)pdf include', r'\1',  unicode(e), flags=re.MULTILINE|re.DOTALL).strip()).html.body.contents
          latex_str += HTMLContents2TeX(e_contents)
          # print 'HTMLContents2TeX: contents: str: pdf include'
        else:
          e_html += unicode(e)
      elif hasattr(e, 'name'):
        if e.name in ['h2', 'h3', 'h4', 'p', 'blockquote', 'ul', 'ol', 'div', 'table']:
          if e_html.strip():
            if not ignore:
              latex_str += pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')
            else:
              latex_str += CommentTeX(pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash'))
          else:
            if not ignore:
              latex_str += '\n'
            else:
              latex_str += '% \n'
          e_html     = ''
          if not ignore:
            latex_str   += ConvertHTMLElement(e, TableEnv)
          else:
            latex_str   += CommentTeX(ConvertHTMLElement(e, TableEnv))
        else:
          e_html += unicode(e)
      else:
        e_html += unicode(e)
    if e_html:
      if not ignore:
        latex_str += pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')
      else:
        latex_str += CommentTeX(pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash'))
  return latex_str

def heading_HTMLEntity2TeX(html_entity):
  heading_contents = None
  if html_entity.contents[0].name == 'a':
    heading_contents = html_entity.contents[0].contents
  else:
    heading_contents = html_entity.contents
  heading_TeX = HTMLContents2TeX(heading_contents)
  heading_TeX = re.sub(r'\n', '', heading_TeX)
  heading_TeX = re.sub(r'^[0-9\. ]*', '', heading_TeX )
  if(html_entity.name == 'h2'):
    heading_TeX = ''.join(['\\chapter{', heading_TeX, '}'])
  if(html_entity.name == 'h3'):
    heading_TeX = ''.join(['\\section{', heading_TeX, '}'])
  if(html_entity.name == 'h4'):
    heading_TeX = ''.join(['\\subsection{', heading_TeX, '}'])
  return heading_TeX

def paragraph_HTMLEntity2TeX(html_entity):
  paragraph_TeX = HTMLContents2TeX(html_entity.contents)
  if re.search(r'\\textbackslash{}\(\\textbackslash\{\}ref\\{(.*)\\}\\textbackslash{}\)', paragraph_TeX):
    paragraph_TeX = re.sub(r'\\textbackslash{}\(\\textbackslash\{\}ref\\{(.*)\\}\\textbackslash{}\)', r'\\ref{\1}', paragraph_TeX)
  if re.search(r'\(\\textbackslash{}\((.*)\\textbackslash{}\)\)', paragraph_TeX):
    paragraph_TeX = re.sub(r'\(\\textbackslash{}\((.*)\\textbackslash{}\)\)', (lambda x: ''.join(['($', re.sub(r'\\textbackslash{}', r'\\', x.group(1)), '$)'])), paragraph_TeX)
  return paragraph_TeX

def blockquote_HTMLEntity2TeX(html_entity):
  return '\n'.join(['\\begin{quote}', HTMLContents2TeX(html_entity.contents), '\\end{quote}'])

def ul_HTMLEntity2TeX(html_entity):
  li_contents_list = [l.contents for l in html_entity.find_all('li')]
  li_TeX_list      = [ ''.join(['\\item ', HTMLContents2TeX(l).strip()]) for l in li_contents_list ]
  return ''.join(['\\begin{itemize}\n', '\n'.join(li_TeX_list), '\n\\end{itemize}'])

def ol_HTMLEntity2TeX(html_entity):
  counter=''
  type=''
  if html_entity.has_attr('start'):
    counter = '\\setcounter{enumi}{' + str(int(html_entity['start']) - 1) + '}\n'
  if html_entity.has_attr('type'):
    type = ''.join(['[', html_entity['type'],']'])
  li_contents_list = [l.contents for l in html_entity.find_all('li')]
  li_TeX_list      = [ ''.join(['\\item ', HTMLContents2TeX(l).strip()]) for l in li_contents_list ]
  return ''.join(['\\begin{enumerate}', type,'\n', counter, '\n'.join(li_TeX_list), '\n\\end{enumerate}'])

def table_HTMLEntity2TeX(table_entity, TableEnv = False):
  table_matrix = []
  max_num_cols = 0
  for r in table_entity.children:
    if r.name == 'tr':
      row_vector = []
      for d in r.children:
        if d.name == 'td':
          colspan = 1
          rowspan = 1
          nowrap  = False
          valign  = 'l'
          align   = ''
          if d.has_attr('colspan'):
            colspan = int(d['colspan'])
          if d.has_attr('rowspan'):
            rowspan = int(d['rowspan'])
          if d.has_attr('nowrap'):
            if d['nowrap'] == 'nowrap':
              nowrap = True
          if d.has_attr('valign'):
            # print d['valign']
            if d['valign'] == 'middle':
              valign = 'M'
            if d['valign'] == 'bottom':
              valign = 'B'
          minWidth = HTMLContentsWidth(d.contents, nowrap)
          maxWidth = HTMLContentsWidth(d.contents, True)
          # td_latex = HTMLContents2TeX(d.contents, TableEnv = True)
          row_vector.append((colspan, rowspan, nowrap, valign, align, minWidth, maxWidth))
      row_num_cells = sum([d_element[0] for d_element in row_vector])
      if row_num_cells > max_num_cols:
        max_num_cols = row_num_cells
      table_matrix.append(row_vector)
  
  ## Column Widths
  col_min_width = [None]  * max_num_cols
  col_max_width = [None]  * max_num_cols
  col_nowrap    = [True] * max_num_cols
  for r in table_matrix:
    c=0
    for d in r:
      colspan = d[1]
      if colspan == 1:
        col_nowrap[c] = (col_nowrap and d[2])
        if col_max_width[c] is None:
          col_max_width[c] = d[6]
        else:
          col_max_width[c] = max(col_max_width[c], d[6])
        if col_min_width[c] is None:
          col_min_width[c] = d[5]
        else:
          col_min_width[c] = max(col_min_width[c], d[5])
      c += colspan
  
  for r in table_matrix:
    c=0
    for d in r:
      colspan = d[0]
      if colspan > 1:
        # print [d[5], d[6]]
        if sum(col_min_width[c:(c+colspan)]) < d[5]:
          for ci in range(c,(c+colspan)):
            col_min_width[ci] += ((d[5] - sum(col_min_width[c:(c+colspan)]))/colspan)
        if sum(col_max_width[c:(c+colspan)]) < d[6]:
          for ci in range(c,(c+colspan)):
            col_max_width[ci] += ((d[6] - sum(col_max_width[c:(c+colspan)]))/colspan)
      c += colspan
  
  col_width = [None]  * max_num_cols
  for c in range(max_num_cols):
    # weighted mean
    col_width[c] = .8*col_min_width[c] + .2*col_max_width[c]
    # geometric mean
    # col_width[c] = sqrt(col_min_width[c]*col_max_width[c]) 
    # harmonic mean
    # col_width[c] = 2/((1/col_min_width[c])+(1/col_max_width[c]))
    threshold = 8
    w_m = max(0, col_max_width[c] - threshold)
    w_M = 1
    col_width[c] = (w_m*col_width[c] + w_M*col_max_width[c])/(w_m + w_M)
  
  table_latex = '\\begin' 
  if TableEnv:
    table_latex += '{tabular}'
  else:
    table_latex += '{longtable}'
  preamble = ''.join(['c' if col_nowrap[idx] else ('p{'+ ("%.2f" % col_width[idx]) +'em+2\\arrayrulewidth}') for idx in range(max_num_cols) ])
  table_latex += ('{'+preamble+'}\n')
  r_idx = 0
  for r in table_entity.children:
    row_latex = ''
    if r.name == 'tr':
      c_idx = 0
      d_idx = 0
      for d in r.children:
        if d.name == 'td':
          colspan = table_matrix[r_idx][d_idx][0]
          cell_width = sum(col_width[c_idx:(c_idx+colspan)])
          td_latex = HTMLContents2TeX(d.contents, TableEnv = True)
          
          cell_latex = ' '
          if td_latex.strip():
            if colspan > 1 or table_matrix[r_idx][d_idx][2] :
              cell_latex = '\\multicolumn{'+str(colspan)+'}{'+ table_matrix[r_idx][d_idx][3] +'}{\\nowrapcell{' + td_latex + '}}'
            elif '\\\\' in td_latex:
              cell_latex = '\\Xcell{'+("%.2f" % cell_width)+'em+2\\arrayrulewidth}{' + td_latex + '}'
            else:
              cell_latex = td_latex
          if row_latex == '':
            row_latex = cell_latex
          else:
            row_latex += ' & ' + cell_latex
          d_idx += 1
          c_idx += colspan
      table_latex += row_latex
      table_latex += '\\\\\n'
      r_idx += 1
  
  if TableEnv:
    table_latex += '\\end{tabular}'
  else:
    table_latex += '\\end{longtable}'
  return table_latex 

def ConvertHTMLElement(html_element, TableEnv=False):
  tag = html_element.name
  if tag == 'h2' or tag == 'h3' or tag == 'h4':
    return heading_HTMLEntity2TeX(html_element)
  if tag == 'p' or tag == 'span':
    return paragraph_HTMLEntity2TeX(html_element)
  if tag == 'div':
    if html_element.has_attr('class'):
      if 'figure' in html_element['class']:
        return '\n'.join(['\\begin{figure}\\centering', paragraph_HTMLEntity2TeX(html_element).strip(), '\\end{figure}'])
      if 'indent' in html_element['class']:
        return '\n'.join(['\\begin{adjustwidth}{1em}{1em}', paragraph_HTMLEntity2TeX(html_element).strip(), '\\end{adjustwidth}'])
      if 'smaller' in html_element['class']:
        return '\n'.join(['{\small ', paragraph_HTMLEntity2TeX(html_element).strip(), '}'])
    return paragraph_HTMLEntity2TeX(html_element) 
  if tag == 'blockquote':
    return blockquote_HTMLEntity2TeX(html_element)
  if tag == 'ul':
    return ul_HTMLEntity2TeX(html_element)
  if tag == 'ol':
    return ol_HTMLEntity2TeX(html_element)
  if tag == 'table':
    return table_HTMLEntity2TeX(html_element, TableEnv)
  return ''

def ConvertHTML(entry_html_entity):
  entry_TeX = ''
  ignore=False
  if entry_html_entity:
    if entry_html_entity.children:
      for i in entry_html_entity.children:
        if i.name:
          if not ignore:
            entry_TeX += '\n'
            entry_TeX += ConvertHTMLElement(i).strip()
            if i.name == 'p':
              entry_TeX += '\n'
          else:
            entry_TeX += '% \n'
            entry_TeX += CommentTeX(ConvertHTMLElement(i).strip())
            if i.name == 'p':
              entry_TeX += '% \n'
        else:
          if str(i) == 'pdf exclude begin':
            ignore=True
            # print 'ConvertHTML: pdf exclude begin'
            entry_TeX += '% '
            entry_TeX += str(i)
            entry_TeX += '\n'
          elif str(i) == 'pdf exclude end':
            entry_TeX += '\n% '
            entry_TeX += str(i)
            entry_TeX += '\n'
            ignore=False
            # print 'ConvertHTML: pdf exclude end'
          elif re.match(r'pdf include.*pdf include', unicode(i), flags=re.MULTILINE|re.DOTALL):
            i_contents = BeautifulSoup(re.sub(r'pdf include(.*)pdf include', r'\1',  unicode(i), flags=re.MULTILINE|re.DOTALL).strip()).html.body.contents
            entry_TeX += HTMLContents2TeX(i_contents)
            # print 'ConvertHTML: pdf include'
          else:
            if not ignore:
              if re.match(r'\\\[.*\\\]', str(i).strip(), flags=re.MULTILINE|re.DOTALL):
                entry_TeX = re.sub('\n\n\Z', '\n', entry_TeX, flags=re.MULTILINE) + str(i).strip()
            else:
              if re.match(r'\\\[.*\\\]', str(i).strip(), flags=re.MULTILINE|re.DOTALL):
                entry_TeX = re.sub('\n\n\Z', '\n', entry_TeX, flags=re.MULTILINE) + CommentTeX(str(i).strip())
  return entry_TeX



def OutputTeX(title, author, preamble='', main_text='', bibliography='', acknowledgments='', macros='', pubhistory='', copyright='', url=''):
  frontmatter_template_fname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'frontmatter.template')
  f = open(frontmatter_template_fname, 'r')
  frontmatter_template=Template(f.read())
  f.close()
  
  src_tex = frontmatter_template.substitute(title=title, author=author, copyright=copyright, pubhistory=pubhistory, url=url, MathJaxMacros=macros)
  src_tex = '\n'.join([src_tex, preamble, '\n\\tableofcontents\n\n\\setcounter{secnumdepth}{2}',  main_text, bibliography, acknowledgments, '\\end{document}'])
  return src_tex

def ProcessNotes(src_tex, base_url):
  note_list = re.findall(r'(\\textsuperscript\{\{\[\}(\\hyperdef\{\}\{.*\}\{\})?\{?\\href\{(.*)\\#(.*)\}\{(.*)\}\}?\{]\}\})', src_tex, flags=re.MULTILINE)
  soup_dict = {}
  for note_url in list(set([n[2] for n in note_list])):
    r = requests.get(urljoin(base_url, note_url))
    soup = BeautifulSoup(r.text)
    soup_dict[note_url] = soup
  
  for note_url in soup_dict:
    soup=soup_dict[note_url]
    note_num = None
    for i in soup.select('#aueditable')[0].children:
      if i.name:
        if i.name == 'div':
          if i.has_attr('id'):
            note_num = i['id']
        for a in i.find_all('a'):
          if a.has_attr('name'):
            note_num = a['name']
        if note_num:
          for j in xrange(len(note_list)):
            if note_list[j][3] == note_num and note_list[j][2] == note_url:
               if(len(note_list[j])==5):
                 note_list[j] = note_list[j] + ([],)
               note_list[j][5].append(i)
  
  for n in note_list:
    for e in n[5]:
      for tag in e.find_all('a'):
        if tag.has_attr('name'):
          tag.replaceWith('')
        elif tag.has_attr('href'):
          if re.match(r'index\.html?#.*', tag['href']):
            tag.replaceWith('')
    
    note_text = ''
    if len(n) > 5:
      note_text = '\n'.join([ConvertHTMLElement(e) for e in n[5]])
      note_text = ''.join(['\\setlength{\\tempparskip}{\\parskip}\\setlength{\\tempparindent}{\\parindent}\\sidenote[][]{', note_text, '}\\setlength{\\parindent}{\\tempparindent}\\setlength{\\parskip}{\\tempparskip}'])
    note_superscript = n[0]
    src_tex = src_tex.replace(note_superscript, note_text)
  
  return re.sub(r'\\\[.*?\\\]', lambda x: ConvertMathJaX2TeX(x.group(0)), src_tex, flags=re.MULTILINE|re.DOTALL)
    

def main():
  url=''
  output='output.tex'
  args = sys.argv[1:]
  if(len(args)>0):
    url = args[0]
    if( len(args)>1):
      output=args[1]
  else:
    helpConvertSEPHTML()
    sys.exit()
  
  r  = requests.get(url)
  
  soup = BeautifulSoup(r.text)
  
  TeXMacros = ''
  for s in soup.find_all('script'):
    if s.has_attr('src'):
      if s['src'] == 'local.js':
        r_TeXMacros = requests.get( urljoin(url, s['src']) )
        if re.search(r'window.MathJax\s*=\s*(.*);', r_TeXMacros.text, re.DOTALL):
          js_snippet  = re.search(r'window.MathJax\s*=\s*(.*);', r_TeXMacros.text, re.DOTALL).group(1)
          json_obj = demjson.decode(js_snippet)
          if 'TeX' in json_obj:
             if 'Macros' in json_obj['TeX']:
               for m in json_obj['TeX']['Macros']:
                 if re.match(r'\\unicode{x.*}', json_obj['TeX']['Macros'][m]):
                   json_obj['TeX']['Macros'][m] = unichr(int(re.sub(r'\\unicode{x(.*)}', r'\1', json_obj['TeX']['Macros'][m]), 16))
                 TeXMacros = '\n'.join([TeXMacros, ''.join(['\\providecommand{\\', m, '}{', json_obj['TeX']['Macros'][m], '}']), ''.join(['\\renewcommand{\\', m, '}{', json_obj['TeX']['Macros'][m], '}'])])
  
  title = soup.select('#aueditable h1')[0].text
  author_info = filter(None, [s.strip() for s in soup.select('#article-copyright')[0].text.split('by\n')[1].split('\n')])
  author = author_info[0]
  copyright_info = ' '.join(soup.select('#article-copyright')[0].text.split())
  pubhistory_info = soup.select('#pubinfo')[0].text
  preamble = soup.select('#aueditable #preamble')[0]
  main_text = soup.select('#aueditable #main-text')[0]
  bibliography = None
  if soup.select('#aueditable #bibliography'):
    bibliography = soup.select('#aueditable #bibliography')[0]
  acknowledgments = None
  if soup.select('#aueditable #acknowledgments'):
    acknowledgments = soup.select('#aueditable #acknowledgments')[0]
  
  preamble_TeX        = ConvertHTML(preamble)
  main_text_TeX       = ConvertHTML(main_text)
  bibliography_TeX    = ConvertHTML(bibliography)
  acknowledgments_TeX = ''
  if acknowledgments:
    if acknowledgments.children:
      for i in acknowledgments.children:
        if i.name:
          if i.name == "h3" and i.text == "Acknowledgments":
            acknowledgments_TeX = '\n'.join([acknowledgments_TeX, '\\setcounter{secnumdepth}{-1}\n\\chapter{Acknowledgments}'])
          else:
            acknowledgments_TeX = '\n'.join([acknowledgments_TeX, ConvertHTMLElement(i)])
  
  full_TeX   = OutputTeX(title, author, preamble_TeX, main_text_TeX, bibliography_TeX, acknowledgments_TeX, TeXMacros, pubhistory_info, copyright_info, url)
  full_TeX   = ProcessNotes(full_TeX, url)
  
  for img in re.findall(r'\\includegraphics{(.*?)}', full_TeX, flags=re.MULTILINE):
    img_local = os.path.join(os.path.dirname(os.path.abspath(output)), img)
    downloader = urllib.URLopener()
    downloader.retrieve(urljoin(url, img), img_local)
    if re.match('.*.svg', img):
      img_local_pdf = re.sub(r'(.*).svg', r'\1.pdf', img_local)
      img_pdf = re.sub(r'(.*).svg', r'\1.pdf', img)
      call(["inkscape", '-D', '-z', ''.join(['--file=', img_local]), ''.join(['--export-pdf=', img_local_pdf])])
      full_TeX = re.sub(''.join([r'\\includegraphics{', img, '}']), ''.join([r'\\includegraphics[max width=\\textwidth]{', img_pdf, '}']), full_TeX, flags=re.MULTILINE)
    else:
      full_TeX = re.sub(''.join([r'\\includegraphics{', img, '}']), ''.join([r'\\includegraphics[max width=\\textwidth]{', img, '}']), full_TeX, flags=re.MULTILINE)
  
  output_file = open(output, "w")
  output_file.write(full_TeX.encode('utf8'))
  output_file.close()

def helpConvertSEPHTML():
  args = sys.argv[0:]
  print(''.join(['Usage: \n', args[0], ' <URL to the entry> [<output.tex>] \n']))
  print(''.join(['For example:']))
  print(''.join(['\t', args[0], ' https://plato.stanford.edu/entries/comte/ comte.tex \n']))
  print(''.join(['or\n\t', args[0], ' https://plato.stanford.edu/entries/comte/ \n']))

if __name__ == "__main__":
  main()
