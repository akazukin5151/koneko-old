import abc
from abc import ABC, abstractmethod
from typing import *

def is_image(myfile: str): ...
def filter_jpg(path: str): ...
def xcoord(image_number: int, number_of_columns: int, width: int, increment: int): ...
def number_prefix(myfile: str): ...
def display_page(page: List[Tuple[Tuple[str, ...], ...]], rowspaces: Tuple[int, ...], cols: Iterator[int], left_shifts: List[int], path: int) -> None: ...

class View(ABC, metaclass=abc.ABCMeta):
    def __init__(self, path: str, number_of_columns: int, rowspaces: Tuple[int, ...], page_spaces: Tuple[int, ...], rows_in_page: int) -> None: ...
    @abstractmethod
    def render(self) -> None: ...

class Gallery(View):
    def __init__(self, path: str, number_of_columns: int, rowspaces: Tuple[int, ...], page_spaces: Tuple[int, ...], rows_in_page: int) -> None: ...
    def render(self) -> None: ...

class Card(View):
    def __init__(self, path: str, preview_paths: List[str], messages: List[str], preview_xcoords: Optional[List[List[int]]], number_of_columns: Optional[int], rowspaces: Optional[Tuple[int, ...]], page_spaces: Optional[Tuple[int, ...]], rows_in_page: Optional[int]) -> None: ...
    def render(self) -> None: ...