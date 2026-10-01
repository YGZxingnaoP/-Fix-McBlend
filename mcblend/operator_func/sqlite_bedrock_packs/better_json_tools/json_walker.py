'''
A module that provides tools for easy access to JSON data using JSON paths.
'''
from __future__ import annotations
import json
import re
from typing import Union, Type, Optional, IO, Callable, Iterator, Any

class SKIP_LIST:
    '''Used as literal value for JSONSplitWalker paths'''

# def _remove_escape_characters(text: str) -> str:
#     '''Prints to a string, removint the escape characters'''
#     with io.StringIO() as output:
#         print(text, file=output, end='')
#         contents = output.getvalue()
#     return contents

def _tuple_to_path_str(path: tuple[Union[str, int], ...]):
    result: list[str] = []
    for k in path:
        if isinstance(k, int):
            result.append(f'[{k}]')
        elif isinstance(k, str): # pyright: ignore[reportUnnecessaryIsInstance]
            if re.fullmatch("[a-zA-Z$_]+[a-zA-Z$_0-9]*", k):
                # Mathes JS variable name (like connect like a.b.c)
                if len(result) == 0:  # First item skip the dot
                    result.append(k)
                else: # Add dot before
                    result.append(f".{k}")
            else:
                # Does not match JS variable name (like connect like
                # ["a"]["b"]["c"])
                k = json.dumps(k)  # escape special characters and add quotes
                result.append(f'[{k}]')
        else:
            raise TypeError(f"Invalid key type {type(k)}")
    return "".join(result)

class JSONPath:
    '''
    Represents a path in a JSON file. The paths internally use a tuple listing
    the keys, but they can be represented or created from a string. The string
    representation is similar to the one used in JavaScript.

    The path objects can be used to access the data of :class:`JSONWalker`.

    Example:
        >>> from better_json_tools import JSONPath
        >>> path = JSONPath(("a", "$abc", 1, 2, 'with quote "'))
        >>> print(path.data)
        ... ('a', '$abc', 1, 2, 'with quote "')
        >>> print(path)
        ... a.$abc[1][2]["with quote \""]
        >>> another_path = JSONPath(str(path))
        >>> print(another_path)
        ... a.$abc[1][2]["with quote \""]
        >>> print(another_path.data == path.data)
        ... True
    '''
    def __init__(self, path: Union[str, tuple[Union[str, int], ...]]):
        if isinstance(path, str):
            self.data = JSONPath._from_path_str(path)
        else:
            self.data = path

    def __str__(self) -> str:
        '''Returns a string representation of the path.'''
        return _tuple_to_path_str(self.data)

    @staticmethod
    def _from_path_str(path_str: str) -> tuple[Union[str, int], ...]:
        '''Converts a path string to a JSONPath.'''
        if path_str == "":
            return tuple()

        # Results
        path: list[int | str] = []
        curr_path = path_str

        # Add . to the start of the string to make the patterm matching work
        # better
        if not curr_path.startswith("["):
            curr_path = "." + curr_path
        while True:
            if curr_path == "":
                break
            if curr_path.startswith("."):
                # Match a.b.c
                match = re.match(r"\.([a-zA-Z$_]+[a-zA-Z$_0-9]*)", curr_path)
                if match is None:
                    raise ValueError(f"Invalid path: {path_str}")
                path.append(match.group(1))
                curr_path = curr_path[match.end():]
            elif curr_path.startswith("["):
                if len(curr_path) < 3: # shortest possible path is like [0]
                    raise ValueError(f"Invalid path: {path_str}")
                if curr_path[1] == '"':
                    # Match ["a"]["b"]["c"]
                    match = re.match(r'\[("(?:[^"]|\\")*")\]', curr_path)
                    if match is None:
                        raise ValueError(f"Invalid path: {path_str}")
                    path.append(json.loads(match.group(1)))
                    curr_path = curr_path[match.end():]
                else:
                    # Match [0][1][2]
                    match = re.match(r"\[([0-9]+)\]", curr_path)
                    if match is None:
                        raise ValueError(f"Invalid path: {path_str}")
                    path.append(int(match.group(1)))
                    curr_path = curr_path[match.end():]
            else:
                raise ValueError(f"Invalid path: {path_str}")
        return tuple(path)

