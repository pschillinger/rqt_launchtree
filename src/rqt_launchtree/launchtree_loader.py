#!/usr/bin/env python3
import sys

from roslaunch.xmlloader import XmlLoader, loader
from rosgraph.names import get_ros_namespace

from rqt_launchtree.launchtree_context import LaunchtreeContext


class LaunchtreeLoader(XmlLoader):

    def _include_tag(self, tag, context, ros_config, default_machine, is_core, verbose):
        inc_filename = self.resolve_args(tag.attributes['file'].value, context)
        ros_config.push_level(inc_filename, unique=True)
        result = super(LaunchtreeLoader, self)._include_tag(
            tag, context, ros_config, default_machine, is_core, verbose)
        ros_config.pop_level()
        return result

    def _node_tag(self, tag, context, ros_config, default_machine, is_test=False, verbose=True):
        try:
            if is_test:
                self._check_attrs(tag, context, ros_config,
                                  XmlLoader.TEST_ATTRS)
                (name,) = self.opt_attrs(tag, context, ('name',))
                test_name, time_limit, retry = self._test_attrs(tag, context)
                if not name:
                    name = test_name
            else:
                self._check_attrs(tag, context, ros_config,
                                  XmlLoader.NODE_ATTRS)
                (name,) = self.reqd_attrs(tag, context, ('name',))
        except Exception as e:
            pass  # will be handled in super

        ros_config.push_level(name)
        result = super(LaunchtreeLoader, self)._node_tag(
            tag, context, ros_config, default_machine, is_test, verbose)
        ros_config.pop_level()
        return result

    def _rosparam_tag(self, tag, context, ros_config, verbose):
        param_file = tag.attributes['file'].value \
            if 'file' in tag.attributes else ''
        if param_file != '':
            param_filename = self.resolve_args(param_file, context)
            level_name = ros_config.push_level(param_filename, unique=True)
        result = super(LaunchtreeLoader, self)._rosparam_tag(
            tag, context, ros_config, verbose)
        if param_file != '':
            ros_config.pop_level()
            context.add_rosparam(tag.attributes.get(
                'command', 'load'), param_filename, level_name)
        return result

    def _load_launch(self, launch, ros_config, is_core=False, filename=None, argv=None, verbose=True):
        if argv is None:
            argv = sys.argv

        self._launch_tag(launch, ros_config, filename)
        self.root_context = LaunchtreeContext(
            get_ros_namespace(), filename, config=ros_config)
        loader.load_sysargs_into_context(self.root_context, argv)

        if len(launch.getElementsByTagName('master')) > 0:
            print("WARNING: ignoring defunct <master /> tag")
        self._recurse_load(ros_config, launch.childNodes,
                           self.root_context, None, is_core, verbose)
