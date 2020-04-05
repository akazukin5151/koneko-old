"""
The default image renderer for koneko.
"""

import os
import fnmatch

import cytoolz
from pixcat import Image

from pure import cd


# - Pure functions
def is_jpg(myfile):
    if fnmatch.fnmatch(myfile, "*.jpg"):
        return True
    return False


def filter_jpg(path):
    with cd(path):
        return sorted(filter(is_jpg, os.listdir(".")))


@cytoolz.curry
def xcoord(image_number, number_of_columns, width):
    return image_number % number_of_columns * width + 2  # Magic


def number_prefix(myfile):
    return int(myfile.split("_")[0])


def display_page(page, rowspaces, cols, left_shifts, path):
    # TODO: rewrite with functional style map and currying
    with cd(path):
        for (index, space) in enumerate(rowspaces):
            for col in cols:
                Image(page[index][col]).thumbnail(310).show(
                    align="left", x=left_shifts[col], y=space
                )


def render_page(page_space, page, rowspaces, cols, left_shifts, path):
    """
    The reason for using pages is because every time something in a different
    row is displayed, the entire terminal shifts.
    So if you try to naively plot every image as it loads, it would result
    in a cascading gallery l
                            i
                             k
                              e
                                this.
    Hence, the need to plot each row of images in order
    """
    print("\n" * page_space)  # Scroll to new 'page'
    display_page(page, rowspaces, cols, left_shifts, path)


def main(path):
    """
    Each page has 2 rows. A page means printing those blank lines to move the
    cursor down (and the terminal screen).

    rowspaces : tuple of ints
        Vertical spacing between (the two) rows
    page_spaces : tuple of ints
        Vertical spacing between pages. Number of newlines to print for every page
    left_shifts : list of ints
        Horizontal position of the image
    """
    number_of_columns = 5  # Magic
    cols = range(number_of_columns)
    total_width = 90
    width = total_width // number_of_columns
    rowspaces = (0, 9)
    page_spaces = (26, 24, 24)

    file_list = filter_jpg(path)
    calc = xcoord(number_of_columns=number_of_columns, width=width)
    left_shifts = list(map(calc, cols))

    each_row = cytoolz.partition_all(number_of_columns, file_list)
    pages_list = list(cytoolz.partition(2, each_row))
    # len(pages_list) == number of pages
    # len(pages_list[i]) == number of rows in each page (for each i)

    os.system("clear")
    for (i, page) in enumerate(pages_list):
        render_page(page_spaces[i], page, rowspaces, cols, left_shifts, path)

    print(" " * 8, 1, " " * 15, 2, " " * 15, 3, " " * 15, 4, " " * 15, 5, "\n")


if __name__ == "__main__":
    main("/tmp/koneko/2232374/1/")
