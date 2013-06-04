# coding=latin-1

"""
Console User Interface

This module implements a console user interface for idxbeast.

Copyright (c) 2013, François Jeannotte.
"""

import apsw
from   contextlib import closing
import ctypes
import datetime
import math
import msvcrt
import os
import os.path
import subprocess
import sys
import time

import win32clipboard
import win32console

import core
import server

def sizeof_fmt(num):
    """
    Display a number of bytes in a human readable format. Taken from:
    http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
    """
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0
    return "%3.1f %s" % (num, 'TB')

def str_fill(s, length):
    """
    Truncates a string to the given length, using an ellipsis (...) in the
    middle if necessary.

    >>> str_fill('abcdefghijklmnopqrstuvwxyz', 15)
    'abcdef...uvwxyz'
    >>> str_fill('abcdef', 15)
    'abcdef         '
    """
    assert length > 0
    s = str(s)
    if len(s) == length:
        return s
    if len(s) > length:
        if length < 9:
            s = s[-length:]
        else:
            q,r = divmod(length-3, 2)
            s = s[0:q] + '...' + s[-(q+r):]
    if len(s) < length:
        s = s + ' '*(length - len(s))
    assert len(s) == length, 'len(s): {}, length:{}'.format(len(s), length)
    return s

class COORD(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short),
                ("y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("left"  , ctypes.c_short),
                ("top"   , ctypes.c_short),
                ("right" , ctypes.c_short),
                ("bottom", ctypes.c_short)]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [("dwSize"             , COORD),
                ("dwCursorPosition"   , COORD), 
                ("wAttributes"        , ctypes.c_ushort), 
                ("srWindow"           , SMALL_RECT), 
                ("dwMaximumWindowSize", COORD)]

k32 = ctypes.windll.kernel32
stdout = k32.GetStdHandle(-11)

def wait_key():
    """
    Waits until a key is pressed. Returns the key.
    """
    while True:
        if msvcrt.kbhit():
            return msvcrt.getch()
        else:
            time.sleep(0.01)

def getcurpos():
    """
    Returns the cursor position as a COORD.
    """
    conInfo = CONSOLE_SCREEN_BUFFER_INFO()
    k32.GetConsoleScreenBufferInfo(stdout, ctypes.byref(conInfo)) 
    return conInfo.dwCursorPosition

def setcurpos(x, y):
    """
    Sets the cursor position.
    """
    k32.SetConsoleCursorPosition(stdout, COORD(x, y))

def putchxy(x, y, ch):
    """
    Puts a char at the specified position. The cursor position is not affected.
    """
    prevCurPos = getcurpos()
    setcurpos(x, y)
    msvcrt.putch(ch)
    setcurpos(prevCurPos.x, prevCurPos.y)

def get_console_size():
    """ Returns a (X, Y) tuple. """
    h = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
    x = h.GetConsoleScreenBufferInfo()['MaximumWindowSize'].X
    y = h.GetConsoleScreenBufferInfo()['MaximumWindowSize'].Y
    return (x,y)

def set_text_color(colors=None):
    """
    Sets the text color on the console. Calling this function with None (the
    default) will restore default colors. The colors must be a iterable of
    strings.
    """

    flags = 0

    # If colors is None, use defaults colors
    if not colors:
        flags = win32console.FOREGROUND_BLUE | win32console.FOREGROUND_GREEN | win32console.FOREGROUND_RED

    # colors is set, process it
    else:

        # If colors is a single string, use this as the single flag
        if isinstance(colors, basestring):
            flags = win32console.__dict__[colors]

        # Otherwise, consider colors a list of strings
        else:
            for color in colors:
                flags = flags | win32console.__dict__[color]

    # Set the color
    h = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
    h.SetConsoleTextAttribute(flags)

def write_color(text, colors, endline=False):
    """
    Prints the specified text, without endline, with the specified colors.
    After printing, the default color is restored.
    """
    text = unicode(text)
    set_text_color(colors)
    sys.stdout.write(text.encode('cp850'))
    if endline:
        sys.stdout.write('\n')
    set_text_color()

