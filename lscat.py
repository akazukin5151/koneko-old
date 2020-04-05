import os
import fnmatch

import cytoolz
from pixcat import Image

from pure import cd


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


def init_consts(number_of_columns, width, path):
    # TODO: split up function to smaller pieces
    file_list = filter_jpg(path)
    cols = range(number_of_columns)
    calc = xcoord(number_of_columns=number_of_columns, width=width)
    left_shifts = list(map(calc, cols))

    partition_file_list = list(cytoolz.partition_all(number_of_columns, file_list))

    page1 = partition_file_list[:2] # First 2; 0-4 and 5-9
    page2 = partition_file_list[2:4] # 10-14 and 15-19
    page3 = partition_file_list[4:] # 20-24 and 25-29
    return page1, page2, page3, left_shifts, cols

def display_page(page, vertspaces, cols, left_shifts, path):
    """
    The reason why it has to this complicated thing, is because every time
    something in a different row is displayed, the entire terminal shifts.
    So if you try to naively plot every image as it loads, it would result
    in a cascading gallery l
                            i
                             k
                              e
                                this.
    Hence, the need to plot each row of images in order

    vertspaces : tuple of int
        Vertical spacing between rows
    """
    # TODO: rewrite with functional style map and currying
    with cd(path):
        for (index, space) in enumerate(vertspaces):
            for col in cols:
                Image(page[index][col]).thumbnail(310).show(
                    align="left", x=left_shifts[col], y=space
                )


def render(page1, page2, page3, cols, left_shifts, path):
    """
    Each page has 2 rows. A page means printing those blank lines to move the
    cursor down (and the terminal screen).
    """
    os.system("clear")
    print("\n" * 26)  # Scroll to new 'page'
    display_page(page1, (0, 9), cols, left_shifts, path)

    print("\n" * 24)  # Magic
    display_page(page2, (0, 9), cols, left_shifts, path)
    #breakpoint()
    print("\n" * 24)  # Magic
    display_page(page3, (0, 9), cols, left_shifts, path)


def main(path):
    number_of_columns = 5  # Magic
    total_width = 90
    width = total_width // number_of_columns

    page1, page2, page3, left_shifts, cols = init_consts(number_of_columns, width, path)
    try:
        render(page1, page2, page3, cols, left_shifts, path)
    except IndexError:
        pass
    finally:  # Magic
        print(
            " " * 8,
            1,
            " " * 15,
            2,
            " " * 15,
            3,
            " " * 15,
            4,
            " " * 15,
            5,
        )


if __name__ == "__main__":
    main("/tmp/koneko/2232374/1/")
