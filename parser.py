from pom import PulseSequence
import functools
import sys
import util
import types
from pyparsing import ParseResults,White,Word,Literal,srange,nums,Group,\
	alphas,Optional,OneOrMore,LineEnd,alphanums,ZeroOrMore,lineno,col,\
	Regex

class ParsingError(Exception):
	def __init__(self,msg,*items):
		self.msg = msg
		self.items = items 
	def __str__(self):
		out = [t.info() for t in self.items]
		return 'parsing error: %s\nproblem item(s):\n%s' \
			% (self.msg,'\n'.join(out))

def tok2str(tok):
	if isinstance(tok,ParseResults):
		list = tok.asList()
		return tok2str(list) 
	elif type(tok) == type([]):
		out = ''
		for item in tok:
			out = out + tok2str(item)
		return out
	elif isinstance(tok,str):
		return tok 
	else:
		raise Exception('internal error type=%s' % type(tok))

def toklen(tok):
	s = tok2str(tok)
	return len(s)

class CodeItem(ParseResults):
	def __init__(self,s,loc,t):

		if isinstance(t,ParseResults):
			name = t.getName()
			tlist = t.asList()
		else:
			name = None
			tlist = t

		ParseResults.__init__(self,tlist)

		self.__ci_name = name
		self.__ci_source = s
		self.__ci_loc = loc

	def getName(self):
		return self.__ci_name

	def __str__(self):
		tok = ParseResults.__str__(self)
		lineno = self.lineno()
		col = self.col()
		return 'line=%d col=%d tokens=%s' % (lineno,col,tok) 

	def __repr__(self):
		return ParseResults.__str__(self)

	def info(self):
		src = self.source()
		line = self.lineno()
		col = self.col()
		return '(line=%3d col=%3d) %s' % (line,col,src)

	def col(self):
		return col(self.__ci_loc,self.__ci_source)

	def lineno(self):
		return lineno(self.__ci_loc,self.__ci_source)

	def source(self):
		return tok2str(self)

	def __getitem__(self,i):
		
		t = ParseResults.__getitem__(self,i)

		#here I might want to support slicing as well
		if isinstance(i,int):
			offset = 0
			for j in range(i):
				tj = ParseResults.__getitem__(self,j)
				offset += toklen(tj)
			loc = self.__ci_loc + offset
			s = self.__ci_source
			return CodeItem(s,loc,t)
		else:
			return t

def AnchorPatch(target_item):
	def anchor_name(target_item):
		return target_item[0].source()
	def anchor_num(target_item):
		if len(target_item)==1:
			return 0
		elif len(target_item)==2:
			return int(target_item[1].source())
	target_item.anchor_name = types.MethodType(anchor_name,target_item)
	target_item.anchor_num = types.MethodType(anchor_num,target_item)
	return target_item

def EventCodePatch(target_item,channel):
	#add methods for rf code item
	target_item.channel = channel
	def is_wide_event(target_item):
		if len(target_item[1])==3:
			return True
		elif len(target_item[1])==2:
			return False
		else:
			raise Exception('internal error')
	def start_anchor_source(target_item):
		if target_item.is_wide_event():
			return AnchorPatch(target_item[1][0][1])
		else:
			return AnchorPatch(target_item[1][1])

	def end_anchor_source(target_item):
		if target_item.is_wide_event():
			return AnchorPatch(target_item[1][2])
		else:
			raise Exception('internal error end_anchor() called on non-wide event')
	def anchor_source(target_item):
		if target_item.is_wide_event():
			raise Exception('internal error anchor() called on wide event')
		else:
			return target_item.start_anchor_source()

	target_item.is_wide_event = types.MethodType(is_wide_event,target_item)
	target_item.start_anchor_source = types.MethodType(start_anchor_source,target_item)
	target_item.anchor_source = types.MethodType(anchor_source,target_item)
	target_item.end_anchor_source = types.MethodType(end_anchor_source,target_item)

def RFEventCodePatch(target_item,channel):
	#add methods for rf code item
	EventCodePatch(target_item,channel)
	def pulse_type(target_item):
		return target_item[0].source()
	target_item.pulse_type = types.MethodType(pulse_type,target_item)
	target_item.event_type = 'rf'

def PFGEventCodePatch(target_item,channel):
	EventCodePatch(target_item,channel)
	def pfg_name(target_item):
		i = target_item[0]
		if len(i) == 1:
			return i[0].source()
		elif len(i) == 2:
			return i[1].source()
		else:
			raise Exception('internal error')
		
	def pfg_sign(target_item):
		i = target_item[0]
		if len(i) == 1:
			return 1
		elif len(i) == 2 and i[0].source() == '~':
			return -1
		else:
			raise Exception('internal error')

	target_item.pfg_name = types.MethodType(pfg_name,target_item)
	target_item.pfg_sign = types.MethodType(pfg_sign,target_item)
	target_item.event_type = 'pfg'
	

