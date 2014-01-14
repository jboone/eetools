#!/usr/bin/env python
#
# Copyright (c) 2014 Jared Boone <jared@sharebrained.com>
#
# This file is part of eetools.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

# This is a bodged-together script to parse KiCAD PCB files (old style, circa 2012)
# and do various interesting calculations based on trace length and PCB stack-up.
# With some refactoring, it has the potential to be an interesting and useful,
# general-purpose tool.

import sys
import math
from collections import defaultdict

def mil(mil_value):
	# TODO: Implement returning a convertable unit.
	return mil_value
	
class Stack(object):
	def __init__(self):
		self._layers = [
			{
				'name': '1_top',
				'ordinal': 15,
				'material': 'copper',
				'thickness': (mil(1.7), mil(0.4)),
			},
			{
				'material': '2 x 1080',
				'e_r': (4.5, 0.1),
				'thickness': (mil(4.4), mil(0.7)),
			},
			{
				'name': '2_gnd',
				'ordinal': 6,
				'material': 'copper',
				'thickness': (mil(1.4), mil(0.4)),
			},
			{
				'material': 'core',
				'e_r': (4.5, 0.1),
				'thickness': (mil(8), mil(2)),
			},
			{
				'name': '3_inner',
				'ordinal': 5,
				'material': 'copper',
				'thickness': (mil(1.4), mil(0.4)),
			},
			{
				'material': '2 x 2116',
				'e_r': (4.5, 0.1),
				'thickness': (mil(8.4), mil(2)),
			},
			{
				'name': '4_gnd',
				'ordinal': 4,
				'material': 'copper',
				'thickness': (mil(1.4), mil(0.4)),
			},
			{
				'material': 'core',
				'e_r': (4.5, 0.1),
				'thickness': (mil(8), mil(0.8)),
			},
			{
				'name': '5_pwr',
				'ordinal': 3,
				'material': 'copper',
				'thickness': (mil(1.4), mil(0.4)),
			},
			{
				'material': '2 x 2116',
				'e_r': (4.5, 0.1),
				'thickness': (mil(8.4), mil(2)),
			},
			{
				'name': '6_inner',
				'ordinal': 2,
				'material': 'copper',
				'thickness': (mil(1.4), mil(0.4)),
			},
			{
				'material': 'core',
				'e_r': (4.5, 0.1),
				'thickness': (mil(8), mil(2)),
			},
			{
				'name': '7_gnd',
				'ordinal': 1,
				'material': 'copper',
				'thickness': (mil(1.4), mil(0.4)),
			},
			{
				'material': '2 x 1080',
				'e_r': (4.5, 0.1),
				'thickness': (mil(4.4), mil(0.7)),
			},
			{
				'name': '8_bot',
				'ordinal': 0,
				'material': 'copper',
				'thickness': (mil(1.7), mil(0.4)),
			},
		]
	
	def layer_index_by_ordinal(self, ordinal):
		for layer in self._layers:
			if 'ordinal' in layer:
				if layer['ordinal'] == ordinal:
					return self._layers.index(layer)
		return None
		
	def layer_distance(self, ordinal_1, ordinal_2):
		layer_1_index = self.layer_index_by_ordinal(ordinal_1)
		layer_2_index = self.layer_index_by_ordinal(ordinal_2)
		if layer_1_index > layer_2_index:
			layer_1_index, layer_2_index = layer_2_index, layer_1_index
		thickness = sum([layer['thickness'][0] for layer in self._layers[layer_1_index:layer_2_index+1]])
		return thickness

class Board(object):
	def __init__(self):
		self._nets_by_name = {}
		self._nets_by_number = {}
		
	def parse(self, line):
		pass
		
	def add(self, child):
		if isinstance(child, Net):
			if child.name in self._nets_by_name:
				raise RuntimeError('multiple nets named "%s"' % child.name)
			self._nets_by_name[child.name] = child
			if child.number in self._nets_by_number:
				raise RuntimeError('multiple nets numbered "%d"' % child.number)
			self._nets_by_number[child.number] = child
		elif isinstance(child, Tracks):
			if hasattr(self, 'tracks'):
				raise RuntimeError('Multiple TRACK sections in BOARD')
			self.tracks = child
	
	@property
	def nets(self):
		return self._nets_by_number.values()
		
	def net_by_name(self, name):
		return self._nets_by_name[name]

	def net_by_number(self, number):
		return self._nets_by_number[number]