# The height of the interactive search console UI, not including the result
# rows.
search_cui_height = 17

def upd_search_display(conn, width, res_limit, search_str, sel_index,
                       sel_page, orderby, orderdir):

    # The rows are selectable with the A-Z chars, this limits the maximum
    # number of rows to 26
    assert res_limit > 0 and res_limit <= 26

    # Print the search query
    search_str_prefix = 'query: '
    setcurpos(0, getcurpos().y)
    print '{}{}'.format(search_str_prefix,
                        str_fill(search_str, width - len(search_str_prefix)))
    print

    # Execute the search and display the number of results, search time
    if len(search_str) > 1:
        start_time = time.clock()
        tot, cur = core.search(conn, search_str, res_limit, sel_page*res_limit,
                               orderby, orderdir)
        elapsed = time.clock() - start_time
        page_cnt = int(math.ceil(float(tot) / res_limit))
        print str_fill('{} results ({:.6f} seconds)'.format(tot, elapsed), width)
    else:
        cur = tuple()
        page_cnt = 0
        print str_fill('No results', width)
    print

    # Print the results table header
    print width*'-'
    print '      |  relev |   freq |  avgidx | document'
    print width*'-'

    # Fill the results table
    row_count = 0
    sel_loc = ''
    for relev, freq, avgidx, id, type_, locator, title in cur:
        if row_count == sel_index:
            selection_str = '*'
            sel_loc = locator
        else:
            selection_str = ' '
        print ' {}[{}] | {:>6.3f} | {:>6} | {:>7} | {}'.format(
              chr(ord('A') + row_count), selection_str, relev, int(freq),
              int(avgidx), str_fill(locator, width - 36))
        row_count += 1
    for _ in range(res_limit - row_count): print ' '*width
    print width*'-'
    print

    # Print the help and current parameters
    page_fmt = '{} of {}'.format(sel_page + 1, page_cnt) if page_cnt else ''
    print 'PgUp/PgDn  Page             : {}'.format(str_fill(page_fmt, width - 32))
    print 'F1         Order by         : {}'.format(str_fill(orderby , width - 32))
    print 'F2         Order direction  : {}'.format(str_fill(orderdir, width - 32))
    print
    print 'F3         Open with notepad'
    print 'F4         Open with default application'
    print 'F5         Copy locator to clipboard'
    print 'ESC        Quit'

    # Return the cursor to the first line, right after the search string
    setcurpos(len(search_str_prefix) + len(search_str), getcurpos().y -
              res_limit - search_cui_height)

    return row_count, page_cnt, sel_loc
  
def do_search(args):
    """Launch the interactive search console UI."""

    # Connect to the DB
    conn = apsw.Connection(args.db)

    # Setup initial parameters
    search_str = ' '.join(args.word)
    sel_index  = 0
    sel_page   = 0
    orderby    = 'relev'
    orderdir   = 'desc'
    init_line  = getcurpos().y
    res_limit  = 5
    width      = args.cuiwidth

    # Process user input and update display
    while True:
        row_count, page_count, sel_loc = upd_search_display(conn,
                                                            width,
                                                            res_limit,
                                                            search_str,
                                                            sel_index,
                                                            sel_page,
                                                            orderby,
                                                            orderdir) 
        k = wait_key()
        if ord(k) == 8: # BACKSPACE, erase last char
            search_str = search_str[:-1]
        elif ord(k) == 27: # ESC, quit
            break
        elif ord(k) == 224: # Control key
            other_k = wait_key()
            if ord(other_k) == 72: # Up arrow
                if sel_index > 0: sel_index -= 1
            elif ord(other_k) == 80: # Down arrow
                if sel_index < row_count-1: sel_index += 1
            elif ord(other_k) == 73: # Page up
                if sel_page > 0: sel_page -= 1
            elif ord(other_k) == 81: # Page down
                if sel_page < page_count-1: sel_page += 1
        elif ord(k) == 0: # F key (e.g., F1, F2, etc.)
            other_k = wait_key()
            if ord(other_k) == 59: # F1
                if orderby == 'relev': orderby = 'freq'
                elif orderby == 'freq': orderby = 'avgidx'
                else: orderby = 'relev'
            elif ord(other_k) == 60: # F2
                if orderdir == 'asc': orderdir = 'desc'
                else: orderdir = 'asc'
            elif sel_loc and ord(other_k) == 61: # F3
                subprocess.Popen(['notepad.exe', sel_loc])
            elif sel_loc and ord(other_k) == 62: # F4
                os.startfile(sel_loc)
            elif sel_loc and ord(other_k) == 63: # F5
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(sel_loc)
                win32clipboard.CloseClipboard()
        elif (ord(k) >= 48 and ord(k) <= 57) or (ord(k) >= 97 and ord(k) <= 122) or ord(k) == 32 or ord(k) == 95:
            search_str += k
            sel_index = 0
            sel_page  = 0
        elif ord(k) >= 65 and ord(k) <= (64 + row_count):
            sel_index = ord(k) - 65

    # Return the cursor to its original position
    setcurpos(0, getcurpos().y + res_limit + search_cui_height)

