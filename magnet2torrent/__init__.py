#!/usr/bin/env python
# -*- coding: utf-8 -

'''
    BSD 3-Clause License
    Copyright (c) 2017, Dejan Noveski
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this
      list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above copyright notice,
      this list of conditions and the following disclaimer in the documentation
      and/or other materials provided with the distribution.

    * Neither the name of the copyright holder nor the names of its
      contributors may be used to endorse or promote products derived from
      this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
    FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
    DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
    OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
    OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

from __future__ import print_function, unicode_literals
import argparse
import logging
import os
import sys
import tempfile
import shutil
import time
from functools import partial
from multiprocessing import Pool, Process, get_logger, log_to_stderr
import libtorrent


log = logging.getLogger(__name__)

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



def handle_url(url, directory, timeout=20, temp_path=tempfile.mkdtemp()):
    """Given a magnet url and a directory, handle the url - write the torrent file to the directory.

    Args:
        url (str): Magnet URL (full)
        directory (str): local directory
        timeout (int): Timeout after seconds
    """

    log.info("Opening session for link %s", url)

    session = libtorrent.session()
    params = {
        'url': url,
        'save_path': temp_path,
        'duplicate_is_error': True,
        'storage_mode': libtorrent.storage_mode_t(2),
        'paused': False,
        'auto_managed': True,
    }

    handle = session.add_torrent(params)

    log.info("Waiting metadata")
    tout = 0
    while not handle.has_metadata():
        time.sleep(1)
        tout += 1
        if tout > timeout:
            log.error("Metadata retrieval timeout. Bump -t")
            return None
    session.pause()

    log.info("Metadata retrieved")
    torrent_info = handle.get_torrent_info()

    torrent_file = libtorrent.create_torrent(torrent_info)
    torrent_file.set_comment(torrent_info.comment())
    torrent_file.set_creator(torrent_info.creator())

    file_path = os.path.join(directory, "%s.torrent" % torrent_info.name())

    with open(file_path, 'wb') as f_handle:
        f_handle.write(libtorrent.bencode(torrent_file.generate()))
        f_handle.close()

    session.remove_torrent(handle)
    log.info("Torrent file saved to %s", file_path)


def run():
    """Run the script"""

     # Parse the command line args
    args = setup_args()

    # Setup logging
    log.setLevel(getattr(logging, args.loglevel.upper()))

    # No dir provided, save in home folder
    if not args.dir:
        args.dir = os.getenv("MAGNET2TORRENT_SAVE_PATH",
                             os.path.expanduser("~"))

    # Make handle url partial so we can call it in a worker pool
    pool_size = args.process_pool
    if len(args.magnet_urls) < pool_size:
        pool_size = len(args.magnet_urls)

    temp_dir = tempfile.mkdtemp()
    pool = Pool(pool_size)
    handler = partial(handle_url, directory=args.dir, timeout=args.timeout, temp_path=temp_dir)
    # Handle interrupt and fill in the pool
    try:
        res = pool.map_async(handler, args.magnet_urls)
        res.get(args.timeout + 5)
    except KeyboardInterrupt:
        log.warning("Terminating workers")
        shutil.rmtree(temp_dir)
        pool.terminate()
    else:
        shutil.rmtree(temp_dir)
        log.debug("Pool closing")
        pool.close()
    pool.join()