class Net(object):
	def parse(self, line):
		line_split = line.split()
		if line_split[0] == 'Na':
			self.number = int(line_split[1])
			quote_split = line.split('"')
			if len(quote_split) != 3:
				raise RuntimeError('unexpected number of quotes in net property "%s"' % line)
			self.name = quote_split[1]
		elif line_split[0] == 'St':
			pass
		else:
			raise RuntimeError('Unhandled net property in line "%s"' % line)
	
	def __repr__(self):
		return '%s(%d)' % (self.name, self.number)

class Track(object):
	shape_map = {
		0: 'segment',
		1: 'rectangle',
		2: 'arc',
		3: 'circle',
		4: 'polygon',
		5: 'curve',
	}
	
	type_map = {
		0: 'copper',
		1: 'via',
	}
	
	def parse(self, line):
		line_split = line.split()
		if line_split[0] == 'Po':
			self.shape = Track.shape_map[int(line_split[1])]
			self.start_x = int(line_split[2])
			self.start_y = int(line_split[3])
			self.end_x = int(line_split[4])
			self.end_y = int(line_split[5])
			self.width = int(line_split[6])
			self.drill = int(line_split[7])
		elif line_split[0] == 'De':
			self.layer = int(line_split[1])
			self.type = Track.type_map[int(line_split[2])]
			self.net_number = int(line_split[3])
			self.timestamp = int(line_split[4], 16)
			self.status = int(line_split[5], 16)
		else:
			raise RuntimeError('Unhandled track property in line "%s"' % line)
	
	def __repr__(self):
		return 'Track(%(shape)s/%(type)s: %(start_x)d,%(start_y)d - %(end_x)d,%(end_y)d x %(width)d)' % self.__dict__

class Tracks(object):
	def __init__(self):
		self._tracks = []
		self._tracks_by_net_number = defaultdict(list)
		
	def parse(self, line):
		line_split = line.split()
		if line_split[0] == 'Po':
			if hasattr(self, '_new_track'):
				raise RuntimeError('Po arrived when another Po was pending in TRACKS')
			self._new_track = Track()
			self._new_track.parse(line)
		elif line_split[0] == 'De':
			self._new_track.parse(line)
			self._tracks_by_net_number[self._new_track.net_number].append(self._new_track)
			self._tracks.append(self._new_track)
			del self._new_track
		else:
			raise RuntimeError('Unhandled track property in line "%s"' % line)

	def by_net(self, net):
		return self._tracks_by_net_number[net.number]

	def __repr__(self):
		return str(self._tracks_by_net_number)
		#return ','.join(map(repr, self._tracks))

sections = {
	'BOARD': Board,
	'GENERAL': None,
	'SHEETDESCR': None,
	'SETUP': None,
	'EQUIPOT': Net,
	'NCLASS': None,
	'TEXTPCB': None,
	'MODULE': None,
	'PAD': None,
	'SHAPE3D': None,
	'DRAWSEGMENT': None,
	'TRACK': Tracks,
	'ZONE': None,
	'CZONE_OUTLINE': None,
	'POLYSCORNERS': None,
}

board = Board()
board.stack = Stack()

context = [board]

def context_push(keyword):
	context.append(keyword)

def context_pop(keyword):
	return context.pop()

def context_parse(line):
	if not isinstance(context[-1], str):
		context[-1].parse(line)

def context_add_child(child):
	if context:
		if not isinstance(context[-1], str):
			context[-1].add(child)

f_board = open(sys.argv[1], 'r')
for line in f_board:
	line = line.strip()
	if line.startswith('$'):
		line_split = line.split()
		first_word = line_split[0].upper()
		
		context_operation = None
		context_keyword = None
		if first_word.startswith('$END'):
			context_keyword = first_word[4:]
			popped_object = context_pop(context_keyword)
			context_add_child(popped_object)
		else:
			context_keyword = first_word[1:]
			handler = sections[context_keyword]
			push_value = context_keyword
			if handler:
				push_value = handler()
			context_push(push_value)
	else:
		context_parse(line)

usb_pipe_rx_nets = [net for net in board.nets if net.name.startswith('/fpga_usb0/PIPE_RX_DATA') or net.name.startswith('/fpga_usb0/PIPE_RX_VALID') or net.name.endswith('/PCLK')]
usb_pipe_tx_nets = [net for net in board.nets if net.name.startswith('/fpga_usb0/PIPE_TX_DATA') or net.name.endswith('/PIPE_TX_CLK')]
usb_pipe_nets = usb_pipe_rx_nets + usb_pipe_tx_nets

