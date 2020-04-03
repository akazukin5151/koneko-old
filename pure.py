import os
import threading
import itertools
import funcy
import cytoolz
from contextlib import contextmanager

import time
import functools


def timer(func):
    @functools.wraps(func)  # Preserve original func.__name__
    def wrapper(*args, **kwargs):
        t0 = time.time()
        value = func(*args, **kwargs)
        t1 = time.time()
        total = t1 - t0
        with open("/home/twenty/Workspace/pixiv/time.txt", "a") as the_file:
            the_file.write(f"{func.__name__!r}() time: {total}\n")
        return value

    return wrapper


@contextmanager
def cd(newdir):
    """
    Change current script directory, do something, change back to old directory
    See https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022

    Parameters
    ----------
    newdir : str
        New directory to cd into inside 'with'
    """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def spin(done, message):
    for char in itertools.cycle("|/-\\"):  # Infinite loop
        print(message, char, flush=True, end="\r")
        if done.wait(0.1):
            break
    print(" " * len(char), end="\r")  # clears the spinner


@funcy.decorator
def spinner(call, message=""):
    """
    See http://hackflow.com/blog/2013/11/03/painless-decorators/
    """
    done = threading.Event()
    spinner = threading.Thread(target=spin, args=(done, message))
    spinner.start()
    result = call()
    done.set()
    spinner.join()
    return result


def split_backslash_last(str):
    """
    Intended for splitting url to get filename, but it has lots of applications...
    """
    return str.split("/")[-1]


def generate_filepath(filename):
    filepath = f"{os.path.expanduser('~')}/Downloads/{filename}"
    return filepath


def prefix_filename(old_name, new_name, number):
    img_ext = old_name.split(".")[-1]
    number_prefix = str(number).rjust(2, "0")
    new_file_name = f"{number_prefix}_{new_name}.{img_ext}"
    return new_file_name


def process_coords(input_command, split_string):
    x, y = input_command.split(split_string)
    x, y = int(x), int(y)
    return find_number_map(x, y)


def find_number_map(x, y):
    assert x >= 1 and y >= 1
    # 7 = number of cols; 5 = number of rows
    # 7 columns, 30 images
    number_map = list(cytoolz.partition_all(7, range(30)))

    try:
        # coordinates are 1-based index
        number = number_map[y - 1][x - 1]
    except IndexError:
        print("Invalid number!\n")
        return False
    return number


def process_coords_slice(gallery_command, exclude_letter):
    """
    # I don't know why I spent so much time on this
    Supports: (o x,y) (o x y) (oxy)
    IMPROVEMENT: (o xy)
    """
    splitspace = gallery_command.split(" ")
    if len(splitspace) == 1:
        splitcomma = splitspace[0].split(",")
        if len(splitcomma) == 1:
            # oxy
            xy = splitcomma[0].split(exclude_letter)[1]
            x, y = xy[0], xy[1]
        else:
            # ox,y --> ['ox', 'y']
            x = splitcomma[0][1]
            y = splitcomma[1]
    else:
        if len(splitspace) == 2:
            if len(splitspace[0]) == 1:
                # o x,y --> ['o', 'x,y']
                x = splitspace[1][0]
                y = splitspace[1][2]
            else:
                # ox y --> ['ox', 'y']
                x = splitspace[0][1]
                y = splitspace[1]
        else:
            # o x y --> ['o', 'x', 'y']
            x, y = splitspace[1], splitspace[2]

    return find_number_map(int(x), int(y))