## Type definitions
JSON = Union[dict[str, Any], list[Any], str, float, int, bool, None]
JSON_KEY = Union[str, int]
JSON_PATH_KEY = Union[str, int, JSONPath]
JSON_SPLIT_KEY = Union[str, Type[int], Type[str], None, Type[SKIP_LIST]]
JSON_WALKER_DATA = Union[dict[str, Any], list[Any], str, float, int, bool, None, Exception]



class JSONWalker:
    '''
    A class that represents a path in the JSON file for easy access to its
    values.
    '''
    def __init__(
            self, data: JSON_WALKER_DATA, *,
            parent: Optional[JSONWalker] = None,
            parent_key: Optional[JSON_KEY] = None):
        if not isinstance(
                data, (Exception, dict, list, str, float, int, bool, type(None))):
            raise ValueError('Input data is not JSON.')
        self._data: JSON_WALKER_DATA = data
        self._parent = parent
        self._parent_key = parent_key

    @property
    def parent(self) -> JSONWalker:
        '''
        The parent of this json walker (the walker that created this walker).

        :rises: :class:`KeyError` when this :class:`JSONWalker` is a root
            object.
        '''
        if self._parent is None:
            raise KeyError("You can't get parent of the root object.")
        return self._parent

    @property
    def parent_key(self) -> JSON_KEY:
        '''
        The key used to access this walker from its parent

        :rises: :class:`KeyError` when this :class:`JSONWalker` is a root
            object
        '''
        if self._parent_key is None:
            raise KeyError("You can't get parent of the root object.")
        return self._parent_key

    @staticmethod
    def loads(json_text: Union[str, bytes], **kwargs: Any) -> JSONWalker:
        '''
        Creates json walker using `json.loads()` function. Passes all arguments
        to `json.loads` and tries to creat the walker base on the result.
        '''
        data = json.loads(json_text, **kwargs)
        return JSONWalker(data)

    @staticmethod
    def load(json_file: IO[Any], **kwargs: Any) -> JSONWalker:
        '''
        Creates json walker using `json.load()` function. Passes all arguments
        to `json.load` and tries to creat the walker base on the result.
        '''
        data = json.load(json_file, **kwargs)
        return JSONWalker(data)

    @property
    def data(self) -> JSON_WALKER_DATA:
        '''
        The data from JSON that this walker points to.
        '''
        return self._data

    @data.setter
    def data(self, value: JSON):
        if self._parent is not None:
            self.parent.data[  # type: ignore
                self.parent_key  # type: ignore
            ] = value
        self._data = value

    def create_path(
            self, data: JSON, *,
            exists_ok: bool = True,
            can_break_data_structure: bool = True,
            can_create_empty_list_items: bool = True,
            empty_list_item_factory: Optional[Callable[[], JSON]] = None):
        '''
        Creates path to the part of JSON file pointed by this walker.

        :param data: the data to put at the end of the path.
        :param exists_ok: if False, the ValueError will be risen if the path
            to this item already exists.
        :param can_break_data_structure: if True than the function will be able
            to replace certain existing paths with dicts or lists. Example -
            if path "a"/"b"/"c" points at integer, creating path
            "a"/"b"/"c"/"d" will replace this integer with a dict in order to
            make "d" a valid key. Setting this to false would cause a KeyError
            in this situation.
        :param can_create_empty_list_items: enables filling up the lists in
            JSON with values produced by the empty_list_item_factory in order
            to match the item index specified in the path. Example - if you
            specify a path to create "a"/5/"c" but the list at "a" path only
            has 2 items, then the function will create additional item so
            the 5th index can be valid.
        :param empty_list_item_factory: a function used to create items for
            lists in order to make indices specified in the path valid (see
            can_create_empty_list_items function parameter). If this value
            is left as None than the lists will be filled with null values.
        '''
        if self.exists:
            if exists_ok:
                return
            raise ValueError("Path already exists")
        if empty_list_item_factory is None:
            empty_list_item_factory = lambda: None
        curr_item = self.root
        path = self.path
        for key in path:
            if isinstance(key, str):  # key is a string data must be a dict
                if not isinstance(curr_item.data, dict):
                    if not can_break_data_structure:
                        raise KeyError(key)
                    curr_item.data = {}
                if key not in curr_item.data:
                    can_break_data_structure = True  # Creating new data
                curr_item = curr_item / key
            elif isinstance(key, int):  # pyright: ignore[reportUnnecessaryIsInstance]
                # key is an int data must be a list
                if key < 0:
                    raise KeyError(key)
                if not isinstance(curr_item.data, list):
                    if not can_break_data_structure:
                        raise KeyError(key)
                    curr_item.data = []
                if len(curr_item.data)-1 < key:
                    if not can_create_empty_list_items:
                        raise KeyError(key)
                    curr_item.data += [
                        empty_list_item_factory()
                        for _ in range(1+key-len(curr_item.data))
                    ]
                    can_break_data_structure = True  # Creating new data
                curr_item = curr_item / key
            else:
                raise KeyError(key)
        self._parent = curr_item.parent
        self._parent_key = curr_item.parent_key
        self.data = data

    @property
    def exists(self) -> bool:
        '''
        Returns true if path to this item already exists. This function
        recursively checks the entire path to this item starting from root so
        even if the object is detached from the root somewhere in the middle
        of the path, the function will still return correct value.
        '''
        keys: list[JSON_KEY] = []
        root = self
        try:
            while True:
                keys.append(root.parent_key)
                root = root.parent
        except KeyError:
            pass
        keys = list(reversed(keys))
        root_data = root.data
        try:
            for key in keys:
                root_data = root_data[key]  # type: ignore
        except:  # pylint: disable=bare-except
            return False
        return True

    @property
    def root(self) -> JSONWalker:
        '''
        The root object of this JSON file.
        '''
        root = self
        try:
            while True:
                root = root.parent
        except KeyError:
            pass
        return root

    @property
    def path(self) -> tuple[JSON_KEY, ...]:
        '''
        Full JSON path up to this point starting from the root of the JSON file
        in from of a tuple of keys.
        '''
        result: list[JSON_KEY] = []
        parent = self
        try:
            while True:
                result.append(parent.parent_key)
                parent = parent.parent
        except KeyError:
            pass
        return tuple(reversed(result))

    @property
    def path_str(self) -> str:
        '''
        Full JSON path up to this point starting from the root of the JSON file
        in form of a string.
        '''
        return _tuple_to_path_str(self.path)

    def __truediv__(self, key: JSON_PATH_KEY) -> JSONWalker:
        '''
        The `/` operator creates descendant path in the JSON file.
        '''
        if isinstance(key, JSONPath):
            walker = self
            for k in key.data:
                walker = walker / k
            return walker
        try:
            return JSONWalker(
                self.data[key],  # type: ignore
                parent=self, parent_key=key)
        except Exception as e:  # pylint: disable=broad-except
            return JSONWalker(e, parent=self, parent_key=key)

    def __floordiv__(self, key: JSON_SPLIT_KEY) -> JSONSplitWalker:
        '''
        The `//` operator creates JSONSplitWalker object with multiple
        alternative paths that matched provided key.

        :raises:
            :class:`TypeError` - invalid input data type

            :class:`re.error` - invlid regular expression.
        '''
        # pylint: disable=too-many-return-statements
        # ANYTHING
        if key is None:
            if isinstance(self.data, dict):
                return JSONSplitWalker([
                    JSONWalker(v, parent=self, parent_key=k)
                    for k, v in self.data.items()
                ])
            if isinstance(self.data, list):
                return JSONSplitWalker([
                    JSONWalker(v, parent=self, parent_key=i)
                    for i, v in enumerate(self.data)
                ])
        # ANY LIST ITEM
        elif key is int:
            if isinstance(self.data, list):
                return JSONSplitWalker([
                    JSONWalker(v, parent=self, parent_key=i)
                    for i, v in enumerate(self.data)
                ])
        # ANY DICT ITEM
        elif key is str:
            if isinstance(self.data, dict):
                return JSONSplitWalker([
                    JSONWalker(v, parent=self, parent_key=k)
                    for k, v in self.data.items()
                ])
        # REGEX DICT ITEM
        elif isinstance(key, str):
            if isinstance(self.data, dict):
                result: list[JSONWalker] = []
                for k, v in self.data.items():
                    if re.fullmatch(key, k):
                        result.append(JSONWalker(
                            v, parent=self, parent_key=k))
                return JSONSplitWalker(result)
        # IF it's a list use ing key ELSE return split walker with self
        elif key is SKIP_LIST:
            if isinstance(self.data, list):
                return self // int
            return JSONSplitWalker([self])
        else:  # INVALID KEY TYPE
            raise TypeError(
                'Key must be a regular expression or one of the values: '
                'str, int, or None')
        # DATA DOESN'T ACCEPT THIS TYPE OF KEY
        return JSONSplitWalker([])

    def __add__(self, other: Union[JSONSplitWalker, JSONWalker]) -> JSONSplitWalker:
        '''
        The `+` operator adds json walkers creating a split walker with more
        values.
        '''
        if isinstance(other, JSONWalker):
            data = [self, other]
        else:
            data = other.data + [self]
        return JSONSplitWalker(
            [i for i in data if not isinstance(i.data, Exception)])


