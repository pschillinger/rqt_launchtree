#!/usr/bin/env python
import os
import re
import yaml
import threading
import itertools

import rospy
import rospkg
import roslaunch

from rqt_launchtree.launchtree_loader import LaunchtreeLoader
from rqt_launchtree.launchtree_config import LaunchtreeConfig, LaunchtreeArg, LaunchtreeRemap, LaunchtreeParam, LaunchtreeRosparam

from python_qt_binding import loadUi
from python_qt_binding.QtCore import Qt, Signal
from python_qt_binding.QtGui import QIcon, QColor
from python_qt_binding.QtWidgets import QFileDialog, QWidget, QTreeWidgetItem

class LaunchtreeEntryItem(QTreeWidgetItem):
	_type_order = [dict, roslaunch.core.Node, LaunchtreeRosparam, roslaunch.core.Param, LaunchtreeRemap, LaunchtreeArg, object]
	#inconsistent = False
	def __init__(self, *args, **kw ):
		super(LaunchtreeEntryItem, self).__init__(*args, **kw)
		self.inconsistent = False
	def __ge__(self, other):
		own_type_idx = map(lambda t: isinstance(self.instance, t), self._type_order).index(True)
		other_type_idx = map(lambda t: isinstance(other.instance, t), self._type_order).index(True)
		if own_type_idx != other_type_idx:
			return own_type_idx >= other_type_idx
		return self.text(0) >= other.text(0)
	def __lt__(self, other):
		return not self.__ge__(other)


