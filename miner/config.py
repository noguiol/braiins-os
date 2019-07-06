# Copyright (C) 2018  Braiins Systems s.r.o.
#
# This file is part of Braiins Build System (BB).
#
# BB is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import copy

from collections import namedtuple
from ruamel import yaml
from ruamel.yaml.comments import CommentedMap, CommentedSeq

YAML_DICT_TYPE = CommentedMap
YAML_LIST_TYPE = CommentedSeq

EmptyDict = CommentedMap
EmptyList = CommentedSeq


class ConfigWrapper:
    INITIALIZED = '_initialised'

    """
    Class to simplify access to `YAML` configuration object
    """
    def __new__(cls, root, path='', formatter=None):
        """
        Create ConfigWrapper object or return original `root` object

        :param root:
            `YAML` root list or dictionary.
        :param path:
            Current path to this root attribute.
        :param formatter:
            Callable object which is called to format string value where '{' is found.
        :return:
            If root is not `YAML` dictionary or list then return its original value otherwise return root wrapped in
            `ConfigWraper`.
        """
        if type(root) not in (YAML_DICT_TYPE, YAML_LIST_TYPE):
            if formatter and type(root) is str and '{' in root:
                root = formatter(root)
            return root
        else:
            return super().__new__(cls)

    def __init__(self, root, path='', formatter=None):
        """
        Initialize ConfigWrapper object

        :param root:
            `YAML` root list or dictionary.
        :param path:
            Current path to this root attribute.
        :param formatter:
            Callable object which is called to format string value where '{' is found.
        """
        self._root = root
        self.path = path
        self.formatter = formatter

        # special attribute to mark initialized object have to be set last
        setattr(self, self.INITIALIZED, True)

    def __deepcopy__(self, memo):
        """
        Create deep copy of config wrapper
        """
        cls = self.__class__
        result = cls.__new__(cls, root=self._root)
        memo[id(self)] = result
        for key, value in self.__dict__.items():
            if key == self.INITIALIZED:
                # attribute which marks object initialization have to be set last
                continue
            setattr(result, key, copy.deepcopy(value, memo))
        # mark initialized object
        setattr(result, result.INITIALIZED, True)
        return result

    def __delattr__(self, item):
        """
        Delete attribute from configuration
        """
        del self._root[item]

    def __setattr__(self, key, value):
        """
        Set new attribute or modify current one in configuration
        """
        if self.INITIALIZED not in self.__dict__:
            # allows attributes to be set in the __init__ method
            return super().__setattr__(key, value)
        elif key in self.__dict__:
            # any class attributes are handled normally
            super().__setattr__(key, value)
        else:
            self._root[key] = value

    def is_dict(self) -> bool:
        """
        Check if current root is `YAML` dictionary

        :return:
            True when root is `YAML` dictionary
        """
        return type(self._root) is YAML_DICT_TYPE

    def is_list(self) -> bool:
        """
        Check if current root is `YAML` list

        :return:
            True when root is `YAML` list
        """
        return type(self._root) is YAML_LIST_TYPE

    def __str__(self) -> str:
        """
        Return string representation of configuration

        :return:
            String with configuration
        """
        return str(self._root)

    def _join_attribute(self, attribute: str) -> str:
        """
        Join attribute with current configuration path

        :param attribute:
            The name of attribute to be appended to the path.
        :return:
            Attribute when current path is empty or attribute appended to the path with `.` delimiter.
        """
        return attribute if not self.path else '.'.join((self.path, attribute))

    def __getattr__(self, item: str):
        """
        Access to dictionary key with object attribute

        :param item:
            The name of attribute.
        :return:
            ConfigWrapper object with value get from `YAML` dictionary.
        """
        if self.is_dict():
            result = self._root.get(item)
            if result is not None:
                return ConfigWrapper(result, path=self._join_attribute(item), formatter=self.formatter)
        raise AttributeError("Configuration '{}' has no attribute '{}'".format(self.path, item))

    def __getitem__(self, item):
        """
        Access configuration file as an array

        :param item:
            The name of attribute.
        :return:
            ConfigWrapper object with value get from `YAML` dictionary or list.
        """
        result = None
        path = None
        if self.is_dict():
            result = self._root.get(item)
            if result is None:
                raise KeyError("Configuration '{}' has no attribute '{}'".format(self.path, item))
            path = self._join_attribute(item)
        elif type(item) is not int:
            raise TypeError('list indices must be integers, not {}'.format(str(type(item))))
        elif item < len(self._root):
            result = self._root[item]
            path = '{}[{}]'.format(self.path, item)
        else:
            raise IndexError("Configuration '{}' index out of range".format(self.path))
        return ConfigWrapper(result, path=path, formatter=self.formatter)

    def __iter__(self):
        """
        Return generator object as an iterator

        :return:
            Items are objects ConfigWrapper or basic types when value is not `YAML` dictionary or list.
        """
        return (ConfigWrapper(value, formatter=self.formatter) for value in self._root)

    def __contains__(self, item):
        """
        Check if item is in the current configuration

        :param item:
            Key or value.
        :return:
            True when item is in the current configuration.
        """
        return item in self._root

    def get_item(self, item, default=None):
        """
        Return value of item or default value when item is not set

        :param item:
            The name of attribute.
        :param default:
            Default value used when no value is set for specified item.
        :return:
            Value of item or default value when item is not set.
        """
        value = self._root[item] if item in self._root else None
        return ConfigWrapper(value, formatter=self.formatter) if value is not None else default

    def get(self, path, default=None):
        """
        Return value of item or default value when item is not set

        :param path:
            Path to the attribute specified by attributes separated by dot.
        :param default:
            Default value used when no value is set for specified item.
        :return:
            Value of item or default value when item is not set.
        """
        if not path:
            raise AttributeError("Missing path to the configuration attrigute")
        current = self
        for item in path.split('.'):
            current = current.get_item(item)
            if current is None:
                current = default
                break
        return current

    def setdefault(self, path, default=None):
        """
        Return value of item or set and return default value when item is not set

        :param path:
            Path to the attribute specified by attributes separated by dot.
        :param default:
            Default value used when no value is set for specified item.
        :return:
            Value of item or default value when item is not set.
        """
        if not path:
            raise AttributeError("Missing path to the configuration attrigute")
        previous = self
        current = default
        items = iter(path.split('.'))
        for item in items:
            current = previous.get_item(item)
            if current is None:
                current = item
                for next_item in items:
                    setattr(previous, current, EmptyDict())
                    previous = previous.get(current)
                    current = next_item
                setattr(previous, current, default)
                current = previous.get(current)
                break
            previous = current
        return current

    def append(self, item):
        """
        Appends a passed item into the existing list
        """
        self._root.append(ConfigWrapper(item))

    def items(self):
        """
        Return generator object as an iterator

        :return:
            Items are pairs where is contain key and value.
        """
        pairs = self._root.items() if self.is_dict() else enumerate(self._root)
        return ((key, ConfigWrapper(value, formatter=self.formatter)) for key, value in pairs)

    def _merge(self, attribute, value):
        """
        Auxiliary method for recursive merging of two configurations

        :param attribute:
            Name of attribute used for overloading.
        :param value:
            Value of attribute for overloading.
        """
        def merge_type(root_value, value):
            return type(value) is ConfigWrapper and type(root_value._root) is type(value._root)

        root_value = self.get(attribute)
        if not root_value or not merge_type(root_value, value):
            # if attribute does not exist or has different type then simply copy/override this attribute
            if type(value) is ConfigWrapper:
                value = value._root
            setattr(self, attribute, copy.deepcopy(value))
            return
        # source and destination attribute can be merged
        if type(root_value._root) is YAML_LIST_TYPE:
            # lists are replaced
            setattr(self, attribute, copy.deepcopy(value._root))
            return
        # dictionary is recursively merged
        for next_attribute, next_value in value.items():
            root_value._merge(next_attribute, next_value)

    def merge(self, config):
        """
        Merge settings from another configuration

        Dictionaries are merged and lists are replaced with new one settings.

        :param config:
            Dictionary with configuration tree.
        """
        for attribute, value in config.items():
            self._merge(attribute, value)

    def dump(self, stream):
        """
        Dump current configuration to the opened stream

        It preserves comments from loaded from input file.

        :param stream:
            Opened stream for writing.
        """
        yaml.dump(self._root, stream=stream, Dumper=yaml.RoundTripDumper)