def do_index(args):

    # Launch indexing
    print 'Indexing sources:'
    for i, src in enumerate(args.src):
        print '{}: {}'.format(i + 1, src)
    print 'DB path : {}'.format(args.db)
    print 'Log file: {}'.format(args.logfile)
    start_time = time.clock()
    dstat, istat_array = core.start_indexing(args.db, args.src, args.nbprocs,
                                             args.exts, args.recurselinks)

    # Wait for indexing to complete, update status
    curpos = getcurpos()
    #c_width = get_console_size()[0] - 10
    c_width = args.cuiwidth
    while dstat.status != 'Idle':
        time.sleep(0.2)
        setcurpos(curpos.x, curpos.y)
        print
        print '-'*c_width
        print 'status   : {}'.format(str_fill(dstat.status, c_width-18))
        print str_fill('counts   : listed: {:<7}, up-to-date: {:<7}, outdated: {:<7}, new: {:<7}'.format(
        dstat.listed_count, dstat.uptodate_count, dstat.outdated_count, dstat.new_count), c_width-18)
        print 'document : {}'.format(str_fill(dstat.current_doc, c_width-18))
        print 'DB status: {}'.format(str_fill(dstat.db_status, 40))
        print
        print '-'*c_width
        header = ' {:^12} | {:^75}'.format('Progress', 'Document')
        print header
        print '-'*c_width
        for i in range(len(istat_array)):
            dat = istat_array[i]
            done_percentage = 0
            print ' {:>12} | {:>75}'.format(
            dat.doc_done_count, str_fill(dat.current_doc, 75)),
            if dat.status == 'writing':
                col = 'FOREGROUND_GREEN'
            elif dat.status == 'locked':
                col = 'FOREGROUND_RED'
            else:
                col = None
            write_color(str_fill(dat.status, 25), col, endline=True)
        print '-'*c_width

    elapsed_time = time.clock() - start_time
    print
    print 'Indexing completed in {}.'.format(datetime.timedelta(seconds=elapsed_time))

def do_stats(args):
    print 'Size of DB       : {}'.format(sizeof_fmt(os.path.getsize(args.db)))
    with closing(apsw.Connection(args.db)) as conn:
        cur = conn.cursor()
        for cnt, in cur.execute('SELECT COUNT(*) FROM match;'):
            print 'Unique words     : {}'.format(cnt)
        for cnt, in cur.execute('SELECT COUNT(*) FROM doc;'):
            print 'Indexed documents: {}'.format(cnt)

def main(cmd, args):
    if cmd == 'search':   do_search(args)
    elif cmd == 'index':  do_index(args)
    elif cmd == 'server': server.run(args.db)
    elif cmd == 'stats':  do_stats(args)
    else: raise Exception('Unknown command: {}'.format(cmd))

