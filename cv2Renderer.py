"""
TODO:
- better UI code in general?
- use cv2's builtin trackbar (slider) code!

"""

import cv2          # opencv-python
import numpy as np  # general math library
import time         # used for FPS counter
from typing import Callable # justt used for a callback typehint


## some basic math functions for 2D cartesian systems:
def distAngleBetwPos(posOne, posTwo): #returns distance and angle between 2 positions
    """get distance and angle between 2 positions (2-sized arrays/lists)"""
    funcPosDelta = [posTwo[0]-posOne[0], posTwo[1]-posOne[1]]
    funcDistance = 0 #var init
    funcAngle = np.arctan2(funcPosDelta[1], funcPosDelta[0]) 
    if(abs(funcPosDelta[0]) < 0.0001): #sin(angle) can be 0, which results in divide by 0 errors.
        funcDistance = abs(funcPosDelta[1])
    elif(abs(funcPosDelta[1]) < 0.0001): #floating point error, alternatively you could check the angle
        funcDistance = abs(funcPosDelta[0])
    else:
        funcDistance = funcPosDelta[1]/np.sin(funcAngle)  #soh
        #funcDistance = funcPosDelta[0]/np.cos(funcAngle)  #cah
    return(np.array([funcDistance, funcAngle])) #return an np.array because the alternative is a tuple, which is (needlessly) immutable

def distSqrdBetwPos(posOne, posTwo): #returns distance^2 between 2 positions (useful for efficient distance thresholding)
    """get distance squared between 2 positions (2-sized arrays/lists), useful for efficient distance thresholding (compare to threshold squared)"""
    return((posTwo[0]-posOne[0])**2 + (posTwo[1]-posOne[1])**2)  #A^2 + B^2 = C^2

def distAnglePosToPos(funcRadius, funcAngle, funcPos): #returns a new pos given an angle, distance and starting pos
    """get position that is the entered distance and angle away from the entered position"""
    return(np.array([funcPos[0] + funcRadius * np.cos(funcAngle), funcPos[1] + funcRadius * np.sin(funcAngle)]))

ASA = lambda scalar, inputArray : [scalar + entry for entry in inputArray]



class cv2WindowHandler():
    """ a handler for a cv2 window. This class does not render things,
         it just handles the basic interactions with the OS,
         like opening, closing changing resolution, etc."""
    def __init__(self, resolution: tuple[int,int], windowName:str='(cv2) window'):
        """ initialize cv2 window """
        self.keepRunning = False # intended to be set to false by the UI handler (or any other code of course) when the window should close
        self.window = np.zeros((resolution[1],resolution[0],3), dtype=np.uint8)
        # self.oldWindowSize: tuple[int, int] = self.window.get_size()
        self._windowName = windowName # keep around to destroy the right window in __del__
        # cv2.namedWindow(self._windowName, flags=(cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO | cv2.WINDOW_GUI_NORMAL)) # cv2's windows are resizable BUT, it just warpes the image!
        cv2.namedWindow(self._windowName, flags=(cv2.WINDOW_AUTOSIZE | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)) #
        # self.frameRefresh() # not needed, as cv2.namedWindow() handles all the basic initialization
        self.keepRunning = True

        ## now some underwater stuff:
        self.mousePos :list[int,int]=[0,0] # updated in the _mouseCallbackWrapper
        self.mouseCallbackFunc: Callable[[int,int,int,int,'cv2WindowHandler'], None] = None # args are: (event, mouseX, mouseY, flags, self)
        cv2.setMouseCallback(self._windowName, self._mouseCallbackWrapper, self) # required to retrieve the mouse position at any given time (not just during a UI event)

        self.keyboardCallbackFunc: Callable[[int,'cv2WindowHandler'], None] = None # args are: (keycode, self)

    def __del__(self):
        self.end()

    def checkWindowOpen(self):
        """ checks whether the cv2 window is still open or not
            cv2 does not generate sny sort of event, it just lets the user close stuff at any time """
        return(cv2.getWindowProperty(self._windowName, cv2.WND_PROP_VISIBLE) > 0.0)

    def end(self):
        """deinitialize the window (required for ending without crashing)"""
        if(self.checkWindowOpen()): #if the window never started, quit might error out or something stupid
            print("quitting cv2 window:", self._windowName)
            cv2.destroyWindow(self._windowName)
            self.keepRunning = False # should already have been done, but just to be sure

    def frameRefresh(self):
        """push the drawn frame(buffer) to the display"""
        if(not self.checkWindowOpen()): # running imshow() after the window closed will re-open it
            self.keepRunning = False
        else:
            cv2.imshow(self._windowName, self.window)
            keycode = cv2.waitKey(1) # if you only use imshow when you have a new result to display, then windows (OS) thinks the window is not responding (and has crashed), when it's actually fine
            if(keycode >= 0):
                self._keyboardCallbackWrapper(keycode)
    
    @staticmethod
    def _mouseCallbackWrapper(event:int, mouseX:int, mouseY:int, flags:int, self:'cv2WindowHandler'):
        """ a wrapper for the mouse callback """
        self.mousePos[0] = mouseX;   self.mousePos[1] = mouseY # store the mouse position, sothat it can be requested at any time (instead of only in events)
        if(callable(self.mouseCallbackFunc)):
            self.mouseCallbackFunc(event, mouseX, mouseY, flags, self)
    
    def _keyboardCallbackWrapper(self, keycode:int):
        """ called when cv2.waitKey(0) returns something other than -1 """
        if(keycode == 27): # ASCII escape
            self.keepRunning = False # (exiting when 'esc' key is pressed)
        if(callable(self.keyboardCallbackFunc)):
            self.keyboardCallbackFunc(keycode, self)


