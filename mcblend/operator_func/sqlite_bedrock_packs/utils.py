'''
Functions for analyzing Molang expressions.
'''
import re

def find_molang_resources(
        molang: str, resource_prefixes: list[str]) -> dict[str, list[str]]:
    '''
    Finds all resources of specified types in a molang expression. Returns
    a dictionary keyed by the resource type, with values being a list of
    found resources.

    Example
    -------
    >>> find_molang_resources(
            molang=(
                "q.is_baby = 1 ? array.skin[q.variant] : ("
                "q.mark_variant ? texture.default : texture.default2)"
            ),
            resource_prefixes=["array", "texture"])
    {'array': ['array.skin'], 'texture': ['texture.default', 'texture.default2']}
    '''
    molang = molang.lower()
    results: dict[str, list[str]] = {
        prefix: []
        for prefix in resource_prefixes
    }
    for resource_prefix in resource_prefixes:
        # Capturing groups crops the first part of the search for example:
        # geometry.default -> geometry
        item_pattern = re.compile(
            f'{resource_prefix}\\.(\\w+)', flags=re.IGNORECASE)
        for item_name in item_pattern.findall(molang):
            results[resource_prefix].append(item_name)
    return results

def split_item_name(item_name: str) -> tuple[str, str, int]:
    '''
    Splits given name of the item into three parts: napespace, name and data
    value. If the name is missing the namespace, than the default namespace
    value is minecraft. If the data value is missing is set to 0.

    In rare cases when the data value can't be converted to int, the data
    value and the separator (:) are considered to be part of the name.

    Example
    -------
    >>> split_item_name("minecraft:stone")
    ('minecraft', 'stone', 0)
    >>> split_item_name("stone")
    ('minecraft', 'stone', 0)
    >>> split_item_name("minecraft:stone:1")
    ('minecraft', 'stone', 1)
    '''
    item_name = item_name.lower()
    if ':' in item_name:
        namespace, name = item_name.split(':', 1)
    else:
        namespace = 'minecraft'
        name = item_name
    if ':' in name:
        name, data_str = name.rsplit(':', 1)
        try:
            data = int(data_str)
        except ValueError:
            name = f'{name}:{data_str}'
            data = 0
    else:
        data = 0
    return namespace, name, data

def parse_format_version(version: str) -> tuple[int, ...]:
    '''
    Parses string with format version (dot separated numbers).
    '''
    return tuple(int(part) for part in version.split('.'))
