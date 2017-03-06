import sys
import os
import os.path
import re
import requests
import pypandoc
import demjson
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
  try:
    call(['xelatex', '-interaction=batchmode', script_id], stdout=FNULL, stderr=subprocess.STDOUT)
  except OSError:
    print 'xelatex not found.'
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
    return [val[0]/val[1], 0.0, 0.0]
  else:
    return [0.0, 0.0, 0.0]

def TeXTotalHeight(tex_str, TotalWidth=['\\textwidth']):
  script_template_fname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'get_total_height.template')
  f = open(script_template_fname, 'r')
  script_template = Template(f.read())
  f.close()
  
  set_hsize = '\n'.join(['\\setlength{\\hsize}{'+w+'}' for w in TotalWidth])
  get_width_script = script_template.substitute(sethsize=set_hsize, tex_to_measure=tex_str.strip())
  
  DIR_CURRENT = os.getcwd()
  DIR_TEMP    = tempfile.mkdtemp()
  os.chdir(DIR_TEMP)
  script_id = str(uuid.uuid4())
  get_width_script_file = open(os.path.join(DIR_TEMP, script_id+'.tex'), "w")
  get_width_script_file.write(get_width_script.encode('utf8'))
  get_width_script_file.close()
  
  FNULL = open(os.devnull, 'w')
  try:
    call(['xelatex', '-interaction=batchmode', script_id], stdout=FNULL, stderr=subprocess.STDOUT)
  except OSError:
    print 'xelatex not found.'
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
    return 0.0


def WidthGT(w1, w2, w_em=10.00002, w_tabcolsep=6, w_arrayrulewidth=0.4):
  w1AGETw2 = True
  w1ALETw2 = True
  for i in range(len(w1)):
    if w1[i] < w2[i]:
      w1AGETw2 = False
    if w1[i] > w2[i]:
      w1ALETw2 = False
  if w1AGETw2:
    return True
  elif w1ALETw2:
    return False
  else:
    return w1[0]*w_em + w1[1]* w_tabcolsep + w1[2]*w_arrayrulewidth >= w2[0]*w_em + w2[1]* w_tabcolsep + w2[2]*w_arrayrulewidth

def MaxWidth(w1, w2):
  if WidthGT(w1, w2):
    return w1
  return w2

def SumWidth(width_list):
  sum_width = [0.0] * 3
  if width_list:
    for w in width_list:
      sum_width[0] += w[0]
      sum_width[1] += w[1]
      sum_width[2] += w[2]
  return sum_width

def HTMLContentsWidth(contents, nowrap=False):
  maxWidth = [0.0, 0.0, 0.0]
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
              width = TeXWidth(latex_str, nowrap)
              maxWidth = MaxWidth(width, maxWidth)
            e_html = ''
          width = TeXWidth(ConvertHTMLElement(e), nowrap)
          maxWidth = MaxWidth(width, maxWidth)
          #  shouldn't really happen
        elif e.name == 'table':
          # print maxWidth
          width    = HTMLEntityWidth(e, nowrap)
          maxWidth = MaxWidth(width, maxWidth)
          # print width
          # print maxWidth
        else:
          e_html += unicode(e)
      else:
        e_html += unicode(e)
    if e_html:
      latex_str = pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')
      width = TeXWidth(latex_str, nowrap)
      maxWidth = MaxWidth(width, maxWidth)
  return maxWidth

def HTMLEntityWidth(html_entity, nowrap=False):
  tag = html_entity.name
  if tag == 'table':
    table_width = [0,0,0]
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
            td_width[1] += 2.0
            td_width[2] += 1.0
            row_width_vector.append(td_width)
        row_width = SumWidth(row_width_vector)
        row_width[2] += 1.0
        table_width = MaxWidth(row_width, table_width)
    # print table_width
    return table_width
  else:
    return HTMLContentsMinWidth(html_entity.contents, nowrap)

