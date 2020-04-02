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
    return image_number % number_of_columns * width + 1


def number_prefix(myfile):
    return int(myfile.split("_")[0])


def init_consts(number_of_columns, width, path):
    # TODO: split up function to smaller pieces
    file_list = filter_jpg(path)
    cols = range(number_of_columns)
    calc = xcoord(number_of_columns=number_of_columns, width=width)
    left_shifts = list(map(calc, cols))
    rows = range(-(-len(file_list) // number_of_columns))  # Round up

    partition_file_list = list(cytoolz.partition_all(number_of_columns, file_list))

    # 2 rows in page 1, 3 rows in page 2
    page1 = partition_file_list[:2]
    page2 = partition_file_list[2:]
    return page1, page2, left_shifts, rows


def display_page(page, spaces, rows, left_shifts, path):
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
    """
    # TODO: rewrite with functional style map and currying
    with cd(path):
        for (index, space) in enumerate(spaces):
            for row in rows:
                Image(page[index][row]).thumbnail(300).show(
                    align="left", x=left_shifts[row], y=space
                )


def render(page1, page2, rows, left_shifts, path):
    os.system("clear")
    print("\n" * 26)  # Scroll to new 'page'
    display_page(page1, (0, 8), rows, left_shifts, path)

    print("\n" * 23)  # Scroll to new 'page'
    display_page(page2, (0, 8, 16), rows, left_shifts, path)


def main(path):
    number_of_columns = 7
    total_width = 140
    width = total_width // number_of_columns

    page1, page2, left_shifts, rows = init_consts(number_of_columns, width, path)
    try:
        render(page1, page2, rows, left_shifts, path)
    except IndexError:
        pass
    finally:
        print(' '*4, 1,' '*18, 2,' '*17, 3,' '*17, 4, ' '*17, 5)


if __name__ == "__main__":
    main("/tmp/koneko/2232374/1/")