class Parser:
	def __init__(self,output=None,file=None):
		"""output is output PulseSequence object
		"""
		self.pom = output 
		self.grammar = None
		self._stack = []
		self.file = file
		fh = open(file,'rb')
		self.source = fh.read()

		self.anchor_group_tokens = []
		self.time_tokens = []
		self.rf_channel_tokens = util.HashableArray()
		self.pfg_channel_tokens = util.HashableArray()

	def wrap_named_tokens(f):
		"""filters named tokens
		"""
		def wrapper(self,s,loc,tok):
			#code_items = TokenList(s,loc,tok)
			code_items = []
			cloc = loc
			for t in tok:
				inc = toklen(t)
				if isinstance(t,ParseResults):
					code_items.append(CodeItem(s,cloc,t))
				cloc = cloc + inc
			f(self,code_items)
		return functools.update_wrapper(wrapper,f)

	@wrap_named_tokens
	def collect_anchor_line(self,anchor_groups):
		self.anchor_group_tokens.extend(anchor_groups)

	@wrap_named_tokens
	def collect_time_line(self,time_items):
		self.time_tokens.extend(time_items)

	@wrap_named_tokens
	def collect_rf_channel_line(self,items):
		self.collect_channel_line(items,'rf')

	@wrap_named_tokens
	def collect_pfg_channel_line(self,items):
		self.collect_channel_line(items,'pfg')

	def collect_channel_line(self,items,type):
		header = items.pop(0)
		chan = header[0].source()
		table_name = type + '_channel_tokens'
		if chan in self.__dict__[table_name]:
			table = self.__dict__[table_name][chan]
		else:
			table = []
			self.__dict__[table_name][chan] = table
		table.extend(items)

	def process_anchor_tokens(self):
		agl = self.anchor_group_tokens
		for g in agl:
			size = 1
			name = g[1].source()
			if len(g)==5:
				size = g[3].source()
			size = int(size)
			self.pom.append_anchor_group(name,size=size,source=g)

	def validate_anchor_order(self,anchor_tokens):
		"""anchors must come in the same order as in the groups

		if two successive anchors belong to the same group, their indexes
		must be increasing monotonically
		"""
		alist = []
		for a in anchor_tokens:
			if len(a) == 3:
				alist.append(a[0][1])
				alist.append(a[2])
			else:
				alist.append(a[1])

		#collect anchor group size info into ag_size dictionary
		ag_size = {}
		ag = self.pom.get_anchor_groups()
		ag_names = ag.keys()
		for name in ag_names:
			size = self.pom.get_anchor_group(name=name).get_size()
			ag_size[name] = size

		cord = -1 #ord(er) of anchor groups starts at 0
		cnum = 0  #index of anchor starts at 1
		seen = [] #full names of inspected anchors
		for anchor in alist:

			name = anchor[0].source()
			if len(anchor) == 2:
				num = int(anchor[1].source())
			else:
				num = -1

			ahandle = (name,num)

			if ahandle in seen:
				raise ParsingError('anchor repeats in same line',anchor)
			else:
				seen.append(ahandle)

			if name not in ag_names:
				raise ParsingError('anchor not defined in the anchors line',anchor)

			#check anchor index
			if num > ag_size[name]:
				raise ParsingError('index of anchor exceeds anchor group size',anchor)
			elif num == -1 and ag_size[name] >1:
				raise ParsingError('this anchor must have numeric index > 1, since its group has other anchors',anchor)
			elif ag_size[name] == 1:
				if num != -1:
					raise ParsingError('this anchor should not have numeric index, since it is the only anchor in the group',anchor)
			elif num == 0:
				raise ParsingError('anchor index must be > 0',anchor)

			ord = ag.ord(name)#order of the anchor group
			if ord < cord:
				raise ParsingError('anchor is out of sequence',anchor)
			elif ord == cord:
				#we are in the same anchor group as looked previously
				if num < cnum:
					raise ParsingError('incorrect order of anchor within group',anchor)
				elif num == cnum:
					raise Exception('internal error')
			cord = ord #remember number of group just looked at
			cnum = num

	def process_time_tokens(self):

		time_items = self.time_tokens
		#get type of first item
		item0 = time_items[0].getName()
		if item0 == 'delay':
			self.pom.insert_anchor_group(name='Origin',size=1,pos=0)
		else:
			item0 = 'anchor'

		#collect anchors
		anchors = []
		for t in time_items:
			citem = t.getName()
			if citem in ('single_anchor','double_anchor'):
				anchors.append(t)

		self.validate_anchor_order(anchors)

		#both anchors in dashed anchor groups must be from the same group
		#also collect a list of used groups
		groups = []
		for a in anchors:
			if len(a) == 3:
				anchor1 = a[0][1][0]
				anchor2 = a[2][0]
				name1 = anchor1.source()
				name2 = anchor2.source()
				if name1 != name2:
					raise ParsingError('these anchors must belong to the same group',anchor1,anchor2)
				groups.extend([name1,name2])
			else:
				name = a[1][0].source()
				groups.append(name)

		ag = self.pom.get_anchor_groups()
		for g in ag:
			if g.name not in groups:
				item = g.get_source()
				if item != None:
					raise ParsingError('this anchor group is not used in time line',item)

		#add timing items to the object model
		pom = self.pom
		c_group = ag[0]
		for item in time_items:
			name = item.getName()
			if name == 'delay':
				dly = item.source()
				d = pom.procure_delay(dly,source=item)
				c_group.set_post_delay(d)
			else:
				if name == 'single_anchor':
					a = item[1]
					a_name = a[0].source()
					a_index = 1
					if len(a) == 2:
						a_index = a[1].source()
				else: #double_anchor
					a = item[0][1]
					a2 = item[2]
					a_name = a[0].source()
					a_index = a[1].source()
					a2_name = a2[0].source()
					a2_index = a2[1].source()

				c_group = pom.get_anchor_group(a_name)
				c_group.set_timed_anchor(a_index)
				if name == 'double_anchor':
					c_group.set_timing_anchor(a2_index)
				else:
					c_group.set_timing_anchor(a_index)

	def process_channel_tokens(self):
		rf = self.rf_channel_tokens
		pfg = self.pfg_channel_tokens

		for (chan,code) in rf.items():
			for item in code:
				RFEventCodePatch(item,chan)
				self.pom.add_event(item)
		for (chan,code) in pfg.items():
			for item in code:
				PFGEventCodePatch(item,chan)
				self.pom.add_event(item)

	def set_grammar(self,grammar):
		self.grammar = grammar

	def process_tokens(self,s,loc,tok):
		self.process_anchor_tokens()
		self.process_time_tokens()
		self.process_channel_tokens()

	def run(self):
		return self.grammar.parseString(self.source)

	def raise_time_line_error(self,s,loc,expr,err):
		raise ParseError('could not parse time line',loc)

