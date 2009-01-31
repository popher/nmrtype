#!/usr/bin/python
import sys
import os

#including slash in the end use blank if all is in paths
#settings for 1&1
latex_dir = '/usr/local/texlive/2008/bin/x86_64-linux/'
IMAGE_DIR = '/var/www/vhosts/default/htdocs/nmrwiki/images/NMRPulse' #where to put image files
IMAGE_DIR_URL = 'http://wikichemistry.org/nmrwiki/images/NMRPulse'
from Numeric import *

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
	#utility function loads key=value pairs into a table
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
	
	def draw(self,draw_object):
		pass

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

	def _determine_type(self):
		types = {}
		for e in self.events:
			if e._type in ('rf_pulse','pfg'):
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

	def has_event(self,channel):
		for e in self.events:
			if e.channel == channel:
				return True
		return False

	def calc_drawing_dimensions(self,maxh):

		self._determine_type()

		w = 0
		if self.type == 'normal':
			for e in self.events:
				e.calc_drawing_dimensions(maxh)
				ew = e.drawing_width
				if ew > w:
					w = ew
		elif self.type in ('empty','pegging'):
			w = 0
		else:
			raise 'internal error: unknown anchor type \'%s\'' % self.type

		self.drawing_width = w

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
		ch = ps.get_rf_channel(channel)
		d = ps.get_draw_object()
		x = self.xcoor
		y = ch.ycoor
		d.line(((x,y-3),(x,y+3)))

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
						+ 'because it already contains ' \
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

	def compile(self):
		for a in self.anchor_list:
			a.compile()

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

class Channel:
	def __init__(self,name,type):
		self.type = type
		self.name = name
		self.height_above = None
		self.neight_below = None
		self.ycoor = None
		self.template = None #todo remove this 
		self.label = None #initialized by _parse_variables
	def prepare_label(self):
		text = self.name
		if self.label != None:
			text = self.label
		im = latex2image(text)
		self.label_image = im
		self.label_width = im.size[0]
		

#an object collecting information about pulse sequence elements
#that is applied to several instances of the events
#for example several pulses can share a phase-cycling table
#or several pfg's in the pulse sequence can be identical 
#this class is populated at run time by function PulseSequence._procure_object
#then before pulse sequence is drawn information from template can be copied 
#to the instances as a temporary plug
#or maybe not so temporary ...
class PulseSequenceElementTemplate:
	def __init__(self,type,name):
		self._type = type #must match corresponding PulseSequenceElement._type
		self.name = name
		if type == 'pfg' or type == 'pfg_wide':
			self.strength=100

class PulseSequenceElement:
	def __init__(self):
		self.anchor = None
		self.drawing_width = 0
		self.drawing_height = 0
		self.template = None #instance of PulseSequenceElementTemplate
	def __str__(self):
		return self._type

	def load_template_data(self):#temporary ? plug
		if self.template != None:
			keys = self.template.__dict__.keys()
			for key in keys:
				val = self.template.__dict__[key]
				self.__dict__[key] = val

	def get_type(self):
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
		x = self.xcoor
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
			
		
	def draw_up_rect_pulse(self,draw_obj):
		d = draw_obj
		x = self.xcoor
		y = self.ycoor
		w = self.drawing_width
		h = self.drawing_height

		bg = self.pulse_sequence.bg_color
		fg = self.pulse_sequence.fg_color

		if self.type == '90':
			bg = fg

		d.rectangle((x-w/2,y-h,x+w/2,y),fill=bg,outline=fg)

	def draw_fid(self,draw_obj):
		d = draw_obj
		x = self.xcoor
		y = self.ycoor
		w = self.drawing_width
		h = self.drawing_height
		xval = arange(w)
		yval = multiply(h,multiply(-sin(multiply(xval,0.6)),exp(multiply(-0.04,xval))))
		xval = add(xval,x-w/2)
		yval = add(yval,y)
		fg = self.pulse_sequence.fg_color
		bg = self.pulse_sequence.bg_color

		d.line(((x-w/2,y),(x+w/2-1,y)),fill=bg)

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
	def __str__(self):
		return self.name + ' ' + self.label + ' ' + self.table


