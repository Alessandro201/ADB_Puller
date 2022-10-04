from pathlib import Path, PurePosixPath
from argparse import ArgumentParser, BooleanOptionalAction
import os
import sys
import subprocess
import threading
import shlex
from datetime import datetime
from time import time


def read_arguments():
    my_parser = ArgumentParser(description='Pull files with adb driver. If a file was already pulled the default '
                                           'behaviour is to skip it.')

    # Add the arguments
    my_parser.add_argument('-d',
                           '--dest',
                           type=str,
                           help='The folder in which to save the items pulled')

    my_parser.add_argument('--dry-run',
                           action='store_true',
                           default=False,
                           help='Do not pull anything but print the files which will be pulled and their destination')

    my_parser.add_argument('--skip-existing',
                           action=BooleanOptionalAction,
                           default=True,
                           help='Skip already existing items')

    my_parser.add_argument('--keep-metadata',
                           action=BooleanOptionalAction,
                           default=True,
                           help='Use "adb pull" with "-a" flag to keep metadata like last modified time ecc')

    my_parser.add_argument('-p',
                           '--already_pulled',
                           type=str,
                           nargs='*',
                           help='Optional, file containing already pulled items to skip')

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

    if args.already_pulled:
        for i in args.already_pulled:
            if not os.path.isfile(i):
                sys.exit(f"The already_pulled file doesn't exists: '{i}'")

    args.dest = Path(args.dest).resolve()
    if not args.dest.is_dir():
        sys.exit(f"The folder output you have inserted does not exists: {args.dest}")

    return args


def get_file_list(root):
    print(f'Building file list of "{root}"')
    process = subprocess.run(shlex.split(f'adb shell ls -R "{root}"', posix=False), stdout=subprocess.PIPE,
                             universal_newlines=True, encoding='utf-8')
    out = process.stdout

    file_paths = list()

    parent_path = ''
    for line in out.split('\n'):
        if not line:
            continue

        if line[0] == '/':
            # This line contains the parent path
            parent_path = line.strip().strip(':')

            # adb shows folder and files alike in the output of ls, but each time it shows the contents of a folder
            # it prints the parent one. I can add all folders and files to files_path, and everytime adb prints a folder
            # before printing its content I can remove it from file_paths.

            # Output example:
            # /sdcard/main_folder:
            # folder1
            # file1
            # /sdcard/main_folder/folder1:
            # file2
            #
            # I can then remove folder1 from filelist
            try:
                file_paths.remove(parent_path)
            except ValueError:
                pass

        elif line.strip() == '':
            # Empty line
            pass
        else:
            file_name = line.strip()
            file_path = str(PurePosixPath(parent_path, file_name))

            file_paths.append(file_path)

    return file_paths


def get_file_destinations(files, main_dest, src_root=None, skip_existing=True):
    # Get path of src relative to src_root by removing it from the path
    # compute destination by joining the src_relative to the main_destination

    main_dest = Path(main_dest).resolve()

    src_dest = list()
    for src in files:
        if src_root:
            try:
                # Get the file_path relative to the parent of src_root, which is the folder that we searched
                # for the files to pull. In this way if I want to pull "/sdcard/DCIM" I will pull it in "./DCIM"
                # At the same time
                rel_src = PurePosixPath(src).relative_to(PurePosixPath(src_root).parent)
            except ValueError as err:
                sys.exit(f"{err} \nsrc_root '{src_root}' passed to the function get_file_destination should work")

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


class Command:
    """
    This class should allow the script to skip a file if it takes more that timeout seconds
    """

    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        def target():
            self.process = subprocess.Popen(self.cmd, shell=True, stdout=subprocess.PIPE)
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()
            print(f"Timeout Error: {self.cmd} \nReturn Code: {self.process.returncode}")
            return False
        return True


if __name__ == '__main__':
    FAILED_OUTPUT = 'failed.txt'
    DONE_OUTPUT = 'pulled.txt'
    ENCODING = 'utf-8'

    args = read_arguments()

    already_pulled = list()
    if args.already_pulled:
        for i in args.already_pulled:
            already_pulled.extend(read_filelist(i))

    already_pulled = set(already_pulled)

    # Read file lists from the inputs if given
    files_path = list()
    files_src_dest = list()
    if args.input:
        for i in args.input:
            filelist = read_filelist(i)
            filelist = remove_duplicates(filelist, already_pulled)

            files_src_dest_temp = get_file_destinations(filelist, args.dest, skip_existing=args.skip_existing)
            files_src_dest.extend(files_src_dest_temp)

    else:
        for src in args.source:
            filelist = get_file_list(src)
            filelist = remove_duplicates(filelist, already_pulled)
            # write_output(filelist, f"{Path(src).name}.txt")

            files_src_dest_temp = get_file_destinations(filelist, args.dest, src,
                                                        skip_existing=args.skip_existing)
            files_src_dest.extend(files_src_dest_temp)

    failed = list()

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
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"{current_time} -> Pulling {len(files_src_dest)} files... it may take some time...")

        for (src, dest) in tqdm(files_src_dest):
            keep_metadata_flag = '-a'
            if not args.keep_metadata:
                keep_metadata_flag = ''

            command = f'adb pull {keep_metadata_flag} "{src}" "{dest}"'
            command = Command(command)

            if not command.run(timeout=60):
                print(f"failed {src}")
                append_to_output(src, FAILED_OUTPUT, encoding=ENCODING)
            else:
                append_to_output(src, DONE_OUTPUT, encoding=ENCODING)

    else:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"You don't have tqdm installed so you won't see any progress bar.\n"
              f"{current_time} -> Pulling {len(files_src_dest)} files... it may take some time...")

        from math import ceil

        chunk_10 = ceil(len(files_src_dest) / 10)

        for index, (src, dest) in enumerate(files_src_dest):
            keep_metadata_flag = '-a'
            if not args.keep_metadata:
                keep_metadata_flag = ''

            command = f'adb pull {keep_metadata_flag} "{src}" "{dest}"'
            command = Command(command)

            if not command.run(timeout=60):
                print(f"failed {src}")
                append_to_output(src, FAILED_OUTPUT, encoding=ENCODING)
            else:
                append_to_output(src, DONE_OUTPUT, encoding=ENCODING)

            files_pulled = index + 1
            if files_pulled % chunk_10 == 0:
                percentage = (files_pulled / chunk_10) * 10
                if percentage == 100:
                    # Skip 100% because it may be 100 due to rounding error but it actually is less than the total
                    continue
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"{current_time} -> #{percentage}%  items pulled: {files_pulled}")

        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"{current_time} -> #100%  items pulled: {files_pulled}")

    print(f"Pulling done in {time() - start:.3f} seconds. Failed pulls are saved to 'failed.txt', if any.")
