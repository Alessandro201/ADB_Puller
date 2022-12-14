import os
import shlex
import subprocess
import sys
import threading
from argparse import ArgumentParser, BooleanOptionalAction
from datetime import datetime
from pathlib import Path, PurePosixPath
from time import time

import psutil


def read_arguments():
    my_parser = ArgumentParser(description='Pull files with adb driver')

    # Add the arguments
    my_parser.add_argument('-d',
                           '--dest',
                           type=str,
                           help='The folder in which to save the items pulled')

    my_parser.add_argument('--skip',
                           type=str,
                           nargs='*',
                           help='Skip the files provided')

    my_parser.add_argument('-t',
                           '--timeout',
                           type=int,
                           action='store',
                           default=120,
                           help='Timeout after which to skip failed files. (default: %(default)d)')

    my_parser.add_argument('-f',
                           '--filter',
                           action='store',
                           nargs='*',
                           help='Choose which file to copy or not. Use regex.')

    my_parser.add_argument('--dry-run',
                           action='store_true',
                           default=False,
                           help='Do not pull anything but print the files which will be pulled and their destination')

    # noinspection PyTypeChecker
    my_parser.add_argument('--skip-existing',
                           action=BooleanOptionalAction,
                           default=True,
                           help='Skip already existing items')

    # noinspection PyTypeChecker
    my_parser.add_argument('--keep-metadata',
                           action=BooleanOptionalAction,
                           default=True,
                           help='Use "adb pull" with "-a" flag to keep metadata like last modified time ecc')

    my_parser.add_argument('--skip-from-file',
                           type=str,
                           nargs='*',
                           help='Optional, file containing items to skip')

    my_group = my_parser.add_mutually_exclusive_group(required=True)

    my_group.add_argument('-s',
                          '--source',
                          type=str,
                          nargs='*',
                          help='The folder or item(s) to pull')

    my_group.add_argument('-i',
                          '--input',
                          type=str,
                          nargs='*',
                          help='File from which to read the items to pull')

    # Execute parse_args()
    args = my_parser.parse_args()

    if args.input:
        for i in args.input:
            if not os.path.isfile(i):
                sys.exit(f"The input file doesn't exists: '{i}'")

    if args.skip_from_file:
        for i in args.skip_from_file:
            if not os.path.isfile(i):
                sys.exit(f"The skip_from_file file doesn't exists: '{i}'")

    args.dest = Path(args.dest).resolve()
    if not args.dest.is_dir():
        sys.exit(f"The folder output you have inserted does not exists: {args.dest}")

    return args


def get_file_list_from_adb(root):
    """
    Use "ls -R" to find the files of a folder
    """

    print(f'Building file list of "{root}"')
    process = subprocess.run(shlex.split(f'adb shell ls -R "{root}"', posix=False), stdout=subprocess.PIPE,
                             universal_newlines=True, encoding='utf-8')
    output_lines = process.stdout.split('\n')

    # Filter out empty lines
    output_lines = list(filter(None, output_lines))

    # If the output of ls is only a line, and it's the root it means that the path is a file
    if len(output_lines) == 1 and root == output_lines[0].strip():
        print(f"{root} is a file")
        file_paths = [root]
        return file_paths

    file_paths = list()
    current_parent_path = ''
    for line in output_lines:
        """
        "ls -R" shows folder and files alike in the output, but each time it shows the contents of a folder
        it prints the parent one. I can add all folders and files to files_path, and everytime adb prints a parent folder
        I can remove it from file_paths.
        
        Output example:
        /sdcard/main_folder:
        folder1
        file1
        /sdcard/main_folder/folder1:
        file2
        
        I can then remove folder1 from filelist
        """

        if line[0] == '/':
            # This line contains the parent path
            current_parent_path = line.strip().strip(':')

            try:
                file_paths.remove(current_parent_path)
            except ValueError:
                pass

        else:
            file_name = line.strip()
            file_path = str(PurePosixPath(current_parent_path, file_name))

            file_paths.append(file_path)

    return file_paths


def get_file_destinations(files, main_dest, root_src=None, skip_existing=True):
    # Get path of src relative to src_root by removing it from the path
    # compute destination by joining the src_relative to the main_destination

    main_dest = Path(main_dest).resolve()

    src_dest = list()
    for src in files:
        if root_src:
            try:
                # Get the file_path relative to the parent of src_root, which is the folder that we searched
                # for the files to pull. In this way if I want to pull "/sdcard/DCIM" I will pull it in "./DCIM"
                # At the same time
                rel_src = PurePosixPath(src).relative_to(PurePosixPath(root_src).parent)
            except ValueError as err:
                sys.exit(f"{err} \nsrc_root '{root_src}' passed to the function get_file_destination should work")

        else:
            # This branch is used when the files are not read from adb but from a list in a file.

            # Get the parent folder of the source and remove the starting '/'
            rel_src = src[1:]

        dest = Path(main_dest, rel_src)

        if skip_existing and dest.exists():
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest = str(dest)

        src_dest.append((src, dest))

    return src_dest


def write_output(to_write, output_file, encoding='utf-8'):
    with open(output_file, 'w', encoding=encoding) as f:
        for line in to_write:
            f.write(line + "\n")


def append_to_output(to_write, output_file, encoding='utf-8'):
    if not os.path.isfile(output_file):
        open(output_file, 'x')  # just for creating it

    with open(output_file, 'a', encoding=encoding) as f:
        if type(to_write) == str:
            f.write(to_write + "\n")
        elif type(to_write) in (list, tuple, set):
            for line in to_write:
                f.write(line + "\n")
        else:
            print("Unrecognized variable type during the writing of the failed files. Saving it as is.")
            f.write(to_write + "\n")


