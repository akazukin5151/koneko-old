import os
import threading
import itertools
import funcy
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
def spinner(call, message=''):
    """
    See http://hackflow.com/blog/2013/11/03/painless-decorators/
    """
    done = threading.Event()
    spinner = threading.Thread(target=spin, args=(done,message))
    spinner.start()
    result = call()
    done.set()
    spinner.join()
    return result