def PrintWidth(width):
  list_width_str = []
  str_em=("%.3fem" % width[0]) # diff between article & tufte
  if str_em != "0.000em":
    list_width_str.append(str_em)
  
  str_tcs=("%.3f\\tabcolsep" % width[1])
  if str_tcs != '0.000\\tabcolsep':
    list_width_str.append(str_tcs)
  
  str_arw=("%.3f\\arrayrulewidth" % width[2])
  if str_arw != "0.000\\arrayrulewidth":
    list_width_str.append(str_arw)
  
  if list_width_str:
    return '+'.join(list_width_str)
  else:
    return '0pt'

def HTMLContents2TeX(contents, TableEnv=False, TotalWidth = ['\\textwidth']):
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
          e_contents = BeautifulSoup(re.sub(r'pdf include(.*)pdf include', r'\1',  unicode(e), flags=re.MULTILINE|re.DOTALL).strip(), 'lxml').html.body.contents
          latex_str += HTMLContents2TeX(e_contents)
          # print 'HTMLContents2TeX: contents: str: pdf include'
        else:
          e_html += unicode(e)
      elif hasattr(e, 'name'):
        if e.name in ['h2', 'h3', 'h4', 'p', 'blockquote', 'ul', 'ol', 'div', 'table']:
          if e_html.strip():
            if not ignore:
              latex_str += pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash')     
              if e.name == 'p':
                latex_str += '\n'
            else:
              latex_str += CommentTeX(pypandoc.convert(e_html, 'tex', format='html+tex_math_single_backslash'))
              if e.name == 'p':
                latex_str += '\n'
          else:
            if not ignore:
              latex_str += '\n'
            else:
              latex_str += '% \n'
          e_html     = ''
          if not ignore:
            latex_str   += ConvertHTMLElement(e, TableEnv, TotalWidth)
          else:
            latex_str   += CommentTeX(ConvertHTMLElement(e, TableEnv, TotalWidth))
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
  return '\n'.join(['\\begin{quote}', HTMLContents2TeX(html_entity.contents).strip(), '\\end{quote}'])

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

