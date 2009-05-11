#!/usr/bin/python
import sys
import os

#including slash in the end use blank if all is in paths
#settings for 1&1
latex_dir = '/usr/local/texlive/2008/bin/x86_64-linux/'
IMAGE_DIR = '/var/www/vhosts/default/htdocs/nmrwiki/wiki/images/NMRPulse' #where to put image files
IMAGE_DIR_URL = 'http://nmrwiki.org/wiki/images/NMRPulse'
from Numeric import *
import copy

#including slash in the end use blank if all is in paths
#settings for hostmonster
#latex_dir = '/home/nmrwikio/incoming/teTeX/bin/x86_64-unknown-linux-gnu/' 
#IMAGE_DIR = '/home/nmrwikio/www/wiki/images/NMRPulse' #where to put image files
#IMAGE_DIR_URL = 'http://nmrwiki.org/wiki/images/NMRPulse'
#sys.path.append('/home/nmrwikio/incoming/Imaging-1.1.6/PIL') #path to Python Imaging Library
#sys.path.append('/home/nmrwikio/incoming/python-modules/numpy/lib64/python2.3/site-packages') #path to numpy library
#from numpy import *

latex_cmd = latex_dir + 'latex'
dvipng_cmd = latex_dir + 'dvipng'
import re
import Image

label_regex_token = '[a-zA-Z0-9_]+'
anchor_basename_token = '[a-z]+'

element_name_regex_token = '[a-zA-Z0-9]+'
expression_regex_token = '[\^\_\{\}a-zA-Z0-9\*\/\(\)]+'

blanks_re = re.compile(r'\s\s+')

"""@package docstring
nmrType creates pulse sequence image from a simple text markup
"""

#todo these functions need to be packaged
def carray(array):
	return '{'+ ','.join(map(lambda x: str(x),array)) + '}'

def latex2image(text):
	"""creates png files from latex source
	"""
	import os
	from tempfile import NamedTemporaryFile
	t = NamedTemporaryFile(mode='a+',dir=IMAGE_DIR)
	latex = r"""\documentclass{article}
\pagestyle{empty}
\begin{document}
$$%s$$
\end{document}\n """ % text
	t.write(latex)
	t.flush()
	bname = os.path.basename(t.name)
	os.system('%s -halt-on-error %s > /dev/null' % (latex_cmd,t.name))
	os.system('rm %s.log' % bname)
	os.system('rm %s.aux' % bname)
	if not os.path.exists('%s.dvi' % bname):
		raise ParsingError('problem parsing latex: %s' % text)

	os.system('%s %s.dvi -T tight -D 130 -o %s.png > /dev/null' % (dvipng_cmd,bname,bname))
	os.system('rm %s.dvi' % bname)
	im = Image.open('%s.png' % bname)
	os.system('rm %s.png' % bname)
	t.close()
	return im

def paste_image(im,pulse_sequence,coor,yplacement='center',xplacement='center'):
#pastes image into pulse_sequence object image
	s = im.size
	eq_image = im
	t_size = pulse_sequence._image.size
	paste_image = Image.new('L',t_size,256)

	x = coor[0]
	if xplacement == 'center':
		x = int(coor[0] - eq_image.size[0]/2)
	elif xplacement == 'left':
		x = int(coor[0] - eq_image.size[0])
	elif xplacement == 'right':
		x = coor[0]
	else:
		raise 'internal error unknown %s xplacement' % xplacement

	y = coor[1]
	if yplacement == 'center':
		y = int(coor[1] - eq_image.size[1]/2)
	elif yplacement == 'center-clear':
		y = int(coor[1] - eq_image.size[1]/2 - 4)#todo this is a plug
	elif yplacement == 'above':
		y = int(coor[1] - eq_image.size[1])
	elif yplacement == 'below':
		y = coor[1]
	else:
		raise 'internal error unknown %s yplacement' % yplacement
	
	paste_image.paste(eq_image,(int(x),int(y)))

	from ImageChops import darker
	newimage = darker(paste_image,pulse_sequence._image)
	pulse_sequence._image.paste(newimage,(0,0))

def draw_latex(text,pulse_sequence,coor,yplacement='center',xplacement='center'):
	#coor is duple of (x,y) where the drawing should be centered
	#yplacement: center, above, below
	im = latex2image(text)
	paste_image(im,pulse_sequence,coor,yplacement,xplacement)
	
def parse_param(input):
	"""utility function loads key=value pairs into a table
	"""
	bits = input.split('=')
	if len(bits) == 2:
		return {bits[0].strip():bits[1].strip()}
	elif len(bits) > 2:
		val_re = re.compile(r'(%s)\s*$' % label_regex_token)
		m = val_re.search(bits[1])
		if m:
			key = bits[0].strip()
			val = val_re.sub('',bits[1]).strip()
			bits[1] = m.group(1)
			bits.pop(0)
			param_table = parse_param('='.join(bits))
			param_table[key] = val
			return param_table
		else:
			raise ParsingError('%s <-here a name token expected' % bits[1])

class CodeLineSuccess:
	pass

class CodeLine:
	regex = None
	empty = re.compile(r'^\s*$')
	code = None
	def __init__(self,regex):
		self.regex = re.compile(regex)
	def try_add_code(self,code):
		m = self.regex.match(code)
		if m:
			code = m.group(1).strip()
			if self.code:
				code = self.code + ' ' + code
			self.code = code
			raise CodeLineSuccess()

class DecorLineList(CodeLine):
	def __init__(self,regex):
		CodeLine.__init__(self,regex)
		self.list = []
	def try_add_code(self,code):
		m = self.regex.match(code)
		if m:
			type = m.group(1).strip()
			code = m.group(2).strip()
			self.list.append({'type':type,'code':code})
			raise CodeLineSuccess()

class CodeLineTable(CodeLine):
	def __init__(self,regex):
		CodeLine.__init__(self,regex)
		self.table = {}
		self.item_order = []
	def try_add_code(self,code):
		m = self.regex.match(code)
		if m:
			key = None
			if m.group(1):
				key = m.group(1).strip()
				if not key in self.item_order:
					self.item_order.append(key)
			code = m.group(2).strip()
			if self.table.has_key(key):
				code = self.table[key] + ' ' + code
			self.table[key] = code
			raise CodeLineSuccess()

class ParsingError:
	text =  None
	def __init__(self,text):
		self.text = blanks_re.sub(' ',text)
	def __str__(self):
		print 'parsing error - ' , self.text

class CompilationError:
	text =  None
	def __init__(self,text):
		self.text = blanks_re.sub(' ',text)
	def __str__(self):
		print 'compilation error - ' , self.text

class ChannelCodeParsingError:
	channel_name = None
	channel_text = None
	error_text = None
	def __init__(self,ch_name,ch_text,error_text):
		self.channel_name = ch_name
		self.channel_text = ch_text
		self.error_text = blanks_re.sub(' ',error_text)

	def __str__(self):
		print 'Error parsing pulse sequence for channel %s' \
			% (self.channel_name)
		print self.error_text
		print 'Problem line:'
		print 'channel %s: %s' % (self.channel_name,self.channel_text)
	
class FunctionVar:
	"""DAO type class for function type variables in PulseScript
	"""
	def __init__(self,name,vars):
		"""vars is array of associative arrays of following structure
		[{type:positional|named,name:Null|name,value:value},...]
		variables should be all positional or all named
		"""
		self.name = name
		type = vars[0]['type']
		for var in vars:
			if var['type'] != type:
				raise ParsingError('variables must be either all named or all positional')
		self.var_type = type
		if type == 'positional':
			args = []
			for var in vars:
				args.append(var['value'])
		elif type == 'named':
			args = {}
			for var in vars:
				args[var['name']] = var['value']
		else:
			raise 'internal error unknown type of function variable in PulseScript source'
		self.args = args 
	def get_arg(self,key):
		return self.args[key]
	def get_args(self):
		return self.args
	def get_name(self):
		return self.name

class Decoration:
	def __init__(self,type,code):
		par = parse_param(code)

		par_table = {'vdash':('start','end','anchor'),
							'point':('anchor','label','show_at','align')}

		if type in par_table.keys():
			ap = par_table[type]
			for key in par.keys():
				if key in ap:
					self.__dict__[key] = par[key]
				else:
					raise ParsingError('unknown parameter %s for decoration %s' % (key,type))
		else:
			raise ParsingError('unknown decoration type %s' % type)

		self.type = type
	
	def draw(self,draw_object): #Decoration.draw()
		pass

class N:
	"""class for numbers to use in building delay expressions
	"""
	def __init__(self,value):
		if value == 'pi':
			self._val = 3.14159265
		elif isinstance(value, (int, long, float)):
			self._val = float(value)
		else:
			raise "internal error: initializing class N with unexpected value"
	def get_type(self):#N.get_type()
		return 'num'

	def get_op(self):
		return None

	def get_val(self):
		return self._val

	def get_primary_delay_list(self): #N.get_primary_delay_list()
		"""dummy function needed for recursive retrieval of 
		primary delay lists from the expressions
		"""
		return []
	def get_eqn_str(self):
		num = '%.15f' % self._val
		num_re = re.compile(r'\.?0*$')
		return num_re.sub('',num)

	def reduce(self):
		pass

	def get_varian_expression(self):
		return self.get_eqn_str()

	def is_zero(self):
		if self._val == 0:
			return True
		return False
	
	def is_one(self):
		if self._val == 1:
			return True
		return False

class E:
	"""delay expression class
	holds tree representation of formula for calulating delays
	operands are either expressions or PulseSequenceElement objects
	or number objects 
	
	units are seconds

	e = E('set',delay1) #one operand!
	e = E('add',delay1,pulse2,pulse3) #multiple operands
	e = E('sub',delay1,delay2) #note two operands!
	e = E('div',delay1,delay2) #note two operands!
	e = E('max',delay1,delay2,...) #multiple operands
	e = E('mul',...) #multiple operands
	"""
	def __init__(self,type,*arg):
		ok_types = ('add','sub','max','set','div','mul')
		ok_operands = ('delay','rf_wide_pulse','rf_pulse','pfg'
				,'expression','num','acq','wide_event_toggle')
		if type not in ok_types:
			raise 'internal error: unknown delay expression type %s' % type
		if (type == 'sub' or type == 'div') and len(arg) != 2:
			raise 'internal error: sub expression requires two operands'
		if type == 'set' and len(arg) != 1:
			raise 'internal error: set expression requires one operand'

		for op in arg:
			if op.get_type() not in ok_operands:
				raise 'internal error: illegal operand type %s' % op.get_type()
		self._operator = type
		self._operands = list(arg)

	def get_op(self):
		"""get operation type
		"""
		return self._operator

	def get_operands(self):
		return self._operands

	def get_type(self): #E.get_type()
		return 'expression';

	def get_primary_delay_list(self): #E.get_primary_delay_list()
		"""return list of primary delay components of
		the expression
		"""
		list = []
		names = []
		for arg in self._operands:
			newlist = arg.get_primary_delay_list()
			for item in newlist:
				if item.name not in names:
					list.append(item)
					names.append(item.name) #would be less code with better POM
		return list

	def get_eqn_str(self):
		op = self._operator
		tokens = []
		for arg in self._operands:
			tokens.append(arg.get_eqn_str())
		if op == 'max':
			return 'max(' + ','.join(tokens) + ')'
		elif op == 'add':
			return '+'.join(tokens)
		elif op == 'mul':
			return '*'.join(tokens)
		elif op == 'sub':
			return '(' + tokens[0] + '-(' + tokens[1] + '))'
		elif op == 'set':
			return tokens[0]
		elif op == 'div':
			return '(' + tokens[0] + ')/(' + tokens[1] + ')'
		else:
			raise 'internal error: unknown operator %s' % op

	def get_varian_max_expression(self,args):
		if len(args) == 0:
			return None 
		elif len(args) == 1:
			return args[0]
		else:
			first = args.pop(0)
			rest = self.get_varian_max_expression(args)
			return 'MAX(%s,%s)' % (first,rest)

	def get_varian_expression(self):
		op = self._operator
		tokens = []
		orig = self.get_eqn_str()
		for arg in self._operands:
			tokens.append(arg.get_varian_expression())
		if op == 'max':
			tbl = {}
			for t in tokens:
				tbl[t] = 1
			tokens = tbl.keys()
			if len(tokens) == 0:
				return '0'
				raise CompilationError('max expression %s has no arguments' % self.get_eqn_str())
			else:
				text = self.get_varian_max_expression(tokens)
				return text
		elif op == 'add':
			nonzero = []
			for t in tokens:
				try:
					if float(t) != 0:
						nonzero.append(t)
				except:
					nonzero.append(t)
			if len(nonzero) > 0:
				text = '+'.join(nonzero)
				return text
			else:
				return '0'
		elif op == 'mul':
			text = '*'.join(tokens)
			return text
		elif op == 'sub':
			try:
				if float(tokens[1]) == 0:
					text = tokens[0]
			except:
				try:
					if float(tokens[0]) == 0:
						text = '-(%s)' % tokens[1]
				except:
					text = tokens[0] + '-(' + tokens[1] + ')'
			return text
		elif op == 'set':
			return tokens[0]
		elif op == 'div':
			try:
				if float(tokens[0]) == 0:
					text = '0'
			except:
				text = '(' + tokens[0] + ')/(' + tokens[1] + ')'
			return text
		else:
			raise 'internal error: unknown operator %s' % op

	def get_operand(self,index):
		return self._operands[index]

	def reduce(self):
		op = self._operator
		#reduce operands
		for arg in self._operands:
			arg.reduce()

		#flatten 'set'
		flat = []
		for arg in self._operands:
			if arg.get_op() == 'set':
				flat.append(arg.get_operand(0))
			else:
				flat.append(arg)
		self._operands = flat

		#get rid of zeroes and ones in mul
		if (op == 'div'):
			op1 = self._operands[0]
			op2 = self._operands[1]
			if op1.is_zero():
				self.set_zero()
			if op2.is_zero():
				raise CompilationError('division by zero')
			elif op2.is_one():
				self.set(op1)
		elif (op == 'mul'):
			#collect and multiply numbers

			#get rid of ones
			
			#check for multiplication by zero
			for op in self._operands:
				if op.is_zero():
					self.set_zero()
		elif (op == 'add'):
			#get rid of zeroes
			nozeroes = []
			for arg in self._operands:
				if not arg.is_zero():
					nozeroes.append(arg)
			self._operands = nozeroes
			#collect and add numbers

			#if all numbers set to number
		elif (op == 'sub'):
			if self.get_operand(1).is_zero():
				self.set(self.get_operand(0))

		if op in ['mul','add','max'] and len(self._operands) == 1:
			self.set(self._operands[0])

	def set(self,op):
		self._operator = 'set'
		self._operands = [op]

	def set_zero(self):
		self.set(N(0))

	def is_zero(self):
		if self.get_type() == 'num' and self.get_val() == 0:
			return True
		return False

	def is_one(self):
		if self.get_type() == 'num' and self.get_val() == 1:
			return True
		return False

