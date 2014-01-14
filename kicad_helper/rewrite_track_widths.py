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

# This is a hacked-together script to modify a KiCAD PCB file (old style, circa 2012)
# to adjust trace widths for traces of specific net classes. This is handy if you're
# adjusting a PCB to a new PCB stack-up and the impedance characteristics change the
# trace widths required to achieve a specific impedance.

# This is not a general-purpose tool, but could likely be refactored to be usable
# for any arbitrary KiCAD PCB.

import sys

def kicad_to_inch(kicad_unit):
	return kicad_unit / 10000.0

def kicad_to_mil(kicad_unit):
	return kicad_unit / 10.0

def kicad_to_mm(kicad_unit):
	return kicad_to_inch(kicad_unit) * 25.4

def mil_to_kicad(mil):
	return int(round(mil * 10.0))

def parse_equipot(line):
	line_split = line.split()
	if line_split[0] == 'Na':
		number = int(line_split[1])
		quote_split = line.split('"')
		if len(quote_split) != 3:
			raise RuntimeError('unexpected number of quotes in net property "%s"' % line)
		return {
			'name': quote_split[1],
			'number': number,
		}
	elif line_split[0] == 'St':
		return {
		}
	else:
		raise RuntimeError('Unhandled net property in line "%s"' % line)

def parse_track(line):
	line_split = line.split()
	if line_split[0] == 'Po':
		return {
			'shape': int(line_split[1]),
			'start_x': int(line_split[2]),
			'start_y': int(line_split[3]),
			'end_x': int(line_split[4]),
			'end_y': int(line_split[5]),
			'width': int(line_split[6]),
			'drill': int(line_split[7]),
		}
	elif line_split[0] == 'De':
		return {
			'layer': int(line_split[1]),
			'type': int(line_split[2]),
			'net_number': int(line_split[3]),
			'timestamp': int(line_split[4], 16),
			'status': int(line_split[5], 16),
		}
	else:
		raise RuntimeError('Unhandled track property in line "%s"' % line)

def format_track(attributes):
	return [
		'Po %(shape)d %(start_x)d %(start_y)d %(end_x)d %(end_y)d %(width)d %(drill)d' % attributes,
		'De %(layer)d %(type)d %(net_number)d %(timestamp)X %(status)X' % attributes,
	]

net_by_number = {
}

net_by_name = {

}

# net_classes = {
# 	'50 Ohm': {
# 		'matching': (
# 			'^/clock_generator/FE_CLK',
# 			''
# 		)
# 	}
# }

net_class_by_name = {
}

# def net_name_to_net_class(net_name):
# 	if net_name.startswith('/clock_generator/FE_CLK'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/ddr2/') and net_name != '/ddr2/VREF':
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_configuration/PIPE_'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_usb0/PIPE_'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_configuration/ULPI_'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_ddr2/CLK_'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_front_end_misc/D'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_front_end_bank_b/D'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_front_end_bank_c/D'):
# 		return '50 Ohm'
# 	elif net_name.startswith('/fpga_front_end_bank_c/D'):
# 		return '50 Ohm'
# 	elif net_name == '/usb0_interfaces/DM' or net_name == '/usb0_interfaces/DP':
# 		return '45 Ohm'
# 	elif net_name.startswith('/usb0_interfaces/SS'):
# 		return '45 Ohm'
# 	else:
# 		return None

section = None

outside_widths = set()
inside_widths = set()

f_board = open(sys.argv[1], 'r')
for line in f_board:
	line = line.strip()
	line_lower = line.lower()
	if line_lower == '$track':
		section = 'track'
	elif line_lower == '$endtrack':
		section = None
	elif line_lower == '$equipot':
		section = 'equipot'
	elif line_lower == '$endequipot':
		section = None
		net_by_number[current_equipot['number']] = current_equipot
		net_by_name[current_equipot['name']] = current_equipot
		current_equipot = None
	elif line_lower == '$nclass':
		section = 'nclass'
	elif line_lower == '$endnclass':
		section = None
		net_class_by_name[current_netclass['name']] = current_netclass
		current_netclass = None
	elif line_lower == '$czone_outline':
		section = 'czone_outline'
	elif line_lower == '$endczone_outline':
		section = None
	else:
		if section == 'track':
			if line.startswith('Po '):
				current_track = parse_track(line)
				line = None
			elif line.startswith('De '):
				current_track.update(parse_track(line))
				net_class = net_by_number[current_track['net_number']]['class']
				#if current_track['shape'] == 3 and current_track['type'] == 1 and current_track['width'] < mil_to_kicad(18.0):
				#	current_track['width'] = mil_to_kicad(17.7)
				if current_track['layer'] in (0, 15):
					# outside layers
					if current_track['shape'] == 0 and (net_class['name'] == '50 Ohm' or current_track['width'] < mil_to_kicad(7.5)):
						current_track['width'] = mil_to_kicad(7.0)
					outside_widths.add(current_track['width'])
				elif current_track['layer'] in (2, 5):
					# inside layers
					if current_track['shape'] == 0 and (net_class['name'] == '50 Ohm' or current_track['width'] < mil_to_kicad(7.0)):
						current_track['width'] = mil_to_kicad(6.5)
					inside_widths.add(current_track['width'])
				else:
					# ignore
					pass
				line = format_track(current_track)
			else:
				pass
		elif section == 'equipot':
			if line.startswith('Na '):
				current_equipot = parse_equipot(line)
			elif line.startswith('St '):
				current_equipot.update(parse_equipot(line))
			else:
				# ignore
				pass
		elif section == 'nclass':
			if line.startswith('Name '):
				name = line.split(None, 1)[1][1:-1]
				current_netclass = {
					'name': name,
					'nets': set(),
				}
			elif line.startswith('AddNet '):
				net_name = line.split(None, 1)[1][1:-1]
				current_netclass['nets'].add(net_name)
				net = net_by_name[net_name]
				net['class'] = current_netclass
		elif section == 'czone_outline':
			if line.startswith('ZClearance '):
				items = line.split()
				clearance = int(items[1])
				if clearance < mil_to_kicad(7.0):
					clearance = mil_to_kicad(7.0)
				items[1] = str(clearance)
				line = ' '.join(items)
			elif line.startswith('ZMinThickness '):
				items = line.split()
				thickness = int(items[1])
				if thickness < mil_to_kicad(7.0):
					thickness = mil_to_kicad(7.0)
				items[1] = str(thickness)
				line = ' '.join(items)
	if line is not None:
		if isinstance(line, str):
			print(line)
		else:
			for o in line:
				print(o)

#print('outside widths', map(kicad_to_mil, outside_widths))
#print('inside widths', map(kicad_to_mil, inside_widths))

#for net_number in sorted(nets):
#	net = nets[net_number]
#	print(net['name'], net['class'])