ddr2_nets = [net for net in board.nets if
	net.name.startswith('/ddr2/DQ') or
	net.name.startswith('/ddr2/DM') or
	net.name.startswith('/ddr2/A') or
	net.name.startswith('/ddr2/RAS#') or
	net.name.startswith('/ddr2/CAS#') or
	net.name.startswith('/ddr2/WE#') or
	net.name.startswith('/ddr2/S#') or
	net.name.startswith('/ddr2/ODT') or
	net.name.startswith('/ddr2/BA') or
	net.name.startswith('/ddr2/CK')
]

fe_b_nets = [net for net in board.nets if
	net.name.startswith('/fpga_front_end_bank_b/D')
]

fe_c_nets = [net for net in board.nets if
	net.name.startswith('/fpga_front_end_bank_c/D')
]

outer_layers = (15, 0)
inner_layers = (5, 2)

def track_length(track):
	if track.type == 'copper':
		dx = track.end_x - track.start_x
		dy = track.end_y - track.start_y
		return math.sqrt(math.pow(dx, 2.0) + math.pow(dy, 2.0))
	elif track.type == 'via':
		return 0
	else:
		raise RuntimeError('track layer %d is not copper (%s)' % (track.layer, track.type))

def track_delay(track):
	if track.type == 'copper':
		length_inch = kicad_to_inch(track_length(track))
		if track.layer in outer_layers:
			delay_sec = length_inch * 150e-12
		elif track.layer in inner_layers:
			delay_sec = length_inch * 180e-12
		else:
			raise RuntimeError('track layer %d unknown prop delay' % track.layer)
		return delay_sec
	elif track.type == 'via':
		return 0
	else:
		raise RuntimeError('track layer %d is not copper (%s)' % (track.layer, track.type))

def net_length(net):
	return sum([track_length(track) for track in board.tracks.by_net(net)])

def net_delay(net):
	return sum([track_delay(track) for track in board.tracks.by_net(net)])

def kicad_to_inch(kicad_unit):
	return kicad_unit / 10000.0

def kicad_to_mm(kicad_unit):
	return kicad_to_inch(kicad_unit) * 25.4

def display_bus_lengths(board, nets):
	net_lengths = dict([(net, kicad_to_mm(net_length(net))) for net in nets])
	min_net = min(net_lengths, key=net_lengths.get)
	min_length = net_lengths[min_net]
	max_net = max(net_lengths, key=net_lengths.get)
	max_length = net_lengths[max_net]

	for net in sorted(net_lengths, key=net_lengths.get):
		net_tracks = board.tracks.by_net(net)
		vias = [track for track in net_tracks if track.type == 'via']
		length = net_lengths[net]
		net_short_name = net.name.split('/')[-1]
		print('%20s: %5.2f %5.2f %5.2f %d' % (net_short_name, length, length - min_length, max_length - length, len(vias)))

def display_bus_info(board, nets):
	net_lengths = dict([(net, net_length(net)) for net in nets])
	min_length_net = min(net_lengths, key=net_lengths.get)
	max_length_net = max(net_lengths, key=net_lengths.get)
	min_length = net_lengths[min_length_net]
	max_length = net_lengths[max_length_net]

	net_delays = dict([(net, net_delay(net)) for net in nets])
	min_delay_net = min(net_delays, key=net_delays.get)
	max_delay_net = max(net_delays, key=net_delays.get)
	min_delay = net_delays[min_delay_net]
	max_delay = net_delays[max_delay_net]

	def mm(value):
		return '%5.1f mm' % kicad_to_mm(value)
	
	def ps(value):
		return '%3.0f ps' % (value * 1e12)
	
	print('%20s   len    min+   max-    len      min+     max-    via' % ('',))
	for net in sorted(net_delays, key=net_delays.get):
		net_tracks = board.tracks.by_net(net)
		vias = [track for track in net_tracks if track.type == 'via']
		length = net_lengths[net]
		delay = net_delays[net]
		net_short_name = net.name.split('/')[-1]
		print('%20s: %s %s %s %s %s %s %3d' % (net_short_name,
			ps(delay), ps(delay - min_delay), ps(max_delay - delay),
			mm(length), mm(length - min_length), mm(max_length - length),
			len(vias))
		)

#display_bus_info(board, usb_pipe_rx_nets)
#print('-' * 72)
#display_bus_info(board, usb_pipe_tx_nets)
#print('-' * 72)
#display_bus_info(board, ddr2_nets)
#print('-' * 72)
display_bus_info(board, fe_c_nets)
print('-' * 72)
display_bus_info(board, fe_b_nets)

#print(board.stack.layer_distance(0, 15))
