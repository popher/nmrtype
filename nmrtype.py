#!/usr/bin/python
import pulsescript 
import sys
#from PulseSequence import PulseSequence
#from Varian import Varian
#from Bruker import Bruker
#from Spinach import Spinach

code = pulsescript.parse(sys.argv[1])
#seq = PulseSequence(code)
#seq.draw()

#var = Varian(seq)
#var.print()

#var = Varian(path)
#bruk = Bruker(seq)
#bruk.print()
#spin = Spinach(seq)
#spin.print()
