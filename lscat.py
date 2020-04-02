import os
import fnmatch
import cytoolz
from pixcat import Image
from koneko import cd


def is_jpg(myfile):
    if fnmatch.fnmatch(myfile, "*.jpg"):
        return True
    return False


def filter_jpg():
    with cd("/tmp/koneko/2232374/1/"):
        return sorted(filter(is_jpg, os.listdir(".")))


@cytoolz.curry
def xcoord(image_number, number_of_columns, width):
    return image_number % number_of_columns * width


def number_prefix(myfile):
    return int(myfile.split("_")[0])


def init_consts(number_of_columns, width):
    # TODO: split up function to smaller pieces
    file_list = filter_jpg()
    cols = range(number_of_columns)
    calc = xcoord(number_of_columns=number_of_columns, width=width)
    left_shifts = list(map(calc, cols))
    rows = range(-(-len(file_list) // number_of_columns))  # Round up

    partition_file_list = list(
        cytoolz.partition_all(number_of_columns, file_list)
    )

    # 2 rows in page 1, 3 rows in page 2
    page1 = partition_file_list[:2]
    page2 = partition_file_list[2:]
    return page1, page2, left_shifts, rows


def display_page(page, spaces, rows, left_shifts):
    with cd("/tmp/koneko/2232374/1/"):
        for (index, space) in enumerate(spaces):
            for row in rows:
                Image(
                    page[index][row]
                ).thumbnail(
                    300
                ).show(
                    align="left", x=left_shifts[row], y=space
                )


def render(page1, page2, rows, left_shifts):
    os.system("clear")
    print("\n" * 26)  # Scroll to new 'page'
    display_page(page1, (0, 8), rows, left_shifts)

    print("\n" * 23)  # Scroll to new 'page'
    display_page(page2, (0, 8, 16), rows, left_shifts)


def main():
    number_of_columns = 7
    total_width = 140
    width = total_width // number_of_columns
    # TODO: how to render font?
    fontfamily = "Hiragino-Sans-GB-W3"
    fontsize = 16

    page1, page2, left_shifts, rows = init_consts(number_of_columns, width)
    try:
        render(page1, page2, rows, left_shifts)
    except IndexError:
        pass


if __name__ == "__main__":
    main()
