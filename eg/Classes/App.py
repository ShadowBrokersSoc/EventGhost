# This file is part of EventGhost.
# Copyright (C) 2005 Lars-Peter Voss <bitmonster@eventghost.org>
# 
# EventGhost is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# EventGhost is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with EventGhost; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
#
# $LastChangedDate$
# $LastChangedRevision$
# $LastChangedBy$

import eg
import wx
import sys
import time
import threading
from eg.WinApi.Dynamic import (
    WM_QUERYENDSESSION, 
    WM_ENDSESSION, 
    SetProcessShutdownParameters,
)


class App(wx.App):
    
    def __init__(self):
        self.onExitFuncs = []
        wx.App.__init__(self, 0)
    
    
    def OnInit(self):
        self.SetAppName(eg.APP_NAME)
        self.SetExitOnFrameDelete(False)
        
        # set shutdown priority for this app, so we get 
        # shutdown last (hopefully)
        SetProcessShutdownParameters(0x0100, 0)
        
        # We don't use wxWindows EVT_QUERY_END_SESSION handling, because we
        # would get an event for every frame the application has and that
        # would make it hard to distinguish between individual logoff
        # requests. So we simply disable the built-in handling by assigning
        # a dummy function and generate our own event in the hidden
        # MessageReceiver window.
        self.Bind(wx.EVT_QUERY_END_SESSION, eg.DummyFunc)
        self.Bind(wx.EVT_END_SESSION, eg.DummyFunc)
        eg.messageReceiver.AddHandler(
            WM_QUERYENDSESSION, 
            self.OnQueryEndSession
        )
        
        eg.messageReceiver.AddHandler(
            WM_ENDSESSION, 
            self.OnEndSession
        )
        
        return True
    
    
    @eg.LogItWithReturn
    def OnQueryEndSession(self, hwnd, msg, wparam, lparam):
        """System is about to be logged off"""
        # This method gets called from MessageReceiver on a
        # WM_QUERYENDSESSION win32 message.
        if eg.document.CheckFileNeedsSave() == wx.ID_CANCEL:
            eg.PrintDebugNotice("User canceled shutdown in OnQueryEndSession")
            return 0
        return 1


    @eg.LogItWithReturn
    def OnEndSession(self, hwnd, msg, wparam, lparam):
        """System is logging off"""
        egEvent = eg.eventThread.TriggerEvent("OnEndSession")
        while not egEvent.isEnded:
            time.sleep(0.01)
        eg.CallWait(eg.document.Close)
        eg.taskBarIcon.alive = False
        eg.taskBarIcon.Destroy()
        #self.ExitMainLoop()
        eg.CallWait(self.OnExit)
        return 0
         
        
    @eg.LogIt
    def Exit(self, dummyEvent=None):
        if eg.document.CheckFileNeedsSave() == wx.ID_CANCEL:
            return
        if eg.pyCrustFrame:
            eg.pyCrustFrame.Close()
        eg.document.Close()
        eg.taskBarIcon.alive = False
        eg.taskBarIcon.Destroy()
        self.ExitMainLoop()
        
        
    @eg.LogIt
    def OnExit(self):
        if not eg.startupArguments.translate:
            eg.PrintDebugNotice("Triggering OnClose")    
            egEvent = eg.eventThread.TriggerEvent("OnClose")
            while not egEvent.isEnded:
                self.Yield()
                
            eg.PrintDebugNotice("Calling exit funcs")    
            for func in self.onExitFuncs:
                eg.PrintDebugNotice(func)
                func()
                
            eg.PrintDebugNotice("Calling eg.DeInit()")    
            eg.Init.DeInit()
        
        eg.PrintDebugNotice("Threads:")
        for thread in threading.enumerate():
            eg.PrintDebugNotice(" ", thread, thread.getName())
                
        while self.Pending():
            self.Dispatch()
                
        # try to wait till all utility threads have ended
        currentThread = threading.currentThread()
        for thread in threading.enumerate():
            if (
                thread is not currentThread 
                and (thread is not eg.messageReceiver._ThreadWorker__thread) 
                and not thread.isDaemon() 
                and thread.isAlive()
            ):
                eg.PrintDebugNotice(
                    "joining: " + str(thread) + repr(thread._Thread__target)
                )
                thread.join(5.0)
        
        eg.PrintDebugNotice("Threads:")
        for thread in threading.enumerate():
            eg.PrintDebugNotice(" ", thread, thread.getName())
        eg.PrintDebugNotice("Done!")
        sys.exit(0)
