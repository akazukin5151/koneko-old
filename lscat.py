import os
import fnmatch
import cytoolz
from pixcat import Image


def is_jpg(myfile):
    if fnmatch.fnmatch(myfile, "*.jpg"):
        return True
    return False


def filter_jpg():
    os.chdir("/tmp/koneko/2232374/1/")
    return sorted(filter(is_jpg, os.listdir(".")))


@cytoolz.curry
def calc_left_shift(image_number, number_of_columns, width):
    col = image_number % number_of_columns
    left_shift = col * width
    return left_shift


def number_prefix(myfile):
    return int(myfile.split("_")[0])


def init_consts(number_of_columns, width):
    # TODO: split up function to smaller pieces
    file_list = filter_jpg()
    cols = range(number_of_columns)
    calc = calc_left_shift(number_of_columns=number_of_columns, width=width)
    left_shifts = list(map(calc, cols))
    rows = range(-(-len(file_list) // number_of_columns))  # Round up

    partition_file_list = list(cytoolz.partition_all(number_of_columns, file_list))
    # 2 rows in page 1, 3 rows in page 2
    page_1 = partition_file_list[:2]
    page_2 = partition_file_list[2:]
    return page_1, page_2, left_shifts, rows


def display_page(page, spaces, rows, left_shifts):
    for (i, space) in enumerate(spaces):
        for row in rows:
            (
                Image(page[i][row])
                .thumbnail(300)
                .show(align="left", x=left_shifts[row], y=space)
            )


def render(page_1, page_2, rows, left_shifts):
    os.system("clear")
    print("\n" * 26)  # Scroll to new 'page'
    spaces = (0, 8)
    display_page(page_1, spaces, rows, left_shifts)

    print("\n" * 23)  # Scroll to new 'page'
    spaces = (0, 8, 16)
    display_page(page_2, spaces, rows, left_shifts)


def main():
    NUMCOLS = 7
    total_width = 140
    WIDTH = total_width // NUMCOLS
    # TODO: how to render font?
    FONTFAMILY = "Hiragino-Sans-GB-W3"
    FONTSIZE = 16

    page_1, page_2, left_shifts, rows = init_consts(NUMCOLS, WIDTH)
    try:
        render(page_1, page_2, rows, left_shifts)
    except IndexError:
        pass


if __name__ == "__main__":
    main()
