import os

import pytest

import pure
from page_json import * # Imports the current_page (dict) stored in disk


def test_split_backslash_last():
    assert (
        pure.split_backslash_last("https://www.pixiv.net/en/users/2232374") == "2232374"
    )
    assert (
        pure.split_backslash_last("https://www.pixiv.net/en/artworks/78823485")
        == "78823485"
    )


def test_generate_filepath():
    assert (
        pure.generate_filepath("78823485_p0.jpg")
        == f"{os.path.expanduser('~')}/Downloads/78823485_p0.jpg"
    )


def test_prefix_filename():
    assert pure.prefix_filename("old.jpg", "new", 2) == "02_new.jpg"
    assert pure.prefix_filename("old.jpg", "new", 10) == "10_new.jpg"


def test_find_number_map():
    assert pure.find_number_map(1, 1) == 0
    assert pure.find_number_map(5, 1) == 4
    assert pure.find_number_map(2, 5) == 29
    assert pure.find_number_map(7, 4) == 27
    assert pure.find_number_map(7, 1) == 6
    assert pure.find_number_map(7, 5) == False
    assert pure.find_number_map(-1, -1) == False
    assert pure.find_number_map(0, 0) == False


def test_process_coords():
    assert pure.process_coords("1,1", ",") == 0
    assert pure.process_coords("5 1", " ") == 4
    assert pure.process_coords("2,5", ",") == 29
    assert pure.process_coords("7 4", " ") == 27
    assert pure.process_coords("7,1", ",") == 6
    assert pure.process_coords("7 5", " ") == False
    assert pure.process_coords("-1 -1", " ") == False
    assert pure.process_coords("0,0", ",") == False


def test_process_coords_slice():
    assert pure.process_coords_slice("o 1,1") == 0
    assert pure.process_coords_slice("d 5 1") == 4
    assert pure.process_coords_slice("d25") == 29
    assert pure.process_coords_slice("d  7 4") == 27
    assert pure.process_coords_slice("o 71") == 6
    assert pure.process_coords_slice("o 7 5") == False

def test_url_given_size():
    assert pure.url_given_size(page_json['illusts'][0], 'medium') == "https://i.pximg.net/c/540x540_70/img-master/img/2020/03/10/04/07/08/80017594_p0_master1200.jpg"
    assert pure.url_given_size(page_json['illusts'][1], 'large') == "https://i.pximg.net/c/600x1200_90_webp/img-master/img/2020/02/29/19/09/35/79799236_p0_master1200.jpg"

