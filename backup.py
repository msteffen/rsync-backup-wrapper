#!/usr/bin/python

from backup_lib import *
import textwrap as tw

def main():
  # Parse flags (which are used to initialize a Backup instance)
  arg_parser = argparse.ArgumentParser(
      description="Efficiently backup a directory tree using rsync.",
      epilog=tw.dedent("""\
      Examples:
          ./backup.py --src=/home/mjs/sensitive --dst=/net/backups/today
          ./backup.py --src=/home/mjs/sensitive --dst=/net/backups/today \\
              --prev_backup=/net/backups/6_months_ago

      Using --backup_drive:
          ./backup.py --src=/Users/msteffen --backup_drive="/Volumes/Backup Drive/Macbook/"
          (if e.g. "30-Jan-2014" exists in /Volumes/Backup Drive/Macbook, then --prev_backup
          will automatically be set to /Volumes/Backup Drive/Macbook/30-Jan-2014)

      Using --backup_order:
          ./backup.py --src=/Users/msteffen --backup_drive="/Volumes/Backup Drive/Macbook/" \\
              --backup_order="Documents,my_passwords.kdb,..."
          (Will back up all files in /Users/msteffen, starting with "Documents" and "my_passwords.kdb)"
      """),
      formatter_class=argparse.RawTextHelpFormatter)
  arg_parser.add_argument('--src', type=str,
      help="The directory to be backed up")
  arg_parser.add_argument('--dst', type=str,
      help="The directory that will receive the backup")
  arg_parser.add_argument('--prev_backup', type=str,
      help=tw.fill(tw.dedent("""\
      A directory used for a previous backup. To save space, if a file hasn't
      changed since this backup was taken, the file is backed up by creating a
      hard link to here from --dst, instead of being copied""")))
  # Either --backup_drive or --dst/--prev_backup should be specified
  arg_parser.add_argument('--backup_drive', type=str,
      help=tw.fill(tw.dedent("""\
      A directory where the new backup should be placed, which follows this
      script's naming convention for incremental backups (backups are named
      with the date they were taken). --dst will be constructed and
      --prev_backup will be inferred if this flag is set. If this is set, don't
      set those flags.""")))
  arg_parser.add_argument('--backup_order', type=str,
      help=tw.fill(tw.dedent("""\
      A comma-separated list of files and directories in --src, or the special
      name \"...\".  Files will be backed up in the order listed in this
      argument, and once \"...\" is reached all remaining files will be backed
      up. This allows you to back up small, important files before large,
      unimportant ones, so that they're not lost if a backup is interrupted or
      fails. If you don't wish to back up all the files in --src, simply omit
      the \"...\" argument.""")))
  args = arg_parser.parse_args()

  # Validate flag values
  assert args.src, "Must specify --src. Run `./backup.py --help` for usage info"
  assert args.backup_drive or args.dst, \
      "Must specify exactly one of --dst or --backup_drive. Run " \
      "`./backup.py --help` for usage info"
  assert not args.backup_drive or not args.dst, \
      "Must specify exactly one of --dst or --backup_drive. Run " \
      "`./backup.py --help` for usage info"
  assert not args.backup_drive or not args.prev_backup, \
      "Must specify at most one of --prev_backup or --backup_drive. Run " \
      "`./backup.py --help` for usage info"

  # Create function arguments to Backup constructor depending on flag values
  backup_args = {"src": args.src}
  backup_order = [
      s for s in args.backup_order.strip().split(",") if len(s) > 0 ]
  if len(backup_order) > 0:
    backup_args["backup_order"] = backup_order

  # Create Backup object
  if args.backup_drive:
    backup = Backup.FromBackupDrive(drive=args.backup_drive, **backup_args)
  else:
    if args.prev_backup: backup_args["prev_backup"] = args.prev_backup
    backup = Backup(dst=args.dst, **backup_args)

  # Perform backup
  backup.run_rsync_cmds()
  print("\033[1;32mDONE!\033[0m")

if __name__ == "__main__":
  main()
