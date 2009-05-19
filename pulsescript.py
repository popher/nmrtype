#!/usr/bin/python
import sys
import os
import re
from pom import PulseSequence, POMError

label_regex_token = '[a-zA-Z0-9_]+'
anchor_basename_token = '[a-z]+'
element_name_regex_token = '[a-zA-Z0-9]+'
expression_regex_token = '[\^\_\{\}a-zA-Z0-9\*\/\(\)]+'

"""@package docstring
PulseScript reads the NMR pulse sequence written in the PulseScript code
this is the only module that deals with the PulseScript directly
"""

class AddCodeSuccess:
	"""fake success exception, used in the lexer
	"""
	pass


class CodeItem:
	"""primary code element class for extracting information from code
	and for reporting parsing errors back to the user
	"""
	def __init__(self,source='',regex=None,lineno=None,colno=1):
		"""match is regex match object that matched source of CodeItem
		lineno - source line
		colno - source column
		"""
		if regex == None:
			regex = r'^.*$'

		if lineno == None:
			raise 'internal error: lineno is a mandatory parameter'

		self.regex = regex
		self.re = re.compile(regex)
		self.match = self.re.search(source)
		self.source = source 
		self.lineno = lineno
		self.colno = colno

	def is_valid(self):
		if self.match == None:
			return False
		return True

	def __str__(self):
		content = self.get_content()
		if self.colno == None:
			colno = -1
		else:
			colno = self.get_colno()
		if self.lineno == None:
			lineno = -1
		else:
			lineno = self.lineno
		return 'line: %d col: %d content: \'%s\'' % (lineno,colno,content)

	def get_content(self,partno=0):
		if not self.is_valid():
			return '' 
		return self.match.group(partno)

	def get_subitem(self,partno=0):
		source = self.get_content(partno)
		colno = self.get_colno(partno)
		lineno = self.lineno
		return CodeItem(source=source,colno=colno,lineno=lineno)

	def get_lineno(self):
		return self.lineno

	def get_colno(self,partno=0):
		"""get column number for content element
		"""
		if self.is_valid():
			offset = self.match.start(partno)
		else:
			offset = 0
		return self.colno + offset

	def get_regex(self):
		return self.regex
	
	def set_colno(self,colno):
		self.colno = colno

	def deliver(self,regex='^.*$'):
		"""create a new CodeItem based on current and a new regular expression

		no regex means deliver the whole thing
		"""
		source = self.get_content()
		colno = self.get_colno()
		lineno = self.lineno
		newitem = CodeItem(source=source,regex=regex,colno=colno,lineno=lineno)
		return newitem

	def emit(self,regex):#CodeItem.emit()
		"""emit a new CodeItem, matching regex, anchored at the beginning
		before emission, leading space is cut out, 
		after emission the emitted contend is cut out

		if nothing matches regex, invalid item is emitted
		and current item stays untouched

		parameter regex - plain string regex, not compiled
		"""
		#validate regex
		if regex[0] == '^':
			raise 'internal error, regex must not be start-anchored'
		aregex = '^\s*' + regex
	
		#make code item
		item = self.deliver(aregex)
		if item.is_valid():
			#excise new item
			icontent = item.get_content()
			tmp = self.source.replace(icontent,'',1)	
			if tmp == self.source and len(icontent) > 0:
				raise 'cant strip prefix!!!'

			lineno = self.lineno
			colno = self.get_colno() + len(icontent)
			self.__init__(source=tmp,lineno=lineno,colno=colno)
			item = item.deliver(regex) #here empty space will be disregarded

		return item

	def _is_whatever(self,regex):
		whatever = re.compile(regex)
		if whatever.match(self.source):
			return True
		else:
			return False

	def is_comment(self):
		return self._is_whatever(r'^\s*#.*$')
	def is_wrapped(self):
		return self._is_whatever(r'^\s+\S+')
	def is_empty(self):
		return self._is_whatever(r'^\s*$')