class ListWalker:
    """
    Iterator class for access list with inheritance based on `YAML` configuration
    """
    def __init__(self, root: ConfigWrapper, list_name: str):
        """
        Initialize ListWalker for specified list

        :param root:
            Configuration root where selected and base lists are searched.
        :param list_name:
            Name of selected list.
        """
        self._root = root
        self._list_name = list_name

    def _get_list(self, list_name: str):
        """
        Generator for accessing all items from the list with inheritance

        :param list_name:
            Name of root list.
        :return:
            Generator object with list iterator.
        """
        list_node = self._root.get(list_name)
        if not list_node:
            raise AttributeError("Cannot find list base with the name '{}'".format(list_name))
        base = list_node.get('base')
        list = list_node.get('list')
        if base:
            for base_list in base:
                yield from self._get_list(base_list)
        if list:
            for item in list:
                yield item

    def __iter__(self):
        """
        Return generator object as an iterator

        :return:
            Items are objects contained in the list and its predecessors.
        """
        yield from self._get_list(self._list_name)


class RemoteWalker:
    """
    Iterator class for access remote repositories in configuration file
    """
    Remote = namedtuple('Remote', ['name', 'uri', 'branch', 'fetch'])

    def __init__(self, remote, platform):
        """
        Initialize RemoteWalker with remote attribute

        :param remote:
            Attribute remote from configuration file.
        """
        self.platform = platform
        self.repos = remote.repos
        # get global settings
        self._aliases = remote.aliases
        self._location = remote.get('location', None)
        self._branch = remote.get('branch', 'master')
        self._fetch = remote.get('fetch', 'yes')
        self._fetch_force = remote.fetch_always == 'yes'

    def __iter__(self):
        """
        Return generator object as an iterator

        :return:
            Items are named tuples with `name`, `uri`, `branch` and `fetch` attribute.
        """
        for name, repo in self.repos.items():
            remote_attributes = {
                'location': repo.get('location', self._location),
                'project': repo.get('project', None),
                'branch': repo.get('branch', self._branch)
            }

            match = repo.get('match', None)
            if match:
                # sort pattern to set attribute with lowest priority (shortest platform prefix)
                # and continue to attributes with highest priority (longest platform prefix)
                for pattern, attributes in sorted(match.items()):
                    if not self.platform.startswith(pattern):
                        continue
                    for attribute, value in attributes.items():
                        remote_attributes[attribute] = value

            location = remote_attributes['location']
            project = remote_attributes['project']
            branch = remote_attributes['branch']

            if not location or not project:
                continue

            server = self._aliases[location]
            uri = '{}/{}'.format(server, project)
            fetch = self._fetch_force or repo.get('fetch', self._fetch) == 'yes'
            yield self.Remote(name, uri, branch, fetch)


def load_config(path: str):
    """
    Load and return configuration file

    :param path:
        Path to configuration file in `YAML` format.
    :return:
        ConfigWrapper object used for easier access to configuration attributes.
    """
    root = YAML_DICT_TYPE()
    if path:
        with open(path, 'r') as ymlfile:
            root = yaml.load(ymlfile, Loader=yaml.RoundTripLoader)
    return ConfigWrapper(root)
