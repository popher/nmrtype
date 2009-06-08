class HashableArray:
	"""array, whose elements are accessible by keys
	if they were originally stored with keys

	uniqueness of all keys is strictly enforced
	"""
	def __init__(self):
		self._array = [] #array contains ordered list of values
		self._table = {} #table key -> ord mapping 
		self._keys = [] #keys contains ordered list of keys

	def _new_key(self):
		import random
		key = 'key'
		if len(self._array) > 0:
			key = self._table.keys()[0]
		while key in self._table.keys():
			key = random.randint(1,1000000)
		return key

	def __str__(self):
		out = []
		for key in self._keys:
			i = self._table[key]
			val = self._array[i]
			out.append('%s=%s' % (key,val))
		return '\n'.join(out)

	def __getitem__(self,key):
		if isinstance(key,int):
			return self.get(ord=key)
		elif isinstance(key,str):
			return self.get(key=key)
		else:
			raise TypeError

	def __setitem__(self,key,item):
		if isinstance(key,int):
			self.insert(pos=key,value=item)
		elif isinstance(key,str):
			self.insert(key=key,value=item)
		else:
			raise TypeError

	def __contains__(self,key):
		if key in self._keys:
			return True
		else:
			return False

	def items(self):
		out = []
		for key in self._keys:
			ord = self._table[key]
			val = self._array[ord]
			out.append((key,val))
		return out

	def insert(self,key=None,value=None,pos=None):
		if key == None:
			key = self._new_key()

		if self._table.has_key(key):
			raise TypeError('item %s already exists' % key)
		else:
			if pos != None:
				if pos > len(self._array) - 1:
					raise IndexError('index in HashArray.put() out of range')
				for k in self._table.keys():
					i = self._table[k]
					if i >= pos:
						self._table[k] = i + 1
			else:
				pos = len(self._array)
			self._array.insert(pos,value)	
			self._keys.insert(pos,key)
			self._table[key] = pos 

	def get(self,key=None,ord=None):
		if key != None and ord != None:
			raise TypeError('must use either key or ord in HashableArray.get()')
		if key != None:
			return self._array[self._table[key]]
		if ord != None:
			return self._array[ord]

	def ord(self,key):
		return self._table[key]

	def keys(self):
		return self._keys

	def values(self):
		return self._array

	def size(self):
		return len(self._keys)

	def next(self):
		if self._iter_i >= len(self._array):
			raise StopIteration
		else:
			i = self._iter_i
			self._iter_i = i + 1
			return self._array[i]

	def __iter__(self):
		self._iter_i = 0
		return self