class JSONSplitWalker:
    '''
    Multiple walker objects grouped together. This class can be browse JSON
    file contents from multiple JSON paths at once.
    '''

    def __init__(self, data: list[JSONWalker]) -> None:
        self._data: list[JSONWalker] = data

    @property
    def data(self) -> list[JSONWalker]:
        '''
        The list of the :class:`JSONWalker` objects contained in this object.
        '''
        return self._data

    def __truediv__(self, key: JSON_PATH_KEY) -> JSONSplitWalker:
        '''
        Applies `/` operator to all of the :class:`JSONWalkers` in this split
        walker.
        '''
        result: list[JSONWalker] = []
        for walker in self.data:
            new_walker = walker / key
            if not isinstance(new_walker.data, Exception):
                result.append(new_walker)
        return JSONSplitWalker(result)

    def __floordiv__(self, key: JSON_SPLIT_KEY) -> JSONSplitWalker:
        '''
        Applies `//` operator to all of the :class:`JSONWalkers` in this split
        walker, creating even more split walkers (all groupped together in
        one object).
        '''
        result: list[JSONWalker] = []
        for walker in self.data:
            new_walker = walker // key
            result.extend(new_walker.data)
        return JSONSplitWalker(result)

    def __add__(self, other: Union[JSONSplitWalker, JSONWalker]) -> JSONSplitWalker:
        '''
        The `+` operator adds json walkers creating a split walker with more
        values.
        '''
        if isinstance(other, JSONWalker):
            data = self.data + [other]
        else:
            data = self.data + other.data
        return JSONSplitWalker(
            [i for i in data if not isinstance(i.data, Exception)])

    def __iter__(self) -> Iterator[JSONWalker]:
        '''
        Yield every walker contained in this object.
        '''
        for i in self.data:
            yield i

    def __len__(self) -> int:
        '''
        Return the number of walkers contained in this object.
        '''
        return len(self.data)
