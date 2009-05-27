from pom import PulseSequence
import functools
from pyparsing import *

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

class Token(ParseResults):
	def __init__(self,s,loc,t):
		#maybe need to be more careful about getName()
		ParseResults.__init__(self,t,name=t.getName())
		self._token_source = s
		self._token_loc = loc
	def col(self):
		return col(self._token_loc,self._token_source)
	def lineno(self):
		return lineno(self._token_loc,self._token_source)

class TokenList:

	def __init__(self,s,loc,tok):
		self.source = s
		self.loc_origin = loc
		self._tokens = tok
		self.items = []

		cloc = loc

		#extract named tokens
		for t in tok:
			inc = self.toklen(t)
			if isinstance(t,ParseResults):
				print t.getName()
				self.items.append(Token(s,cloc,t))
			cloc = cloc + inc

	def __getitem__(self,i):
		return self.items[i]

	def tok2str(self,tok):
		if isinstance(tok,ParseResults):
			list = tok.asList()
			return self.tok2str(list) 
		elif type(tok) == type([]):
			out = ''
			for item in tok:
				out = out + self.tok2str(item)
			return out
		elif isinstance(tok,str):
			return tok 
		else:
			raise Exception('internal error type=%s' % type(tok))
	
	def toklen(self,tok):
		s = self.tok2str(tok)
		return len(s)

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

	def parse_anchor_def(self,s,loc,tok):
		name = tok[1]
		size = 1
		if len(tok)==5:
			size = tok[3]
		self.pom.append_anchor_group(name,size=int(size),source=S(loc,tok,self.file))

	def parse_single_anchor(self,s,loc,tok):
		return ParseResults(tok,name='single_anchor',asList=False)

	def parse_double_anchor(self,s,loc,tok):
		return ParseResults(tok,name='double_anchor',asList=False)

	def wrap_tokens(f):
		"""goes through tokens, 
		puts them into Toklist
		"""
		def wrapper(self,s,loc,tok):
			code_items = TokenList(s,loc,tok)
			f(self,code_items)
		return functools.update_wrapper(wrapper,f)

	@wrap_tokens
	def parse_time_line(self,time_items):

		#get type of first item
		item0 = time_items[0].getName()
		if item0 == 'delay':
			self.pom.insert_anchor_group(name='Origin',size=1,pos=0)
		else:
			item0 = 'anchor'

		#make sure that delays and anchors alternate
		pitem = None 
		for t in time_items:
			print t
			print 'line=%d col=%d' % (t.lineno(),t.col())
			citem = t.getName()
			if citem in ('single_anchor','double_anchor'):
				citem = 'anchor'
			if citem == pitem:
				msg = 'repeated %s in time line;' % citem
				msg = msg + ' ' + 'delays and anchors must alternate' 
				raise ParsingError(msg,t)

	def set_grammar(self,grammar):
		self.grammar = grammar

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
	AG_DEF = Literal('@') + Word(alphas) + \
		Optional(Literal('[') + INT + Literal(']'))
	AG_DEF.setParseAction(ps.parse_anchor_def)

	AG_LINE = Literal('anchors:') + OneOrMore(W + AG_DEF) + \
			Optional(W) + LineEnd()

	SINGLE_ANCHOR = Group(Literal('@') + Group(Word(alphas) + Optional(INT))).setResultsName('single_anchor')
	DOUBLE_ANCHOR = Group(SINGLE_ANCHOR + Word('-') + Group(Word(alphas) + Optional(INT))).setResultsName('double_anchor')
	ANCHOR = DOUBLE_ANCHOR | SINGLE_ANCHOR 

	DELAY = Group(Word(alphas,bodyChars=alphanums)).setResultsName('delay')

	TIME_LINE = Literal('time:') + Optional(W + SINGLE_ANCHOR) + \
			ZeroOrMore(W+DELAY+W+ANCHOR) + Optional(W) + LineEnd()

	TIME_LINE.setFailAction(ps.raise_time_line_error)
	TIME_LINE.setParseAction(ps.parse_time_line)
	grammar = AG_LINE + TIME_LINE.setResultsName('parse_line')
	grammar.parseWithTabs()
	grammar.leaveWhitespace()
	ps.set_grammar(grammar)

	ps.run()
	return pom