class Anchor:
	def __init__(self,name):
		self.name = name
		self.decoration = None
		self.label = None
		self.events = []
		self.group = None #parent anchor group
		self.xcoor = None
		self.type = 'empty' #empty|pegging|normal read below
		self.drawing_width = None #this works differently for anchors with
								#centered and wide events
								#anchor type can be either pegging (harboring 
								#events stretched between two anchors)
								#or normal(containing events attached to single anchor)
								#or empty - containing zero events
								#a combo type is impossible

	def _bootstrap_objects(self,ps_obj):
		self.pulse_sequence = ps_obj
		for e in self.events:
			e._bootstrap(ps_obj)

	def get_max_xcoor(self):#Anchor.get_max_xcoor()
		x = self.xcoor
		pw = self.drawing_post_width
		return x+pw

	def determine_type(self):
		"""determine type of anchor "normal|pegging"
		assign corresponding value of type variable
		"""
		types = {}
		for e in self.events:
			if e._type in ('rf_pulse','pfg','wide_event_toggle'):
				types['normal'] = 1
			elif e._type in ('acq','rf_wide_pulse','pfg_wide'):
				types['pegging'] = 1
			else:
				raise 'internal error unknown anchored event type %s' % e._type

		if len(types.keys()) == 1:
			self.type = types.keys()[0]
		elif len(types.keys()) == 0:
			self.type = 'empty'
		else:
			raise ParsingError('cannot determine type of anchor @%s' % self.name\
										+' some events are attached to this anchor only, others to '\
										+'this one and some other one - not allowed')

	def time(self): #Anchor.time()
		"""initialize two expression objects per anchor
		that will be used to calculate equations for delays between events
		one for pre-anchor dead time and one for post-anchor dead time

		this function is merged with calc_drawing_dimensions, so probably should
		be renamed???
		"""
		pres = []
		posts = []
		for e in self.events:
			e.time()
			pres.append(e.pre_span)
			posts.append(e.post_span)

		length = E('max',*(self.events))
		half = E('div',length,N(2))
		self.pre_span = E('max',*(pres)) 
		self.post_span = E('max',*(posts))
		self.span = E('add',self.pre_span,self.post_span) 

		#calc drawing dimensions - moved in code from separate function
		self.determine_type()

		anchor_w = 0
		anchor_pre_w = 0
		anchor_post_w = 0
		if self.type == 'normal':
			for e in self.events:
				e.calc_drawing_dimensions()
				ew = e.drawing_width
				pre_w = e.drawing_pre_width
				post_w = e.drawing_post_width
				if ew > anchor_w:
					anchor_w = ew
				if pre_w > anchor_pre_w:
					anchor_pre_w = pre_w
				if post_w > anchor_post_w:
					anchor_post_w = post_w
					
		elif self.type in ('empty','pegging'):
			anchor_w = 0
			anchor_pre_w = 0
			anchor_post_w = 0
		else:
			raise 'internal error: unknown anchor type \'%s\'' % self.type

		self.drawing_width = anchor_w
		self.drawing_pre_width = anchor_pre_w
		self.drawing_post_width = anchor_post_w

	def set_xcoor(self,xcoor): #Anchor.set_xcoor()
		self.xcoor = xcoor
		for e in self.events:
			e.set_xcoor()

	def has_event(self,channel):
		e = self.get_event(channel)
		if e == None:
			return False
		else:
			return True

	def get_event(self,channel):
		"""assumes that there can be only one
		event per channel per anchor
		"""
		for e in self.events:
			if e.channel == channel:
				return e
		return None 

	def get_events(self,channel=None): #Anchor.get_events()
		channel = self.pulse_sequence.get_channel_key(channel)
		output = []
		for e in self.events:
			if e.channel == channel:
				output.append(e)
		return output

	def _are_events_compatible(self,e1,e2):
		compatible_groups = (('rf_wide_pulse','acq'),
							('rf_pulse'),
							('pfg'),('pfg_wide'))
		t1 = e1._type
		t2 = e2._type
		for g in compatible_groups:
			if t1 in g and t2 in g:
				return True
		return False

	def draw_tic(self,channel):
		ps = self.pulse_sequence
		ch = ps.get_channel(channel)
		d = ps.get_draw_object()
		x = self.xcoor
		y = ch.ycoor
		deltay_above = ps.blank_tic_size
		deltay_below = ps.blank_tic_size 
		if self.has_event(channel):
			deltay_above = 0
			deltay_below = ps.event_tic_size
		d.line(((x,y-deltay_above),(x,y+deltay_below)))

	def draw_tics_on_all_channels(self):
		ps = self.pulse_sequence
		chlist = ps.get_channel_list()
		for channel in chlist:
			self.draw_tic(channel)

	def add_event(self,event):

		if len(self.events) > 0:
			type = event._type
			if type == 'delay':
				raise 'internal parser error: delays cannot be added as events'

			n1 = event.name
			t1 = event._type
			n2 = self.events[0].name
			t2 = self.events[0]._type
			if not self._are_events_compatible(event,self.events[0]):
				err_text = 'event %s of %s type ' % (n1,t1)\
						+ 'cannot be added to anchor @%s' % self.name \
						+ ' because it already contains ' \
						+ 'event %s of %s type' % (n2,t2)
				raise ParsingError(err_text)	
		self.events.append(event)

	def __str__(self):
		name = 'Null'
		if self.name:
			name = self.name
			
		a_text = '@' + name
		num = len(self.events)

		e_lines = []
		for e in self.events:
			l = e.__str__()
			if l == None:
				l = ''
			e_lines.append(l)

		e_txt = ';'.join(e_lines)

		a_text = a_text + ' (%d events: %s)' % (num,e_txt)
		return a_text

class AnchorGroup:
	def __init__(self):
		self.anchor_list = []
		self.timed_anchor = None #anchor before which previous group's post-delay comes
		self.timing_anchor = None #anchor after which post_delay is to be applied
		self.post_delay = None
		self.xcoor = None
		self.drawing_pre_width = 0
		self.drawing_post_width = 0

	def time(self): #AnchorGroup.time()
		for a in self.anchor_list:
			a.time() #calculate anchor pre_span and post_span

		ta = self.timed_anchor
		if ta == None:
			raise ParsingError('all anchor groups must be timed')

		#calculate anchor coordinates in the anchor group relative to timed anchor
		self.set_xcoor(0)
		self.calc_drawing_width()

	def get_max_xcoor(self):
		return self.anchor_list[-1].get_max_xcoor()

	def calc_drawing_width(self):
		al = self.anchor_list
		last = len(al) - 1
		self.drawing_pre_width = al[0].drawing_pre_width - al[0].xcoor 
		self.drawing_post_width = al[last].xcoor + al[last].drawing_post_width
		self.drawing_width = self.drawing_pre_width + self.drawing_post_width

	def get_drawing_pre_width(self,delay): #AnchorGroup.get_drawing_pre_width()
		"""get drawing_pre_width on a given channel for the anchor group
		if channel==None, use first channel (first line with rf header)
		"""
		channel = delay.show_at
		ps = self.pulse_sequence
		channel = ps.get_channel_key(channel)
		channel_events = self.get_events(channel=channel)
		if len(channel_events):
			ea = delay.end_anchor
			xcoor = ea.xcoor
			if ea.has_event(channel):
				xcoor = xcoor - ea.get_event(channel).drawing_pre_width

			for e in channel_events:
				if e.anchor.xcoor < xcoor:
					xcoor = e.anchor.xcoor - e.drawing_pre_width
			return self.xcoor - xcoor
		else:
			return 0

	def get_drawing_post_width(self,delay): #AnchorGroup.get_drawing_post_width
		"""get drawing_post_width on a given channel for the anchor group
		"""
		channel = delay.show_at
		ps = self.pulse_sequence
		channel = ps.get_channel_key(channel)

		channel_events = self.get_events(channel=channel)

		if len(channel_events) > 0:
			sa = delay.start_anchor
			xcoor = sa.xcoor
			if sa.has_event(channel):
				xcoor = xcoor + sa.get_event(channel).drawing_post_width
				
			xcoor = delay.start_anchor.xcoor #left drawing edge
			for e in channel_events:
				try_xcoor = e.anchor.xcoor + e.drawing_post_width
				if try_xcoor > xcoor:
					xcoor = try_xcoor
			return xcoor - self.xcoor
		else:
			return 0


	def get_events(self,channel=None): #AnchorGroup.get_events()
		events = []
		ps = self.pulse_sequence
		channel = ps.get_channel_key(channel)
		for a in self.anchor_list:
			a_events = a.get_events(channel)
			events.extend(a_events)
		return events

	def set_xcoor(self,xcoor): #AnchorGroup.set_xcoor()

		self.xcoor = xcoor
		ta = self.timed_anchor
		al = self.anchor_list

		ta_index = al.index(ta) 
		ta.set_xcoor(xcoor)
		prev_a = ta
		c_index = ta_index - 1
		while c_index >= 0:
			a = al[c_index]
			a.set_xcoor(prev_a.xcoor - prev_a.drawing_pre_width - a.drawing_post_width)
			c_index = c_index - 1
			prev_a = a
		prev_a = ta
		c_index = ta_index + 1
		while c_index < len(al):
			a = al[c_index]
			a.set_xcoor(prev_a.xcoor + prev_a.drawing_post_width + a.drawing_pre_width)
			c_index = c_index + 1
			prev_a = a

	def get_anchor(self,a_name):
		for a in self.anchor_list:
			if a.name == a_name:
				return a
		raise 'anchor @%s not found in the anchor group' % a.name

	def set_timed_anchor(self,a_name):
		a = self.get_anchor(a_name)
		self.timed_anchor = a

	def set_timing_anchor(self,a_name):
		a = self.get_anchor(a_name)
		self.timing_anchor = a

	def draw_all_tics(self):#AnchorGroup.draw_all_tics()
		for a in self.anchor_list:
			a.draw_tics_on_all_channels()

	def _bootstrap_objects(self,ps_obj):
		self.pulse_sequence = ps_obj
		for a in self.anchor_list:
			a._bootstrap_objects(ps_obj)
			if self.post_delay:
				self.post_delay._bootstrap(ps_obj)

	def __str__(self):
		if len(self.anchor_list) > 0:
			out = '[anchor group]\n'

			if self.xcoor:
				disp = self.xcoor
				out = out + 'Display offset: '
				out = out + disp.__str__() + '\n'

			out = out + 'Anchors sequence: '
			for a in self.anchor_list:
				out = out + a.__str__() + ' '
			out = out + '\nTimed anchor: ' + self.timed_anchor.__str__()
			out = out + '\nTiming anchor: ' + self.timing_anchor.__str__()
			out = out + '\n'
		else:
			out = '[pulse sequence start]\n'
		out = out + 'Post delay: ' + self.post_delay.__str__()
		return out + '\n'

class Dimension:
	def __init__(self,name):
		self.name = name
		self.template = None

class Channel:
	def __init__(self,name,type):
		self.type = type
		self.name = name
		self.height_above = None
		self.neight_below = None
		self.ycoor = None
		self.power = None
		self.template = None #todo remove this 
		self.label = None #initialized by _parse_variables
		self._compile_wide_event_status = 'off'
	def prepare_label(self):
		text = self.name
		if self.label != None:
			text = self.label
		im = latex2image(text)
		self.label_image = im
		self.label_width = im.size[0]

	def is_wide_event_on(self):#Channel.is_wide_event_on()
		if self._compile_wide_event_status == 'on':
			return True
		else:
			return False

	def wide_event_on(self):
		if self._compile_wide_event_status == 'on':
			raise CompilationError('new wide event on channel %s while previous one has not finished' % self.name)
		self._compile_wide_event_status = 'on'

	def wide_event_off(self):
		if self._compile_wide_event_status == 'off':
			raise CompilationError('wide event is already off %s when trying to turn it off again' % self.name)
		self._compile_wide_event_status = 'off'

#an object collecting information about pulse sequence elements
#that is applied to several instances of the events
#for example several pulses can share a phase-cycling table
#or several pfg's in the pulse sequence can be identical 
#this class is populated at run time by function PulseSequence._procure_object
#then before pulse sequence is drawn information from template can be copied 
#to the instances as a temporary plug
#or maybe not so temporary ...
class PulseSequenceElementTemplate: #todo upgrade this class must become more influential
	def __init__(self,type,name):
		self._type = type #must match corresponding PulseSequenceElement._type
		self.name = name
		if type == 'pfg' or type == 'pfg_wide':
			self.strength=100

