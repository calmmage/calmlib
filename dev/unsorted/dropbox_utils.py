import datetime
import os
import sys
import time
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import dropbox
import six

from calmlib import get_personal_logger
from calmlib.autocast import autocast_args
from calmlib.found_on_the_web import stopwatch

logger = get_personal_logger(__name__)


# todo: remove remaining prints. Where are they hiding? Something about timings of operations.
#  Oh, I guess it's that stopwatch method


def list_folder(dbx, folder, subfolder):
    """List a folder.
    Return a dict mapping unicode filenames to
    FileMetadata|FolderMetadata entries.
    """
    path = '/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'))
    while '//' in path:
        path = path.replace('//', '/')
    path = path.rstrip('/')
    try:
        with stopwatch('list_folder'):
            res = dbx.files_list_folder(path)
    except dropbox.exceptions.ApiError as err:
        logger.debug(f'Folder listing failed for {path} -- assumed empty: {err}')
        return {}
    else:
        rv = {}
        for entry in res.entries:
            rv[entry.name] = entry
        return rv


def download(dbx, folder, subfolder, name):
    """Download a file.
    Return the bytes of the file, or None if it doesn't exist.
    """
    path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    while '//' in path:
        path = path.replace('//', '/')
    with stopwatch('download'):
        try:
            md, res = dbx.files_download(path)
        except dropbox.exceptions.HttpError as err:
            logger.error(f'*** HTTP error {err}')
            return None
    data = res.content
    logger.debug(f'{len(data)} bytes; md: {md}')
    return data


def upload(dbx, fullname, folder, subfolder, name, overwrite=False):
    """Upload a file.
    Return the request response, or None in case of error.
    """
    path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    while '//' in path:
        path = path.replace('//', '/')
    mode = (dropbox.files.WriteMode.overwrite
            if overwrite
            else dropbox.files.WriteMode.add)
    mtime = os.path.getmtime(fullname)
    with open(fullname, 'rb') as f:
        data = f.read()
    with stopwatch('upload %d bytes' % len(data)):
        try:
            res = dbx.files_upload(
                data, path, mode,
                client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
                mute=True)
        except dropbox.exceptions.ApiError as err:
            logger.error(f'*** API error {err}')
            return None
    logger.debug(f"uploaded as {res.name.encode('utf8')}")
    return res


def yesno(message, default, args):
    """Handy helper function to ask a yes/no question.
    Command line arguments --yes or --no force the answer;
    --default to force the default answer.
    Otherwise a blank line returns the default, and answering
    y/yes or n/no returns True or False.
    Retry on unrecognized answer.
    Special answers:
    - q or quit exits the program
    - p or pdb invokes the debugger
    """
    if args.default:
        logger.debug(message + '? [auto]' + ('Y' if default else 'N'))
        return default
    if args.yes:
        logger.debug(message + '? [auto] YES')
        return True
    if args.no:
        logger.debug(message + '? [auto] NO')
        return False
    if default:
        message += '? [Y/n] '
    else:
        message += '? [N/y] '
    while True:
        answer = input(message).strip().lower()
        if not answer:
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        if answer in ('q', 'quit'):
            logger.debug('Exit')
            raise SystemExit(0)
        if answer in ('p', 'pdb'):
            import pdb
            pdb.set_trace()
        logger.debug('Please answer YES or NO.')


@autocast_args
def download_and_save(dbx, md, subpath: Path):
    """
    :param dbx: dropbox.Dropbox object
    :param md: metadata from dropbox
    :param subpath: - path on disk where data is to be saved
    :return:
    """
    # if md is dir - run recurrently
    if isinstance(md, dropbox.files.FolderMetadata):
        os.makedirs(subpath, exist_ok=True)
        listing = list_folder(dbx, '', md.path_display)
        for k, v in listing.items():
            download_and_save(dbx, v, subpath / k)
    # if md is file
    elif isinstance(md, dropbox.files.FileMetadata):
        data = download(dbx, '', '', md.path_display)
        with open(subpath, 'wb') as f:
            f.write(data)
    else:
        raise TypeError(f"Unknown dropbox listing type: {type(md)}")