class CodeEntry:
	"""class for logical blocks of code lines
	blocks can be simple or composite
	composite ones have two or more subentries, each one having its
	own key

	simple or composite depends on regex given to the __init__() function
	regex can have one (=>simple) or more (=>composite) capture groups
	"""
	def __init__(self,regex):

		#construct regex for code entry
		regex = r'^' + regex + r':(.*)$' #require colon

		self.regex = regex
		self.re = re.compile(regex)
		self.code_table = {} #table to hold code lines for each subentry
		self.subentry_order = [] #array to remember order of subentries, e.g. channels and item selectors
		#item selecors in particular need to be evaluated in correct order during parsing

		ngroups = self.re.groups
		if ngroups == 1:
			self.type = 'simple'
		else:
			self.type = 'composite'

	def __str__(self):
		out = []
		for subentry in self.subentry_order:
			bits = self.code_table[subentry]
			for bit in bits:
				out.append(bit.__str__())
		return '\n'.join(out)

	def code_items(self,regex=None):
		"""interface to iterating parser
		"""
		self._iter_regex = regex
		return self.__iter__()

	def __iter__(self):
		import copy
		#prep disposable copy for parsing
		self._iter_code_table = {}
		for subentry in self.subentry_order:
			carray = self.code_table[subentry]
			newcarray = []
			for item in carray:
				newitem = item.deliver()
				newcarray.append(item)
			self._iter_code_table[subentry] = carray
		self._iter_subentries = copy.deepcopy(self.subentry_order)
		return self

	def emit(self,regex):
		return self.next(regex)

	def next(self,regex=None):
		"""extracts next item matching regex passed to the iter object
		"""
		#done when all subentries are processed
		if len(self._iter_subentries) == 0:
			raise StopIteration

		#get the CodeItem from current subentry 
		csubentry = self._iter_subentries[0]
		carray = self._iter_code_table[csubentry]
		citem = carray[0] # <--- this is it

		if regex != None:
			item_regex = regex
		else:
			item_regex = self._iter_regex

		item = citem.emit(item_regex)

		#dicard empty elements
		if carray[0].is_empty():
			carray.pop(0)
		if len(carray) == 0:
			self._iter_subentries.pop(0)

		return item

	def lex_code(self,code):
		if self.type == 'simple':
			subentry_name = '__main__'
			subentry_code = code.get_subitem(1)	
		else:
			subentry_name = code.get_content(1)
			subentry_code = code.get_subitem(2) 
		return (subentry_name,subentry_code)

	def try_add_code(self,code):

		#strip the header, record column 
		#number in the resulting item
		#save header key if exists as subentry name

		entry_code = code.deliver(self.regex)
		if entry_code.is_valid():
			(subentry_name,code) = self.lex_code(entry_code)

			if subentry_name not in self.subentry_order:
				self.subentry_order.append(subentry_name)
				self.code_table[subentry_name] = []

			self.ctable = self.code_table[subentry_name]
			self.add_code(code)
			raise AddCodeSuccess()

	def add_code(self,code):
		self.ctable.append(code)

class ParsingError(Exception):
	#todo: remember to highlight remaining string from colno and up if item is invalid
	def __init__(self,message,item):
		self.item = item 
		self.msg = message
	def __str__(self):
		colno = self.item.get_colno()
		problem = self.item.get_content()
		lineno = self.item.get_lineno()
		msg = self.msg
		return 'parsing error on line %d, col %d with %s in line\n%s' \
			% (lineno,colno,problem,msg)