class PulseSequenceElement(E): #this is weird - element inherits from expression type
	"""base class for pulse sequence elements: delays, phases, pulses, etc

	instant events have reference to carrying anchor (except phases)
	wide events have an additional reference to end_anchor

	currently (Feb 14 2009) anchors that are referenced by end_anchor
	do not themseleves point to wide events

	however at compile stage for production of code WideEventToggle elements are
	inserted to anchors at the beginning and the end of wide events
	"""
	def __init__(self):
		self.anchor = None
		self.drawing_width = 0
		self.drawing_pre_width = 0  #pixels before anchor
		self.drawing_post_width = 0 #pixels after anchor
		self.drawing_height = 0
		self.template = None #instance of PulseSequenceElementTemplate
		self.expr = None
		self.name = None
		self.channel = None
		self.edge = 'center' #issue: not needed for phase
		self.pre_span = None  #these aren't needed for phase either - so maybe phase shouldn be PSE
		self.post_span = None
	def __str__(self):
		return self._type

	def get_op(self): #PulseSequenceElement.get_op() plug
		return None

	def get_maxh(self):
		"""get channel drawing height
		"""
		return self.pulse_sequence.channel_drawing_height

	def set_ycoor(self,ycoor):#PulseSequenceElement.set_ycoor()
		self.ycoor = ycoor

	def get_primary_delay_list(self): #PulseSequenceElement.get_primary_delay_list()
		"""dummy function that returns empty list
		only delays should return primary delay components from
		their expressions
		"""
		return []

	def get_varian_expression(self):
		if self.expr == None:
			if self.get_type() in ['rf_pulse','delay'] and self.__dict__.has_key('varian_name'):
				if self.get_type() == 'rf_pulse' and self.type == '180':
					return self.varian_name + '*2' #todo remove temp plug
				return self.varian_name
			elif self.get_type() == 'pfg' and self.__dict__.has_key('varian_grad_span'):
				return self.varian_grad_span
			else:
				return self.name
		else:
			return self.expr.get_varian_expression()

	def reduce(self):
		pass

	def time(self): # PulseSequenceElement.time()
		"""calculate pre_span and post_span expressions

		Limitation: this method can be only called after compile initialization
		it's because wide events are not represented by WideEventToggle events just after
		the user input parsing this needs to be fixed in the future issue of PS object model

		Prerequisites: definition of .pre_gating_delay, .post_gating_delay
		btw: pulse element also has .pre_comp_delay and .post_comp_delay
		time() method is different for Pulse() object, because there is optional compensation delay
		"""
		(pre,post) = (None,None)
		if self.edge not in ('center','left','right'):
			raise 'internal error: unknown value of edge %s in element %s' % (self.edge,self.name)
		if self.edge == 'center':
			pre = E('set',E('div',self,N(2)))
			post = pre
		elif self.edge == 'left':
			pre = E('set',N(0))
			post = E('set',self)
		elif self.edge == 'right':
			pre = E('set',self)
			post = E('set',N(0))
		self.pre_span = E('add',pre,self.pre_gating_delay)
		self.post_span = E('add',post,self.post_gating_delay)

	def set_xcoor(self,xcoor=None):#PulseSequenceElement.set_xcoor()
		if xcoor == None:
			self.xcoor = self.anchor.xcoor
		else:
			self.xcoor = xcoor

	def calc_drawing_dimensions(self):
		"""this function calculates .drawing_pre_width and .drawing_post_width
		based on .edge alignment parameter 
		this function is only meaningful if .drawing_width is set
		"""
		if self.edge == 'center':
			half = int(self.drawing_width/2) #may be issues with pixel imperfect sizing 
			self.drawing_pre_width = half
			self.drawing_post_width = half
			self.drawing_width = half*2
		elif self.edge == 'left':
			self.drawing_pre_width = 0
			self.drawing_post_width = self.drawing_width
		elif self.edge == 'right':
			self.drawing_pre_width = self.drawing_width
			self.drawing_post_width = 0
		else:
			raise 'internal error: unknown value of edge %s in element %s' % (self.edge,self.name)

	def get_eqn_str(self):
		"""returns symbol to be used in the formula to calculate length of element
		"""
		return self.name

	def load_template_data(self):#temporary ? plug
		if self.template != None:
			keys = self.template.__dict__.keys()
			for key in keys:
				val = self.template.__dict__[key]
				self.__dict__[key] = val

	def get_type(self): #PulseSequenceElement.get_type()
		return self._type

	def is_pegged(self):
		if self._type in ('acq','rf_wide_pulse','pfg_wide'):
			return True
		elif self._type == 'delay':
			raise 'is_pegged for delays not implemented'
		return False

	def draw_pegged_pulse(self,draw_obj):
		d = draw_obj

		#calculate coordinates of four points
		#defining the tetrangle

		x1 = self.anchor.xcoor
		y1 = self.ycoor

		x2 = self.anchor.xcoor

		y2 = y1 - self.drawing_height*self.h1/100

		x3 = self.end_anchor.xcoor
		y3 = y1 - self.drawing_height*self.h2/100

		x4 = x3
		y4 = y1

		fg = self.pulse_sequence.fg_color
		bg = self.pulse_sequence.bg_color

		d.line(((x1,y1),(x2,y2)))
		d.line(((x2,y2),(x3,y3)))
		d.line(((x3,y3),(x4,y4)))

		if self.label != None:
			ycoor = int((2*y1+y3+y2)/4)
			yplacement = 'center'
			if self._type == 'pfg_wide':
				ycoor = max(y1,y2,y3) + 3
				yplacement = 'below'
			draw_latex(self.label,self.pulse_sequence,(int((x1+x3)/2),ycoor),yplacement=yplacement)

	def draw_up_arc_pulse(self,draw_obj,order=0.5):
		d = draw_obj
		x = self.edge_calc_x()
		y = self.ycoor
		w = self.drawing_width
		h = self.drawing_height
		bg = self.pulse_sequence.bg_color
		fg = self.pulse_sequence.fg_color


		xval = arange(w)
		yval = multiply(power(sin(multiply(divide(xval,float(w-1)),3.14159265)),order),h)

		xval = add(xval,x-w/2)
		yval = add(-yval,y)

		n = len(xval)
		x1 = xval[0]
		y1 = yval[0]
		for i in arange(n):
			d.line(((x1,y1),(xval[i],yval[i])))
			x1 = xval[i]
			y1 = yval[i]

	def draw_up_shaped_pulse(self,draw_obj):
		self.draw_up_arc_pulse(draw_obj,4)

	def edge_calc_x(self):
		"""calculate x offset according to "edge" anchor alignment setting
		"""
		w = self.drawing_width
		x = self.xcoor
		if self.__dict__.has_key('edge'):
			if self.edge == 'left':
				x = x + w/2	
			elif self.edge == 'right':
				x = x - w/2
		return x
		
	def draw_up_rect_pulse(self,draw_obj):
		d = draw_obj
		y = self.ycoor
		w = self.drawing_width
		h = self.drawing_height

		x = self.edge_calc_x()

		bg = self.pulse_sequence.bg_color
		fg = self.pulse_sequence.fg_color

		if self.type == '90':
			bg = fg

		d.rectangle((x-w/2,y-h,x+w/2,y),fill=bg,outline=fg)

	def draw_fid(self,draw_obj):
		d = draw_obj
		x = self.xcoor
		y = self.ycoor
		#w = self.drawing_width
		w = self.pulse_sequence.acq_drawing_width
		h = self.pulse_sequence.acq_drawing_height
		xval = arange(w)
		yval = multiply(h,multiply(-sin(multiply(xval,0.6)),exp(multiply(-0.05,xval))))
		xval = add(xval,x)
		yval = add(yval,y)
		fg = self.pulse_sequence.fg_color
		bg = self.pulse_sequence.bg_color

		d.line(((x,y),(x+w-1,y)),fill=bg)

		x1 = xval[0]
		y1 = yval[0]

		n = len(xval)
		for i in arange(n):
			d.line(((x1,y1),(xval[i],yval[i])),fill=fg)
			x1 = xval[i]
			y1 = yval[i]

	def _bootstrap(self,ps_obj):
		self.pulse_sequence = ps_obj

class Phase(PulseSequenceElement):
	def __init__(self,name,**kwarg):
		self._type = 'phase'
		self.name = name
		self.label = None
		self.table = None

	def fix_table_into_array(self): #todo remove temp plug
		if self.table != None:
			if type(self.table) == type([]):
				pass
			elif type(self.table) == type(1):
				self.table = [self.table]
			else:
				raise 'internal error unsupported type of phase table'

	def __str__(self):
		str = self.name + ' ' + self.label
		str = str + ' ' + self.table.__str__()
		return str

class Delay(PulseSequenceElement):
	def __init__(self,name,expr=None):
		PulseSequenceElement.__init__(self)
		self._type = 'delay'
		self.type = 'general' #todo remove? plug in better POM
		self.length = None    #length of delay in seconds
		self.name = name
		self.label = None
		self.formula = None
		self.show_at = None #channel at which to draw delay
		self.start_anchor = None
		self.end_anchor = None
		self.expr = expr #delay expression assignment in constructor
		self.label_yoffset = 0
		self.image = None #image object
		self.template = PulseSequenceElementTemplate('delay',name)
		#start_anchor
		#end_anchor assinged in PulseSequence._attach_delays_to_anchors()

	def __str__(self):
		if self.expr:
			expr = ' expression=%s' % self.expr.get_eqn_str()
		else:
			expr = self.name
		#used to print out formula, but so far it's empty anyway
		return '%s label=%s formula=%s' % (self.name,self.label,expr)

	def get_primary_delay_list(self): #Delay.get_primary_delay_list()
		if self.expr == None:
			return [self]
		else:
			return self.expr.get_primary_delay_list()

	def get_eqn_str(self):
		#if delay expression evaluates to None, then this delay is primary parameter
		#and needs to be set externally by the spectroscopist
		if self.expr == None:
			return PulseSequenceElement.get_eqn_str(self)
		else:
			return self.expr.get_eqn_str()

	def get_varian_code(self):
		expr = self.get_varian_expression()
		try:
			if float(expr) == 0:
				return []
		except:
			return ['\tdelay(%s);' % expr]

	def set_xcoor(self,xcoor): #Delay.set_xcoor()
		"""set x coordinate of delay
		"""
		self.xcoor = xcoor

	def calc_drawing_width(self): #Delay.calc_drawing_width()
		"""if delay is hidden, then default width is returned
		otherwise an image is generated from label
		then the resulting value taken directly from the image width
		"""
		if self.is_hidden():
			self.drawing_width = 10 #todo magic number
			return
		if self.label:
			text = self.label
		else:
			text = self.name
		self.image = latex2image(text)
		self.drawing_width = self.image.size[0]

	def draw_bounding_tics(self):#Delay.draw_bounding_tics()
		"""a tic mark will be drawn on a side where anchor has no attached events
		"""
		start = self.start_anchor
		end = self.end_anchor
		start.draw_tic(self.show_at)
		end.draw_tic(self.show_at)

	def draw(self,draw_obj): #Delay.draw()
		"""this routine is really drawing a delay label text, and does nothing if 
		delay is "hidden"
		"""

		if self.is_hidden():
			return

		if self.label:
			text = self.label
		else:
			text = self.name
		self.ycoor = self.pulse_sequence.get_rf_channel_ycoor(self.show_at) \
						- self.pulse_sequence.channel_drawing_height/2 \
						- int(self.label_yoffset)

		image_obj = self.pulse_sequence.get_image_object()
		#delay label xplacement is 'center'
		paste_image(self.image,self.pulse_sequence,(self.xcoor,self.ycoor),'center-clear','center')

		self.draw_bounding_tics()

	def is_hidden(self):
		if self.template.__dict__.has_key('hide'):
			if self.template.hide == False:
				return False
			elif self.template.hide == True:
				return True
			else:
				raise 'internal error. wrong value of Delay.template.hide'
		else:
			return False


class WideEventToggle(PulseSequenceElement):
	"""class for turning on/off wide event
	not used for drawing output, only used for compilation into code

	this type of event does not have channel assigned - maybe 
	get_channel() getter is needed for PulseSequenceElement
	so that channel will be read from the wide event iself?
	"""
	def __init__(self,type='on',event=None):
		PulseSequenceElement.__init__(self)
		self._type = 'wide_event_toggle'
		if type not in ('on','off'):
			raise 'internal error: unknown type %s of WideEventToggle' % type
		self.type = type
		self.event = event
		self.expr = N(0)  #todo remove this plug

	def get_eqn_str(self):
		return self.event.get_eqn_str()

	def set_ycoor(self,ycoor):
		PulseSequenceElement.set_ycoor(self,ycoor)
		self.event.ycoor = ycoor

	def set_xcoor(self,xcoor=None): #WideEventToggle.set_xcoor()
		PulseSequenceElement.set_xcoor(self,xcoor)
		if self.type == 'on':
			self.event.xcoor = self.xcoor

	def get_type(self):#WideEventToggle.get_type()
		return self.event.get_type()

	def calc_drawing_dimensions(self):
		if self.type == 'on':
			self.event.calc_drawing_dimensions()

	def draw(self,draw_obj): #WideEventToggle.draw()
		if self.type == 'on':
			self.event.draw(draw_obj)

class VPulse:
	"""Varian pulse class
	"""
	def __init__(self,pw='0.0',ph='zero',gt1='rof1',gt2='rof2',channel=1):
		self.pw = pw
		self.ph = ph
		self.gt1 = gt1
		self.gt2 = gt2
		self.channel = channel  #hardware channel 1,2,3,4,...
	def render(self):
		if self.channel == 1:
			call = 'rgpulse'
		elif self.channel == 2:
			call = 'decrgpulse'
		elif self.channel == 3:
			call = 'dec2rgpulse'
		return '\t%s(%s,%s,%s,%s);' % (call,self.pw,self.ph,self.gt1,self.gt2)

class VSimPulse:
	"""Class for Varian simultaneous square pulse
	"""
	def __init__(self):
		self.events=[None,None,None] #up to three simultaneous pulses
	def add_event(self,p):
		"""add VPulse object to slot corresponding to the channel
		"""
		if isinstance(p,Pulse):
			vp = p.get_varian_parameters()
		elif isinstance(p,VPulse):
			vp = p
		else:
			raise 'wrong parameters type in VSimPulse.add_event()'
		ch = vp.channel
		self.events[ch-1] = vp

	def render(self):#VSimPulse.render()
		"""print simpulse or sim3pulse statement
		using VSimPulse object
		"""
		if self.events[2] != None:
			call = 'sim3pulse'
			if self.events[1] == None:
				self.add_event(VPulse(channel=2))
			if self.events[0] == None:
				self.add_event(VPulse(channel=1))
		else:
			call = 'simpulse'
			if self.events[0] == None:
				raise CompilationError('no pulse on channel 1 in Varian simpulse')
		if len(self.events) > 3:
			raise CompilationError('more then 3 simultaneous pulses for varian not supported yet')

		events = []
		for e in self.events:
			if e != None:
				events.append(e)

		text = '\t%s(' % call
		for e in events:
			text = text + e.pw + ','
		for e in events:
			text = text + e.ph + ','
		text = '%s%s,%s);' % (text,events[0].gt1,events[0].gt2) #temporary plug
		return text