def table_HTMLEntity2TeX(table_entity, TableEnv = False, TotalWidth = ['\\textwidth']):
  table_matrix = []
  max_num_cols = 0
  for r in table_entity.children:
    if r.name == 'tr':
      row_vector = []
      valign_row = ''
      if r.has_attr('valign'):
        valign_row = r['valign']
      align_row  = ''
      if r.has_attr('align'):
        align_row = r['align']
      for d in r.children:
        if d.name == 'td':
          colspan = 1
          rowspan = 1
          nowrap  = False
          valign  = 'middle'
          align   = 'left'
          if d.has_attr('colspan'):
            colspan = int(d['colspan'])
          if d.has_attr('rowspan'):
            rowspan = int(d['rowspan'])
          if d.has_attr('nowrap'):
            if d['nowrap'] == 'nowrap':
              nowrap = True
          
          if d.has_attr('valign'):
            valign = d['valign']
          elif valign_row:
            valign = valign_row
          
          if d.has_attr('align'):
            align = d['align']
          elif align_row:
            align = align_row
          if d.has_attr('class'):
            if 'center' in d['class']:
              align='center'
          minWidth = HTMLContentsWidth(d.contents, nowrap)
          maxWidth = HTMLContentsWidth(d.contents, True)
          # td_latex = HTMLContents2TeX(d.contents, TableEnv = True)
          row_vector.append((colspan, rowspan, nowrap, valign, align, minWidth, maxWidth))
      row_num_cols = sum([d_element[0] for d_element in row_vector])
      if row_num_cols > max_num_cols:
        max_num_cols = row_num_cols
      table_matrix.append(row_vector)
  
  ## Column Widths
  col_min_width = [None] * max_num_cols
  col_max_width = [None] * max_num_cols
  col_nowrap    = [True] * max_num_cols
  for r in table_matrix:
    c=0
    for d in r:
      colspan = d[0]
      if colspan == 1:
        col_nowrap[c] = (col_nowrap and d[2])
        if col_min_width[c] is None:
          col_min_width[c] = d[5]
        else:
          col_min_width[c] = MaxWidth(col_min_width[c], d[5])
        if col_max_width[c] is None:
          col_max_width[c] = d[6]
        else:
          col_max_width[c] = MaxWidth(col_max_width[c], d[6])
      c += colspan
  
  
  for r in table_matrix:
    c=0
    for d in r:
      colspan = d[0]
      if colspan > 1:
        # print [d[5], d[6]]
        n_wrap = colspan - sum(col_nowrap[c:(c+colspan)])
        if WidthGT(d[5], SumWidth(col_min_width[c:(c+colspan)])):
          for ci in range(c,(c+colspan)):
            if not col_nowrap[ci]:
              for j in range(len(col_min_width[ci])):
                col_min_width[ci][j] += ((d[5][j] - sum([w[j] for w in col_min_width[c:(c+colspan)]]))/n_wrap)
                # print 'expanded'
        if WidthGT(d[6], SumWidth(col_max_width[c:(c+colspan)])):
          for ci in range(c,(c+colspan)):
            if not col_nowrap[ci]:
              for j in range(len(col_max_width[ci])):
                col_max_width[ci][j] += ((d[6][j] - sum([w[j] for w in col_max_width[c:(c+colspan)]]))/n_wrap)
                # print 'expanded'
      c += colspan
  
  
  # col_width = []
  for c in range(max_num_cols):
    threshold = 9
    if col_max_width[c][0] < threshold:
      col_min_width[c] = col_max_width[c]
  #   weight_mu = max(0, col_max_width[c][0] - threshold)
  #   weight_M  = 1
  #   w = []
  #   for j in range(len(col_min_width[c])):
  #     # weighted mean
  #     mu = .9*col_min_width[c][j] + .1*col_max_width[c][j]
  #     # geometric mean
  #     # col_width[c] = sqrt(col_min_width[c]*col_max_width[c]) 
  #     # harmonic mean
  #     # col_width[c] = 2/((1/col_min_width[c])+(1/col_max_width[c]))
  #     w.append((weight_mu*mu + weight_M*col_max_width[c][j])/(weight_mu + weight_M))
  #   col_width.append(w)
  
  fixed_width = [0.0, 0.0, 0.0]
  flexibility = [0.0] * max_num_cols
  for c in range(max_num_cols):
    if col_nowrap[c]:
      fixed_width      = SumWidth([fixed_width, col_max_width[c]])
    else:
      flexibility[c]   = col_max_width[c][0]
  fixed_width[1] += 2*max_num_cols
  fixed_width[2] += (max_num_cols+1)
  F = sum(flexibility)
  if sum(flexibility) > 0:
    for c in range(max_num_cols):
      flexibility[c] = flexibility[c]/F
  
  col_width_str=[]
  for c in range(max_num_cols):
    if col_nowrap[c]:
      col_width_str.append(PrintWidth(col_max_width[c]))
    else:
      if col_max_width[c][0] < 1.05*col_min_width[c][0]:
        col_width_str.append(PrintWidth(col_max_width[c]) + '+2pt')
      else:
        col_width_str.append('\\minof{'+PrintWidth(col_max_width[c]) + '+2pt' +\
                     '}{\\maxof{' + PrintWidth(col_min_width[c]) + '+2pt' + \
                     '}{(\\hsize-(' + PrintWidth(fixed_width)+'))*\\real{'+("%.2f"%flexibility[c])+'}}}')
  
  table_latex = '\\begin' 
  if TableEnv:
    table_latex += '{tabular}'
  else:
    table_latex += '{longtable}'
  preamble = ''
  for idx in range(max_num_cols):
    if col_nowrap[idx]:
      preamble += 'l'
    else:
      preamble += ('p{{' +col_width_str[idx]+ '}}')
  table_latex += ('{'+preamble+'}\n')
  r_idx = 0
  for r in table_entity.children:
    row_latex = ''
    if r.name == 'tr':
      row_td_latex = []
      d_idx = 0
      c_idx = 0
      for d in r.children:
        if d.name == 'td':
          td_latex = ''
          if d.contents:
            colspan = table_matrix[r_idx][d_idx][0]
            cell_width_str = ('{' + '+'.join(col_width_str[c_idx:(c_idx+colspan)]) + '}')
            td_latex = HTMLContents2TeX(d.contents, True, TotalWidth+[cell_width_str])
          row_td_latex.append(td_latex)
          d_idx += 1
          c_idx += colspan
          
      
      row_num_cells = len(row_td_latex)
      non_empty_cells = [False] * row_num_cells
      for idx in range(row_num_cells):
        if row_td_latex[idx].strip():
          non_empty_cells[idx] = True
      
      row_skip = [0] * row_num_cells
      needs_skip = False
      if sum(non_empty_cells) > 1:
        needs_skip = not all([table_matrix[r_idx][i][3]=='top' for i in range(row_num_cells) if non_empty_cells[i]])
      # print (r_idx, needs_skip)
      # print table_matrix[r_idx]
      # print non_empty_cells
      # print '----------------------'
      d_idx = 0
      c_idx = 0
      if needs_skip:
        max_total_height = 0
        cell_heights = []
        for td_latex in row_td_latex:
          if td_latex.strip():
            colspan = table_matrix[r_idx][d_idx][0]
            cell_width_str = '+'.join(col_width_str[c_idx:(c_idx+colspan)])
            # cell_width[1] += (2*(colspan-1))
            # cell_width[2] += (colspan-1)
            h = TeXTotalHeight(td_latex, TotalWidth + [cell_width_str])
            if h > max_total_height:
              max_total_height = h
            cell_heights.append(h)
          else:
            cell_heights.append(0)
          c_idx+=colspan
          d_idx+=1
        for i in range(row_num_cells):
          if table_matrix[r_idx][i][3]=='middle':
            row_skip[i] = .5*(max_total_height - cell_heights[i])
          elif table_matrix[r_idx][i][3]=='bottom':
            row_skip[i] = (max_total_height - cell_heights[i])
            
      c_idx = 0
      d_idx = 0
      for d in r.children:
        if d.name == 'td':
          colspan = table_matrix[r_idx][d_idx][0]
          rowspan = table_matrix[r_idx][d_idx][1]
          nowrap  = table_matrix[r_idx][d_idx][2]
          valign  = table_matrix[r_idx][d_idx][3]
          align   = table_matrix[r_idx][d_idx][4]
          cell_width_str = ('{' + '+'.join(col_width_str[c_idx:(c_idx+colspan)]) + '}')
          # cell_width[1] += (2*(colspan-1))
          # cell_width[2] += (colspan-1)
          skip_size  = 0
          if needs_skip:
            skip_size = row_skip[d_idx]
          td_latex = row_td_latex[d_idx]
          cell_latex = RenderCell(td_latex, cell_width_str, colspan, rowspan, nowrap, valign, align, skip_size)
          if row_latex == '':
            row_latex = ' ' + cell_latex
          else:
            row_latex += '\n& ' + cell_latex.strip()
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