class Pulse(PulseSequenceElement):
	def __init__(self,type,channel,name=None):
		PulseSequenceElement.__init__(self)
		self._type = 'rf_pulse'
		self.type = type
		self.name = name
		#extra stuff
		self.length = None
		self.power = None 
		self.channel = channel
		self.phase = None
		self.label = None

	def __str__(self):
		out = self.type
		if self.phase:
			out = out + ' phase ' + self.phase.__str__()
		return out

	def calc_drawing_dimensions(self,maxh):
		#width_table = {'90':14,'180':22,'shp':42,'lp':14,'rect':14}
		width_table = {'90':9,'180':13,'shp':28,'lp':10,'rect':10}
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

	def draw(self,draw_obj):
		if self.type in ('90','180','lp','rect'):
			PulseSequenceElement.draw_up_rect_pulse(self,draw_obj)
		elif self.type == 'shp':
			PulseSequenceElement.draw_up_shaped_pulse(self,draw_obj)

		if self.label != None:
			coor = (self.xcoor,self.ycoor - self.drawing_height - 3) #todo: fix magic number drawing offset
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
			coor = (self.xcoor,self.ycoor - self.drawing_height - 3)
			draw_latex(text,seq,coor,yplacement='above')
			

class WidePulse(Pulse):
	def __init__(self,type,channel,**kwarg):
		Pulse.__init__(self,type,channel,**kwarg)
		self._type = 'rf_wide_pulse'
		self.end_anchor = None
		self.label = None
		self.h1 = None
		self.h2 = None
		self.maxh = None

	def calc_drawing_dimensions(self,maxh):
		self.drawing_width = self.end_anchor.xcoor - self.anchor.xcoor
		if self.type in ('fid','echo'):
			self.drawing_height = 0.7*maxh
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

	def draw(self,draw_obj):
		if self.type == 'fid':
			PulseSequenceElement.draw_fid(self,draw_obj)
		elif self.type == 'echo':
			PulseSequenceElement.draw_echo_fid(self,draw_obj)

class GradPulse(PulseSequenceElement):
	def __init__(self,name,channel):
		self._type = 'pfg'
		self.type = 'shaped'#shaped or rectangular
		self.alternated = False
		self.name = name
		self.label = None
		self.channel = channel
		self.duration = None
		self.strength = 100
		self.drawing_height = None
		self._maxh = 0
	def __str__(self):
		return 'pfg %s %s %s %s' % (self.channel,self.name,self.duration,self.strength)
	def calc_drawing_dimensions(self,maxh):
		self.drawing_width = 12  #was 32
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

		text = self.name
		if self.label != None:
			text = self.label
		draw_latex(text,self.pulse_sequence,(int(self.xcoor),int(y + 3)),yplacement='below')

class WideGradPulse(GradPulse):
	def __init__(self,name,channel):
		GradPulse.__init__(self,name,channel)
		self._type = 'pfg_wide'
		self.end_anchor = None
		self.template = None
		self.h1 = None
		self.h2 = None
		self.drawing_width = 0
	def calc_drawing_dimensions(self,maxh):
		self.h1 = self.strength 
		self.h2 = self.strength 
		self.drawing_height = maxh
		
	def draw(self,psdraw):
		if not self.alternated:
			PulseSequenceElement.draw_pegged_pulse(self,psdraw)


class Delay(PulseSequenceElement):
	def __init__(self,name):
		PulseSequenceElement.__init__(self)
		self._type = 'delay'
		self.length = None    #length of delay in seconds
		self.name = name
		self.label = None
		self.formula = None
		self.show_at = None #channel at which to draw delay
		self.start_anchor = None
		self.end_anchor = None
		self.label_yoffset = 0
		self.template = PulseSequenceElementTemplate('delay',name)
		#start_anchor
		#end_anchor assinged in PulseSequence._attach_delays_to_anchors()

	def __str__(self):
		return '%s label=%s formula=%s' % (self.name,self.label,self.formula)

	def calc_drawing_coordinates(self):
		"""xcoor assigned as average xcoor of delay's start and end anchors
		"""
		self.xcoor = int((self.start_anchor.xcoor + self.end_anchor.xcoor)/2)

	def validate(self):
		"""validation of hide parameter
		"""
		t = self.template
		if t.__dict__.has_key('hide'):
			val = t.hide
			false = re.compile(r'^false$',re.IGNORECASE)
			true = re.compile(r'^true$',re.IGNORECASE)
			if false.match(val):
				self.template.hide = False
			elif true.match(val):
				self.template.hide = True
			else:
				raise ParsingError("Problem with value of parameter 'hide'"\
					+'in delay %s.' % self.name \
					+ " Allowed values are 'true' and 'false'")

	def draw_bounding_tics(self):
		"""a tic mark will be drawn on a side where anchor has no attached events
		"""
		start = self.start_anchor
		end = self.end_anchor
		if not start.has_event(self.show_at):
			start.draw_tic(self.show_at)
		if not end.has_event(self.show_at):
			end.draw_tic(self.show_at)

	def draw(self,draw_obj):
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
		draw_latex(text,self.pulse_sequence,(self.xcoor,self.ycoor),yplacement='center-clear')

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