def read_filelist(input_file, encoding='utf-8'):
    with open(input_file, 'r', encoding=encoding) as f:
        return list([line.strip() for line in f.readlines()])


def print_iterable(iterable, prefix=''):
    for item in iterable:
        if type(item) in (list, dict):
            print_iterable(item, prefix + '\t')
        else:
            print(prefix + '\t->  '.join(item))


def remove_duplicates(file_list, duplicates: set):
    filtered_file_list = list()

    for item in file_list:
        if item in duplicates:
            continue
        filtered_file_list.append(item)

    return filtered_file_list


def filter_files(file_list, filters):
    import re

    new_file_list = list()

    for file in file_list:
        for filt in filters:
            if re.search(filt, file):
                new_file_list.append(file)

    return new_file_list


def get_files_paths_and_destinations(args):
    """
    Find which files need to be pulled and their destinations
    """

    # Files to skip
    skip_files = list()
    if args.skip_from_file:
        for i in args.skip_from_file:
            skip_files.extend(read_filelist(i))

    if args.skip:
        skip_files.extend(args.skip)

    skip_files = set(skip_files)

    files_src_dest = list()
    if args.input:
        # Read file lists from the inputs
        for i in args.input:
            filelist = read_filelist(i)
            filelist = remove_duplicates(filelist, skip_files)
            if args.filter:
                filelist = filter_files(filelist, args.filter)

            files_src_dest_temp = get_file_destinations(filelist, args.dest,
                                                        root_src=None, skip_existing=args.skip_existing)
            files_src_dest.extend(files_src_dest_temp)

    else:
        # Get file list from the android folders
        for src in args.source:
            filelist = get_file_list_from_adb(src)
            filelist = remove_duplicates(filelist, skip_files)

            if args.filter:
                filelist = filter_files(filelist, args.filter)

            files_src_dest_temp = get_file_destinations(filelist, args.dest,
                                                        root_src=src, skip_existing=args.skip_existing)
            files_src_dest.extend(files_src_dest_temp)

    return files_src_dest


def pull_with_progressbar(files_src_dest, args):
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"{current_time} -> Pulling {len(files_src_dest)} files... it may take some time...")

    for (src, dest) in tqdm(files_src_dest):
        keep_metadata_flag = '-a'
        if not args.keep_metadata:
            keep_metadata_flag = ''

        command = f'adb pull {keep_metadata_flag} "{src}" "{dest}"'

        if not run_command(command, timeout=args.timeout):
            append_to_output(src, FAILED_OUTPUT, encoding=ENCODING)
        else:
            append_to_output(src, DONE_OUTPUT, encoding=ENCODING)


def pull_without_progressbar(files_src_dest, args):
    from math import ceil

    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"You don't have tqdm installed so you won't see any progress bar.\n"
          f"{current_time} -> Pulling {len(files_src_dest)} files... it may take some time...")

    chunk_10 = ceil(len(files_src_dest) / 10)

    for index, (src, dest) in enumerate(files_src_dest):
        keep_metadata_flag = '-a'
        if not args.keep_metadata:
            keep_metadata_flag = ''

        command = f'adb pull {keep_metadata_flag} "{src}" "{dest}"'

        if not run_command(command, timeout=args.timeout):
            append_to_output(src, FAILED_OUTPUT, encoding=ENCODING)
        else:
            append_to_output(src, DONE_OUTPUT, encoding=ENCODING)

        files_pulled = index + 1
        if files_pulled % chunk_10 == 0:
            percentage = (files_pulled / chunk_10) * 10

            # Skip 100% because it may be 100 due to rounding error, but it actually is less than the total
            if percentage == 100:
                continue

            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"{current_time} -> #{percentage}%  items pulled: {files_pulled}")

    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"{current_time} -> #100%  items pulled: {files_pulled}")


def run_command(cmd, timeout):
    try:
        # Run the command and after a timeout expires kill the process. This works with adb.exe because it does not
        # spawn child processes. In case self.cmd does spawn other processes you would need to kill the whole
        # process tree. You can check by adding "shell=True" to subprocess.run which will spawn the command
        # into its own process, and thus will not be killed after the timeout expires.

        subprocess.run(cmd, capture_output=True, timeout=timeout, check=True)

    except subprocess.TimeoutExpired:
        print(f"\nTimeoutExpired on {cmd}")
        print(f"Process tree killed.")
        return False

    except subprocess.CalledProcessError as err:
        print(f"Error running {err.cmd} \nReturncode: {err.returncode} - Error: {err.stderr.decode('utf-8')}")
        return False

    return True


if __name__ == '__main__':
    FAILED_OUTPUT = 'failed.txt'
    DONE_OUTPUT = 'done.txt'
    ENCODING = 'utf-8'

    args = read_arguments()

    files_src_dest = get_files_paths_and_destinations(args)

    if not files_src_dest:
        print(f"No files to pull! They were probably already pulled. To force the pulling and overwrite the existing "
              f"files use the flag '--no-skip-existing'")
        sys.exit()

    if args.dry_run:
        print_iterable(files_src_dest)
        sys.exit()

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    start = time()

    if tqdm:
        pull_with_progressbar(files_src_dest, args)
    else:
        pull_without_progressbar(files_src_dest, args)

    print(f"Pulling done in {time() - start:.3f} seconds. Failed pulls are saved to 'failed.txt', if any.")
