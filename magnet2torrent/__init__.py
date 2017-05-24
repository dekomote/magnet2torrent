#!/usr/bin/env python
# -*- coding: utf-8 -

from __future__ import print_function, unicode_literals
import argparse
import logging
import os
import sys
import tempfile
import time
from functools import partial
from multiprocessing import Pool, Process, get_logger, log_to_stderr
import libtorrent as lt


logger = logging.getLogger('MAGNET2TORRENT')

def setup_args():
    """Setup and parse the command line arguments

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('magnet_urls', metavar='URL', type=str,
        nargs='+', help='List of urls to parse')
    parser.add_argument(
        "-d", "--dir",
        help="Save torrent files to specified directory instead of pushing it to stdout")
    parser.add_argument(
        "-l", "--loglevel", help="Log level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO")
    parser.add_argument(
        "-j", "--process_pool", default=4, type=int,
        help="Max number of processes in parallel",)
    parser.add_argument(
        "-t", "--timeout",
        help="Max seconds to wait for metadata", type=int, default=10)
    return parser.parse_args()



def handle_url(url, dir, timeout=20):
    """Given a magnet url and a dir, handle the url - write the torrent file to the dir.

    Args:
        url (str): Magnet URL (full)
        dir (str): local directory
        timeout (int): Timeout after seconds
    """
    logger = logging.getLogger('MAGNET2TORRENT')

    logger.info("Opening session for link %s", url)
    session = lt.session()
    temp_path = tempfile.gettempdir()

    params = {
        'save_path': temp_path,
        'duplicate_is_error': False,
    }

    handle = lt.add_magnet_uri(session, url, params)

    logger.info("Waiting metadata for %s", url)
    tout = 0
    while (not handle.has_metadata()):
        time.sleep(.1)
        tout += 0.1
        if tout >= timeout:
            logger.error("Waiting metadata timed out for %s", url)
            return

    logger.info("Metadata for %s retrieved", url)
    torrent_info = handle.get_torrent_info()

    fs = lt.file_storage()
    for file in torrent_info.files():
        fs.add_file(file)
    torrent_file = lt.create_torrent(fs)
    torrent_file.set_comment(torrent_info.comment())
    torrent_file.set_creator(torrent_info.creator())

    file_path = os.path.join(dir, "%s.torrent" % torrent_info.info_hash())

    with open(file_path, 'wb') as f:
        f.write(lt.bencode(torrent_file.generate()))
        f.close()

    logger.info("Torrent file saved to %s", file_path)


def run():
    """Run the script"""

     # Parse the command line args
    args = setup_args()

    # Setup logging
    logger.setLevel(getattr(logging, args.loglevel.upper()))

    # No dir provided, save in home folder
    if not args.dir:
        from os.path import expanduser
        args.dir = expanduser("~")

    # Make handle url partial so we can call it in a worker pool
    pool_size = args.process_pool
    if len(args.magnet_urls) < pool_size:
        pool_size = len(args.magnet_urls)
    pool = Pool(pool_size)
    handler = partial(handle_url, dir=args.dir, timeout=args.timeout)

    # Handle interrupt and fill in the pool
    try:
        res = pool.map_async(handler, args.magnet_urls)
        res.get(args.timeout + 5)
    except KeyboardInterrupt:
        logger.warning("Caught KeyboardInterrupt, terminating workers")
        pool.terminate()
    else:
        logger.debug("Pool closing")
        pool.close()
    pool.join()