class PulseSequence:
	"""Toplevel pulse sequence object
	"""
	def __init__(self):
		self._object_type_list = ('pfg','pfg_wide','rf_pulse','rf_wide_pulse',
								'acq','phase')
		for ot in self._object_type_list:
			self.__dict__[ot + '_table'] = {}

		self._rf_channel_table = {}
		self._pfg_channel_table = {}
		self._delay_list = [] 
		self._decoration_list = []
		self._draft_image_no = 0

	def get_rf_channel(self,name):
	#todo here is a catch - only rf channels are returned
		ct = self._rf_channel_table
		if ct.has_key(name):
			return ct[name]
		else:
			raise ParsingError("There is no rf channel '%s'" % name)

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

	def compile(self):
		"""calculate all actual delays, pulse timing parameters
		initialize all necessary data to output in Varian or Bruker format
		"""
		for g in self._glist:
			g.compile()

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

	def _parse_disp(self):
		code = self._code['disp'].code
		self._validate_anchor_order(code)

		bits = code.split()
		disp_re = re.compile(r'^(\+)?(\d+|\d*\.\d+)@(%s)$' % label_regex_token) #anchor_name

		cdisp = 0
		for bit in bits:
			m = disp_re.match(bit)
			if m:
				rel = m.group(1)
				disp = int(m.group(2))*10
				a_name = m.group(3)
				a = self.get_anchor(a_name)
				g = a.group
				#if g.timed_anchor != a:
				#	raise ParsingError('problem with anchor %s:' % ('@' + a_name) \
				#					+ ' all anchors in disp line must be timed')#why?
				if rel:
					raise ParsingError('in entry %s <b>"+"</b> signs in disp line are no longer used, please delete them' % bit)
				cdisp = cdisp + disp
				g.xcoor = cdisp
			else:
				raise ParsingError('could not parse entry %s in disp line ' \
						'entries are expected in the following format: ' \
						'<positive number>@<anchor name>' % bit)

	def _parse_time(self):
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
		code = self._code['anchors'].code
		head_group = AnchorGroup()#special start anchor group with null name and offset
		a = Anchor(None) #special unnamed anchor
		head_group.timed_anchor = a      #anchor with interval before
		head_group.timing_anchor = a     #anchor with interval after
		head_group.anchor_list.append(a)
		head_group.xcoor = 0

		tokens = (label_regex_token,label_regex_token)
		anchor_group_re = re.compile(r'^@%s(:?(:?,|-+)%s)*$' % tokens)

		new_anchor_group_re = re.compile(r'^@(%s)(:?\[([1-9]\d*)\])$' % anchor_basename_token );
		# @a--b,c5,sdfg345
		# @a,@b1-5,@7
		# @g1-7

		at_re = re.compile(r'^@')
		dash_re = re.compile(r'-+')

		self._glist = [head_group]
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
			g = AnchorGroup()
			self._glist.append(g)

			for a_name in a_names:
				a = Anchor(a_name)
				a.group = g
				g.anchor_list.append(a)

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

	def _parse_rf(self):
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
					p = self._procure_object('rf_pulse',pulse_type,ch,name=pulse_name)
					a = self.get_anchor(a_name)
					p.anchor = a#anchor bug
					a.add_event(p)

				elif wm:
					event = None
					start_a_name = None
					end_a_name = None

					event_type = wm.group(1)
					start_a_name = wm.group(2)
					end_a_name = wm.group(5)
					event_name = wm.group(7)

					if event_type == 'acq':
						event = self._procure_object('acq',ch,name=event_name)
					else:
						event = self._procure_object('rf_wide_pulse',
										event_type,ch,
										name=event_name)
					a = self.get_anchor(start_a_name)
					sa =  self.get_anchor(end_a_name)
					event.anchor = a#anchor bug
					event.end_anchor = sa#anchor_bug
					a.add_event(event)
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
			ParsingError('no %s named %s found in the pulse sequence' % (type,name))
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
		else:
			raise '_get_objects not implemented for type %s' % type

	def _parse_variables(self,type,allowed_keys):

		table = self._code[type].table
		for obj_name in table.keys():
			code = table[obj_name]
			par = parse_param(code) #parse parameters given in the variable line
			obj_list = self._get_objects(type,obj_name)
			for obj in obj_list:
				#todo problem: channels don't need template, but who cares....(for now)
				if obj.template == None:
					obj.template = PulseSequenceElementTemplate(type,obj_name)

				for key in par.keys():
					if key in allowed_keys:
						obj.__dict__[key] = par[key]
						obj.template.__dict__[key] = par[key]
					else:
						raise ParsingError('key \'%s\' not allowed for %s' % (key,type))

	def _parse_positive_percent(self,input,name):
		try:
			input = float(input)
			if input > 100:
				raise
			if input < 0:
				raise
		except:
			raise ParsingError('%s value must be a real number from 0 to 100' % name)
		return input

	def _parse_cpd_height_values(self):
		wp = self.rf_wide_pulse_table.values()
		for p in wp:
			if p.template and p.template.__dict__.has_key('h1'):
				if p.template.h1 != None:
						p.template.h1 = self._parse_positive_percent(p.template.h1,'wide pulse h1 parameter')	
						if p.template.__dict__.has_key('h2') and p.template.h2 != None:
							p.template.h2 = self._parse_positive_percent(p.template.h2,'wide pulse h2 parameter')
				elif p.template.__dict__.has_key('h2') and p.template.h2 != None:
					raise ParsingError('h2 in wide pulse parameters must be used together with h1')

	def _parse_gradient_values(self):
		pfg = self.pfg_table.values()
		wpfg = self.pfg_wide_table.values()
		for p in pfg + wpfg:
			val = p.template.strength
			try:
				p.template.strength = float(val)
			except:
				bits = val.split(',')
				msg = "don't understand strength value %s of gradient pulse %s" \
						% (val,p.name)
				msg = msg + ': strength must be a floating point number or a list of two numbers'

				num_val = len(bits)
				if num_val != 2:
					raise ParsingError(msg)

				values = []
				for b in bits:
					try:
						values.append(float(b))
					except:
						raise ParsingError(msg)
				p.alternated = True
				p.template.strength = values
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
				elif len(phases) > 1:
					raise 'internal error: too many phase objects named %s' % p.phase

	def _validate_delay_values(self):
		delays = self.get_delays()
		for d in delays:
			d.validate()

	def _parse_code(self):
		#first parse anchor input
		#keys ['disp' , 'phases', 'pfg', 'delays', 'acq', 'rf', 'pulses', 'decorations', 'time']

		self._parse_anchor_groups() #create list of anchor groups '_glist' & anchors 
		self._parse_time() #populate _delay_list, set timed and timing delays to anchor groups
		self._parse_disp() #parse disp line, add xcoor to anchors
		self._parse_rf()
		self._parse_pfg()

		self._parse_variables('delays',('label','formula','show_at','hide','label_yoffset'))
		self._validate_delay_values()

		self._parse_variables('pulses',('phase','quad','arrow','label'))
		self._parse_variables('acq',('phase','type'))

		self._parse_variables('gradients',('duration','strength','type','label'))
		self._parse_gradient_values()#for echo-antiecho type gradients 
									 #(comma separated strength values)
									 #convert string values to numerical values

		self._parse_variables('cpd',('label','h1','h2'))
		self._parse_cpd_height_values()#convert h1 and h2 into numerical values

		self._init_phases()
		self._parse_variables('phases',('label','table'))
		self._attach_phases_to_pulses()

		self._parse_variables('rfchan',('label'))
		self._parse_variables('pfgchan',('label'))

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
					raise ParsingError('could not recognize input line\n%s' % line)
				except CodeLineSuccess:
					pass

		self._code = {'disp':disp,'time':time,'rf':rf,'pfg':pfg,'acq':acq,'anchors':anchors,
				'pulses':pulses,'phases':phases,'delays':delays,'decorations':decorations,
				'gradients':gradients,'cpd':cpd,'rfchan':rfchan,'pfgchan':pfgchan}

	def _calc_drawing_coordinates(self):
		"""Iterates through list of anchor groups, then in the
		nested loop - through list of anchors and calculates drawing
		dimensions for each anchor (i.e. dimensions of anchor elements).
		calculate drawing coordinates of pegged events and delays

		details:
		validate presence of timed anchor per group, presence of drawing offset
		xcoor assigned to timed anchor, calculate dimensions of all anchors
		then assign xcoor to all other anchors based on xcoor of timed anchor
		and width of anchors
		"""
		gl = self._glist
		for g in gl:
			ta = g.timed_anchor
			if ta == None:
				raise ParsingError('all anchor groups must be timed')
			xcoor = g.xcoor
			if xcoor == None:
				raise ParsingError('all anchor groups must have defined drawing offset')

			ta.xcoor = xcoor
			al = g.anchor_list
			maxh = self.channel_drawing_height

			for a in al:
				a.calc_drawing_dimensions(maxh)#calculate width taken up by elements attached to an anchor
			#this won't touch pegged events, because their width depends on anchor coordinates

			ta_index = g.anchor_list.index(ta)#index of timed anchor in anchor list

			c_index = ta_index - 1
			c_coor = ta.xcoor
			prev_a = ta
			while c_index >= 0:
				a = al[c_index]
				c_coor = c_coor - a.drawing_width/2 - prev_a.drawing_width/2
				a.xcoor = c_coor
				c_index = c_index - 1
				prev_a = a

			c_index = ta_index + 1
			c_coor = ta.xcoor
			prev_a = ta
			while c_index < len(al):
				a = al[c_index]
				c_coor = c_coor + a.drawing_width/2 + prev_a.drawing_width/2
				a.xcoor = c_coor
				c_index = c_index + 1
				prev_a = a

		#now we can calculate widths of pegged events (those attached to two anchors)
		for g in gl:
			al = g.anchor_list
			for a in al:
				for e in a.events:
					if e.is_pegged():
						e.calc_drawing_dimensions(maxh)

		for d in self._delay_list:
			d.calc_drawing_coordinates()#no need to give height here

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
		self._calc_drawing_coordinates()#calc dimensions
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
		self.channel_drawing_height = 35 
		self.margin_above = 40
		self.margin_below = 20
		self.margin_right = 20
		self.margin_left = 20
		self._bottom_drawing_limit =self.margin_above
		self.image_mode = 'L'
		self.fg_color = 0
		self.bg_color = 256
		w = int(self._glist[-1].xcoor)
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
		if t in ('rf_pulse','rf_wide_pulse','acq'):
			return self._rf_channel_table[event.channel].ycoor
		elif t == 'pfg' or t == 'pfg_wide':
			return self._pfg_channel_table[event.channel].ycoor
		else:
			raise '_calc_coor doesnt work with %s events' % t

	def _draw_delays(self):
		delays = self._delay_list
		for d in delays:
			d.draw(self._draw_object)

	def _draw_decorations(self):
		dl = self._decoration_list
		for d in dl:
			d.draw(self._draw_object)

	def _draw(self,file):
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

		for a in anchors:
			x = a.xcoor
			if a.type == 'normal':
				for e in a.events:
					ch = e.channel	
					e.xcoor = x
					e.ycoor = self._calc_event_ycoor(e)
					e.draw(d)
			elif a.type == 'pegging':
				for e in a.events:
					ch = e.channel
					e.xcoor = x + e.drawing_width/2 + 1 #+1 may be a bad hack
					e.ycoor = self._calc_event_ycoor(e)
					e.draw(d)
					
		self._draw_delays()
		self._draw_decorations()
		self._make_space_for_channel_labels()
		self._draw_channel_labels()
		self._save_image()

	def _make_space_for_channel_labels(self):
		import ImageChops
		self._image = ImageChops.offset(self._image,self.margin_left,0)

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

	def draw(self):
		"""Creates pulse sequence png drawing based
		on fully initialized PulseSequence object
		"""
		self._init_drawing_parameters()#set basic drawing parameters
		self._prepare_for_drawing()#determine sizes of all objects
		self._init_drawing_object()#calculate channel y-offsets and image height
		(file,link) = self._create_output_file()
		self._draw(file)
		print link 

	def print_varian(self):
		"""Creates varian pulse sequence file based on the pulse
		sequence object
		"""
		pass
	
	def __str__(self):
		lines = []
		for g in self._glist:
			lines.append(g.__str__())
		return '\n'.join(lines)

seq = PulseSequence()
try:
	seq.read()
	seq.draw()
	#seq.typeVarian()
	sys.exit(0)
except ParsingError,value:
	print value
	sys.exit(1)
