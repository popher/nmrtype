nmrtype aims to implement a target platform independent NMR pulse sequence code generator

name "nmrtype" was chosen because part of the goal is helping to easily "type in" the pulse sequence while minimizing the necessary input and maximizing readability of the code

nmrtype uses new pulse sequence definition language that is based on "anchors" - or control points within the pulse sequence. Events are associated with those control points and are entered on a line that corresponds to a particular channel

In addition to generating code, nmrtype currently produces a bitmap image of the pulse sequence. Vector graphics output will be added after core code generation is developed.

This project is based on the [NMR pulse sequence drawing extension](http://nmrwiki.org/wiki/index.php?title=Pulse_sequence_drawing) used at [NMR Wiki](http://nmrwiki.org). Please take a look at this extension to get an idea about the nmrtype pulse sequence syntax.