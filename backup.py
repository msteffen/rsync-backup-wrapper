#!/usr/bin/python
import argparse
from datetime import date, time, datetime
import os
from os.path import abspath, exists, isabs, isdir, join, normpath
import re
import subprocess
from sys import stdin

def main():
  # Establish backup locations
  arg_parser = argparse.ArgumentParser(
  description="Efficiently backup a directory tree using rsync.",
  epilog="""Examples:
  ./backup.py --src=/Users/msteffen --backup_drive="/Volumes/Seagate Backup Plus Drive/Macbook/"
  ./backup.py --src=/home/mjs/sensitive --dst=/net/backups/today --prev_backup=/net/backups/6_months_ago
  """,
  formatter_class=argparse.RawTextHelpFormatter)

  arg_parser.add_argument('--src', type=str, help="The directory to be backed "
      "up")

  # Either --backup_drive or --dst/--prev_backup should be specified
  arg_parser.add_argument('--backup_drive', type=str, help="A directory where "
      "the backup should be placed, which follows this script's naming "
      "convention. --dst will be constructed and --prev_backup will be "
      "inferred if this flag is set.")
  arg_parser.add_argument('--dst', type=str, help="The directory that will "
      "receive the backup")
  arg_parser.add_argument('--prev_backup', type=str, help="A directory used "
      "for a previous backup. To save space, files that haven't changed since "
      "the previous backup are hardlinked from --dst, instead of copied to "
      "--dst")
  args = arg_parser.parse_args()

  # Validate flag values
  assert args.src, "Must specify --src. Run `./backup.py --help` for usage info"
  assert args.backup_drive or args.dst
  assert not args.backup_drive or not args.dst
  assert not args.backup_drive or not args.prev_backup

  # Run backup
  if args.backup_drive:
    backup = Backup.FromBackupDrive(args.backup_drive)
  else:
    backup = Backup(args.src, args.dst, args.prev_backup)
  backup.backup_with_rsync()

  print("\033[1;32mDONE!\033[0m")

class Backup:
  """ Data structure with all information needed to create a backup """

  # NOTE: if this is ever changed, all existing backups will have to be renamed
  # or else this class won't be able to find the most recent backup in a
  # directory
  _DATE_FORMAT = "%m-%b-%Y"
  _LOG_FILE = "rsync_backup.log"
  _DONE_FILE = "BACKUP_DONE"

  def __init__(self, src, dst, prev_backup=None):
    src = abspath(src)
    dst = abspath(dst)
    prev_backup = abspath(prev_backup) if prev_backup else None

    # Validate & sanitize arguments
    assert isdir(src), "src({}) is not a dir".format(src)
    assert prev_backup is None or isdir(prev_backup), \
        "prev_backup ({}) is not a dir".format(prev_backup)
    if not exists(dst):
      os.mkdir(dst)
    else:
      assert isdir(dst), "dst exists and isn't dir: {}".format(dst)
      assert not exists(join(dst, Backup._DONE_FILE)), \
          "dst ({}) already contains a completed backup".format(dst)

    self.src = src
    self.dst = dst
    self.prev_backup = prev_backup

  @staticmethod
  def FromBackupDrive(src, drive):
    """
      Initialize and return a Backup object from a directory (usually where an
      external backup drive has been mounted) and a convention based on backup
      frequency

      Keyword arguments:
      drive -- a global path to a directory where an external backup drive has
          been mounted (or a subdirectory inside an external backup drive, if
          the drive is shared)
    """
    src = abspath(src)
    drive = abspath(drive)
    assert isdir(src), "src ({}) is not a dir".format(src)
    assert isdir(drive),  "drive ({}) is not a dir".format(drive)

    ## Scan previous backups and find the most recent
    today = datetime.combine(date.today(), time())  # Need plain date (for ==)
    most_recent = None
    for d in os.listdir(drive):
      if not isdir(d): continue
      try:
        t = datetime.strptime(d.strip(), Backup._DATE_FORMAT)
        if t == today: continue
        if most_recent is None or t > most_recent:
          most_recent = t
      except:
        print "Skipping unrecognized dir {}".format(d)
        continue

    most_recent_path = None
    if most_recent:
      most_recent_path = join(drive, most_recent.strftime(Backup._DATE_FORMAT))
    return Backup(src=src, prev_backup=most_recent_path,
        dst=join(drive, datetime.today().strftime(Backup._DATE_FORMAT)))

  def backup_with_rsync(self, dry_run=False):
    """
      Backup the subtree under `self.src` to `self.dst`, linking against files in
      `self.prev_backup` if they're unchanged (i.e. if
      [self.src/.../file] == [prev_backup/.../file]).

      If `self.prev_backup` is unset, don't do any linking
    """
    args = [
      # Archive mode (preserves most file attributes) and verbose logging
      '-av',

      # Ignore character and block device files, and special files (e.g.
      # sockets)
      '--no-D',

      # Use checksum to determine file equality (see man page; default bahavior
      # in rysnc is to compare timestamp and file size to determine equality,
      # but that's fragile. This is much slower though, so perhaps this should
      # be disabled later)
      '--checksum',

      # output lines:
      # %n The filename
      # %b The number of bytes actually transferred
      # %l The actual size of the file
      # %i info line (http://stackoverflow.com/questions/1113948/rsync-output)
      '--out-format="%n (%b/%l) %i"',
    ]

    if self.prev_backup:
      args += [
        # If a file is the same in both `self.src` and `self.prev_backup`,
        # create a hardlink in `self.dst` to `self.prev_backup` instead of
        # copying the file
        '--link-dest={}'.format(self.prev_backup)
      ]
    if dry_run: args += ['--dry-run']

    cmd = ['rsync'] + args + [
      # append a "/" to `self.src`, so rsync copies its contents instead of the
      # directory itself. Note that `self.src` was already normalized in
      # __init__ by abspath()
      join(self.src, ""),
      self.dst,
    ]
    print "Executing:"
    print " ".join(cmd)
    subprocess.call(cmd,
        stdout=open(join(self.dst, Backup._LOG_FILE), "w"),
        stderr=subprocess.STDOUT)
    open(join(self.dst, Backup._DONE_FILE), "w")  # just $(touch BACKUP_DONE)

if __name__ == "__main__":
  main()
