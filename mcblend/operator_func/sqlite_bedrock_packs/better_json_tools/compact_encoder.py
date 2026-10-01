'''
A module that provides a custom JSON encoder for JSON-like data structures,
that is more compact than the default encoder but still readable.
'''
from typing import Any, TypeGuard, Union, Iterator, cast
import json

class CompactEncoder(json.JSONEncoder):
    '''
    JSONEncoder can be used as `cls` argument to `json.dump` and `json.dumps`.
    It creates formatted JSON strings, with indentation that are more compact
    than the dafault formatting from `json` module. The main difference is that
    the lists of primitives are not split into multiple lines.
    '''

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.__indent: int = -1
        self.respect_indent: bool = True

    def _is_primitive(self, obj: Any) -> TypeGuard[Union[int, bool, str, float]]:
        return isinstance(obj, (int, bool, str, float))

    def encode(self, o: Any) -> str:
        '''
        Return a JSON string representation of a Python data structure.

        Example:
            >>> CompactEncoder().encode({"foo": ["bar", "baz"]})
            '{\\n\\t"foo": ["bar", "baz"]\\n}'
        '''
        return ''.join(self.iterencode(o))

    def iterencode(self, o: Any, *args: Any) -> Iterator[str]:  # type: ignore
        '''
        Encode the given object and yield each string representation line by
        line.

        Example:
            >>> item = {"foo": ["bar", "baz"]}
            >>> ''.join(list(CompactEncoder().iterencode(item))) == \\
            ... CompactEncoder().encode(item)
            True
        '''
        self.__indent += 1
        if self.respect_indent:
            ind = self.__indent*'\t'
        else:
            ind = ''
        if isinstance(o, dict):
            o = cast(dict[Any, Any], o)
            if len(o) == 0:
                yield f"{ind}{{}}"
            else:
                body: list[str] = []
                for k, v in o.items():
                    body.extend([
                        f'{j[:self.__indent]}{json.dumps(k)}: {j[self.__indent:]}'
                        for j in self.iterencode(v)
                    ])
                body_str = ",\n".join(body)
                yield (
                    f'{ind}{{\n'
                    f'{body_str}\n'
                    f'{ind}}}'
                )
        elif isinstance(o, (list, tuple)):
            o = cast(list[Any], o)
            primitive_list = True
            for i in o:
                if not self._is_primitive(i):
                    primitive_list = False
                    break
            if primitive_list:
                body = []
                self.respect_indent = False
                for i in o:
                    body.extend(self.iterencode(i))
                self.respect_indent = True
                yield f'{ind}[{", ".join(body)}]'
            else:
                body = []
                for i in o:
                    body.extend(self.iterencode(i))
                body_str = ",\n".join(body)
                yield (
                    f'{ind}[\n'
                    f'{body_str}\n'
                    f'{ind}]'
                )
        elif self._is_primitive(o):
            if isinstance(o, str):
                yield f'{ind}{json.dumps(o)}'
            else:
                yield f'{ind}{str(o).lower()}'
        elif o is None:
            yield f'{ind}null'
        else:
            raise TypeError('Object of type set is not JSON serializable')
        self.__indent -= 1