def RenderCell(tex_src, width_str, colspan=1, rowspan=1, nowrap=False, valign='middle', align='left', skip=0):
  cell_latex=' '
  
  halign_tag=False
  if align != 'left':
    halign_tag = True
  
  cell_wrapper=False
  if (not nowrap) and '\\\\' in tex_src:
    cell_wrapper=True
  elif nowrap:
    cell_wrapper=True
  
  multicolumn_tag=False
  if colspan > 1:
    multicolumn_tag=True
  if align != 'left':
    multicolumn_tag=True
  
  vskip_in_cell=(valign != 'top') and (skip != 0)
  
  cell_latex=''
  if tex_src.strip():
    begin_cell = ''
    end_cell = ''
    if tex_src.strip():
      if halign_tag:
        if align == 'center':
          begin_cell = '{\\centering '+begin_cell
          end_cell   = end_cell+'}'
        elif align == 'right':
          begin_cell = '{\\raggedleft '+begin_cell
      
      if cell_wrapper:
        if not nowrap:
          begin_cell = '\\nowrapcell{p{'+ width_str +'}}{'+begin_cell
          end_cell   = end_cell+'}'
        else:
          cell_align_nowrap = 'l'
          if align == 'center':
            cell_align_nowrap = 'c'
          elif align == 'right':
            cell_align_nowrap = 'r'
          begin_cell = '\\nowrapcell{'+cell_align_nowrap+'}{' + begin_cell
          end_cell   = end_cell + '}'
    
    if multicolumn_tag:
      column_def = 'l'
      if nowrap:
        column_def = align[0]
      else:
        if align=='center':
          column_def = 'C{' + width_str + '}'
        elif align=='right':
          column_def = 'R{' + width_str + '}'
        else:
          column_def = 'L{' + width_str + '}'
      begin_cell = '\\multicolumn{' + str(colspan) + '}{' + column_def + '}{'+begin_cell
      end_cell   = end_cell + '}'
    
    if vskip_in_cell:
      begin_cell = begin_cell+'\\setlength{\\cellskip}{'+("%.2f\\baselineskip" % skip)+'-\\baselineskip}{\\vskip 0pt}{\\vskip \cellskip}'
      end_cell   = ''+end_cell
    cell_latex = begin_cell + tex_src.strip() + end_cell
  return cell_latex

