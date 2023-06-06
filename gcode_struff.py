

## BAD HACK WARNING!!!:
## while the Ultimaker 2 at work reports its current position (the stuff after 'Count') in millimeters,
##  my home printer seems to prefer outputting raw stepper counts.
## So, to fix things, i added this:
currentPosScalars = [1.0, 1.0, 1.0] # [x,y,z] UltiMaker 2 (at work) outputs in millimeters directly
# currentPosScalars = [1/80.12, 1/80.12, 1/399.78] # [x,y,z] Artillery Sidewinder X1 running custom marlin 2.1.2 outputs in stepper steps. These are the default EEPROM values
## TODO:
##  request the steps per millimeter at the start! (or at least attempt to determine the existance of this setting)

## some GCODE commands:
GCODE_AUTO_HOME = b'G28\n'
GCODE_GET_CURRENT_POSITION = b'M114\n'
GCODE_DISABLE_STEPPERS = b'M18\n' # (M84 does the same thing) disables steppers
GCODE_DISABLE_AUTO_REPORT_POSITION = b'M154 S0\n'
GCODE_DISABLE_AUTO_REPORT_TEMPERATURE = b'M155 S0\n'
GCODE_MARLIN_OK = b'ok\n' # (not Gcode) Marlin FW should respond with 'ok'(+LF) to any acceptable command
def G0(xyzPos: tuple[float,float,float], feedrate:float=(-1), decimals:int=3):
    """ construct G0 (linear move) command. \n
        'xyzPos' is 3d position in millimeters \n
        'feedrate' is (max) speed in millimeters/minute \n
        'decimals' is how many decimal points to round to """
    prefixes = (b' X', b' Y', b' Z', b' F')
    floatToBytes = lambda val : str(round(float(val), decimals)).encode()
    gcode = b'G0'
    for i in range(min(len(xyzPos), 3)):
        gcode += prefixes[i] + floatToBytes(xyzPos[i])
    if(feedrate > 0):
        gcode += prefixes[3] + floatToBytes(feedrate)
    gcode += b'\n' # always gotta add a LineFeed
    return(gcode)
def _parseM114_single(data: bytes) -> tuple[float,float,float]:
    output = [-1,-1,-1]
    parsing = True; dataLeftToParse = data
    AXIS_INDICATOR = b':' # e.g.: b'X:1.00' means X axis has value 1.00 (mm)
    AXIS_CHAR_TO_INDEX = {b'X' : 0,  b'Y' : 1,  b'Z' : 2} # NOTE: extruder values are currently just ignored
    while(parsing):
        colonIndex = dataLeftToParse.find(AXIS_INDICATOR)
        if(colonIndex < 0):
            print("couldn't find another colon, ending parsing", dataLeftToParse)
            parsing = False; break
        splitData = dataLeftToParse.split(AXIS_INDICATOR)
        ## first, decode the axis char:
        axisChar = splitData[0].strip()
        if(len(axisChar) != 1):
            print("failed to find axisChar:", axisChar, dataLeftToParse)
            parsing = False; break
        if(axisChar not in AXIS_CHAR_TO_INDEX): # search for matching key (dict)
            if(axisChar != b'E'): # extruder values can simply be ignored in this project
                print("axisChar not in AXIS_CHAR_TO_INDEX", axisChar)
            if(len(splitData) > 2): # if there are still other axis to parse after this one, skip this one and continue
                dataLeftToParse = chr(splitData[1][-1]).encode() + dataLeftToParse.removeprefix(splitData[0] + AXIS_INDICATOR + splitData[1]) # delete untill the next AXIS_INDICATOR, except for 1 char (next axisChar)
                continue
            else: # if there is no data after this one anyway, just end the loop
                parsing = False; break
        axis = AXIS_CHAR_TO_INDEX[axisChar]
        ## now, determine the value
        valueStr = splitData[1].strip() # start with garbage still attached
        for byte in valueStr: # loop through characters to find where the number ends
            char = chr(byte).encode()
            if(char.isalpha() or (char == b' ')):
                valueStr = valueStr.split(char)[0] # keep everything before the current character
                break
        try:    value = float(valueStr)
        except: print("failed to parse valueStr", valueStr);  parsing = False; break
        output[axis] = value #  axis data parsed
        if(len(splitData) > 2): # if there are still other axis to parse after this one, skip this one and continue
            dataLeftToParse = chr(splitData[1][-1]).encode() + dataLeftToParse.removeprefix(splitData[0] + AXIS_INDICATOR + splitData[1]) # delete untill the next AXIS_INDICATOR, except for 1 char (next axisChar)
            if(len(dataLeftToParse) < 3):
                parsing = False
                # if(len(dataLeftToParse) > 0):
                print("data left over after parsing end?:", dataLeftToParse)
        else: # if there is no data after this one anyway, just end the loop
            parsing = False; break
    return(output)
def parseM114(data: bytes) -> tuple[bool, tuple[float,float,float], tuple[float,float,float]]:
    POS_SEPERATOR = b'Count'
    splitPoses = data.split(POS_SEPERATOR)
    if(len(splitPoses) != 2):
        print("can't parseM114():", data, splitPoses)
        return(False, (0,0,0), (0,0,0))
    targetPos = _parseM114_single(splitPoses[0]) # the first thing it prints is the target pos (set by the last G0)
    currentPos = _parseM114_single(splitPoses[1]) # it also prints the 'Count' pos (a.k.a. the current position)
    for i in range(len(currentPos)):
        currentPos[i] *= currentPosScalars[i]
    return(True, targetPos, currentPos)



"""
an example of some Gcode interpretation. all things after ';' is my commentary (added after-the-fact), '->' indicates what i sent
;->M114
X:0.00Y:0.00Z:0.00E:0.00 Count X: 0.00Y:0.00Z:0.00E:0.00
ok
;->M114
X:0.00Y:0.00Z:0.00E:0.00 Count X: 0.00Y:0.00Z:0.00E:0.00
ok
;->G28
ok     ;(printed AFTER it was done homing)
;->G28
ok     ;(printed AFTER it was done homing)
;->M114
X:0.00Y:225.00Z:219.00E:0.00 Count X: 0.00Y:225.00Z:219.00E:0.00
ok
;->G0 X100 F100 ;(a slow move)
ok
;->M114
X:100.00Y:225.00Z:219.00E:0.00 Count X: 2.46Y:225.00Z:219.00E:0.00    ; so the first one is target position, and the 'Count' is the current position
ok
;->M114
X:100.00Y:225.00Z:219.00E:0.00 Count X: 5.57Y:225.00Z:219.00E:0.00
ok
;->M114
X:100.00Y:225.00Z:219.00E:0.00 Count X: 8.18Y:225.00Z:219.00E:0.00
ok
"""