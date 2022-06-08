#!/usr/bin/env python3
import rospy
from roslaunch.config import ROSLaunchConfig
from roslaunch.core import Param


class LaunchtreeArg(object):
    def __init__(self, name, default=None, value=None, doc=None):
        self.name = name
        self.default = default
        self.value = value
        self.doc = doc

    def merge(self, other):
        if self.default is None and other.default is not None:
            self.default = other.default
        if self.value is None and other.value is not None:
            self.value = other.value
        if self.doc is None and other.doc is not None:
            self.doc = other.doc


class LaunchtreeRemap(object):
    def __init__(self, from_topic, to_topic):
        self.from_topic = from_topic
        self.to_topic = to_topic


class LaunchtreeParam(Param):
    def __init__(self, key, value, command):
        super(LaunchtreeParam, self).__init__(key, value)
        self.command = command


class LaunchtreeRosparam(object):
    def __init__(self, command, filename):
        self.command = command
        self.filename = filename


class LaunchtreeConfig(ROSLaunchConfig):

    def __init__(self):
        super(LaunchtreeConfig, self).__init__()

        self._tree_stack = list()
        self.tree = dict()
        self.idx = 0

    def push_level(self, tree_level, unique=False):
        if unique:
            tree_level += ':%d' % self.idx
            self.idx += 1
        self._tree_stack.append(tree_level)
        return tree_level

    def pop_level(self):
        return self._tree_stack.pop()

    def _add_to_tree(self, key, instance):
        level = self.tree
        for launch in self._tree_stack:
            if not launch in level:
                level[launch] = dict()
            elif not isinstance(level[launch], dict):
                old_instance = level[launch]
                level[launch] = dict()
                level[launch + ':%d' % self.idx] = old_instance
                self.idx += 1
            level = level[launch]
        if key in level:
            if isinstance(level[key], dict) and not '_root' in level[key]:
                # this assumes that the root is added right after its children
                level[key]['_root'] = instance
            elif isinstance(instance, LaunchtreeArg) and isinstance(level[key], LaunchtreeArg):
                level[key].merge(instance)
            else:
                level[key + ':%d' % self.idx] = instance
                self.idx += 1
        else:
            level[key] = instance

    def add_executable(self, exe):
        result = super(LaunchtreeConfig, self).add_executable(exe)
        self._add_to_tree(exe.command, exe)
        return result

    def add_param(self, p, filename=None, verbose=True, command=None):
        p.inconsistent = False
        if p.key in self.params and (p.value != self.params[p.key].value or self.params[p.key].inconsistent):
            p.inconsistent = True
            self.params[p.key].inconsistent = True
            rospy.logwarn('Inconsistent param: %s\n  - %s: %s\n  - %s: %s' %
                          (p.key, p.key, str(p.value), self.params[p.key].key, str(self.params[p.key].value)))
        result = super(LaunchtreeConfig, self).add_param(p, filename, verbose)
        self._add_to_tree(p.key, p)
        return result

    def add_machine(self, m, verbose=True):
        result = super(LaunchtreeConfig, self).add_machine(m, verbose)
        self._add_to_tree(m.name, m)
        return result

    def add_test(self, test, verbose=True):
        result = super(LaunchtreeConfig, self).add_test(test, verbose)
        self._add_to_tree(test.name, test)
        return result

    def add_node(self, node, core=False, verbose=True):
        result = super(LaunchtreeConfig, self).add_node(node, core, verbose)
        self._add_to_tree(node.name, node)
        return result

    def add_arg(self, name, default=None, value=None, doc=None):
        self._add_to_tree(name, LaunchtreeArg(name, default, value, doc))

    def add_remap(self, from_topic, to_topic):
        self._add_to_tree(from_topic, LaunchtreeRemap(from_topic, to_topic))

    def add_rosparam(self, command, filename, unique_name):
        self._add_to_tree(unique_name, LaunchtreeRosparam(command, filename))