def parse(file):

	pom = PulseSequence()
	ps = Parser(output=pom,file=file)

	#Pulse Script grammar
	#edit carefully!
	W = White(ws=' \t\r')
	INT = Word(srange('[1-9]'),bodyChars=nums)
	TOKEN = Group(Word(alphas) + Optional(INT))
	AG_DEF = Group(Literal('@') + Word(alphas) + \
		Optional(Literal('[') + INT + Literal(']'))).setResultsName('anchor_group_def')

	AG_LINE = (Literal('anchors:') + OneOrMore(W + AG_DEF) + \
			Optional(W) + LineEnd()).setParseAction(ps.collect_anchor_line)

	SINGLE_ANCHOR = Group(Literal('@') + TOKEN).setResultsName('single_anchor')
	DOUBLE_ANCHOR = Group(SINGLE_ANCHOR + Word('-') + TOKEN).setResultsName('double_anchor')
	ANCHOR = DOUBLE_ANCHOR | SINGLE_ANCHOR 
	DELAY = Group(Word(alphas,bodyChars=alphanums)).setResultsName('delay')

	TIME_LINE = Literal('time:') + Optional(W + SINGLE_ANCHOR) + \
			ZeroOrMore(W+DELAY+W+ANCHOR) + Optional(W) + LineEnd()
	TIME_LINE.setParseAction(ps.collect_time_line)

	PULSE = Group( ( Literal('90') |Literal('180')|Literal('lp')) + SINGLE_ANCHOR).setResultsName('pulse')
	WIDE_PULSE = Group( Literal('cpd') + DOUBLE_ANCHOR ).setResultsName('wide_pulse')
	ACQ = Group( Literal('acq') + DOUBLE_ANCHOR ).setResultsName('acq')

	RF_CHAN_NAME = Group(Word(alphanums)).setResultsName('channel')
	RF_LINE = Literal('rf') + W + RF_CHAN_NAME \
			+ Literal(':') + OneOrMore(W + (WIDE_PULSE|PULSE|ACQ)) + Optional(W) + LineEnd()
	RF_LINE.setParseAction(ps.collect_rf_channel_line)

	PFG_EVENT_TOKEN = Group(Optional(Literal('~')) + TOKEN)
	PFG = Group( PFG_EVENT_TOKEN + SINGLE_ANCHOR).setResultsName('pfg')
	WIDE_PFG = Group( PFG_EVENT_TOKEN + DOUBLE_ANCHOR).setResultsName('wide_pfg')

	PFG_CHAN_NAME = Regex('x|y|z|mag')
	PFG_LINE = Literal('pfg') + W + Group(PFG_CHAN_NAME).setResultsName('channel') \
			+ Literal(':') + OneOrMore(W + (WIDE_PFG|PFG)) + Optional(W) + LineEnd()
	PFG_LINE.setParseAction(ps.collect_pfg_channel_line)

	grammar = OneOrMore(AG_LINE + TIME_LINE + OneOrMore(RF_LINE|PFG_LINE))
	grammar.parseWithTabs()
	grammar.leaveWhitespace()
	grammar.setParseAction(ps.process_tokens)
	ps.set_grammar(grammar)

	ps.run()
	return pom
