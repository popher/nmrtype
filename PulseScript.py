#!/usr/bin/python
import sys
import os
import re
from PulseSequence import PulseSequence

label_regex_token = '[a-zA-Z0-9_]+'
anchor_basename_token = '[a-z]+'
element_name_regex_token = '[a-zA-Z0-9]+'
expression_regex_token = '[\^\_\{\}a-zA-Z0-9\*\/\(\)]+'
blanks_re = re.compile(r'\s\s+')

"""@package docstring
PulseScript reads the NMR pulse sequence written in the PulseScript code
this is the only module that deals with the PulseScript directly
"""

class CodeLineSuccess:
	pass

class CodeLine:
	regex = None
	empty = re.compile(r'^\s*$')
	code = None
	def __init__(self,regex):
		self.regex = re.compile(regex)

	def __str__(self):
		if self.code == None:
			return ''
		return self.code
	def try_add_code(self,code):
		m = self.regex.match(code)
		if m:
			code = m.group(1).strip()
			if self.code:
				code = self.code + ' ' + code
			self.code = code
			raise CodeLineSuccess()

class CodeLineArray(CodeLine):
	def __init__(self,regex):
		CodeLine.__init__(self,regex)
		self.table = {}
		self.item_order = []
	def __str__(self):
		out = []
		for item in self.item_order:
			code = self.table[item]
			out.append('%s: %s' % (item,code))
		return '\n'.join(out)
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

class PulseScript:
	"""PulseScript code object
	"""
	def __init__(self):
		"""among other things initializes head anchor group
		but does not create first delay

		most global drawing parameters entered here
		"""
		self.read()

	def validate_anchor_order(self,code):
		#todo get this done before release
		pass

	def parse_time(self):
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

	def parse_anchor_groups(self):
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

	def _parse_variables(self,type,key_table,key_aliases={}):

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

	def parse(self):
		"""main PulseScript parsing funtion
		calls multiple specialized parsing routines
		"""
		#first parse anchor input
		#keys ['disp' , 'phases', 'pfg', 'delays', 'acq', 'rf', 'pulses', 'decorations', 'time']

		seq = PulseSequence()

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

		return seq

	def read(self):

		#lines for the
		self.anchors = CodeLine(r'^\s*anchors\s*:(.*)$') #these two are not parametrized
		self.time = CodeLine(r'^\s*time\s*:(.*)$')
		self.rf = CodeLineArray(r'^\s*rf\s+(%s)\s*:(.*)$' % label_regex_token)#these have name
		self.pfg = CodeLineArray(r'^\s*pfg\s+(x|y|z|mag)\s*:(.*)$')

		empty = re.compile(r'^\s*$')
		comment = re.compile(r'^\s*#.*$')
		section = re.compile(r'^\[([^]]+)\]\s*$')

		sections = ('delays','dimensions','options','rfevents','pfgevents',
				'rfchan','includes','phases')

		section_table = {}
		for sec in sections:
			table = CodeLineArray(r'^\s*(.*)\s*:(.*)$')
			self.__dict__[sec] = table 
			section_table[sec] = table

		csection = 'main'
		lines = sys.stdin.readlines()	
		for line in lines:
			if not (empty.match(line) or comment.match(line)):
				sm = section.match(line)
				if sm:
					newsec = sm.group(1)
					if not section_table.has_key(newsec):
						raise ParsingError('unknown section \'%s\', expect one of: %s'\
									% (newsec,', '.join(sections)))
					csection = newsec	

				if csection == 'main':
					try:
						self.anchors.try_add_code(line)
						self.time.try_add_code(line)
						self.rf.try_add_code(line)
						self.pfg.try_add_code(line)
						raise ParsingError('could not recognize code line: %s' % line)
					except CodeLineSuccess:
						pass
				else:
					ctable = self.__dict__[csection]
					try:
						ctable.try_add_code(line)
					except CodeLineSuccess:
						pass