def ConvertHTMLElement(html_element, TableEnv=False, TotalWidth = ['\\textwidth']):
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
    return table_HTMLEntity2TeX(html_element, TableEnv, TotalWidth)
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
            i_contents = BeautifulSoup(re.sub(r'pdf include(.*)pdf include', r'\1',  unicode(i), flags=re.MULTILINE|re.DOTALL).strip(), 'lxml').html.body.contents
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
    soup = BeautifulSoup(r.text, 'lxml')
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
    if(len(args)>1):
      output=args[1]
  else:
    helpConvertSEPHTML()
    sys.exit(1)
  
  try:
    r  = requests.get(url)
    r.raise_for_status()
  except requests.exceptions.HTTPError as err:
    print err
    sys.exit(1)
  except requests.exceptions.RequestException as e:
    print e
    sys.exit(1)
  url = r.url
  
  soup = BeautifulSoup(r.text, "lxml")
  
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
  
  if not soup.select('#aueditable'):
    print 'This page does not appear to be a valid SEP entry.'
    sys.exit(1)
  
  title = soup.select('#aueditable h1')[0].text
  author_info = filter(None, [s.strip() for s in soup.select('#article-copyright')[0].text.split('by\n')[1].split('\n')])
  author = author_info[0]
  copyright_info = pypandoc.convert(' '.join(soup.select('#article-copyright')[0].text.split()), 'tex', format='markdown')
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
    r_img = requests.get(urljoin(url, img))
    with open(img_local, 'wb') as img_local_file:
      img_local_file.write(r_img.content)
    if re.match('.*.svg', img):
      img_local_pdf = re.sub(r'(.*).svg', r'\1.pdf', img_local)
      img_pdf = re.sub(r'(.*).svg', r'\1.pdf', img)
      try:
        call(["inkscape", '-D', '-z', ''.join(['--file=', img_local]), ''.join(['--export-pdf=', img_local_pdf])])
      except OSError:
        print 'inkscape not found. Please manually convert ' + img + 'into .pdf or other formats that can by included by \\includegraphics.'
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