class DropboxSharedFolder:
    @autocast_args
    def __init__(self, token, path: Path, subpath: Path = ''):
        """
        :param token: dropbox oauth token
        :param path: path of the folder to be synced on disk
        :param subpath: path of the folder in the dropbox.
        """
        self.token = token
        self.path = path
        path.mkdir(exist_ok=True)
        self.subpath = subpath

    def sync(self, ask_confirmation=False):
        """
        Uploads all updated files to the dropbox.
        :param ask_confirmation:
        :return:
        """

        folder = self.subpath
        rootdir = self.path
        # logger.debug('Dropbox folder name:', folder)
        # logger.debug('Local directory:', rootdir)
        if not rootdir.exists():
            logger.debug(f'{rootdir} does not exist on your filesystem')
            sys.exit(1)
        elif not rootdir.is_dir():
            logger.debug(f'{rootdir} is not a folder on your filesystem')
            sys.exit(1)

        args = SimpleNamespace(default=not ask_confirmation)

        dbx = dropbox.Dropbox(self.token)

        for dn, dirs, files in os.walk(rootdir):
            subfolder = dn[len(str(rootdir)):].strip(os.path.sep)
            listing = list_folder(dbx, folder, subfolder)
            logger.debug(f'Descending into {subfolder}...')

            # First do all the files.
            for name in files:
                fullname = os.path.join(dn, name)
                if not isinstance(name, six.text_type):
                    name = name.decode('utf-8')
                nname = unicodedata.normalize('NFC', name)
                if name.startswith('.'):
                    logger.debug(f'Skipping dot file: {name}')
                elif name.startswith('@') or name.endswith('~'):
                    logger.debug(f'Skipping temporary file: {name}')
                elif name.endswith('.pyc') or name.endswith('.pyo'):
                    logger.debug(f'Skipping generated file: {name}')
                elif nname in listing:
                    md = listing[nname]
                    md.processed = True
                    mtime = os.path.getmtime(fullname)
                    mtime_dt = datetime.datetime(*time.gmtime(mtime)[:6])
                    size = os.path.getsize(fullname)
                    if (isinstance(md, dropbox.files.FileMetadata) and
                            mtime_dt == md.client_modified and size == md.size):
                        logger.debug(f'{name} is already synced [stats match]')
                    else:
                        logger.debug(f'{name} exists with different stats, downloading')
                        res = download(dbx, folder, subfolder, name)
                        with open(fullname) as f:
                            data = f.read()
                        if res == data:
                            logger.debug(f'{name} is already synced [content match]')
                        else:
                            logger.debug(f'{name} has changed since last sync')
                            if mtime_dt > md.client_modified:
                                upload(dbx, fullname, folder, subfolder, name,
                                       overwrite=True)
                            else:
                                download_and_save(dbx, md, os.path.join(dn, md.name))

                elif yesno('Upload %s' % name, True, args):
                    upload(dbx, fullname, folder, subfolder, name)

            # Then choose which subdirectories to traverse.
            keep = []
            for name in dirs:
                if name.startswith('.'):
                    logger.debug(f'Skipping dot directory: {name}')
                elif name.startswith('@') or name.endswith('~'):
                    logger.debug(f'Skipping temporary directory: {name}')
                elif name == '__pycache__':
                    logger.debug(f'Skipping generated directory: {name}')
                elif yesno('Descend into %s' % name, True, args):
                    logger.debug(f'Keeping directory: {name}')
                    keep.append(name)
                else:
                    logger.debug(f'OK, skipping directory: {name}')
                nname = unicodedata.normalize('NFC', name)
                if nname in listing:
                    listing[nname].processed = True
            dirs[:] = keep

            # download all other files
            for md in listing.values():
                if hasattr(md, 'processed'):
                    continue
                download_and_save(dbx, md, os.path.join(dn, md.name))