class LaunchtreeWidget(QWidget):

	update_launch_view = Signal(object)
	display_load_error = Signal(str, str)

	def __init__(self, context):
		super(LaunchtreeWidget, self).__init__()

		self._rp = rospkg.RosPack()
		self._rp_package_list = self._rp.list()
		res_folder = os.path.join(self._rp.get_path('rqt_launchtree'), 'resource')
		ui_file = os.path.join(res_folder, 'launchtree_widget.ui')
		loadUi(ui_file, self)

		self._block_load = True

		self.editor = 'gedit' # configure via settings

		self.setObjectName('LaunchtreeWidget')
		self.reload_button.setIcon(QIcon.fromTheme('view-refresh'))

		self._properties_empty_ui = os.path.join(res_folder, 'properties_empty.ui')
		self._properties_param_ui = os.path.join(res_folder, 'properties_param.ui')

		self._icon_include = QIcon(os.path.join(res_folder, 'img/include.png'))
		self._icon_node = QIcon(os.path.join(res_folder, 'img/node.png'))
		self._icon_param = QIcon(os.path.join(res_folder, 'img/param.png'))
		self._icon_arg = QIcon(os.path.join(res_folder, 'img/arg.png'))
		self._icon_remap = QIcon(os.path.join(res_folder, 'img/remap.png'))
		self._icon_rosparam = QIcon(os.path.join(res_folder, 'img/rosparam_load.png'))
		self._icon_default = QIcon(os.path.join(res_folder, 'img/default.png'))
		self._icon_warn = QIcon(os.path.join(res_folder, 'img/warn.png'))
		self._launch_separator = '  --  '
		self._highlight_color = QColor(255, 255, 150)
		self._neutral_color = QColor(255, 255, 255, 0)

		# connect signals
		self.update_launch_view.connect(self._update_launch_view)
		self.display_load_error.connect(self._display_load_error)
		self.package_select.currentIndexChanged.connect(self.update_launchfiles)
		self.launchfile_select.currentIndexChanged.connect(lambda idx: self.load_launchfile())
		self.reload_button.clicked.connect(self.load_launchfile)
		self.open_button.clicked.connect(self._root_open_clicked)
		self.launch_view.currentItemChanged.connect(self.launch_entry_changed)
		self.filter_nodes.toggled.connect(lambda t: self._filter_launch_view())
		self.filter_params.toggled.connect(lambda t: self._filter_launch_view())
		self.filter_args.toggled.connect(lambda t: self._filter_launch_view())
		self.filter_remaps.toggled.connect(lambda t: self._filter_launch_view())
		self.filter_empty.toggled.connect(lambda t: self._filter_launch_view())
		self.search_input.textChanged.connect(lambda t: self._filter_launch_view(collapse=t==''))
		self.launch_open_button.clicked.connect(self._launch_open_clicked)

		self.reset()


	def reset(self):
		self._launch_config = LaunchtreeConfig()
		self._package_list = list()
		self._load_thread = None
		self.properties_content.setCurrentIndex(0)
		self.main_view.setCurrentIndex(0)

		self.update_package_list()
		

	def block_load(self, do_block):
		self._block_load = do_block

	def load_launchfile(self):
		if self._block_load: return
		self.launch_view.clear()
		self.properties_content.setCurrentIndex(0)
		self.main_view.setCurrentIndex(0)
		filename = os.path.join(
			self._rp.get_path(self.package_select.currentText()),
			self.launchfile_select.currentText()
		)
		launchargs = roslaunch.substitution_args.resolve_args(self.args_input.text()).split(' ')
		if os.path.isfile(filename):
			self.progress_bar.setRange(0,0)
			self._load_thread = threading.Thread(target=self._load_launch_items, args=[filename, launchargs])
			self._load_thread.daemon = True
			self._load_thread.start()

	def _load_launch_items(self, filename, launchargs):
		self._launch_config = LaunchtreeConfig()
		items = list()
		try:
			loader = LaunchtreeLoader()
			loader.load(filename, self._launch_config, verbose=False, argv=['','',''] + launchargs)
			items = self.display_config_tree(self._launch_config.tree)
		except Exception as e:
			error_msg = re.sub(r'(\[?(?:/\w+)+\.launch\]?)',
				lambda m: '[%s]'%self._filename_to_label(m.group(0)),
				str(e)
			)
			help_msg = ''
			if 'arg to be set' in str(e):
				help_msg = 'You can pass args to the root launch file by specifying them in the "args" input field, for example "arg_key:=arg_value".'
			self.display_load_error.emit(error_msg, help_msg)
		self.update_launch_view.emit(items)


	def display_config_tree(self, config_tree):
		items = list()
		for key, instance in config_tree.items():
			if key == '_root': continue
			i = LaunchtreeEntryItem()
			i.instance = instance
			if isinstance(i.instance, roslaunch.core.Param):
				i.inconsistent = i.instance.inconsistent
			if isinstance(instance, dict):
				childItems = self.display_config_tree(instance)
				i.inconsistent = any(c.inconsistent for c in childItems)
				i.addChildren(childItems)
				i.instance = instance.get('_root', instance)
			if isinstance(i.instance, dict):
				i.setText(0, self._filename_to_label(key.split(':')[0]))
				i.setIcon(0, self._icon_include if not i.inconsistent else self._icon_warn)
			else:
				i.setText(0, self._filename_to_label(key.split(':')[0]) if isinstance(i.instance, LaunchtreeRosparam) else
					key.split(':')[0])
				i.setIcon(0, 
					self._icon_warn if i.inconsistent else 
					self._icon_node if isinstance(i.instance, roslaunch.core.Node) else 
					self._icon_param if isinstance(i.instance, roslaunch.core.Param) else 
					self._icon_arg if isinstance(i.instance, LaunchtreeArg) else 
					self._icon_remap if isinstance(i.instance, LaunchtreeRemap) else 
					self._icon_rosparam if isinstance(i.instance, LaunchtreeRosparam) else 
					self._icon_default)
			items.append(i)
		return items

	def _display_load_error(self, error_msg, help_msg):
		self.error_label.setText(error_msg)
		self.help_label.setText(help_msg)
		self.main_view.setCurrentIndex(1)

	def _update_launch_view(self, items):
		self.launch_view.clear()
		self.launch_view.addTopLevelItems(items)
		self.launch_view.sortItems(0, Qt.AscendingOrder)
		self._filter_launch_view()
		self.progress_bar.setRange(0,1)
		self.progress_bar.setValue(1)
		self._load_thread = None

	def update_package_list(self):
		self._package_list = sorted(
			filter(lambda p: len(self._get_launch_files(self._rp.get_path(p)))>0,
				self._rp_package_list
			)
		)
		self.package_select.clear()
		self.package_select.addItems(self._package_list)
		self.package_select.setCurrentIndex(0)

	def update_launchfiles(self, idx):
		package = self.package_select.itemText(idx)
		folder = self._rp.get_path(package)
		launchfiles = self._get_launch_files(folder)
		self.launchfile_select.clear()
		self.launchfile_select.addItems(launchfiles)

	def _get_launch_files(self, path):
		return sorted(
			itertools.imap(lambda p: p.replace(path + '/', ''),
				itertools.ifilter(self._is_launch_file,
					itertools.chain.from_iterable(
						itertools.imap(lambda f:
							map(lambda n: os.path.join(f[0], n), f[2]),
							os.walk(path)
						)
					)
				)
			)
		)

	def _is_launch_file(self, path):
		if not os.path.isfile(path): return False
		(root, ext) = os.path.splitext(path)
		if ext != '.launch': return False
		return True

	def launch_entry_changed(self, current, previous):
		#clear properties
		if current is None:
			return
		data = current.instance
		if isinstance(data, dict) and data.has_key('_root'):
			data = data['_root']
		if isinstance(data, roslaunch.core.Param):
			self.properties_content.setCurrentIndex(1)
			self.param_name.setText(data.key.split('/')[-1] + ':')
			if isinstance(data.value, list):
				self.param_value_list.clear()
				self.param_value_list.addItems(list(str(v) for v in data.value))
				self.param_value_panel.setCurrentIndex(2)
			elif len(str(data.value)) < 100:
				self.param_value.setText(str(data.value))
				self.param_value_panel.setCurrentIndex(0)
			else:
				self.param_value_long.setPlainText(str(data.value))
				self.param_value_panel.setCurrentIndex(1)
		elif isinstance(data, roslaunch.core.Node):
			self.properties_content.setCurrentIndex(2)
			self.node_package.setText(data.package)
			self.node_type.setText(data.type)
			self.node_namespace.setText(str(data.namespace))
			self.node_args.setText(str(data.args))
			self.node_args.setEnabled(data.args != '')
			self.node_prefix.setText(str(data.launch_prefix) if data.launch_prefix is not None else '')
			self.node_prefix.setEnabled(data.launch_prefix is not None)
			self.node_machine.setText(str(data.machine_name) if data.machine_name is not None else '')
			self.node_machine.setEnabled(data.machine_name is not None)
		elif isinstance(data, LaunchtreeArg):
			self.properties_content.setCurrentIndex(4)
			self.arg_name.setText(data.name)
			self.arg_value.setText(str(data.value) if data.value is not None else '')
			self.arg_default.setText(str(data.default) if data.default is not None else '')
			self.arg_doc.setText(str(data.doc) if data.doc is not None else '')
			self.arg_value.setEnabled(data.value is not None)
			self.arg_default.setEnabled(not self.arg_value.isEnabled())
		elif isinstance(data, LaunchtreeRemap):
			self.properties_content.setCurrentIndex(5)
			self.remap_from.setText(data.from_topic)
			self.remap_to.setText(data.to_topic)
		elif isinstance(data, roslaunch.core.Machine):
			self.properties_content.setCurrentIndex(6)
			self.machine_address.setText(str(data.address))
			self.machine_port.setText(str(data.ssh_port))
			self.machine_user.setText(str(data.user) if data.user is not None else '')
			self.machine_user.setEnabled(data.user is not None)
			self.machine_loader.setText(str(data.env_loader) if data.env_loader is not None else '')
			self.machine_loader.setEnabled(data.env_loader is not None)
		elif isinstance(data, LaunchtreeRosparam):
			self.properties_content.setCurrentIndex(3)
			path_segments = self.launch_view.currentItem().text(0).split(self._launch_separator)
			if len(path_segments) == 2:
				(p, l) = path_segments
				(d, f) = os.path.split(l)
			else:
				p = None
				f = path_segments[0]
			self.file_package.setText(p if p is not None else '')
			self.file_package.setEnabled(p is not None)
			self.file_name.setText(f)
		elif isinstance(data, dict):
			self.properties_content.setCurrentIndex(3)
			(p, l) = self.launch_view.currentItem().text(0).split(self._launch_separator)
			(d, f) = os.path.split(l)
			self.file_package.setText(p)
			self.file_name.setText(f)


		else:
			self.properties_content.setCurrentIndex(0)

	def _filter_launch_view(self, collapse=False):
		show_nodes = self.filter_nodes.isChecked()
		show_params = self.filter_params.isChecked()
		show_args = self.filter_args.isChecked()
		show_remaps = self.filter_remaps.isChecked()
		show_empty = self.filter_empty.isChecked()
		search_text = self.search_input.text()
		highlight = search_text != ''
		expand = not collapse and highlight

		def filter_launch_entry(entry):
			show = False

			# param
			if isinstance(entry.instance, roslaunch.core.Param):
				show = show_params
			# node
			elif isinstance(entry.instance, roslaunch.core.Node):
				show = show_nodes
			# machine (no separate option to display machines, is coupled to nodes)
			elif isinstance(entry.instance, roslaunch.core.Machine):
				show = show_nodes
			# arg
			elif isinstance(entry.instance, LaunchtreeArg):
				show = show_args
			# remap
			elif isinstance(entry.instance, LaunchtreeRemap):
				show = show_remaps

			show &= search_text in entry.text(0)
			if show:
				entry.setBackground(0, self._highlight_color if highlight else self._neutral_color)

			if entry.childCount() > 0:
				not_empty = any(map(filter_launch_entry, map(entry.child, range(entry.childCount()))))
				show |= show_empty or not_empty
				entry.setExpanded(not collapse and (expand or entry.isExpanded()))

			entry.setHidden(not show)
			return show

		for idx in range(self.launch_view.topLevelItemCount()):
			filter_launch_entry(self.launch_view.topLevelItem(idx))


	def _launch_open_clicked(self):
		(p, l) = self.launch_view.currentItem().text(0).split(self._launch_separator)
		filename = os.path.join(self._rp.get_path(p), l)
		thread = threading.Thread(target=os.system, args=['%s %s' % (self.editor, filename)])
		thread.daemon = True
		thread.start()

	def _root_open_clicked(self):
		filename = os.path.join(
			self._rp.get_path(self.package_select.currentText()),
			self.launchfile_select.currentText()
		)
		thread = threading.Thread(target=os.system, args=['%s %s' % (self.editor, filename)])
		thread.daemon = True
		thread.start()


	def shutdown(self):
		pass

	def _filename_to_label(self, filename):
		tail = list()
		for d in reversed(filename.split('/')):
			if d in self._rp_package_list:
				return '%s%s%s' % (d, self._launch_separator, '/'.join(reversed(tail)))
			else:
				tail.append(d)
		return filename