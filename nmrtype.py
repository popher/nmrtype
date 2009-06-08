#!/usr/bin/python
import parser 
import sys
#from PulseSequence import PulseSequence
#from Varian import Varian
#from Bruker import Bruker
#from Spinach import Spinach

#code = parser.parse(sys.argv[1])

code = parser.parse('tests/fastNhsqc.seq')
	

#seq = PulseSequence(code)
#seq.draw()

#var = Varian(seq)
#var.print()

#var = Varian(path)
#bruk = Bruker(seq)
#bruk.print()
#spin = Spinach(seq)
#spin.print()
