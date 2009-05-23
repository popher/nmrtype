class HashableArray:
	"""array, whose elements are accessible by keys
	if they were originally stored with keys

	uniqueness of all keys is strictly enforced
	"""
	def __init__(self):
		self.array = [] #array contains ordered list of values
		self.table = {} #table key -> ord mapping 
		self.keys = [] #keys contains ordered list of keys

	def _new_key(self):
		import random
		key = 'key'
		if len(self.array) > 0:
			key = self.table.keys()[0]
		while key in self.table.keys():
			key = random.randint(1,1000000)
		return key

	def put(self,key=None,value=None):
		if key == None:
			key = self._new_key()

		if self.table.has_key(key):
			ord = self.table[key]
			self.array[ord] = value
		else:
			self.array.append(value)	
			self.keys.append(key)
			ord = len(self.array) - 1
			self.table[key] = ord 

	def get(self,key=None,ord=None):
		if key != None and ord != None:
			raise TypeError('must use either key or ord in HashableArray.get()')
		if key != None:
			return self.array[self.table[key]]
		if ord != None:
			return self.array[ord]

	def ord(self,key):
		return self.table[key]

	def keys(self):
		return self.keys

	def values(self):
		return self.array

	def size(self):
		return len(self.keys)

	def next(self):
		if self._iter_i >= len(self.array):
			raise StopIteration
		else:
			i = self._iter_i
			self._iter_i = i + 1
			return self.array[i]

	def __iter__(self):
		self._iter_i = 0
		return self
