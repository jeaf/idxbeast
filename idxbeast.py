# coding=latin-1

"""
idxbeast.py - simple content indexer.

This script implements a simple document indexing application.

Copyright (c) 2013, François Jeannotte.
"""

import argparse
import logging
import logging.handlers
import multiprocessing
import os.path as op
import sys
import urlparse

import core
import cui

def validate_db(db):
    if op.isdir(db):
        raise argparse.ArgumentTypeError('"{}" is a directory, it cannot be '
                                         'used as the DB path.')
    return op.abspath(op.expanduser(db))

def validate_logfile(f):
    if op.isdir(f):
        raise argparse.ArgumentTypeError('"{}" is a directory, it cannot be '
                                         'used as the log file.')
    return op.abspath(op.expanduser(f))

def validate_src(src):

    # First check if the src is a URL (only http is supported)
    parse_result = urlparse.urlparse(src)
    if parse_result.scheme == 'http':
        return parse_result.geturl()

    # If its not a URL, assume it is a directory
    if not op.exists(src):
        raise argparse.ArgumentTypeError('The directory "{}" does not exist'
                                         .format(src))
    if not op.isdir(src):
        raise argparse.ArgumentTypeError('"{}" exists, but is not a directory'
                                         .format(src))
    return op.abspath(op.expanduser(src))

def validate_nb_procs(nb_procs):
    try:
        val = int(nb_procs)
    except:
        raise argparse.ArgumentTypeError('{} is not a valid integer'.format(
                                         nb_procs))
    if val not in range(17):
        raise argparse.ArgumentTypeError('the number of processes must be '
                                         'between 0 and 16 inclusive, {} is '
                                         'invalid.'.format(val))
    return multiprocessing.cpu_count() if val == 0 else val

def validate_recurselinks(n):
    try:
        val = int(n)
    except:
        raise argparse.ArgumentTypeError('{} is not a valid integer'.format(n))
    if val not in range(9):
        raise argparse.ArgumentTypeError('the recursion level must be '
                                         'between 0 and 8 inclusive, {} is '
                                         'invalid.'.format(val))
    return val

def main():

    # Check the first argument for the command name
    supported_cmds = ['index', 'search', 'server', 'stats']
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if not cmd in supported_cmds:
        print 'Error: invalid command.'
        print
        print 'The first argument must be a command name. Supported commands:'
        print
        for c in supported_cmds: print '    {}'.format(c)
        print
        print 'For detailed usage information of a specific command, please '
        print 'use the -h option. For example: idxbeast.py index -h.'
        sys.exit(0)

    # Create the parser object, add common arguments
    parser = argparse.ArgumentParser(prog='{} {}'.format(
                                     op.basename(sys.argv[0]), cmd))
    parser.add_argument('--db', type=validate_db,
                        default=validate_db('~\\idxbeast.db'),
                        help='The path to the DB file to connect to. The '
                             'tilde (~) symbol can be used in the path, and '
                             'will expand to the current user\'s home '
                             'directory. Defaults to ~\\idxbeast.db.')
    parser.add_argument('--logfile', type=validate_logfile,
                        default=validate_logfile('~\idxbeast.log'),
                        help='The path to the log file. More files may be '
                             'created if the log file gets too big. For '
                             'example, idxbeast.log.1, idxbeast.log.2, etc. '
                             'The tilde (~) symbol can be used in '
                             'the path, and will expand to the current '
                             'user\'s home directory. Defaults to '
                             '~\\idxbeast.log.')

    # Add index specific arguments
    if cmd == 'index':
        parser.add_argument('src', nargs='+', type=validate_src,
                            help='One or more indexing sources. The specified '
                                 'directories will be recursively indexed. '
                                 'The tilde (~) symbol can be used in the '
                                 'path, and will expand to the current '
                                 'user\'s home directory.')
        parser.add_argument('--nbprocs', default=validate_nb_procs(0),
                            type=validate_nb_procs,
                            help='The number of indexing processes, an '
                                 'integer between 0 and 16 inclusive. 0 (the '
                                 'default) will use the number of logical '
                                 'CPUs.')
        parser.add_argument('--exts',
                            default='bat c cpp cs cxx h hpp htm html ini java '
                                    'js log md py rest rst txt xml yaml yml',
                            help='A space separated list of file extensions '
                                 'to consider for indexing. The default is a '
                                 'list of the most common text files (e.g., '
                                 'bat, cxx, xml, etc.)')
        parser.add_argument('--recurselinks',
                            default=validate_recurselinks(0),
                            type=validate_recurselinks,
                            help='The recurse level for HTML links. Must be '
                                 'between 0 and 8 inclusive. The default is '
                                 '0, meaning no recursion.')

    # Add search specific arguments
    elif cmd == 'search':
        parser.add_argument('word', nargs='+',
                            help='One or more words to search for')

    # Parse args
    args = parser.parse_args(sys.argv[2:])

    # If the command is search, server, or stats, the DB must already exists
    if cmd in 'search server stats'.split() and not op.isfile(args.db):
        print 'Error: the specified DB ({}) does not exist.'.format(args.db)
        print 'The index command should be run at least once before executing'
        print 'a search, server, or stats command.'
        sys.exit(0)

    # Setup file logging in the core module
    log_handler = logging.handlers.RotatingFileHandler(args.logfile,
                                                       maxBytes=10*1024**2,
                                                       backupCount=5)
    log_handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] '
                                               '%(levelname)s: %(message)s'))
    core.log.add_handler(log_handler)

    # Call console user interface
    return cui.main(cmd, args)

if __name__ == '__main__':
    main()

