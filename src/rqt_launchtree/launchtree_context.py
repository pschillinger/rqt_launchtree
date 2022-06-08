#!/usr/bin/env python3
from roslaunch.loader import LoaderContext


class LaunchtreeContext(LoaderContext):

    def __init__(self, ns, filename, config=None, parent=None, params=None, env_args=None, resolve_dict=False, include_resolve_dict=None, arg_names=None):
        super(LaunchtreeContext, self).__init__(ns, filename, parent,
                                                params, env_args, resolve_dict, include_resolve_dict, arg_names)
        self._config = config

    def add_arg(self, name, default=None, value=None, doc=None):
        result = super(LaunchtreeContext, self).add_arg(
            name, default, value, doc)
        if self._config is not None:
            self._config.add_arg(name, default, value, doc)
        return result

    def add_remap(self, remap):
        result = super(LaunchtreeContext, self).add_remap(remap)
        if self._config is not None:
            self._config.add_remap(remap[0], remap[1])
        return result

    def add_rosparam(self, command, filename, unique_name):
        if self._config is not None:
            self._config.add_rosparam(command, filename, unique_name)

    def child(self, ns):
        result = super(LaunchtreeContext, self).child(ns)
        return LaunchtreeContext(result.ns, result.filename, self._config, result.parent, result.params, result.env_args, result.resolve_dict, result.include_resolve_dict, result.arg_names)
