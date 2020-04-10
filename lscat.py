"""
The default image renderer for koneko.
"""

import os
import fnmatch

import cytoolz
import funcy
from pixcat import Image

from pure import cd


# - Pure functions
def is_image(myfile):
    if fnmatch.fnmatch(myfile, "*.jpg") or fnmatch.fnmatch(myfile, "*.png"):
        return True
    return False


def filter_jpg(path):
    with cd(path):
        return sorted(filter(is_image, os.listdir(".")))


@cytoolz.curry
def xcoord(image_number, number_of_columns, width, increment=2):
    return image_number % number_of_columns * width + increment


def number_prefix(myfile):
    return int(myfile.split("_")[0])


# Impure functions
@funcy.ignore(IndexError, TypeError)
def display_page(page, rowspaces, cols, left_shifts, path):
    with cd(path):
        for (index, space) in enumerate(rowspaces):
            for col in cols:
                Image(page[index][col]).thumbnail(310).show(
                    align="left", x=left_shifts[col], y=space
                )


def render_with_previews(
    page_space,
    page,
    rowspaces,
    cols,
    left_shifts,
    path,
    i,
    preview_images,
    preview_xcoords,
    preview_paths,
    messages,
):
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
    print("\n" * 2)
    print(" " * 19, messages)

    print("\n" * page_space)  # Scroll to new 'page'
    display_page(page, rowspaces, cols, left_shifts, path)

    for (j, xcoord) in enumerate(preview_xcoords):
        display_page(((preview_images[i][j],),), rowspaces, cols, xcoord, preview_paths)


def main(
    path,
    number_of_columns=5,
    rowspaces=(0, 9),
    page_spaces=(26, 24, 24),
    rows_in_page=2,
    print_rows=True,
    preview_xcoords=None,
    preview_paths=None,
    messages=None,
):
    """
    Each page has 2 rows by default. A page means printing blank lines to move
    the cursor down (and the terminal screen). The number of blank lines to
    print for each page is given by page_spaces.

    Parameters
    ========
    rowspaces : tuple of ints
        Vertical spacing between (the two) rows.
        len must be >= number of rows
    page_spaces : tuple of ints
        Vertical spacing between pages. Number of newlines to print for every page
        len must be >= number of pages
    rows_in_page : int
        Number of rows in each page
    print_rows : bool
        Whether to print row numbers in the bottom

    The following parameters are for single image per row, user view
    ========
    preview_xcoords : list of list of int
        For printing previews next to artists. len == 3 (three previews)
        len of inner list == 1 (one column only, only one int needed)
    preview_paths : list of str
        Path to where the preview images are downloaded to
        len must be 3, for three previews. The number of images in each dir/path
        must be == number of pages == len(page_spaces) == number of images
    messages : list of str
        List of text to print next to the images. Only for when rows_in_page = 1
        len must be >= rows_in_page

    Info
    ========
    left_shifts : list of ints
        Horizontal position of the image
    """
    cols = range(number_of_columns)
    total_width = 90
    width = total_width // number_of_columns

    file_list = filter_jpg(path)
    calc = xcoord(number_of_columns=number_of_columns, width=width)
    left_shifts = list(map(calc, cols))

    # Partitions list of files into tuples with len == number_of_columns
    # So each row will contain 5 files, if number_of_columns == 5
    # [(file1, file2, ... , file5), (file6, ... , file10), ...]
    each_row = cytoolz.partition_all(number_of_columns, file_list)

    # Each page has `rows_in_page` rows. Every row is grouped with another.
    # [(row1, row2), (row3, row4), ...]
    # where row1 == (file1, file2, ...)
    pages_list = list(cytoolz.partition(rows_in_page, each_row, pad=None))

    if preview_paths:
        preview_images = list(cytoolz.partition_all(3, sorted(os.listdir(preview_paths))))

    assert len(pages_list[0]) <= len(rowspaces) == rows_in_page
    assert len(pages_list) <= len(page_spaces)
    if messages:
        assert rows_in_page == 1
        assert len(messages) >= rows_in_page

    os.system("clear")
    if not messages:
        for (i, page) in enumerate(pages_list):
            print("\n" * page_spaces[i])  # Scroll to new 'page'
            display_page(page, rowspaces, cols, left_shifts, path)
    else:
        for (i, page) in enumerate(pages_list):
            # TODO: simplify this monster
            render_with_previews(
                page_spaces[i],
                page,
                rowspaces,
                cols,
                left_shifts,
                path,
                i,
                preview_images,
                preview_xcoords,
                preview_paths,
                messages[i],
            )

    if print_rows:
        print(" " * 8, 1, " " * 15, 2, " " * 15, 3, " " * 15, 4, " " * 15, 5, "\n")


if __name__ == "__main__":
    main("/tmp/koneko/2232374/1/")
