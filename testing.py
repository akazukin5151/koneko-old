import os

import pytest

import pure


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
    with pytest.raises(AssertionError):
        pure.find_number_map(-1, -1)
        pure.find_number_map(0, 0)


def test_process_coords():
    assert pure.process_coords("1,1", ",") == 0
    assert pure.process_coords("5 1", " ") == 4
    assert pure.process_coords("2,5", ",") == 29
    assert pure.process_coords("7 4", " ") == 27
    assert pure.process_coords("7,1", ",") == 6
    assert pure.process_coords("7 5", " ") == False
    with pytest.raises(AssertionError):
        pure.process_coords("-1,-1", ",")
        pure.process_coords("0 0", " ")


def test_process_coords_slice():
    assert pure.process_coords_slice("o 1,1", "o") == 0
    assert pure.process_coords_slice("d 5 1", "d") == 4
    assert pure.process_coords_slice("d25", "d") == 29