class PulseScript:
	"""PulseScript code object
	"""
	def __init__(self,file):
		"""among other things initializes head anchor group
		but does not create first delay

		most global drawing parameters entered here
		"""
		self.read(file)

	def __str__(self):
		out = []
		out.append(self.anchors.__str__())
		out.append(self.time.__str__())
		out.append(self.rf.__str__())
		out.append(self.pfg.__str__())
		for section in self.sections:
			out.append(self.__dict__[section].__str__())
		return '\n'.join(out)

	def validate_anchor_order(self,anchors):
		#todo get this done before release
		raise 'not here yet'

	def parse_time(self):
		"""parses code of "time" line

		builds list of delays, to anchor groups assigns: post-delay, 
		timed and timing anchors

		validation: anchor order, start with delay, end with anchor, anchors
		and delays must alternate, delays and anchors subject to pattern matching
		"""
		#first lex the time line
		#sequence must start with delay and end with anchor
		code = self.time
		ps = self.pulse_sequence

		t = label_regex_token
		anchor_re = r'@(%s)((-+)(%s))?$' % (t,t)
		delay_re = r'%s' % t

		items = code.code_items(r'\S+')

		ptype = None
		time_items = []
		used_anchors = []
		for item in items:
			print item
			sys.exit()

			anchor_item = item.deliver(anchor_re) 
			delay_item = item.deliver(delay_re)
			if anchor_item.is_valid():
				ctype = 'anchor'
			elif delay_item.is_valid():
				ctype = 'delay'
			else:
				raise POMError('could not recognize timing item',item)

			if ptype == ctype:
				if ctype == 'anchor':
					expected = 'delay'
					citem = anchor_item
				else:
					expected = 'anchor'
				msg = 'item expected to be %s' % expected
				raise POMError(msg,citem)

			#insert dummy origin anchor if necessary
			if ptype == None:
				if ctype == 'delay': #first anchor is implicit
					aname = 'OriginAnchor'
					time_items.append({'type':'anchor','name':aname})
					ps.insert_anchor_group(aname,1,0) #insert dummy

			if ctype == 'anchor':
				a1_name = anchor_item.get_content(1)
				a2_name = anchor_item.get_content(4)
				anchor_item = None
				used_anchors.append(a1_name)
				if a2_name:
					anchor_item = {'type':'double-anchor','name':a1_name,'name2':a2_name}
					used_anchors.append(a2_name)
				else:
					anchor_item = {'type':'anchor','name':a1_name}
				time_items.append(anchor_item)
			else:
				time_items.append({'type':'delay','name':delay_item.get_content()})

			ptype = ctype

		self.validate_anchor_order(used_anchors)

		c_group = self._glist[0]
		for item in time_items:
			if item['type'] == 'delay':
				ps.append_delay(item['name'])
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

	def parse_anchor_groups(self):
		"""parses text of "anchors" line
		creates list of anchor groups which themselves contain 
		list of their anchors
		"""
		ps = self.pulse_sequence
		tokens = (label_regex_token,label_regex_token)

		anchor_group_re = r'@(%s)(:?\[([1-9]\d*)\])?' % anchor_basename_token

		code = self.anchors
		items = code.code_items(anchor_group_re)
		for item in items:
			if not item.is_valid():
				raise ParsingError('could not parse',item)
			name = item.get_content(1)
			if item.get_content(3) == None:
				size = 1
			else:
				size = int(item.get_content(3))
			try:
				ps.append_anchor_group(name,size)
			except POMError as e:
				raise ParsingError(e.value,item)

	def parse_pfg(self):
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

	def parse_dim(self):
		code_table = self._code['dim'].table
		self._dim_order = self._code['dim'].item_order
		for dim_name in code_table.keys():
			self._dim_table[dim_name] = Dimension(dim_name)

	def parse_rf(self):
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

	def typecast_value(self,val_input,val_type):
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
					typecasted_val = self.typecast_value(v,val_type)
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
			val_value = self.typecast_value(val_input,val_type)
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

	def parse_param(self,input):
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
				param_table = self.parse_param('='.join(bits))
				param_table[key] = val
				return param_table
			else:
				raise ParsingError('%s <-here a name token expected' % bits[1])

	def parse_variables(self,type,key_table,key_aliases={}):

		for key in key_aliases.keys():
			if key not in key_table.keys():
				raise 'internal error: aliases and keys dont agree for type %s' % type

		table = self._code[type].table
		for obj_name in table.keys():
			code = table[obj_name]
			par = self.parse_param(code) #parse parameters given in the variable line
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

	def parse_gradient_values(self):
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

	def parse_decorations(self):
		dl = self._code['decorations'].list
		for d in dl:
			type = d['type']
			code = d['code']
			self._decoration_list.append(Decoration(type,code))

	def init_phases(self):
		phase_names = self._code['phases'].table.keys()
		for name in phase_names:
			self._procure_object('phase',name)

	def attach_phases_to_pulses(self):
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

	def parse(self):
		"""main PulseScript parsing function
		calls multiple specialized parsing routines
		"""
		#first parse anchor input
		#keys ['disp' , 'phases', 'pfg', 'delays', 'acq', 'rf', 'pulses', 'decorations', 'time']

		self.pulse_sequence = PulseSequence()

		self.parse_anchor_groups() #create list of anchor groups '_glist' & anchors 
		self.parse_time() #populate _delay_list, set timed and timing delays to anchor groups
		self.parse_rf()
		self.parse_pfg()
		self.parse_dim()

		delay_parameters = { 'length':'float', 'label':'str', 'formula':'str',
					'show_at':'str', 'hide':'bool', 'label_yoffset':'int'}
		delay_aliases = {'length':['t']}
		self.parse_variables('delays',delay_parameters,delay_aliases)

		self.parse_variables('pulses',{'phase':'str',
						'quad':'str',
						'arrow':'str',
						'label':'str',
						'length':'float',
						'edge':{'type':'str','values':['center','left','right']},
						'comp':{'type':'str','values':['before','after']} #compensation delay 2*pw/pi
						})

		self.parse_variables('acq',{'phase':'str',
						'type':'str'})

		self.parse_variables('gradients',{'length':'float',
						'strength':'float-list',
						'type':'str',
						'edge':{'type':'str','values':['center','left','right']},
						'label':'str'})
		self.parse_gradient_values()#for echo-antiecho type gradients 
									 #(comma separated strength values)
									 #convert string values to numerical values

		self.parse_variables('cpd',{'label':'str',
						'h1':'float',
						'h2':'float'})

		self.init_phases()
		self.parse_variables('phases',{'label':'str',
						'table':'int-list'})

		#todo remove temp plug (fixing phase arrays)
		self.attach_phases_to_pulses() #and fix phase arrays

		self.parse_variables('rfchan',{'label':'str',
						'nucleus':{'type':'str','values':['C','N','H','P','F']},
						'hardware':'int'
						})
		self.parse_variables('pfgchan',{'label':'str'})

		self.parse_variables('dim',{'sampling':'function','quad':'function'})
		
		self.parse_decorations()#decorations are contained in DecorLineList object

		self.assign_delays_to_channels()#decide at what channel draw delay symbols
		self.attach_delays_to_anchors()#each delay now gets start_anchor and end_anchor

		self.hide_acq_delays()
		self.copy_template_data_to_objects()#this is a temp plug has to be done before grads

		return self.pulse_sequence

	def read(self,file):

		#regexes here define headers
		self.anchors = CodeEntry('anchors') #these two are not parametrized
		self.time = CodeEntry('time')
		self.rf = CodeEntry(r'rf\s+(%s)' % label_regex_token)#these have names
		self.pfg = CodeEntry(r'pfg\s+(x|y|z|mag)')

		section_re = r'^\[([^]]+)\]$'
		hdr_re = r'^([^:]+)'

		self.sections = ('delays','dimensions','options','rfevents','pfgevents',
				'rfchan','includes','phases')

		sections = self.sections

		section_table = {}
		for sec in sections:
			table = CodeEntry(r'([^:]+)')
			self.__dict__[sec] = table 
			section_table[sec] = table

		csection = 'main'
		f = open(file)
		cline = 0

 		#if line appears wrapped (i.e. starts with empty space)
		#make sure that we are not in brand new section
		#wrapped line can't be the first in section
		flag_new_section = False

		for raw_line in f:

			cline = cline + 1
			line = CodeItem(source=raw_line,lineno=cline)

			if not (line.is_empty() or line.is_comment()):

				section = line.deliver(section_re)
				if section.is_valid():
					newsecname = section.get_content(1)
					if not newsecname in sections:
						msg = 'unknown section \'%s\', expect one of: %s'\
									% (newsecname,', '.join(sections))
						raise ParsingError(msg,section)
					if csection != newsecname:
						#make sure that new section does not start with wrapped line
						flag_new_section = True
						csection = newsecname
				else:
					if csection == 'main':
						try:
							self.rf.try_add_code(line)
							self.anchors.try_add_code(line)
							self.time.try_add_code(line)
							self.pfg.try_add_code(line)

							if line.is_wrapped():
								msg = 'lines in main section cannot start with empty space'
								raise ParsingError(msg,line)
							#no wrapped lines allowed here

							hdr = line.emit(hdr_re)
							if hdr.is_valid():
								msg = 'could not recognize header'
								raise ParsingError(msg,hdr)
							else:
								raise ParsingError('line must start with a header followed by a colon',line)
						except AddCodeSuccess:
							pass
					else:
						ctable = self.__dict__[csection]
						try:
							ctable.try_add_code(line)

							if line.is_wrapped():
								if flag_new_section:
									msg = 'lines in new section cannot start with empty space'
									raise ParsingError(msg,line)
								else:
									ctable.add_code(line)
									raise AddCodeSuccess

							msg = 'cannot add line to section %s' % csection
							raise ParsingError(msg,line)
						except AddCodeSuccess:
							pass
					flag_new_section = False
		f.close()

def parse(file):
	code = PulseScript(file)
	try:
		code.parse()
	except ParsingError as e:
		print e