class cv2Drawer():
    def __init__(self, windowHandler:cv2WindowHandler, drawSize:tuple[int,int]=None, drawOffset:tuple[int,int]=(0,0), sizeScale:float=15, invertYaxis:bool=True):
        self.windowHandler = windowHandler
        self.drawSize :tuple[int,int]= ((int(drawSize[0]),int(drawSize[1])) if (drawSize is not None) else (self.windowHandler.window.shape[1], self.windowHandler.window.shape[0])) # width and height of the display area (does not need to be 100% of the window)
        self.drawOffset :tuple[int,int]= (int(drawOffset[0]), int(drawOffset[1])) #draw position offset, (0,0) is topleft
        self.viewOffset :list[float,float]= [0.0, 0.0] #'camera' view offsets, changing this affects the real part of realToPixelPos()
        self.sizeScale :float= sizeScale #pixels per real_unit
        self.invertYaxis :bool= invertYaxis #openCV has pixel(0,0) in the topleft, so this just flips the y-axis when drawing things

        self.minSizeScale = 5.0 # note: the unit for sizeScale is pixels per real_unit, so there's no need to make this too small
        self.maxSizeScale = 2000.0 # a reasonable limit to how much you can zoom in
        # self.maxSizeScaleWithCar = 500.0 # zooming in too much makes drawing (the car) really slow (because it has to render the car image at such a high resolution)
        self.centerZooming = False # whether zooming (using the scroll wheel) uses the center of the screen (or the mouse position)

        ## NOTE: openCV prefers BGR by default
        # [  0,255,255] #yellow
        # [255, 50,  0] #dark blue
        # [  0,127,127] #faded yellow
        # [127, 25,  0] #faded blue
        # [  0, 20,127] #faded red
        # [255,220,  0] #light blue

        self.bgColor = [50,50,50] # dark gray
        
        self.normalFontColor = [200, 200, 200]
        self.normalFont = cv2.FONT_HERSHEY_SIMPLEX
        self.normalFontScale = 0.75
        self.normalFontThickness = 2
        self.normalFontSize = lambda string : cv2.getTextSize(string, self.normalFont, self.normalFontScale, self.normalFontThickness)[0] # might break, if fontsizes change
        
        self.gridColor = [100,100,100] # light gray
        self.gridFont = self.normalFont
        self.gridFontScale = self.normalFontScale * (2/3) #
        self.gridFontThickness = 1
        self.gridFontSize = lambda string : cv2.getTextSize(string, self.gridFont, self.gridFontScale, self.gridFontThickness)[0] # might break, if fontsizes change
        
        self.movingViewOffset = False
        self.prevViewOffset = (self.viewOffset[0], self.viewOffset[1])
        self.movingViewOffsetMouseStart = [0,0]
        
        self.FPStimer = time.time()
        self.FPSdata = []
        self.FPSdisplayInterval = 0.25
        self.FPSdisplayTimer = time.time()
        self.FPSstrings = []
        
        self.statDisplayTimer = time.time()
        self.statDisplayInterval = 0.1
        self.statStrings = []

        # self.lastFilename = "" # the name of a loaded file
        self.debugText = [] # a list of text to show on screen

        self.drawGrid = True #a simple grid to help make clear how big units of measurement are. (TBD in 3D rendering mode!)

        if(self.windowHandler.mouseCallbackFunc is None): # unless a custom callback is already set for the windowHandler
            self.windowHandler.mouseCallbackFunc = self._mouseCallbackWrapper # default the windowHandler's callback to this 
        self.mouseCallbackFunc: Callable[[int,int,int,int,'cv2Drawer'], None] = None # args are: (event, mouseX, mouseY, flags, self)
        
        if(self.windowHandler.keyboardCallbackFunc is None): # unless a custom callback is already set for the windowHandler
            self.windowHandler.keyboardCallbackFunc = self._keyboardCallbackWrapper # default the windowHandler's callback to this 
        self.keyboardCallbackFunc: Callable[[int,'cv2Drawer'], None] = None # args are: (keycode, self)
        
        try:
            self.viewOffset = [((self.drawSize[0]/self.sizeScale)/2), ((self.drawSize[1]/self.sizeScale)/2)] # center view on (0.0,0.0) coordinate
            # self.viewOffset = # TBD: center view on thing
            # self.sizeScale = # TBD: show whole thing
        except Exception as theExcept:
            print("couldn't set viewOffset and sizeScale to show the thing:", theExcept)
    
    ## UI stuff:
    def _mouseCallbackWrapper(self, event:int, mouseX:int, mouseY:int, flags:int, _:'cv2WindowHandler'):
        """ a wrapper for the mouse callback. Intended to be used as the custom callback for the windowHandler """
        ## first, the middle-mouse-buttom dragging stuff
        if(event == cv2.EVENT_MBUTTONDOWN): # start of drag
            self.movingViewOffset = True # NOTE: this boolean itself could potentially be replaced by checking the fflag bit: (flags & cv2.EVENT_FLAG_MBUTTON)
            self.movingViewOffsetMouseStart = (mouseX, mouseY)
            self.prevViewOffset = (self.viewOffset[0], self.viewOffset[1])
        elif((event == cv2.EVENT_MOUSEMOVE) and self.movingViewOffset): # actively dragging
            mouseDelta = [] #init var
            if(self.invertYaxis):
                mouseDelta = [float(mouseX - self.movingViewOffsetMouseStart[0]), float(self.movingViewOffsetMouseStart[1] - mouseY)]
            else:
                mouseDelta = [float(mouseX - self.movingViewOffsetMouseStart[0]), float(mouseY - self.movingViewOffsetMouseStart[1])]
            self.viewOffset[0] = self.prevViewOffset[0] + (mouseDelta[0]/self.sizeScale)
            self.viewOffset[1] = self.prevViewOffset[1] + (mouseDelta[1]/self.sizeScale)
        elif(event == cv2.EVENT_MBUTTONUP): # end of drag
            self.movingViewOffset = False
        
        if(event == cv2.EVENT_MOUSEWHEEL):
            scrollDirection = (1.0 if (flags > 0) else (-1.0)) # the sign bit of the flags indicates the scroll direction (i'm not 100% sure how many bits the flags int is)
            viewSizeBeforeChange = [self.drawSize[0]/self.sizeScale, self.drawSize[1]/self.sizeScale]
            mousePosBeforeChange = self.pixelsToRealPos((mouseX, mouseY))
            ## update sizeScale
            self.sizeScale *= 1.0+(scrollDirection/10.0) #10.0 is an arbetrary zoomspeed
            if(self.sizeScale < self.minSizeScale):
                # print("can't zoom out any further")s
                self.sizeScale = self.minSizeScale
            elif(self.sizeScale > self.maxSizeScale):
                # print("can't zoom in any further")
                self.sizeScale = self.maxSizeScale
            dif = None # init var
            if(self.centerZooming): ## center zooming:
                dif = [(viewSizeBeforeChange[0]-(self.drawSize[0]/self.sizeScale))/2, (viewSizeBeforeChange[1]-(self.drawSize[1]/self.sizeScale))/2]
            else: ## mouse position based zooming:
                mousePosAfterChange = self.pixelsToRealPos((mouseX, mouseY))
                dif = [mousePosBeforeChange[0] - mousePosAfterChange[0], mousePosBeforeChange[1] - mousePosAfterChange[1]]
            self.viewOffset[0] -= dif[0] #equalizes from the zoom to 'happen' from the middle of the screen
            self.viewOffset[1] -= dif[1]

        if(callable(self.mouseCallbackFunc)):
            self.mouseCallbackFunc(event, mouseX, mouseY, flags, self)
    
    def _keyboardCallbackWrapper(self, keycode:int, _:'cv2WindowHandler'):
        """ called when waitKey(0) returns something other than -1 """
        char = chr(keycode) # just interprets an ascii table, basically
        if(char == 'z'):
            self.centerZooming = not self.centerZooming
        elif(char == 'g'):
            self.drawGrid = not self.drawGrid

        if(callable(self.keyboardCallbackFunc)):
            self.keyboardCallbackFunc(keycode, self)

    ## regular class functions
    def isInsideWindowPixels(self, pixelPos: np.ndarray):
        """whether or not a pixel-position is inside the window"""
        return((pixelPos[0] < (self.drawSize[0] + self.drawOffset[0])) and (pixelPos[0] > self.drawOffset[0]) and (pixelPos[1] < (self.drawSize[1] + self.drawOffset[1])) and (pixelPos[1] > self.drawOffset[1]))
    
    def drawFPScounter(self):
        """draw a little Frames Per Second counter in the corner to show program performance"""
        newTime = time.time()
        if((newTime - self.FPStimer)>0): #avoid divide by 0
            self.FPSdata.append(round(1/(newTime-self.FPStimer), 1))
        self.FPStimer = newTime #save for next time
        if((newTime - self.FPSdisplayTimer)>self.FPSdisplayInterval):
            self.FPSdisplayTimer = newTime
            self.FPSstrings = []
            if(len(self.FPSdata)>0):
                self.FPSstrings.append(str(round(np.average(np.array(self.FPSdata)), 1))) #average FPS
                self.FPSstrings.append(str(min(self.FPSdata)))                  #minimum FPS
                self.FPSstrings.append(str(max(self.FPSdata)))                  #maximum FPS
                self.FPSdata.sort()
                self.FPSstrings.append(str(self.FPSdata[int((len(self.FPSdata)-1)/2)])) #median FPS
                #print("FPS:", round(np.average(np.array(self.FPSdata)), 1), min(self.FPSdata), max(self.FPSdata), self.FPSdata[int((len(self.FPSdata)-1)/2)])
            else:
                self.FPSstrings = ["inf"]
                #print("FPS: inf")
            self.FPSdata = []
        for i in range(len(self.FPSstrings)):
            fontSize = self.normalFontSize(self.FPSstrings[i])
            cv2.putText(self.windowHandler.window, self.FPSstrings[i], (int(self.drawOffset[0]+self.drawSize[0]-5-fontSize[0]),int(self.drawOffset[1]+((i+1)*(fontSize[1]+5)))), # cv2 uses bottom left corner for test pos
                        self.normalFont, self.normalFontScale, self.normalFontColor, self.normalFontThickness)
    
    def drawStatText(self):
        """draw some usefull information/statistics on-screen"""
        newTime = time.time()
        # if((newTime - self.statDisplayTimer)>self.statDisplayInterval): # doesn't need to be here, as cv2 doesnt need to pre-render fonts (for speed)
        #     self.statDisplayTimer = newTime
        #     self.statStrings = [] # a list of strings
        #     self.statStrings.append(str(round(self.sizeScale, 2))) # an example of showing text
        #     if(len(self.debugText) > 0):
        #         for entry in self.debugText:
        #             self.statStrings.append(entry)
        for i in range(len(self.statStrings)):
            fontSize = self.normalFontSize(self.statStrings[i])
            cv2.putText(self.windowHandler.window, self.statStrings[i], (int(self.drawOffset[0]+5),int(self.drawOffset[1]+((i+1)*(fontSize[1]+5)))), 
                        self.normalFont, self.normalFontScale, self.normalFontColor, self.normalFontThickness)
    
    # def drawLoadedFilename(self):
    #     """shows the name of a loaded file in the corner of the screen"""
    #     if(len(self.lastFilename) > 0):
    #         fontSize = self.normalFontSize(self.lastFilename)
    #         cv2.putText(self.windowHandler.window, self.lastFilename, (int(self.drawOffset[0]+self.drawSize[0]-5-fontSize[0]),int(self.drawOffset[1]+self.drawSize[1]-5)), 
    #                     self.normalFont, self.normalFontScale, self.normalFontColor, self.normalFontThickness)
    
    #pixel conversion functions (the most important functions in here)
    def pixelsToRealPos(self, pixelPos: np.ndarray):
        """return a (real) position for a given pixel position (usually mouse position)
            (mostly used for UI)"""
        if(self.invertYaxis):
            return(np.array([((pixelPos[0]-self.drawOffset[0])/self.sizeScale)-self.viewOffset[0], ((self.drawSize[1]-pixelPos[1]+self.drawOffset[1])/self.sizeScale)-self.viewOffset[1]]))
        else:
            return(np.array([((pixelPos[0]-self.drawOffset[0])/self.sizeScale)-self.viewOffset[0], ((pixelPos[1]-self.drawOffset[1])/self.sizeScale)-self.viewOffset[1]]))
    
    def realToPixelPos(self, realPos: np.ndarray):
        """return the pixel-position (within the entire window) for a given (real) position"""
        if(self.invertYaxis):
            return(np.array([((realPos[0]+self.viewOffset[0])*self.sizeScale)+self.drawOffset[0], self.drawSize[1]-((realPos[1]+self.viewOffset[1])*self.sizeScale)+self.drawOffset[1]])) #invert Y-axis for normal (0,0) at bottomleft display
        else:
            return(np.array([((realPos[0]+self.viewOffset[0])*self.sizeScale)+self.drawOffset[0], ((realPos[1]+self.viewOffset[1])*self.sizeScale)+self.drawOffset[1]]))
    
    #check if things need to be drawn at all    
    def isInsideWindowReal(self, realPos: np.ndarray):
        """whether or not a (real) position is inside the window (note: not computationally efficient)"""
        return(self.isInsideWindowPixels(self.realToPixelPos(realPos))) #not very efficient, but simple
    
    #drawing functions
    def _drawGrid(self):
        ## attempt to calculate an appropriate scale for the grid (to minimize the number of lines drawn)
        gridSpacings = (10.0, 5.0, 2.0, 1.0, 0.5, 0.25, 0.1) # = (0.5, 1.0, 5.0, 10.0, 25.0)
        gridSpacingIndex = (np.log(self.sizeScale) - np.log(self.minSizeScale)) / (np.log(self.maxSizeScale) - np.log(self.minSizeScale)) # produces a number between 0 and 1 (linearized)
        gridSpacingIndex = min(int(gridSpacingIndex*len(gridSpacings)), len(gridSpacings)-1)
        gridSpacing = gridSpacings[gridSpacingIndex]
        lineWidth = int(1)
        ## first, figure out what the window sees. (keeping rotated views in mind)
        screenCenterRealPos = self.pixelsToRealPos(np.array(self.drawSize) / 2.0)
        roundedCenterPos = np.array([screenCenterRealPos[0]-(screenCenterRealPos[0]%gridSpacing), screenCenterRealPos[1]-(screenCenterRealPos[1]%gridSpacing)]) # rounded (down) to the nearest multiple of gridSpacing
        screenMaxRadiusSquared = distSqrdBetwPos(screenCenterRealPos, self.pixelsToRealPos(np.zeros(2))) # terribly inefficient, but whatever.
        gridIttToVal = lambda axis, value : (roundedCenterPos[axis]+(value*gridSpacing)) # obviously excessive use of lambda, but it makes it more abstract when rendering the text in the loop
        gridIttToPos = lambda x, y : np.array([gridIttToVal(0,x),gridIttToVal(1,y)],float) # to go from abstract grid forloop iterator (int) to actual coordinates (real, not pixel)
        withinScreenRadius = lambda x, y : (distSqrdBetwPos(screenCenterRealPos, gridIttToPos(x,y)) < screenMaxRadiusSquared) # the fastest check to see if a position is (probably/bluntly) visible
        ## the following code needs to be refactored to be a little shorter, but at least this is sort of legible and stuff
        def xloop(x): # vertical lines
            yMax = 0
            for y in range(0, 100):
                if(not withinScreenRadius(x,y)):
                    yMax = y;  break # yMax is found, stop this loop
            if(yMax == 0):
                return(False) # if the first entry was already outside the screenRadius, stop looping in this direction
            for y in range(-1, -100, -1):
                if(not withinScreenRadius(x,y)):
                    cv2.line(self.windowHandler.window, self.realToPixelPos(gridIttToPos(x,y)).astype(int), self.realToPixelPos(gridIttToPos(x,yMax)).astype(int), self.gridColor, lineWidth) # draw the vertical line
                    textToRender = str(round(gridIttToVal(0,x),   len(str(gridSpacing)[max(str(gridSpacing).rfind('.')+1, 0):]))) # a needlessly difficult way of rounding to the same number of decimals as the number in the gridSpacings array
                    fontSize = self.gridFontSize(textToRender)
                    cv2.putText(self.windowHandler.window, textToRender, (int(self.realToPixelPos(gridIttToPos(x,y))[0]+5),int(self.drawOffset[1]+self.drawSize[1]-fontSize[1])), # display the text at the bottom of the screen and to the right of the line
                                self.gridFont, self.gridFontScale, self.gridColor, self.gridFontThickness)
                    break # line is drawn, stop this loop
            return(True)
        for x in range(0, 100): # note: loop should break before reaching end!
            if(not xloop(x)):
                break
        for x in range(-1, -100, -1): # note: loop should break before reaching end!
            if(not xloop(x)):
                break
        def yloop(y): # horizontal lines
            xMax = 0
            for x in range(0, 100):
                if(not withinScreenRadius(x,y)):
                    xMax = x;  break # xMax is found, stop this loop
            if(xMax == 0):
                return(False) # if the first entry was already outside the screenRadius, stop looping in this direction
            for x in range(-1, -100, -1):
                if(not withinScreenRadius(x,y)):
                    cv2.line(self.windowHandler.window, self.realToPixelPos(gridIttToPos(x,y)).astype(int), self.realToPixelPos(gridIttToPos(xMax,y)).astype(int), self.gridColor, lineWidth) # draw the horizontal line
                    textToRender = str(round(gridIttToVal(1,y),   len(str(gridSpacing)[max(str(gridSpacing).rfind('.')+1, 0):]))) # a needlessly difficult way of rounding to the same number of decimals as the number in the gridSpacings array
                    fontSize = self.gridFontSize(textToRender)
                    cv2.putText(self.windowHandler.window, textToRender, (int(self.drawOffset[0]+self.drawSize[0]-5-fontSize[0]),int(self.realToPixelPos(gridIttToPos(x,y))[1]+fontSize[1]+5)), # display the text at the right side of the screen and to the right of the line
                                self.gridFont, self.gridFontScale, self.gridColor, self.gridFontThickness)
                    break # line is drawn, stop this loop
            return(True)
        for y in range(0, 100): # note: loop should break before reaching end!
            if(not yloop(y)):
                break
        for y in range(-1, -100, -1): # note: loop should break before reaching end!
            if(not yloop(y)):
                break

    def background(self):
        """draw the background and a grid (if enabled)"""
        self.windowHandler.window[self.drawOffset[1]:self.drawOffset[1]+self.drawSize[1],self.drawOffset[0]:self.drawOffset[0]+self.drawSize[0]] = np.array(self.bgColor) # dont fill entire screen, just this cv2Drawer's area (allowing for multiple cv2Drawers in one window)
        if(self.drawGrid):
            self._drawGrid()
    
    def _dashedLine(self, lineColor: tuple[int,int,int], startPixelPos: np.ndarray, endPixelPos: np.ndarray, lineWidth: int, dashPixelPeriod=20, dashDutyCycle=0.5):
        """(sub function) draw a dashed line"""
        pixelDist, angle = distAngleBetwPos(startPixelPos, endPixelPos)
        for i in range(int(pixelDist/dashPixelPeriod)):
            dashStartPos = distAnglePosToPos(i*dashPixelPeriod, angle, startPixelPos).astype(int)
            dashEndPos = distAnglePosToPos(i*dashPixelPeriod + dashPixelPeriod*dashDutyCycle, angle, startPixelPos).astype(int)
            cv2.line(self.windowHandler.window, dashStartPos, dashEndPos, lineColor, int(lineWidth))
    
    def renderFG(self, drawSpeedTimers: list = None):
        self.drawFPScounter()
        if(drawSpeedTimers is not None):  drawSpeedTimers.append(('drawFPScounter', time.time()))
        self.drawStatText()
        if(drawSpeedTimers is not None):  drawSpeedTimers.append(('drawStatText', time.time()))
        # self.drawLoadedFilename()
        # if(drawSpeedTimers is not None):  drawSpeedTimers.append(('drawLoadedFilename', time.time()))
    
    def drawCircle(self, realPos: np.ndarray, radius: float, color=[255, 255, 255], fill=True):
        cv2.circle(self.windowHandler.window, self.realToPixelPos(realPos).astype(int), int(radius * self.sizeScale), color, (-1 if fill else 3))

    def redraw(self):
        """draw all elements"""
        drawSpeedTimers = [('start', time.time()),]
        self.background()
        if(drawSpeedTimers is not None):  drawSpeedTimers.append(('background', time.time()))

        ## application-specific code here?

        self.renderFG(drawSpeedTimers)

        drawSpeedTimers = [(drawSpeedTimers[i][0], round((drawSpeedTimers[i][1]-drawSpeedTimers[i-1][1])*1000, 1)) for i in range(1,len(drawSpeedTimers)) if ((drawSpeedTimers[i][1]-drawSpeedTimers[i-1][1]) > 0.0001)]
        # print("draw speed times:", sorted(drawSpeedTimers, key=lambda item : item[1], reverse=True))
    
    def updateWindowSize(self, drawSize=[1200, 600], drawOffset=[0,0], sizeScale=-1, autoMatchSizeScale=True):
        """handle the size of the window changing
            (optional) scale sizeScale (zooming) to match previous window size"""
        if(sizeScale > 0):
            self.sizeScale = sizeScale
        elif(autoMatchSizeScale):
            self.sizeScale = min(drawSize[0]/self.drawSize[0], drawSize[1]/self.drawSize[1]) * self.sizeScale #auto update sizeScale to match previous size
        self.drawSize = (int(drawSize[0]), int(drawSize[1]))
        self.drawOffset = (int(drawOffset[0]), int(drawOffset[1]))
        print("updateWindowSize:", self.drawSize, self.drawOffset, self.sizeScale, autoMatchSizeScale)






if __name__ == "__main__": # an example of how this file may be used
    try:
        windowHandler = cv2WindowHandler([1280, 720])
        drawer = cv2Drawer(windowHandler) # only 1 renderer in the window

        # while(windowHandler.checkWindowOpen()):
        while(windowHandler.keepRunning):
            drawer.redraw()
            windowHandler.frameRefresh()
    finally:
        try:
            windowHandler.end() # correctly shut down cv2 window
            print("drawer stopping done")
        except:
            print("couldn't run cv2 window end()")