class Pulse(PulseSequenceElement):
	"""class for RF pulse
	"""
	def __init__(self,type,channel,name=None):
		PulseSequenceElement.__init__(self)
		self._type = 'rf_pulse'
		self.type = type #90,180, shp, rect, lp, etc
		self.name = name
		#extra stuff
		self.length = None 
		self.power = None 
		self.channel = channel
		self.phase = None
		self.label = None
		self.comp = None #compensation delay for 90 degree pulses
		self.edge = 'center' #(left|right|center) - "edge" of pulse to be anchored

	def __str__(self):
		out = self.type
		if self.phase:
			out = out + ' phase ' + self.phase.__str__()
		return out

	def time(self): #Pulse.time()
		PulseSequenceElement.time(self)
		if self.comp == None:
			return
		span = None
		if self.comp == 'before':
			span = self.pre_span
		elif self.comp == 'after':
			span = self.post_span
		#perform surgery on extracted span
		ops = span.get_operands()
		# using ops[1] careful here index must be correct - see PulseSequenceElement.time() method
		#todo: should I check that this is a 90 pulse?
		comp = E('div',E('mul',self,N(2)),N('pi'))
		ops[1] = E('max',ops[1],Delay('comp_delay',expr=comp)) #delay expression assignment

	def calc_drawing_dimensions(self):
		#width_table = {'90':14,'180':22,'shp':42,'lp':14,'rect':14}
		width_table = {'90':9,'180':13,'shp':28,'lp':10,'rect':10}
		maxh = self.get_maxh()
		keys = width_table.keys()
		if self.type in keys:
			self.drawing_width = width_table[self.type]
		else:
			raise ParsingError('Unexpected pulse type %s, must be one of %s' \
							% (self.type,','.join(keys)))
		if self.type == 'lp':
			self.drawing_height = 0.2*maxh
		else:
			self.drawing_height = maxh
		PulseSequenceElement.calc_drawing_dimensions(self)

	def get_varian_parameters(self):# Pulse.get_varian_parameters()
		pw = self.varian_name
		if self.phase != None:
			ph = self.phase.varian_name	
		else:
			ph = 'zero'
		rof1 = self.pre_gating_delay.get_varian_expression()
		rof2 = self.post_gating_delay.get_varian_expression()

		ps = self.pulse_sequence
		ch = ps.get_channel(self.channel).hardware

		#todo remove temporary plug
		#power for pulses muset be more global parameter, like phase
		#now power is either 'high', or 'set' - bespoke for each pulse

		vpulse = VPulse(pw=pw,ph=ph,gt1=rof1,gt2=rof2,channel=ch)
		if self.type == '180':
			vpulse.pw = vpulse.pw + '*2' #todo remove temp plug, should use expr p180=2*p
		return vpulse

	def get_power_level(self):
		power = 'set'
		if self.type in ['180','90']:
			power = 'high'
		return power

	def draw(self,draw_obj):#Pulse.draw()
		if self.type in ('90','180','lp','rect'):
			PulseSequenceElement.draw_up_rect_pulse(self,draw_obj)
		elif self.type == 'shp':
			PulseSequenceElement.draw_up_shaped_pulse(self,draw_obj)

		xcoor = self.edge_calc_x()

		if self.label != None:
			coor = (xcoor,self.ycoor - self.drawing_height - 3) #todo: fix magic number drawing offset
			draw_latex(self.label,self.pulse_sequence,coor,yplacement='above')
			
		if self.phase != None:
			if type(self.phase) == type('string'):
				text = self.phase
			elif type(self.phase) == type(Phase('crap')):
				if self.phase.label != None:
					text = self.phase.label
				else:
					text = self.phase.name
			else:
				raise 'internal error unknown type of phase object'

			seq = self.pulse_sequence
			coor = (xcoor,self.ycoor - self.drawing_height - 3)
			draw_latex(text,seq,coor,yplacement='above')
			

class WidePulse(Pulse):
	def __init__(self,type,channel,**kwarg):
		Pulse.__init__(self,type,channel,**kwarg)
		self._type = 'rf_wide_pulse'
		self.end_anchor = None
		self.label = None
		self.h1 = 100 #default 100% start height
		self.h2 = 100 #default 100% end height
		self.maxh = None

	def get_eqn_str(self):
		return 'cpd_toggle'

	def calc_drawing_dimensions(self):
		#this needs to be redone, b/c width now goes by delay widths
		#self.drawing_width = self.end_anchor.xcoor - self.anchor.xcoor
		maxh = self.get_maxh()
		if self.type in ('fid','echo'):
			self.drawing_height = 0.7*maxh #magic number
		elif self.type in ('cpd','wp'):
			self.drawing_height = maxh
			if self.h1 != None:
				height = self.h1
				if self.h2 != None:
					if self.h1 < self.h2:
						height = self.h2
				else:
					self.h2 = self.h1
			else:
				self.h1 = 50
				self.h2 = 50
		else:
			raise 'unsupported type %s of wide pulse' % self.type

	def draw(self,draw_obj):
		PulseSequenceElement.draw_pegged_pulse(self,draw_obj)

class Acquisition(WidePulse):
	def __init__(self,channel,name=None):
		type = 'acq'
		WidePulse.__init__(self,type,channel,name=None)
		self._type = 'acq'
		self.type = 'fid' 
		self.end_anchor = None
		#display type: 'fid' or 'echo'

	def get_eqn_str(self):
		return 'rcvr_toggle'

	def draw(self,draw_obj):
		if self.type == 'fid':
			PulseSequenceElement.draw_fid(self,draw_obj)
		elif self.type == 'echo':
			PulseSequenceElement.draw_echo_fid(self,draw_obj)

class GradPulse(PulseSequenceElement):
	def __init__(self,name,channel):
		PulseSequenceElement.__init__(self)
		self._type = 'pfg'
		self.type = 'shaped'#shaped or rectangular
		self.alternated = False
		self.name = name
		self.label = None
		self.channel = channel
		self.length = None
		self.strength = 100
		self.drawing_height = None
		self._maxh = 0
	def __str__(self):
		return 'pfg %s %s %s %s' % (self.channel,self.name,self.length,self.strength)
	def calc_drawing_dimensions(self):
		self.drawing_width = 12  #was 32 magic number
		PulseSequenceElement.calc_drawing_dimensions(self)
		maxh = self.get_maxh()
		#magic number below
		maxh = maxh*0.95 #gradient pulse must be shorter so that negative and positive fit
		self._maxh = maxh #for later use

		max_strength = 0
		if self.alternated == True:
			self.drawing_height = []
			self.drawing_height.append(maxh*self.strength[0]/100)
			self.drawing_height.append(maxh*self.strength[1]/100)
		else:
			self.drawing_height = maxh*self.strength/100

	def bottom_ycoor(self):
		m = 0
		if self.alternated == True:
			m = min(self.drawing_height)
		else:
			m = self.drawing_height

		if m < 0:
			return abs(m) + self.ycoor
		else:
			return self.ycoor

	def draw(self,psdraw):
		if self.type == 'shaped':
			if not self.alternated:
				PulseSequenceElement.draw_up_arc_pulse(self,psdraw)
			else:
				#strange hackery about drawing_height of pfg pulses
				dh = self.drawing_height
				self.drawing_height = self.strength[0]*self._maxh/100
				PulseSequenceElement.draw_up_arc_pulse(self,psdraw)
				self.drawing_height = self.strength[1]*self._maxh/100
				PulseSequenceElement.draw_up_arc_pulse(self,psdraw)
				self.drawing_height = dh
		elif self.type == 'rectangular':
			if not self.alternated:
				PulseSequenceElement.draw_up_rect_pulse(self,psdraw)
			else:
				dh = self.drawing_height
				self.drawing_height = self.strength[0]*self._maxh/100
				PulseSequenceElement.draw_up_rect_pulse(self,psdraw)
				self.drawing_height = self.strength[1]*self._maxh/100
				PulseSequenceElement.draw_up_rect_pulse(self,psdraw)
				self.drawing_height = dh

		y = self.bottom_ycoor()

		xcoor = self.edge_calc_x()

		text = self.name
		if self.label != None:
			text = self.label
		draw_latex(text,self.pulse_sequence,(xcoor,int(y + 3)),yplacement='below')

class WideGradPulse(GradPulse):
	def __init__(self,name,channel):
		GradPulse.__init__(self,name,channel)
		self._type = 'pfg_wide'
		self.end_anchor = None
		self.template = None
		self.h1 = None
		self.h2 = None
		self.drawing_width = 0
	def calc_drawing_dimensions(self):
		self.h1 = self.strength 
		self.h2 = self.strength 
		maxh = self.get_maxh()
		self.drawing_height = maxh
		
	def draw(self,psdraw):
		if not self.alternated:
			PulseSequenceElement.draw_pegged_pulse(self,psdraw)

