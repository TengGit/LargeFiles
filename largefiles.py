#!/usr/bin/env python3
# coding: utf-8


'''MIT License

Copyright (c) 2021 Teng K. J.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

largefiles.py --- find large files in a directory

'''

from pathlib import Path
import logging
import math
import numpy as np

# Report progress every report_time file/dir
# so that we can make sure it's running
report_every = 5000
next_report_num = 0
scanned = 0

def format_size(size):
    ''' Add appropriate unit to represent a size.
    
    format_size(1) -> "1B"
    format_size(1024) -> "1KiB"
    format_size(1<<100) -> "1.049e+06YiB"
    etc.
    '''
    for unit in 'B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB':
        if size < 1024:
            return '{:.4g}{}'.format(size, unit)
        size /= 1024
    return '{:.4g}YiB'.format(size)


class File:
    '''Represents a file.
    
    Stats the file's size and store it on init.
    '''
    def __init__(self, path):
        self._obj = path
        self.name = path.name
        try:
            self.size = self._obj.lstat().st_size
        except OSError as ex:
            logging.error(ex)
            self.size = 0
        
        global scanned
        scanned += 1
        
    def __repr__(self):
        return 'File({}), size={}'.format(self.name, format_size(self.size))


class Directory:
    '''Represents a directory.
    
    List all the files and directories in it on init, save the result and sort by size.
    '''
    def __init__(self, path=None):
        path = Directory._default(path, 'path')

        self._obj = path
        self.name = path.name
        self.content = []
        
        global scanned, next_report_num, report_every
        if scanned > next_report_num:
            next_report_num += report_every
            print(scanned, 'Scanning', path, '...', end='\r')
        
        try:
            st_result = self._obj.lstat()
            size = st_result.st_size
            
            # On Windows "junctions" are treated as directories rather than symbloic links.
            # So we must double-check whether it is really a directory.
            st_result2 = self._obj.stat()
            if st_result2.st_ino != st_result.st_ino:
                # logging.warning("skipping Windows junction directory {}...".format(self._obj))
                self.size = 0
                return
            for path in self._obj.iterdir():
                if path.is_symlink():
                    size += path.lstat().st_size
                    continue
                elif path.is_dir():
                    obj = Directory(path)
                else:
                    obj = File(path)
                self.content.append(obj)
                size += obj.size
        except OSError as e:
            size = 0
            logging.error(e)
            
        self.size = size
        scanned += 1
    
    def _default(dirname, name):
        if dirname is None:
            return Path('.')
        elif isinstance(dirname, str):
            return Path(dirname)
        elif not isinstance(dirname, Path):
            raise TypeError('{} must be None, a str or a pathlib.Path'.format(name))
        return dirname
    
    def __repr__(self):
        return 'Directory({}), size={}'.format(self.name, format_size(self.size))
        


def print_tree(path, threshold=1.2, level=0, file=None):
    level_str = '|'*level
    print('{}+ {} {}'.format(level_str, format_size(path.size), path.name), file=file)
    if isinstance(path, Directory):
        result = sorted(path.content, key=lambda x: x.size, reverse=True)
        if len(result) == 0:
            print('{}  (empty)'.format(level_str), file=file)
            return
        min_size = path.size * threshold / len(result)
        others = []
        for subpath in result:
            if subpath.size >= min_size:
                print_tree(subpath, threshold, level+1, file)
            else:
                others.append(subpath.size)
        if len(others)>0:
            print('{}|+ {} ({} others) avg={} stddev={}'.format(
                level_str, format_size(sum(others)), len(others),
                format_size(np.average(others)),
                format_size(math.sqrt(np.var(others)))
            ), file=file)


d = Directory('C:/')


import os
import html
import io
import itertools


# In[23]:


html_template = '''<!DOCTYPE html>
<html>
<head>
<title>Large file report</title>
<style>
.folder, .file {
  font-family: "Consolas", "Courier New", "Courier", monospace;
  font-weight: bold;
  font-size: 14px;
}
.folder-check {
  display: none;
}
.folder-check ~ div {
  display: none;
  padding-left: 1em;
}
.folder-check:checked ~ div {
  display: block;
}
.folder-name {
  color: #009;
}
.file-name {
  color: #090;
}
.size {
  color: #960;
}
.others {
  color: #666;
  font-weight: normal;
}
</style>
</head>
<body>
%s
</body>
</html>'''


def print_html_tree(path, threshold=1.2, level=0, file=None):
    content = print_html_tree_elements(path, threshold, level, builder=io.StringIO())
    print(html_template % content.getvalue(), file=file)

def print_html_tree_elements(path, threshold=1.2, level=0, counter=itertools.count(), builder=io.StringIO()):
    level_str = ' '*level
    if isinstance(path, Directory):
        builder.write(level_str + '<div class="folder">\n')
        builder.write('{} <input type="checkbox" class="folder-check" id="{id}"><label for="{id}" class="folder-name"><span class="size">({size})</span> {name}</label>\n'.format(
            level_str, id=counter.__next__(), name=html.escape(path.name), size=html.escape(format_size(path.size))
        ))
        result = sorted(path.content, key=lambda x: x.size, reverse=True)
        if len(result) == 0:
            min_size = 0
            builder.write('{} <div class="others">(empty)</div>\n'.format(level_str))
        else:
            min_size = path.size * threshold / len(result)
        others = []
        for subpath in result:
            if subpath.size >= min_size:
                print_html_tree_elements(subpath, threshold, level+1, counter, builder)
            else:
                others.append(subpath.size)
        if len(others) > 0:
            builder.write('{} <div class="others"><span class="size">({size})</span> ({num} others avg={avg} stddev={stddev})</div>\n'.format(
                level_str, size=html.escape(format_size(sum(others))), num=len(others),
                avg=html.escape(format_size(np.average(others))),
                stddev=html.escape(format_size(math.sqrt(np.var(others))))
            ))
        builder.write(level_str + '</div>\n')
    else:
        builder.write('{}<div class="file"><span class="size">({size})</span> <span class="file-name">{name}</span></div>\n'.format(
            level_str, size=html.escape(format_size(path.size)), name=html.escape(path.name)
        ))
    return builder


print_html_tree(d, file=open('C:/Large.html', 'w', encoding='utf8'))

