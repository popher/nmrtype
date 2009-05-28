from pom import PulseSequence
import functools
import sys
from pyparsing import ParseResults,White,Word,Literal,srange,nums,Group,\
	alphas,Optional,OneOrMore,LineEnd,alphanums,ZeroOrMore,lineno,col

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

class SourceRef:
	def __init__(self,loc,tok,file):
		if loc == None:
			raise Exception('loc must be positive integer')
		self.loc = loc
		self.tok = tok
		#self.source = ''.join(tok) 
		self.file = file
	def __str__(self):
		return ''.join(self.tok)
S = SourceRef

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
		return 'CodeItem: ' +  ParseResults.__str__(self)

	def __repr__(self):
		return self.__str__()

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

class ParserError(Exception):
	def __init(self,msg,loc):
		self.msg = msg
		self.loc = loc
	def __str__(self):
		pass

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

	def process_anchor_tokens(self):
		agl = self.anchor_group_tokens
		for g in agl:
			size = 1
			name = g[1].source()
			if len(g)==5:
				size = g[3].source()
			size = int(size)
			print 'adding anchor group %s[%d]' % (name,size)
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

		print alist

		sys.exit()

		a = {}
		if a['type'] == 'double-anchor':
			alist.append(a['anchor1'])
			alist.append(a['anchor2'])
		else:
			alist.append(a['anchor'])

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
			name = anchor.get_content(1)
			num = anchor.get_content(2)
			print anchor
			if num == None:
				num = -1 
			else:
				num = int(num)
			ahandle = '%s%d' % (name,num)

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
				print name, ag_size[name]
				raise ParsingError('this anchor must have numeric index > 1',anchor)
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

	def set_grammar(self,grammar):
		self.grammar = grammar

	def process_tokens(self,s,loc,tok):
		self.process_anchor_tokens()
		self.process_time_tokens()

	def run(self):
		return self.grammar.parseString(self.source)

	def raise_time_line_error(self,s,loc,expr,err):
		raise ParseError('could not parse time line',loc)

def parse(file):

	pom = PulseSequence()
	ps = Parser(output=pom,file=file)

	#Pulse Script grammar
	W = White(ws=' \t\r')
	INT = Word(srange('[1-9]'),bodyChars=nums)
	AG_DEF = Group(Literal('@') + Word(alphas) + \
		Optional(Literal('[') + INT + Literal(']'))).setResultsName('anchor_group_def')

	AG_LINE = (Literal('anchors:') + OneOrMore(W + AG_DEF) + \
			Optional(W) + LineEnd()).setParseAction(ps.collect_anchor_line)

	SINGLE_ANCHOR = Group(Literal('@') + Group(Word(alphas) + Optional(INT))).setResultsName('single_anchor')
	DOUBLE_ANCHOR = Group(SINGLE_ANCHOR + Word('-') + Group(Word(alphas) + Optional(INT))).setResultsName('double_anchor')
	ANCHOR = DOUBLE_ANCHOR | SINGLE_ANCHOR 
	DELAY = Group(Word(alphas,bodyChars=alphanums)).setResultsName('delay')

	TIME_LINE = Literal('time:') + Optional(W + SINGLE_ANCHOR) + \
			ZeroOrMore(W+DELAY+W+ANCHOR) + Optional(W) + LineEnd()
	TIME_LINE.setParseAction(ps.collect_time_line)

	grammar = OneOrMore(AG_LINE + TIME_LINE)
	grammar.parseWithTabs()
	grammar.leaveWhitespace()
	grammar.setParseAction(ps.process_tokens)
	ps.set_grammar(grammar)

	ps.run()
	return pom