class PulseSequence:
	"""Toplevel pulse sequence object
	"""
	def __init__(self):
		"""among other things initializes head anchor group
		but does not create first delay

		most global drawing parameters entered here
		"""
		self._object_type_list = ('pfg','pfg_wide','rf_pulse','rf_wide_pulse',
								'acq','phase')
		for ot in self._object_type_list:
			self.__dict__[ot + '_table'] = {} #???is this duplication of below code?

		self._rf_channel_table = {}
		self._pfg_channel_table = {}
		self._dim_table = {} #table to contain information about indirect dimensions (maybe all?)
		self._dim_order = [] 
		self._delay_list = [] 
		self._decoration_list = []
		self._draft_image_no = 0

		head_group = AnchorGroup()#special start anchor group with null name and offset
		a = Anchor(None) #special unnamed anchor
		head_group.timed_anchor = a      #anchor with interval before
		head_group.timing_anchor = a     #anchor with interval after
		head_group.anchor_list.append(a)
		head_group.xcoor = 0
		self._glist = [head_group]

		#some constant drawing parameters
		self.channel_drawing_height = 35 
		self.acq_drawing_width = 70
		self.acq_drawing_height = 35
		self.margin_above = 40
		self.margin_below = 20
		self.margin_right = 20
		self.margin_left = 20
		self.event_tic_size = 4
		self.blank_tic_size = 3
		self.delay_margin_sides = 3
		self._bottom_drawing_limit =self.margin_above
		self.image_mode = 'L'
		self.fg_color = 0
		self.bg_color = 256

	def time(self): #PulseSequence.time()
		for g in self._glist:
			g.time() #and calc relative element drawing offsets
		#calculate minimal necessary delay drawing widths
		for d in self._delay_list:
			d.calc_drawing_width()#no need to give height here

		#separately set acq delay width to default value
		self.set_acq_delay_drawing_widths()

		glist = iter(self._glist)
		cg = glist.next()
		xcoor = 0
		for g in glist:
			cg.set_xcoor(xcoor) #set xcoor of all elements within group solid
			cdelay = cg.post_delay

			#drawing_pre_width and post_width at channel where delay is to be drawn
			g_d_pre_w = g.get_drawing_pre_width(cdelay) + self.delay_margin_sides
			cg_d_post_w = cg.get_drawing_post_width(cdelay) + self.delay_margin_sides
			cg_d_end_xcoor = cg.xcoor + cg_d_post_w

			d_w = cdelay.drawing_width

			#try new g_xcoor as if cg and g were touching - across channels this time
			g_xcoor = cg.xcoor + cg.drawing_post_width + g.drawing_pre_width

			#calc xcoor for g so that delay label fits on channel "show_at"
			#and anchor groups don't overlap
			if cg_d_end_xcoor > g_xcoor - g_d_pre_w - d_w:
				#cdelay label doesn't fit, so move g.xcoor forward so that delay fits
				xcoor = cg_d_end_xcoor + d_w + g_d_pre_w
			else:
				#turns out delay fits this way, accept initial guess
				xcoor = g_xcoor

			cdelay.set_xcoor((cg_d_end_xcoor + xcoor - g_d_pre_w)/2)
			cg = g

		g.set_xcoor(xcoor)

		#now we can calculate widths of wide events (those attached to two anchors)
		#for g in self._glist:
		#	al = g.anchor_list
		#	for a in al:
		#		for e in a.events:
		#			if type(e) == type(WideEventToggle()):
		#				e.set_xcoor(a.xcoor)

	def get_all_events(self):#PulseSequence.get_all_events()
		"""temporary function need to fix main event getter
		get_events() and make it more flexible (jquery style?)	
		this function uses objects quite inappropriately
		"""
		events = []
		for g in self._glist:
			for a in g.anchor_list:
				for e in a.events:
					if e._type == 'wide_event_toggle': #bad style, access private property!!
						if e.type == 'on':
							events.append(e.event)
					else:
						events.append(e)
		return events

	def get_phase_tables(self):
		events = self.get_all_events()  #bug re-using crappy function
		phases = []
		for e in events:
			if e._type == 'rf_pulse' or e._type == 'acq': #bad access private property
				if e.phase != None:
					phases.append(e.phase)
		return phases

	def get_wide_rf_pulses(self):
		return self.get_elements('rf_wide_pulse')

	def get_pulses(self):
		return self.get_elements('rf_pulse')

	def get_phase(self,name):
		phases = self.get_phase_tables()
		for ph in phases:
			if ph.name == name:
				return ph
		return None

	def get_delays(self,d_name=None):
		delay_list = []
		for g in self._glist:
			if d_name != None:
				if g.post_delay != None and g.post_delay.name == d_name:
					delay_list.append(g.post_delay)
			else:
				if g.post_delay != None:
					delay_list.append(g.post_delay)

		if d_name != None:
			if len(delay_list) == 0:
				raise 'no delays named %s found in the pulse sequence' % d_name
		return delay_list

	def get_gradients(self):
		return self.get_elements('pfg')

	def get_elements(self,type):
		events = self.get_all_events()
		elements = []
		for e in events:
			if e._type == type:
				elements.append(e)
		return elements
		
	def set_acq_delay_drawing_widths(self):
		#get list of acq events
		events = self.get_all_events()
		acq = []
		for e in events:
			if e._type == 'acq': #accessing private class member
				acq.append(e)

		#for each event find delay that corresponds to event
		#and set it's drawing_width
		for e in acq:
			start = e.anchor
			end = e.end_anchor
			for d in self._delay_list:
				if d.start_anchor == start and d.end_anchor == end:
					d.drawing_width = self.acq_drawing_width

	def get_events(self,channel=None): #PulseSequence.get_events()
		events = []
		channel = self.get_channel_key(channel)
		for g in self._glist:
			g_events = g.get_events(channel)
			events.extend(g_events)
		return events

	def add_delay(self,dly):
		self._delay_list.append(dly)

	def get_channel_key(self,channel=None):
		"""performs check of channel key returns what's on input
		or first rf channel if channel == Null
		"""
		rf_ct = self._rf_channel_table
		pfg_ct = self._pfg_channel_table

		if channel==None:
			return self._rf_channel_order[0]
		
		rf = rf_ct.has_key(channel)
		pfg = pfg_ct.has_key(channel)
		if rf and pfg:
			#this error check should probably go to parsing stage
			#and there better be one single channel table
			raise ParsingError('rf and pfg channels use the same name %s' % channel)
		elif rf or pfg:
			return channel
		else:
			raise 'internal error: channel %s not found in channel tables' % channel

	def get_rf_channel(self,name):
	#todo here is a catch - only rf channels are returned
		ct = self._rf_channel_table
		if ct.has_key(name):
			return ct[name]
		else:
			raise ParsingError("There is no rf channel '%s'" % name)

	def get_pfg_channel(self,name): #need to be merged into one get_channel
	#todo here is a catch - only rf channels are returned
		ct = self._pfg_channel_table
		if ct.has_key(name):
			return ct[name]
		else:
			raise ParsingError("There is no pfg channel '%s'" % name)

	def get_channel(self,name):
		"""return channel data by name
		will raise error if channel is not found
		"""
		try:
			ch = self.get_rf_channel(name)
		except:
			try:
				ch = self.get_pfg_channel(name)
			except:
				raise ParsingError("channel %s not found in rf & pfg channel lists" % name)
		return ch

	def is_wide_event_on(self):
		for ch in self._rf_channel_table.values() + self._pfg_channel_table.values():
			if ch.is_wide_event_on():
				return True
		return False

	def get_channel_list(self):
		"""return unordred list of names of all channels
		"""
		rft = self._rf_channel_table
		pft = self._pfg_channel_table
		names = {}
		for key in rft.keys() + pft.keys():
			if names.has_key(key):
				raise ParsingError("Duplicate channel %s. Please use unique names for channels" % key)
			names[key] = 1
		return names.keys()

	def get_rf_channels(self):
		return self._rf_channel_table.values()

	def get_draw_object(self):
		return self._draw_object

	def get_rf_channel_ycoor(self,channel):
		ct = self._rf_channel_table
		if channel in ct.keys():
			return ct[channel].ycoor
		else:
			raise ParsingError('%s no such rf channel' % channel)

	def get_acquisitions(self):
		acq_list = []
		for g in self._glist:
			for a in g.anchor_list:
				for e in a.events:
					if e.get_type() == 'acq':
						acq_list.append(e)
		return acq_list

	def get_named_pulse_table1(self):
		return self.rf_pulse_table

	def get_named_pulse_table(self):
		table = {}
		for g in self._glist:
			for a in g.anchor_list:
				for e in a.events:
					if e.get_type() == 'rf_pulse' and e.name != None:
						table[e.name] = e
		return table
						

	def get_anchor(self,a_name):
		for g in self._glist:
			try: 
				a = g.get_anchor(a_name)
				return a
			except:
				pass
		raise 'anchor %s not found' % a_name

	def get_image_object(self):
		return self._image

	def save_draft_image(self):
		n = self._draft_image_no
		self._image.save('draft%d.png' % n)
		self._draft_image_no = n + 1

	def create_anchor_group(self,a_names = []):
		"""creates new anchor group, populates it 
		with anchors named as in a_names array
		returns newly created anchor group
		"""
		g = AnchorGroup()
		self._glist.append(g)
		for a_name in a_names:
			a = Anchor(a_name)
			a.group = g
			g.anchor_list.append(a)
		return g

	def get_anchor_groups(self):
		"""returns list of anchor groups
		"""
		return self._glist;

	def _procure_object(self,type,*arg,**kwarg):
	#unnamed objects won't be stored in tables

		if not type in self._object_type_list:
			raise '_procure_object for type %s not implemented' % type

		class_map = {'rf_pulse':Pulse,'rf_wide_pulse':WidePulse,
						'acq':Acquisition,'pfg':GradPulse,'pfg_wide':WideGradPulse,'phase':Phase}

		obj_class = class_map[type]

		table_name = type + '_template_table'
		if not self.__dict__.has_key(table_name):
			self.__dict__[table_name] = {}
		template_table = self.__dict__[table_name]

		#get object table
		table = self.__dict__[type + '_table']
		#get object key
		obj_key = None
		if type in ('rf_pulse','acq','rf_wide_pulse'):
			if kwarg.has_key('name'):
				obj_key = kwarg['name']
		elif type in ('pfg','phase','pfg_wide'):
			if len(arg) > 0:
				obj_key = arg[0]

		#create a new object
		try:
			obj = obj_class(*arg,**kwarg)
		except:
			err = 'could not create object of type %s\n' % type
			err = err + 'argument list: ' + arg.__str__() + '\n'
			err = err + 'argument table: ' + kwarg.__str__()
			raise err

		#obj_key is name of new object
		if obj_key:
			template = None
			if template_table.has_key(obj_key):
				template = template_table[obj_key]
			else:
				template = PulseSequenceElementTemplate(type,obj_key)
				template_table[obj_key] = template

			obj.template = template

		table[obj_key] = obj
		return obj

	def _validate_anchor_order(self,code):
		#todo get this done before release
		pass

	def _parse_time(self):
		"""parses code of "time" line

		builds list of delays, to anchor groups assigns: post-delay, 
		timed and timing anchors

		validation: anchor order, start with delay, end with anchor, anchors
		and delays must alternate, delays and anchors subject to pattern matching
		"""
		#first lex the time line
		#sequence must start with delay and end with anchor
		code = self._code['time'].code
		group_list = self._glist

		self._validate_anchor_order(code)

		t = label_regex_token
		anchor_re = re.compile(r'^@(%s)((,|-+)(%s))?$' % (t,t))
		delay_re = re.compile(r'^%s$' % t)

		bits = code.split()
		if anchor_re.match(bits[0]):
			raise ParsingError('first item in the time line must be delay, %s found' % bits[0])
		if not anchor_re.match(bits[-1]):
			raise ParsingError('last item in the time line must be anchor, %s found' % bits[0])

		items = []
		#prev item name and type
		pname = 'OriginAnchor'
		ptype = 'anchor' #thats the implied zero time anchor
		#group bits into anchors and delays
		#delays and anchors must alternate
		for bit in bits:
			am = anchor_re.match(bit)
			dm = delay_re.match(bit)
			if am:
				a1_name = am.group(1)
				a2_name = am.group(4)
				if ptype == 'anchor':
					raise ParsingError('two anchors %s and %s found in a row. '\
										% (pname,bit) \
										+'Anchors and delays must alternate.')
				item = None
				if a2_name:
					item = {'type':'double-anchor','name':a1_name,'name2':a2_name}
				else:
					item = {'type':'anchor','name':a1_name}

				items.append(item)
				ptype = 'anchor'
			elif dm:
				if ptype == 'delay':
					raise ParsingError('two delays %s and %s found in a row. '\
									% (pname,bit) \
								+'Delays must alternate with anchors.')
				items.append({'type':'delay','name':bit})
				ptype = 'delay'
			else:
				raise ParsingError('did not recognize entry %s either delay symbol ' % bit \
									+ 'or two-anchor group expected: e.g. @a,b')
			pname = bit
			
		c_group = group_list[0]
		for item in items:
			if item['type'] == 'delay':
				d = Delay(item['name'])
				self._delay_list.append(d)
				c_group.post_delay = d 
			elif item['type'] in ('anchor','double-anchor'):
				a1_name = item['name']
				a2_name = None
				if item['type'] == 'double-anchor':
					a2_name = item['name2']
				c_group = self.get_anchor(a1_name).group
				c_group.set_timed_anchor(a1_name)
				if a2_name:
					c_group.set_timing_anchor(a2_name)
				else:
					c_group.set_timing_anchor(a1_name)

	def _parse_anchor_groups(self):
		"""parses text of "anchors" line
		creates list of anchor groups which themselves contain 
		list of their anchors
		"""
		code = self._code['anchors'].code

		tokens = (label_regex_token,label_regex_token)
		anchor_group_re = re.compile(r'^@%s(:?(:?,|-+)%s)*$' % tokens)

		new_anchor_group_re = re.compile(r'^@(%s)(:?\[([1-9]\d*)\])$' % anchor_basename_token );
		# @a--b,c5,sdfg345
		# @a,@b1-5,@7
		# @g1-7

		at_re = re.compile(r'^@')
		dash_re = re.compile(r'-+')

		group_list = self._glist

		bits = code.split()
		for bit in bits:
			orig = bit
			m = anchor_group_re.match(bit)
			mn = new_anchor_group_re.match(bit)
			a_names = []
			if mn:
				a_base_name = mn.group(1)
				a_anchor_count = int(mn.group(3))
				for i in xrange(1,a_anchor_count+1):
					a_name = '%s%d' % (a_base_name,i)
					a_names.append(a_name)
			elif m:
				bit = at_re.sub('',bit)
				bit = dash_re.sub(',',bit)
				a_names = bit.split(',')

			else:
				raise ParsingError('could not parse anchor group ' \
						'definition %s' % bit)

			self.create_anchor_group(a_names)

	def _parse_pfg(self):
		code_table = self._code['pfg'].table
		self._pfg_channel_order = self._code['pfg'].item_order
		t = label_regex_token
		pfg_re = re.compile(r'^(%s)@(%s)((,|-+)(%s))?$' % (t,t,t))

		for ch in code_table.keys():
			
			self._pfg_channel_table[ch] = Channel(ch,'pfg')

			code = code_table[ch]
			self._validate_anchor_order(code)

			bits = code.split()
			for bit in bits:
				m = pfg_re.match(bit)
				if m:
					pfg_name = m.group(1)
					a1_name = m.group(2)
					a2_name = m.group(4)
					a1 = self.get_anchor(a1_name)

					pfg_event = None 
					if a2_name:
						a2 = self.get_anchor(a2_name)
						pfg_event = self._procure_object('pfg_wide',pfg_name,ch)
						pfg_event.end_anchor = a2
					else:
						pfg_event = self._procure_object('pfg',pfg_name,ch)
					pfg_event.anchor = a1
					a1.add_event(pfg_event) #need to check whether end anchor has compatible event
				else:
					raise ParsingError('misformed pfg statement %s' % bit)

	def _parse_dim(self):
		code_table = self._code['dim'].table
		self._dim_order = self._code['dim'].item_order
		for dim_name in code_table.keys():
			self._dim_table[dim_name] = Dimension(dim_name)

	def _parse_rf(self):
		"""parses the main part of pulse sequence record: channel events
		"""
		code_table = self._code['rf'].table
		self._rf_channel_order = self._code['rf'].item_order

		t = label_regex_token
		pulse_re = re.compile(r'^(shp|90|180|lp|rect)@(%s)(=(%s))?$' \
								% (t,t))
		w_rf_event_re = re.compile(r'^(acq|cpd|wp)@(%s)((,|-+)(%s))(=(%s))?$' \
								% (t,t,t))

		for ch in code_table.keys():

			self._rf_channel_table[ch] = Channel(ch,'rf')

			code = code_table[ch]
			self._validate_anchor_order(code)

			bits = code.split()

			for bit in bits:
				pm = pulse_re.match(bit)
				wm = w_rf_event_re.match(bit)
				if pm:
					pulse_type = pm.group(1)
					a_name = pm.group(2)
					pulse_name = pm.group(4)
					if not pulse_name:
						pulse_name = pulse_type
					p = self._procure_object('rf_pulse',pulse_type,ch,name=pulse_name)
					a = self.get_anchor(a_name)
					a.add_event(p)

				elif wm:
					event_type = wm.group(1)
					start_a_name = wm.group(2)
					end_a_name = wm.group(5)
					event_name = wm.group(7)

					#here is where type of event should be
					#distinguished depending on what comes before @
					if event_type == 'acq':
						event = self._procure_object('acq',ch,name=event_name)
					else:
						event = self._procure_object('rf_wide_pulse',
										event_type,ch,
										name=event_name)
					sa = self.get_anchor(start_a_name)
					ea =  self.get_anchor(end_a_name)
					sa.add_event(event)
					ea.add_event(event)
				else:
					raise ParsingError('misformed pulse statement %s in rf channel \'%s\'' \
										% (bit,ch))

	def _get_anchored_object_list(self,type,name):
		type_map = {'pulses':('rf_pulse'),
					'acq':('acq'),
					'gradients':('pfg','pfg_wide'),
					'cpd':('rf_wide_pulse'),
					'phases':('phase')}

		o_list = []
		for g in self._glist:
			for a in g.anchor_list:
				for e in a.events:
					if e._type in type_map[type] and e.name == name:
						o_list.append(e)
		if len(o_list) == 0:
			raise ParsingError('no %s named %s found in the pulse sequence' % (type,name))
		return o_list

	def _get_objects(self,type,name):
		if type == 'delays':
			return self.get_delays(name)
		elif type in ('pulses','acq','gradients','cpd'):
			return self._get_anchored_object_list(type,name)
		elif type == 'phases':
			return [self.phase_table[name]]
		elif type == 'rfchan':
			return [self._rf_channel_table[name]]
		elif type == 'pfgchan':
			return [self._pfg_channel_table[name]]
		elif type == 'dim':
			return [self._dim_table[name]]
		else:
			raise '_get_objects not implemented for type %s' % type

	def _typecast_value(self,val_input,val_type):
		"""reads string representation of value
		and converts it to value of prescribed type
		todo: incorporate input validation here
		
		allowed types are int,float,bool and &lt;type&gt;-list, where &lt;type&gt;
		is one of the supported base types
		in case it is &lt;type&gt;-list list of values is returned when it's
		really a list, and first value when list has only one item
		"""
		if val_type == 'int':
			return int(val_input)
		elif val_type == 'float':
			return float(val_input)
		elif val_type == 'str':
			return val_input
		elif val_type == 'bool':
			true_re = re.compile(r'^true$',re.IGNORECASE)
			false_re = re.compile(r'^false$',re.IGNORECASE)
			if true_re.match(val_input):
				return True
			if false_re.match(val_input):
				return False
			else:
				raise ParsingError('cannot parse boolean value from %s' % val_input)
		elif val_type == 'function':
			func_re = re.compile(r'^(%s)\(([^)]+)\)\s*$' % label_regex_token)
			m = func_re.match(val_input)
			if m:
				func_name = m.group(1)
				func_var_input = m.group(2)
				#parse function variables
				vars = func_var_input.split(',')
				named_var_re = re.compile(r'^([^:]+):([^:]+)$')
				colon_re = re.compile(r':')
				var_compiled = []
				for var in vars:
					var = var.strip()
					m = named_var_re.match(var)
					if m:
						var_type = 'named'
						var_name = m.group(1)
						var_value = m.group(2)
					else:
						if colon_re.match(var):
							raise ParsingError('only one colon allowed in %s variable \
							definition of function %s' % (var,func_name))
						var_type = 'positional'
						var_value = var
						var_name = None
					var_compiled.append({'type':var_type,'name':var_name,'value':var_value})
				return FunctionVar(func_name,var_compiled)
			else:
				raise ParsingError('cannot parse function style value %s' % val_input)
				
		elif isinstance(val_type,str):
			list_re = re.compile(r'^(.*?)-list$')
			m = list_re.match(val_type)
			if (m):
				val_type = m.group(1)
				val_list = val_input.split(',')
				typecasted_val_list = []
				for v in val_list:
					typecasted_val = self._typecast_value(v,val_type)
					typecasted_val_list.append(typecasted_val)
				if len(typecasted_val_list) == 1:
					return typecasted_val_list[0]
				else:
					return typecasted_val_list
			else:
				raise 'internal error: unknown parameter type %s' % val_type
		elif isinstance(val_type,dict):
			specs = val_type #specs given in a table
			val_type = specs['type'] #type of value for parameter
			val_values = specs['values'] #allowed values
			val_value = self._typecast_value(val_input,val_type)
			tmp_val_list = None
			if not isinstance(val_value,list):
				tmp_val_list = [val_value]
			else:
				tmp_val_list = val_value
			for v in tmp_val_list:
				if v not in val_values:
					raise ParsingError('value %s is not allowed; use one of %s' %
						(v,','.join(val_values)))
			return val_value


	def _parse_variables(self,type,key_table,key_aliases={}):

		for key in key_aliases.keys():
			if key not in key_table.keys():
				raise 'internal error: aliases and keys dont agree for type %s' % type

		table = self._code[type].table
		for obj_name in table.keys():
			code = table[obj_name]
			par = parse_param(code) #parse parameters given in the variable line
			obj_list = self._get_objects(type,obj_name)
			for obj in obj_list:
				#todo problem: channels don't need template, but who cares....(for now)
				#dimensions don't have templates either
				if obj.template == None:
					obj.template = PulseSequenceElementTemplate(type,obj_name)

				for key in par.keys():
					var_type = ''
					var_input = par[key]
					if key not in key_table.keys():
						for try_key,try_values in key_aliases.items():
							if key in try_values:
								key = try_key
								break
						if key not in key_table.keys():
							raise ParsingError('key \'%s\' not allowed for %s' % (key,type))
					var_type = key_table[key]
					var_value = self._typecast_value(var_input,var_type) #recognize types of values
					obj.__dict__[key] = var_value 
					obj.template.__dict__[key] = var_value 

	def _parse_gradient_values(self):
		pfg = self.pfg_table.values()
		wpfg = self.pfg_wide_table.values()
		for p in pfg + wpfg:
			val = p.template.strength
			try:
				iter(val)
				p.alternated = True
			except:
				pass

			max_val = 0
			if p.alternated:
				if abs(p.template.strength[0]) > abs(p.template.strength[1]):
					max_val = abs(p.template.strength[0])
				else:
					max_val = abs(p.template.strength[1])
			else:
				max_val = abs(p.template.strength)
			if max_val > 100:
				raise ParsingError('absolute value of gradient %s exceeds 100' % p.name)

	def _parse_decorations(self):
		dl = self._code['decorations'].list
		for d in dl:
			type = d['type']
			code = d['code']
			self._decoration_list.append(Decoration(type,code))

	def _init_phases(self):
		phase_names = self._code['phases'].table.keys()
		for name in phase_names:
			self._procure_object('phase',name)

	def _attach_phases_to_pulses(self):
		pulse_table = self.get_named_pulse_table1()
		acq_table = self.acq_table

		#iterate over pulses and acquisitions - all items with phase
		for p in pulse_table.values() + acq_table.values() :
			if p.phase != None:
				phases = self._get_objects('phases',p.phase)
				if len(phases) == 1:
					p.template.phase = phases[0]
					p.template.phase.fix_table_into_array()#todo remove temp plug
				elif len(phases) > 1:
					raise 'internal error: too many phase objects named %s' % p.phase

	def _parse_code(self):
		"""main hand-typed code parsing funtion
		calls multiple specialized parsing routines
		"""
		#first parse anchor input
		#keys ['disp' , 'phases', 'pfg', 'delays', 'acq', 'rf', 'pulses', 'decorations', 'time']

		self._parse_anchor_groups() #create list of anchor groups '_glist' & anchors 
		self._parse_time() #populate _delay_list, set timed and timing delays to anchor groups
		self._parse_rf()
		self._parse_pfg()
		self._parse_dim()

		delay_parameters = { 'length':'float', 'label':'str', 'formula':'str',
					'show_at':'str', 'hide':'bool', 'label_yoffset':'int'}
		delay_aliases = {'length':['t']}
		self._parse_variables('delays',delay_parameters,delay_aliases)

		self._parse_variables('pulses',{'phase':'str',
						'quad':'str',
						'arrow':'str',
						'label':'str',
						'length':'float',
						'edge':{'type':'str','values':['center','left','right']},
						'comp':{'type':'str','values':['before','after']} #compensation delay 2*pw/pi
						})

		self._parse_variables('acq',{'phase':'str',
						'type':'str'})

		self._parse_variables('gradients',{'length':'float',
						'strength':'float-list',
						'type':'str',
						'edge':{'type':'str','values':['center','left','right']},
						'label':'str'})
		self._parse_gradient_values()#for echo-antiecho type gradients 
									 #(comma separated strength values)
									 #convert string values to numerical values

		self._parse_variables('cpd',{'label':'str',
						'h1':'float',
						'h2':'float'})

		self._init_phases()
		self._parse_variables('phases',{'label':'str',
						'table':'int-list'})

		#todo remove temp plug (fixing phase arrays)
		self._attach_phases_to_pulses() #and fix phase arrays

		self._parse_variables('rfchan',{'label':'str',
						'nucleus':{'type':'str','values':['C','N','H','P','F']},
						'hardware':'int'
						})
		self._parse_variables('pfgchan',{'label':'str'})

		self._parse_variables('dim',{'sampling':'function','quad':'function'})
		
		self._parse_decorations()#decorations are contained in DecorLineList object

		self._assign_delays_to_channels()#decide at what channel draw delay symbols
		self._attach_delays_to_anchors()#each delay now gets start_anchor and end_anchor

		self._hide_acq_delays()
		self._copy_template_data_to_objects()#this is a temp plug has to be done before grads

	def _hide_acq_delays(self):
		acq_list = self.get_acquisitions()
		for acq in acq_list:
			delays = self.get_delays()
			for d in delays:
				if d.start_anchor == acq.anchor and d.end_anchor == acq.end_anchor:
					d.template.hide = True
					d.type = 'acq' #mark as acquisition delay


	def _read_code(self):
		#unique name lines
		anchors = CodeLine(r'^\s*anchors\s*:(.*)$')
		disp = CodeLine(r'^\s*disp\s*:(.*)$')
		time = CodeLine(r'^\s*time\s*:(.*)$')

		#tables of lines with parametrized name 
		acq = CodeLineTable(r'^\s*acq\s*(%s)?:(.*)$' % label_regex_token)
		rf = CodeLineTable(r'^\s*rf\s+(%s)\s*:(.*)$' % label_regex_token)
		pfg = CodeLineTable(r'^\s*pfg\s+(x|y|z)\s*:(.*)$')
		pulses = CodeLineTable(r'^\s*pulse\s+(%s)\s*:(.*)$' % label_regex_token)
		gradients = CodeLineTable(r'^\s*gradient\s+(%s)\s*:(.*)$' % label_regex_token)
		delays = CodeLineTable(r'^\s*delay\s+(%s)\s*:(.*)$' % label_regex_token)
		phases = CodeLineTable(r'^\s*phase\s+(%s)\s*:(.*)$' % label_regex_token)
		cpd = CodeLineTable(r'^\s*(?:wp|cpd)\s+(%s)\s*:(.*)$' % label_regex_token)
		rfchan = CodeLineTable(r'^\s*rfchan\s+(%s)\s*:(.*)$' % label_regex_token)
		pfgchan = CodeLineTable(r'^\s*pfgchan\s+(%s)\s*:(.*)$' % label_regex_token)
		dimensions = CodeLineTable(r'^\s*dim\s+(%s)\s*:(.*)$' % label_regex_token)

		decorations = DecorLineList(r'^\s*decoration\s+(%s)\s*:(.*)$' % label_regex_token)

		empty = re.compile(r'^\s*$')
		comment = re.compile(r'^\s*#.*$')

		lines = sys.stdin.readlines()	
		for line in lines:
			if not (empty.match(line) or comment.match(line)):
				try:
					anchors.try_add_code(line)
					disp.try_add_code(line)
					time.try_add_code(line)
					rf.try_add_code(line)
					pfg.try_add_code(line)
					acq.try_add_code(line)
					pulses.try_add_code(line)
					phases.try_add_code(line)
					delays.try_add_code(line)
					decorations.try_add_code(line)
					gradients.try_add_code(line)
					cpd.try_add_code(line)
					rfchan.try_add_code(line)
					pfgchan.try_add_code(line)
					dimensions.try_add_code(line)
					raise ParsingError('could not recognize input line\n%s' % line)
				except CodeLineSuccess:
					pass

		self._code = {'disp':disp,'time':time,'rf':rf,'pfg':pfg,'acq':acq,'anchors':anchors,
				'pulses':pulses,'phases':phases,'delays':delays,'decorations':decorations,
				'gradients':gradients,'cpd':cpd,'rfchan':rfchan,'pfgchan':pfgchan,
				'dim':dimensions}


	def _assign_delays_to_channels(self):
		gl = self._glist
		ch1 = self._rf_channel_order[0]
		for g in gl:
			delay = g.post_delay
			if delay != None:
				ch = delay.show_at
				if ch == None:
					delay.show_at = ch1

	def _attach_delays_to_anchors(self):
		gl = self._glist
		prev_delay = None
		for g in gl:
			if prev_delay != None:
				prev_delay.end_anchor = g.timed_anchor
			delay = g.post_delay
			if delay:
				delay.start_anchor = g.timing_anchor
				prev_delay = delay

	def _compile_anchor_list(self):
		alist = []
		for g in self._glist:
			for a in g.anchor_list:
				alist.append(a)
		self.anchor_list = alist

	def _prepare_for_drawing(self):
		#self._assign_delays_to_channels()#decide at what channel draw delay symbols
		#self._attach_delays_to_anchors()#each delay now gets start_anchor and end_anchor
		#self._calc_drawing_coordinates()#this is merged into _compile_init() for now
		self._compile_anchor_list()
		self._prepare_channel_labels()

	def _update_height_limits(self,val,habove,hbelow):
		if val < 0:
			if abs(val) > hbelow:
				hbelow = abs(val)
		else:
			if val > habove:
				habove = val
		return (habove,hbelow)

	def _calc_single_channel_drawing_parameters(self,chan,type):
		gl = self._glist
		habove = 0
		hbelow = 0
		for g in gl:
			for a in g.anchor_list:
				for e in a.events:
					if e.channel == chan:
						if type == 'rf':
							if e.get_type() == 'acq':
								if e.drawing_height > habove:
									habove = e.drawing_height
								if e.drawing_height > hbelow:
									hbelow = e.drawing_height
							else:
								h = e.drawing_height
								if h > habove:
									habove = h
						elif type == 'pfg':
							if e.alternated:
								(habove,hbelow) = self._update_height_limits(e.drawing_height[0],habove,hbelow)
								(habove,hbelow) = self._update_height_limits(e.drawing_height[1],habove,hbelow)
							else:
								(habove,hbelow) = self._update_height_limits(e.drawing_height,habove,hbelow)
						else:
							raise 'internal error'

		dl = self._bottom_drawing_limit

		ch = None
		if type == 'rf':
			ch = self._rf_channel_table[chan]
		elif type == 'pfg':
			ch = self._pfg_channel_table[chan]

		ch.height_above = self.channel_drawing_height
		ch.ycoor = dl + ch.height_above*0.8
		self._bottom_drawing_limit = ch.ycoor + self.channel_drawing_height


	def _calc_channel_drawing_parameters(self):
		for rf in self._rf_channel_order:
			self._calc_single_channel_drawing_parameters(rf,'rf')
		for pfg in self._pfg_channel_order:
			self._calc_single_channel_drawing_parameters(pfg,'pfg')

		lw = 0
		for ch in self._rf_channel_table.values() + self._pfg_channel_table.values():
			new_lw = ch.label_width
			if new_lw > lw:
				lw = new_lw
		self.margin_left = self.margin_left + lw


	def _init_drawing_parameters(self):
		#a whole bunch of drawing parameters moved to PulseSequence.__init__()
		w = int(self._glist[-1].get_max_xcoor()) #x coordinate of last anchor
		self.drawing_width = w

	def _init_drawing_object(self):
		import Image, ImageDraw

		self._calc_channel_drawing_parameters()

		self.drawing_height = self._bottom_drawing_limit + self.margin_below
		w = self.drawing_width + self.margin_right + self.margin_left
		h = self.drawing_height
		mode = self.image_mode
		self._image = Image.new(mode,(int(w),int(h)),self.bg_color)
		self._draw_object = ImageDraw.Draw(self._image)

	def _calc_event_ycoor(self,event):
		t = event.get_type()
		if t in ('rf_pulse','rf_wide_pulse','acq','wide_event_toggle'):
			return self._rf_channel_table[event.channel].ycoor
		elif t == 'pfg' or t == 'pfg_wide':
			return self._pfg_channel_table[event.channel].ycoor
		else:
			raise '_calc_ycoor doesnt work with %s events' % t

	def _draw_delays(self):
		delays = self._delay_list
		for d in delays:
			d.draw(self._draw_object)

	def _draw_decorations(self):
		dl = self._decoration_list
		for d in dl:
			d.draw(self._draw_object)

	def _draw(self,file):#PulseSequence._draw()
		"""PulseSequence object's internal drawing function
		"""
		d = self._draw_object
		anchors = self.anchor_list

		self._image_file = file

		fg = self.fg_color
		w = self.drawing_width

		x0 = self._glist[0].xcoor
		for c in self._rf_channel_table.keys():
			ch = self._rf_channel_table[c]	
			y = ch.ycoor
			d.line(((x0,y),(w,y)),fill=fg)
		for c in self._pfg_channel_table.keys():
			ch = self._pfg_channel_table[c]	
			y = ch.ycoor
			d.line(((x0,y),(w,y)),fill=fg)

		#xcoor calculation now moved to _compile_init stage
		#later perhaps all coordiante calcs to be moved into read (Fef 26 2009)
		for a in anchors:
			#x = a.xcoor
			if a.type == 'normal':
				for e in a.events:
					ch = e.channel	
					#e.xcoor = x
					e.set_ycoor( self._calc_event_ycoor(e) )
					e.draw(d)
			elif a.type == 'pegging': #todo this to be removed in new version
				print "what the heck"
				sys.exit()
					
		self._draw_delays()
		self._draw_decorations() #dummy call for now
		#self.draw_all_tics() #debug
		self._make_space_for_channel_labels()
		self._draw_channel_labels()
		self._save_image()

	def _make_space_for_channel_labels(self):
		import ImageChops,ImageDraw
		self._image = ImageChops.offset(self._image,self.margin_left,0)
		self._draw_object = ImageDraw.Draw(self._image) #add this because we need updated object

	def _draw_channel_labels(self):
		x = self.margin_left - 3
		for ch in self._rf_channel_table.values() + self._pfg_channel_table.values():
			y = ch.ycoor - 3
			im = ch.label_image
			paste_image(im,self,(x,y),yplacement='above',xplacement='left')

	def _save_image(self):
		file = self._image_file
		import ImageFilter
		self._image = self._image.filter(ImageFilter.SHARPEN)
		self._image.save(file)

	def _bootstrap_objects(self):
		for g in self._glist:
			g._bootstrap_objects(self)

	def _copy_template_data_to_objects(self):
		for g in self._glist:
			if g.post_delay != None:
				g.post_delay.load_template_data()
			for a in g.anchor_list:
				for e in a.events:
					e.load_template_data()

	def _prepare_channel_labels(self):
		for ch in self._rf_channel_table.values() + self._pfg_channel_table.values():
			ch.prepare_label()

	def _create_output_file(self):
		letters = "qwertyuiopasdfghjklzxcvbnm1234567890"
		import random
		from time import time
		random.seed(time())
		while 1:
			name_letters = [ random.choice(letters) for x in xrange(30) ]
			base_name = ''.join(name_letters) + '.png'
			file = IMAGE_DIR + '/' + base_name 
			link = IMAGE_DIR_URL + '/' + base_name
			try:
				fd = os.open(file,os.O_EXCL|os.O_CREAT)
				return (file,link)
			except:
				pass

	def read(self):
		"""Reads nmrType pulse sequence source, parses it
		and builds the pulse sequence object
		"""
		self._read_code()
		self._parse_code()
		self._bootstrap_objects()#purpose of this: make way up to pulse seq from objects

	def draw_all_tics(self):#PulseSequence.draw_all_tics()
		for g in self._glist:
			g.draw_all_tics()

	def draw(self):#PulseSequence.draw()
		"""Creates pulse sequence png drawing based
		on fully initialized PulseSequence object
		"""
		self._init_drawing_parameters()#set basic drawing parameters
		self._prepare_for_drawing()#determine sizes of all objects
		self._init_drawing_object()#calculate channel y-offsets and image height
		(file,link) = self._create_output_file()
		self._draw(file)
		print link #prints url to the newly created image

	def _recalc_anchor_group_delays(self,g,pre_dly):
		"""update expression in the pre_dly
		return new delay expression to be subtracted from timing 
		delay of the following anchor group

		g - group to compile
		pre_dly - delay preceding to group g 
		"""
		pre_e = pre_dly.expr
		post_e = N(0)

		calc_post_dly = False
		update_pre_dly = True
		for a in g.anchor_list:
			#pre- and post- anchor group delay calculation
			if a == g.timed_anchor:
				pre_e = E('sub',pre_e, a.pre_span)
				update_pre_dly = False
			if update_pre_dly: 
				pre_e = E('sub',pre_e, a.span) #before timed substract entire length of events
			if calc_post_dly:
				post_e = E('add',post_e, a.span)
			if a == g.timing_anchor:
				post_e = E('add',post_e, a.post_span)
				calc_post_dly = True
		pre_dly.expr = pre_e # delay expression assignment
		return post_e
			
	def _compile_add_gating_delays(self):
		"""adds rf_pulse_gating_delay and pfg_recovery_delay
		to corresponding elements
		"""
		pulse_gating = Delay('rf_pulse_gating_delay')
		pfg_recovery = Delay('pfg_recovery_delay')
		zero_delay = Delay('zero',expr=N(0)) # delay expression assignment

		(pre,post) = (None,None)
		for g in self._glist:
			for a in g.anchor_list:
				for e in a.events:
					if isinstance(e,Pulse):
						pre = pulse_gating
						post = pulse_gating
					elif isinstance(e,GradPulse):
						pre = zero_delay
						post = pfg_recovery
					elif isinstance(e,WideEventToggle):
						pre = zero_delay
						post = zero_delay
					e.pre_gating_delay = pre
					e.post_gating_delay = post


	def _compile_add_delay(self,expr):
		"""creates delay with auto-generated name, appends it to the delay list
		returns the newly created delay
		_compile_add_wide_event_toggles() must be called before this
		"""
		cid = self._compile_cdelay_id
		dly = Delay('dly%d' % cid,expr=expr) # delay expressions assignment
		self.add_delay(dly)
		self._compile_cdelay_id = cid + 1
		return dly

	def _compile_add_wide_event_toggles(self):
		for g in self._glist:
			for a in g.anchor_list:
				a.determine_type()
				if a.type == 'pegging':
					new_events = [] 
					events = a.events
					a.events = new_events
					for e in events:
						start_e = WideEventToggle('on',e)
						end_e = WideEventToggle('off',e)
						start_e.channel = e.channel
						end_e.channel = e.channel
						e.end_anchor.add_event(end_e)
						a.add_event(start_e)
						end_e.anchor = e.end_anchor
						start_e.anchor = a

	def _compile_init(self,src):
		"""initialize data before compilation of user-entered sequence

		makes a copy of the source pulse sequence, then 
		adds wide event toggles (plug - needs to be done at input pending changes in model)
		adds gating delays
		calculates event timings: pre-anchor and post-anchor spans
		creates draft label images to determine their size
		calculates drawing offsets for all elements
		"""
		#import copy
		#src = copy.deepcopy(source)  #bug: copying done before images are calc'd
					#because of this and the fact that compile
					#calculates all drawing offsets as well
					#which is because timing and drawing offset
					#calculations are very similar so they 
					#are clumped together in time() functions
					#--- it's impossible to call draw()
					#before compile()
		self._compile_src = src
		self._compile_cdelay_id = 0 #index for the next delay created by compiler

		#bootstrap wide events to start and end_anchors
		#this code probably must be moved upstream or handling of 
		#wide events must be completely redone
		src._compile_add_wide_event_toggles()


		#initialize default .pre_gating_delay, .post_gating_delay for gradients,
		#pulses, WideEventToggle's
		src._compile_add_gating_delays()

		#function time() also calculates drawing offsets relative to
		#anchors so I decided to put all graphics coordinate
		#calculations here for the ease of maintenance
		#probably this entire _compile_init() function
		#needs to go inside read()
		src.time() #time calculates timings, drawing offsets, generates draft label images
		self._primary_delay_list = src._delay_list
		self._hardware_delay_list = []
		self._rf_channel_table = src._rf_channel_table
		self._pfg_channel_table = src._pfg_channel_table
		self._dim_table = src._dim_table
		self._dim_order = src._dim_order
					
	def _compile_add_anchor_group(self,anchor):
		ng = AnchorGroup()
		self._glist.append(ng)
		ng.anchor_list.append(anchor)
		ng.timing_anchor = anchor
		ng.timed_anchor = anchor
		return ng

	def _compile_build_hardware_delay_list(self):
		#this list is started in the _compile_init
		#by simply copying user-supplied delays
		#here there is some cheating
		#pull out all primary delays from expressions
		#find those that were not supplied by the user
		#and add them to the _hardware_delay_list
		primary_delay_names = []
		for d in self._primary_delay_list:
			primary_delay_names.append(d.name)  #could be shorter with better POM
			
			
		hardware_delay_names = []
		for d in self._delay_list:
			list = d.get_primary_delay_list()
			for pd in list:
				if pd.name not in primary_delay_names:
					if pd.name not in hardware_delay_names:
						self._hardware_delay_list.append(pd)

	def _reduce_delay_expressions(self):
		print 'reducing delay expressions'
		for d in self._delay_list:
			if d.expr != None:
				print 'before: ', d.expr.get_eqn_str()
				d.expr.reduce()
				print 'after: ', d.expr.get_eqn_str()

	def compile(self,src):
		"""Compile user-entered pulse sequence object src into a new one (self)
		that can be converted into the instrument-specific code.
		Compilation involves splitting anchor groups into new ones that
		have only one anchor per group, calculation of all explicit delays,
		merging channels where appropriate.

		NOTE: delays in compiles pulse sequence only have name (automatic) 
		and expr - expression set

		src - source pulse sequence object
		self - compiled pulse sequence object
		"""
		self._compile_init(src) #this calls time on source sequence
		src = self._compile_src

		groups = iter(src.get_anchor_groups())
		pg = groups.next() #dummy start anchor group

		pre_dly_expr = E('set',N(0))

		#first pass on input code - subtract durations of elements from
		#delays between anchor groups
		for g in groups:
			expr = E('sub',pg.post_delay,pre_dly_expr)
			dly = self._compile_add_delay(expr)
			pg.post_delay = dly
			pre_dly_expr = self._recalc_anchor_group_delays(g,dly) #this calls time()
			pg = g

		#second pass actually create new pulse sequence
		#add separate anchor group for each event
		#mark official delays for further use in third pass
		#add dummy zero length delays between new anchor groups

		groups = iter(src.get_anchor_groups())
		pg = groups.next() #dummy group
		self._glist[0].post_delay = pg.post_delay
		for g in groups:
			dly = pg.post_delay
			dly.start_anchor = pg

			anchor_list = copy.copy(g.anchor_list)
			last_anchor = anchor_list.pop() #did a copy because of this pop() call

			for a in anchor_list:
				ng = self._compile_add_anchor_group(a)
				dly.end_anchor = a
				dly = self._compile_add_delay(E('set',N(0)))
				ng.post_delay = dly

			ng = self._compile_add_anchor_group(last_anchor)
			dly.end_anchor = last_anchor
			ng.post_delay = g.post_delay

			pg = ng

		#third pass
		#reassign channels where necessary 
		#insert frequency switch anchors
		#have to do this in the middle of official delays
		self._compile_build_hardware_delay_list() #pull out all the "hardware" delays
		self._pulse_list = self.get_pulses() #vars is a data structure
		self._wide_rf_pulse_list = self.get_wide_rf_pulses()
		self._gradient_list = self.get_gradients()
		#self._reduce_delay_expressions() #this call needs serious work

	def _varian_init_phase_tables(self,phases):
		i = 1
		output = ['\t/* set phase tables */']
		printed = []
		for ph in phases:
			tname = 't%d' % i
			text = '\tsettable(%s, %d, %s);' % (tname,len(ph.table),ph.name)
			ph.varian_name = tname

			output.append(text)	
			i = i+1
		return output

	def _varian_translate_name(self,name):
		"""name translations
		"""
		varian_names = {'pfg_recovery_delay':'gstab','rf_pulse_gating_delay':'rof1',}
		if varian_names.has_key(name):
			return varian_names[name]
		else:
			return name

	def _varian_environment_names(self):
		"""list of varian environment variables
		"""
		#list to be continued
		return ['rof1','sw','sw1','sw2','phase','phase2','ni','ni2','ct']

	def _c_punctuate_var_list(self,list):
		"""input list containts c variables definitions of same type
		all elements of the list receive comma at the end
		the last element gets semicolon ;
		resulting list can be printed out as a valid c statement
		"""
		if len(list) == 0:
			return
		for i in range(len(list)-1):
			list[i] = list[i] + ','
		list[-1] = list[-1] + ';'

	def _varian_get_pulse_base_name(self,pulse):
		p_basename = pulse.type

		if pulse.type == '180':  #define parameters for the 90 instead
			p_basename = '90'
		elif pulse.type != '90':
			p_basename = pulse.name

		#todo this may be packed into a function - pulse name calculations
		channel = self.get_channel(pulse.channel)
		return '%s%s' % (channel.nucleus,p_basename)

	def _varian_get_rf_event_power(self,pulse):
		p = self._varian_get_pulse_base_name(pulse)
		return '%spwr' % p

	def _varian_get_pulse_name(self,pulse):
		p = self._varian_get_pulse_base_name(pulse)
		return 'pw%s' % p

	def _varian_declare_vars(self):
		"""return list of lines containing variable declaration and initiatization
		setion in the varian .c format
		"""
		if len(self._pulse_list) + len(self._delay_list) \
			+ len(self._gradient_list) + len(self._wide_rf_pulse_list) == 0:
			return

		var_text = []

		#here I have to work around a problem of many copies of elements
		printed_pulses = []
		for pulse in self._pulse_list: 

			p_pwr = self._varian_get_rf_event_power(pulse)
			p_name = self._varian_get_pulse_name(pulse)
			p = self._varian_get_pulse_base_name(pulse)

			pulse.varian_power_level = p_pwr  #varian_power_level
			pulse.varian_name = p_name  #varian_name

			channel = self.get_channel(pulse.channel)
			if pulse.type == '90':#todo remove plug
				channel._varian_hard_pulse_power_variable = p_pwr

			if p not in printed_pulses: #here goes the workaround
				var_text.append('\t%s = getval("%s")' % (p_name,p_name))
				var_text.append('\t%s = getval("%s")' % (p_pwr,p_pwr))
				printed_pulses.append(p)

		self._c_punctuate_var_list(var_text)

		if len(var_text):
			out = ['\ndouble  /* declare pulses */']
			out.extend(var_text)

		printed_wides = []
		var_text = []
		for wp in self._wide_rf_pulse_list:
			p_pwr = self._varian_get_rf_event_power(wp)
			wp.varian_power_level = p_pwr
			if p_pwr not in printed_pulses:
				var_text.append('\t%s = getval("%s")' % (p_pwr,p_pwr))
				printed_wides.append(p_pwr)
		self._c_punctuate_var_list(var_text)
		if len(var_text):
			out.append('\ndouble /* decoupling power */')
			out.extend(var_text)

		#might want to use these variables to check for negative delays
		#for better error checking
		#delay_names = []
		#if len(self._delay_list):
		#	out.append('\t/* calculated delays */')
		#	for delay in self._delay_list:
		#		d = delay.name
		#		if d not in delay_names and delay.expr != None:
		#			delay_names.append(d)

		#for i in range(0,int(len(delay_names)/5)+1):
		#	line = '\t' + ','.join(delay_names[i*5:(i+1)*5]) + ','
		#	out.append(line)


		delay_names = []
		var_text = []
		if len(self._primary_delay_list):
			for delay in self._primary_delay_list:
				if delay.type != 'acq': #remove temp plug breaks explicit acq
					d = delay.name + '_dly' #this is to screen real-time t variables, etc
					delay.varian_name = d
					if d not in delay_names:
						var_text.append('\t%s = getval("%s")' % (d,delay.name))
						delay_names.append(d)

		self._c_punctuate_var_list(var_text)
		if len(var_text):
			out.append('\ndouble /* user set delays */')
			out.extend(var_text)

		delay_names = []
		var_text = []
		if len(self._hardware_delay_list):
			for delay in self._hardware_delay_list:
				d = self._varian_translate_name(delay.name)
				delay.varian_name = d #varian_name
				if d not in self._varian_environment_names() and d not in delay_names:
					var_text.append('\t%s = getval("%s")' % (d,d))
					delay_names.append(d)

		self._c_punctuate_var_list(var_text)
		if len(var_text):
			out.append('\ndouble /* hardware specific delays */')
			out.extend(var_text)

		grad_names = []
		var_text = []
		if len(self._gradient_list):
			for grad in self._gradient_list:
				g = grad.name
				gre = re.compile(r'^(.*)(\d+)$')
				m = gre.match(g)
				#match regex ending with numbers
				if m:
					prefix = m.group(1)
					index = m.group(2)
					gt = '%st%s' % (prefix,index)
					glvl = '%s%slvl%s' % (prefix,grad.channel,index)
				else:
					gt = g + 't'
					glvl = g + grad.channel + 'lvl'
				#save symbol names for later
				grad.varian_grad_level = glvl   #varian_grad_level
				grad.varian_grad_span = gt    #varian_grad_span
				if g not in grad_names:
					#print declaration and initialization
					var_text.append('\t%s = getval("%s")' % (gt,gt))
					var_text.append('\t%s = getval("%s")' % (glvl,glvl))
					#for gradient level and gradient duration time
					grad_names.append(g)

		self._c_punctuate_var_list(var_text)
		if len(var_text):
			out.append('\ndouble /* gradients */')
			out.extend(var_text)

		return out;

	def _varian_print_events(self,events):
		if len(events) == 0:
			return []
		out = []
		if isinstance(events[0],GradPulse):
			if len(events) > 1:
				raise CompilationError("simultaneous gradients for varian not supported yet")
			else:
				e = events[0]
				out.append("\trgradient('%s',%s);" % (e.channel,e.varian_grad_level))
				out.append('\tdelay(%s);' % e.varian_grad_span)
				out.append("\trgradient('%s',0.0);" % e.channel)
				out.append('\tdelay(%s);' % e.post_gating_delay.get_varian_expression())
		elif isinstance(events[0],WideEventToggle): #todo fix handling of wide events properly
			#now nothing explicit is done - just switch of status and power
			#in hopes that dm, dmf and dmm type variables can help
			if len(events) > 1:
				raise CompilationError('simultaneous wide event toggles not supported for varian')
			toggle = events[0]
			e = events[0].event
			ch = self.get_channel(e.channel)
			if toggle.type == 'on':
				#set power  todo normally there must just be power switch event
				out.extend(self._varian_adjust_power_for_events_if_needed([e])) #todo remove plug call
				#like for pulses need to use table obspower, decpower, dec2power, etc
				out.append(self._varian_next_status_statement());
				ch.wide_event_on()
			elif toggle.type == 'off':
				out.append(self._varian_next_status_statement());
				#restore power (removed this, decided to switch power just before events
				#out.append(self._varian_restore_default_power_after_event(e)) #another plug
				ch.wide_event_off()
			else:
				raise 'internal error: unknown toggle type \'%s\'' % toggle.type

		elif isinstance(events[0],Pulse):
			#todo major plug here I make assumption that
			#H - channel 1
			#C - channel 2
			#N - channel 3
			#other channels not supported!
			nuclei = {}
			types = {}
			edges = {}
			hardware = {}
			for e in events:
				ch = self.get_channel(e.channel)
				hardware[ch.hardware] = 1
				nuclei[ch.nucleus] = 1
				types[e.type] = 1
				edges[e.edge] = 1
			hlist = hardware.keys()
			nlist = nuclei.keys()
			tlist = types.keys()
			elist = edges.keys()

			if len(elist) > 1:
				raise CompilationError('different pulse edge alignment on the same anchor not yet supported for varian')
			elif elist[0] != 'center' and len(events) > 1:
				raise CompilationError('simultaneous pulses for Varian can be only centered at this time')

			#todo: handle shaped pulses within VPulse and VSimPulse objects
			if 'sh' in tlist:
				#prepare shaped pulse
				if len(nlist) > 1:
					#simultaneous shaped pulse
					pass
				else:
					#ordinary shaped pulse
					pass
			else:
				#prepare rectangular pulse
				if len(hlist) > 1:
					#simultaneous rectangular pulse
					call = ''
					vsp = VSimPulse()
					for p in events:
						vsp.add_event(p)

					pwr_set = self._varian_adjust_power_for_events_if_needed(events)
					out.extend(pwr_set)
					text = vsp.render()
					out.append(text)
				else:
					p = events[0]
					pwr_set = self._varian_adjust_power_for_events_if_needed([p])
					out.extend(pwr_set)
					vp = p.get_varian_parameters()
					out.append(vp.render())
		return out

	def _varian_adjust_power_for_events_if_needed(self,events): #todo this needs to be seriously redone
		#plug assumed tpwr,dpwr,dpwr2
		#power switching delay is ignored
		#three state power level management is used: 'high' (NUC90pwr),'set' (per pulse bespoke),'dec' (decoupling)
		call = self._varian_get_power_call_table()

		out = []

		for e in events:
			ch = self.get_channel(e.channel)
			hardware = ch.hardware
			cpower = ch.power
			epower = e.varian_power_level

			if epower != cpower:
				#print power change statement
				out.append('%s(%s)' % (call[hardware],epower))
				#remember new setting
				ch.power = epower
		return out

	def _varian_restore_default_power_after_event(self,event): #todo this needs to be seriously redone
		#this routine is probably not used now - check it!
		ch = self.get_channel(event.channel)
		nuc = ch.nucleus
		#todo remove plug
		if not self.__dict__.has_key('_varian_hard_pulse_power_variable'):
			lvl = '%s90pwr' % nuc
		else:
			lvl = ch._varian_hard_pulse_power_variable
		if nuc == 'H':
			return 'obspower(%s);' % lvl
		elif nuc == 'C':
			return 'decpower(%s);' % lvl
		elif nuc == 'N':
			return 'dec2power(%s);' % lvl
		else:
			raise 'internal error on H,C,N channels supported for varian so far'

	def _varian_next_status_statement(self):
		status = self._varian_status_table
		cstat = self._varian_cstatus
		self._varian_cstatus = cstat + 1
		return 'status(%s);' % status[cstat]
	
	#try to clump together varian magic names
	def _varian_get_power_call_table(self):
		return {1:'obspower',2:'decpower',3:'dec2power'}

	def _varian_get_default_channel_power(self,ch=1):
		table = ['tpwr','dpwr','dpwr2']
		if ch > 3:
			raise CompilationError('channels above 3 not yet supported for Varian')
		return table[ch-1]

	def _varian_set_hard_pulse_power_levels(self):
		out = []
		channels = self.get_rf_channels()
		channels.sort(lambda x,y: x.hardware - y.hardware)

		call = self._varian_get_power_call_table()

		for ch in channels:
			lvl = '%s90pwr' % ch.nucleus
			text = '\t%s(%s);' % (call[ch.hardware],lvl)
			ch.power = lvl#remember new setting a state
			out.append(text)
		return out

	def _varian_build_pulse_sequence_body(self):
		self._varian_status_table = 'ABCDEFGHIJKLMNOPQRST'
		self._varian_cstatus = 0

		glist = iter(self._glist)
		cg = glist.next()
		out = []
		out.append(self._varian_next_status_statement())

		out.append("\trcvroff();")
		#set power levels
		out.extend(self._varian_set_hard_pulse_power_levels())
		out.append('')

		for g in glist:
			delay = cg.post_delay
			text = delay.get_varian_code()
			out.extend(text)
			anchor = g.anchor_list[0]
			#todo remove temporary plug explicit acqs will break
			if len(anchor.events) > 0 and anchor.events[0].get_type() == 'acq':
				out.append('\trcvron();')
				if not self.is_wide_event_on():
					out.append(self._varian_next_status_statement())
				acq = anchor.events[0].event #get acq event out of toggle event
				if acq.phase != None:
					phase = acq.phase.varian_name
				else:
					phase = 'zero'
				out.append('\tsetreceiver(%s);' % phase)
				break
			text = self._varian_print_events(anchor.events)
			out.extend(text)
			cg = g
		return out

	def _varian_build_quad_detection_statements(self):
		dim_table = self._dim_table
		dim_order = self._dim_order
		cdim = 1
		phase_index = {1:'',2:'2',3:'3',4:'4'}
		dly_index = {1:'2',2:'3',3:'4',4:'5'}

		out = []
		for d in dim_order:
			dim = dim_table[d]
			cdly = dly_index[cdim]

			#take care of the incremented delay
			dim_dly = Delay('d%s' % cdly)

			sampling_type = dim.sampling.get_name()
			if sampling_type != 'linear':
				raise CompilationError('only linear sampling supported for indirect dimensions, have %s' \
					% sampling_type)
			inc_delays = dim.sampling.get_args()

			for dly_name in inc_delays.keys():
				dly_list = []
				for pdelay in self._primary_delay_list:
					if pdelay.name == dly_name:
						dly_list.append(pdelay)
				#todo move this into parsing phase
				try:
					coeff = float(inc_delays[dly_name])
				except:
					raise ParsingError('numeric coefficient expected in sampling expression, have %s' \
						% inc_delays[dly_name])
				for dly in dly_list:
					expr = dly.expr
					dly_copy = Delay(dly.name) #this looks like a hack
					dly.expr = E('add',E('mul',dim_dly,N(coeff)),dly_copy)

			quad_type = dim.quad.get_name()
			if quad_type != 'states_tppi':
				raise CompilationError('quad != states_tppi() not supported yet, have %s' % quad_type)
			phases = dim.quad.get_args()

			#add hypercomplex freq discrimination
			out.append('\tif ((int)(getval("phase%s") + 0.5) == 2){' % phase_index[cdim])
			for ph in phases:
				rt_table = self.get_phase(ph).varian_name
				out.append('\t\ttsadd(%s,1,4);' % rt_table)
			out.append('\t}')
			out.append('\t{')
			out.append('\t\tdouble d%s_init = 0.0;' % cdly)
			out.append('\t\tint t%d_counter;' % cdim)
			out.append('\t\tif (ix==1){')
			out.append('\t\t\td%s_init = d%s;' % (cdly,cdly))
			out.append('\t\t}')
			out.append('\t\tt%d_counter = (int)((d%s-d%s_init)*sw%d + 0.5);' % (cdim,cdly,cdly,cdim))
			out.append('\t\tif (t%d_counter%%2){' % cdim)
			for ph in phases:
				rt_table = self.get_phase(ph).varian_name
				out.append('\t\t\ttsadd(%s,2,4);' % rt_table)
			#todo fix this assuming that have only one acquisition
			acq_rt_table = self.get_acquisitions()[0].event.phase.varian_name #pretty ugly 
			out.append('\t\t\ttsadd(%s,2,4);' % acq_rt_table)
			out.append('\t\t}')
			out.append('\t}')
			cdim = cdim + 1
		return out

	def print_varian(self):
		"""Creates varian pulse sequence file based on the pulse
		sequence object
		"""
		text = []
		text.append("#include <standard.h>");
		text.append("#define MAX(a,b) (a>b)?a:b\n");

		#print phase tables
		phases_tmp = self.get_phase_tables()
		phases = [] #todo this needs to be fixed
		for ph in phases_tmp:
			if ph not in phases:
				phases.append(ph)

		for ph in phases:
			text.append('static int %s[%d]=%s;' % (ph.name,len(ph.table),carray(ph.table)))

		if len(phases) > 0:
			text.append('\n')

		text.append("void pulsesequence(){");
		#declare variables
		text.extend(self._varian_declare_vars())
		#read parameters from environment
		#test.extend(self._varian_init_vars(pulses,delays,grads))

		#set phase tables
		text.extend(self._varian_init_phase_tables(phases))

		#set frequency discrimination scheme
		text.extend(self._varian_build_quad_detection_statements())

		#start pulse sequence
		text.extend(self._varian_build_pulse_sequence_body())
		text.append("}");

		for line in text:
			print line;
	
	def __str__(self):
		lines = []
		for g in self._glist:
			lines.append(g.__str__())
		return '\n'.join(lines)

