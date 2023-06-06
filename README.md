IR_alignment_gcode is a python application i (TLD) created for automated IR UART alignment testing.

I ran it on python 3.10.10  with the following packages:
- matplotlib      3.7.1
- numpy           1.24.2
- opencv-python   4.7.0.72
- openpyxl        3.1.2
- pyserial        3.5

basic usage instructions:
- attach IR QRD PCB to 3d printer carriage (using 3d-printed bracket)
- connect 3D printer serial port to PC (almost all printers still come with a USB serial port, even though SD-cards are the way most people run Gcode)
- attach WEB PCB to print-bed, program it using the provided firmware, setup the UART (if RX is tested, PCB debug serial will repeat what it reads from IR RX, and vice versa)
- run IR_alignment_gcode.py in a terminal
- enter the COM ports it asks for in the commandline, then tab to the GUI window
- press 'h' to auto-home the printer (NOTE: window will not respond untill it's done)
- press 'r' to reset position (and write position)
- if offset is not calibrated, use 'WASD'+'q','e' keys to move the head untill the LED and photodiode look aligned (doesn't need to be 100% perfect)
- press spacebar to start testing (can be paused with spacebar as well)
- once it's done it will show a plot (matplotlib) and save to excel
- if it crashses, it will attempt to save the data it gathered so far to 'output.xlsx'
- you can pause the testing and press 'v' to show a graph at any time
- press 'l' to disable steppers (if you're done, just to avoid overheating)
- press 'k' to manually save to an excel file (can be done mid-test, but you should want to pause)
- you can move the view with middle-mouse-button dragging, zoom by scrolling, turn off the grid with 'g' and change zoom mode (centered vs mouse-bound) with 'z'


exceptions and debugging for new setups:
- for my home printer (Artillery Sidewinder X1) i needed to add the currentPosScalars (in gcode_stuff.py)
