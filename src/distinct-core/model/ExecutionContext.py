import re
import logging

from model.Frame import Frame
from model.SequenceDiagram import SequenceDiagram

from processors.AddEventListenerProcessor import AddEventListenerProcessor
from processors.BroadcastChannelNewProcessor import BroadcastChannelNewProcessor
from processors.BroadcastMessageReceivedProcessor import BroadcastMessageReceivedProcessor
from processors.BroadcastMessageSentProcessor import BroadcastMessageSentProcessor
from processors.ClosedAccessedProcessor import ClosedAccessedProcessor
from processors.CookieSetProcessor import CookieSetProcessor
from processors.CustomEventNewProcessor import CustomEventNewProcessor
from processors.CustomEventReceivedProcessor import CustomEventReceivedProcessor
from processors.DocumentBeforeUnloadProcessor import DocumentBeforeUnloadProcessor
from processors.DocumentCompleteProcessor import DocumentCompleteProcessor
from processors.DocumentInitProcessor import DocumentInitProcessor
from processors.DocumentInteractiveProcessor import DocumentInteractiveProcessor
from processors.DocumentLoadingProcessor import DocumentLoadingProcessor
from processors.FormSubmitProcessor import FormSubmitProcessor
from processors.HTTPRedirectProcessor import HTTPRedirectProcessor
from processors.IndexedDBSetProcessor import IndexedDBSetProcessor
from processors.LocalStorageSetProcessor import LocalStorageSetProcessor
from processors.LocationSetProcessor import LocationSetProcessor
from processors.MessageChannelNewProcessor import MessageChannelNewProcessor
from processors.MessageChannelReceivedProcessor import MessageChannelReceivedProcessor
from processors.MetaRedirectProcessor import MetaRedirectProcessor
from processors.MetaReloadProcessor import MetaReloadProcessor
from processors.PostMessageReceivedProcessor import PostMessageReceivedProcessor
from processors.RefreshRedirectProcessor import RefreshRedirectProcessor
from processors.RefreshReloadProcessor import RefreshReloadProcessor
from processors.RemoveEventListenerProcessor import RemoveEventListenerProcessor
from processors.StatementProcessor import StatementProcessor
from processors.SessionStorageSetProcessor import SessionStorageSetProcessor
from processors.WindowCloseProcessor import WindowCloseProcessor
from processors.WindowOpenProcessor import WindowOpenProcessor
from processors.WindowPropChangedProcessor import WindowPropChangedProcessor
from processors.WindowPropNewProcessor import WindowPropNewProcessor

logger = logging.getLogger(__name__)

class ExecutionContext():

    def __init__(self, report_handler):
        self.report_handler = report_handler

        self.topframe = None # Top frame in hierarchy, i.e., root of the frame hierarchy
        self.statements = {} # Statements received from chrome extension, i.e., flows, SDKs, ...
        self.reports = [] # Reports received from chrome extension, i.e., documentinit, ...
        self.sequencediagram = SequenceDiagram() # Sequence diagram shows reports as visual representation

        # Initialize global statements for report handler
        self.statements["uuid"] = report_handler.uuid
        self.statements["starttime"] = report_handler.starttime
        self.statements["initurl"] = report_handler.config.get("initurl")

    def hierarchy(self):
        """ String representation of execution context is a tree hierarchy """
        if not self.topframe:
            return ""

        dump = {"val": "top"}
        def go_down(current, dump, indent):
            for i in current.frames.keys():
                dump["val"] += "\n{}-> frames[{}]".format('\t'*indent, i)
                go_down(current.frames[i], dump, indent+1)
            for i in current.popups.keys():
                if current.popups[i].closed:
                    continue
                dump["val"] += "\n{}-> popups[{}]".format('\t'*indent, i)
                go_down(current.popups[i], dump, indent+1)

        go_down(self.topframe, dump, 1)
        return dump["val"]

    def process_report(self, report):
        """ Process reports """
        self.reports.append(report)

        key = report["key"]

        # Statements
        if key == "report": # todo: change to statement
            StatementProcessor(self, report)

        # Document Events
        elif key == "documentinit":
            DocumentInitProcessor(self, report)
        elif key == "documentloading":
            DocumentLoadingProcessor(self, report)
        elif key == "documentinteractive":
            DocumentInteractiveProcessor(self, report)
        elif key == "documentcomplete":
            DocumentCompleteProcessor(self, report)
        elif key == "documentbeforeunload":
            DocumentBeforeUnloadProcessor(self, report)
        elif key == "windowopen":
            WindowOpenProcessor(self, report)
        elif key == "windowclose":
            WindowCloseProcessor(self, report)

        # URL Redirect Events
        elif key == "httpredirect":
            HTTPRedirectProcessor(self, report)
        elif key == "formsubmit":
            FormSubmitProcessor(self, report)
        elif key == "metaredirect":
            MetaRedirectProcessor(self, report)
        elif key == "metareload":
            MetaReloadProcessor(self, report)
        elif key == "refreshredirect":
            RefreshRedirectProcessor(self, report)
        elif key == "refreshreload":
            RefreshReloadProcessor(self, report)

        # JS Properties
        elif key == "closedaccessed":
            ClosedAccessedProcessor(self, report)

        # Cross-Origin & Same-Origin Web Messaging
        elif key == "postmessagereceived":
            PostMessageReceivedProcessor(self, report)
        elif key == "addeventlistener":
            AddEventListenerProcessor(self, report)
        elif key == "removeeventlistener":
            RemoveEventListenerProcessor(self, report)
        elif key == "customeventnew":
            CustomEventNewProcessor(self, report)
        elif key == "customeventreceived":
            CustomEventReceivedProcessor(self, report)
        elif key == "messagechannelnew":
            MessageChannelNewProcessor(self, report)
        elif key == "channelmessagereceived":
            MessageChannelReceivedProcessor(self, report)
        elif key == "broadcastchannelnew":
            BroadcastChannelNewProcessor(self, report)
        elif key == "broadcastmessagereceived":
            BroadcastMessageReceivedProcessor(self, report)
        elif key == "broadcastmessagesent":
            BroadcastMessageSentProcessor(self, report)

        # JS Storage
        elif key == "localstorageset":
            LocalStorageSetProcessor(self, report)
        elif key == "sessionstorageset":
            SessionStorageSetProcessor(self, report)
        elif key == "cookieset":
            CookieSetProcessor(self, report)
        elif key == "idbadd" or key == "idbput":
            IndexedDBSetProcessor(self, report)

        # JS Direct Access
        elif key == "windowpropnew":
            WindowPropNewProcessor(self, report)
        elif key == "windowpropchanged":
            WindowPropChangedProcessor(self, report)

        # JS Navigate & JS Reload
        elif key == "locationset":
            LocationSetProcessor(self, report)

    """ Frame Navigation """

    def update_frame(self, old_frame, new_frame):
        """ Update properties of existing frame with properties of new frame
            Properties: href, html
        """
        old_frame.href = new_frame.href
        old_frame.html = new_frame.html

    def get_frame(self, hierarchy):
        """ Get frame in hierarchy
            Returns frame, if frame is found
            Returns None, if frame is not found
        """
        path = hierarchy.split(".")

        if not self.topframe:
            return None

        current = self.topframe
        for i in range(0, len(path) - 1):
            frames = re.search("frames\[(\d)+\]", path[i])
            popups = re.search("popups\[(\d)+\]", path[i])

            if frames:
                frame_idx = int(frames.group(1))
                try:
                    current = current.frames[frame_idx]
                except KeyError as e:
                    return None
            elif popups:
                popup_idx = int(popups.group(1))
                try:
                    current = current.popups[popup_idx]
                except KeyError as e:
                    return None

        last = path[-1]
        frames = re.search("frames\[(\d)+\]", last)
        popups = re.search("popups\[(\d)+\]", last)

        if last == "top":
            return self.topframe
        elif frames:
            frame_idx = int(frames.group(1))
            try:
                return current.frames[frame_idx]
            except KeyError as e:
                return None
        elif popups:
            popup_idx = int(popups.group(1))
            try:
                return current.popups[popup_idx]
            except KeyError as e:
                return None
        else:
            return None

    def insert_frame(self, hierarchy, frame):
        """ Insert frame and all superior frames and superior popups in tree (if not existent)
            Returns frame, if frame inserted successfully
            Returns None, if frame not inserted successfully
        """
        # If frame already exists, just update its properties
        # but keep it in hierarchy tree with references to parents and children
        old_frame = self.get_frame(hierarchy)
        if old_frame:
            self.update_frame(old_frame, frame)
            return old_frame

        path = hierarchy.split(".")

        current = self.topframe
        for i in range(0, len(path) - 1):
            frames = re.search("frames\[(\d)+\]", path[i])
            popups = re.search("popups\[(\d)+\]", path[i])

            if frames:
                frame_idx = int(frames.group(1))
                try:
                    current = current.frames[frame_idx]
                except KeyError as e:
                    # Create intermediate iframe
                    logger.debug(
                        f""" Creating new intermediate iframe with index {frame_idx}
                        in frame '{current.hierarchy()}'"""
                    )
                    inter_frame = Frame()
                    inter_frame.parent = current
                    inter_frame.opener = None
                    idx = current.insert_iframe(frame_idx, inter_frame)
                    current = current.frames[frame_idx]
            elif popups:
                popup_idx = int(popups.group(1))
                try:
                    current = current.popups[popup_idx]
                except KeyError as e:
                    # Create intermediate popup
                    logger.debug(
                        f""" Creating new intermediate popup with index {popup_idx}
                        in frame '{current.hierarchy()}'"""
                    )
                    inter_frame = Frame()
                    inter_frame.parent = None
                    inter_frame.opener = current
                    idx = current.insert_popup(popup_idx, inter_frame)
                    current = current.popups[popup_idx]
            elif path[i] == "top" and current == None:
                # Create topframe
                logger.debug("Creating intermediate topframe")
                inter_frame = Frame()
                inter_frame.parent = None
                inter_frame.opener = None
                self.topframe = inter_frame
                current = self.topframe

        last = path[-1]
        frames = re.search("frames\[(\d)+\]", last)
        popups = re.search("popups\[(\d)+\]", last)

        if frames:
            frame_idx = int(frames.group(1))
            frame.parent = current
            frame.opener = None
            current.insert_iframe(frame_idx, frame)
        elif popups:
            popup_idx = int(popups.group(1))
            frame.parent = None
            frame.opener = current
            current.insert_popup(popup_idx, frame)
        elif last == "top" and not self.topframe:
            self.topframe = frame

        return frame

    def remove_frame(self, hierarchy):
        """ Removes frame and all subframes and subpopups from tree
            Returns True, if frame removed successfully
            Returns False, if frame not removed successfully
        """
        path = hierarchy.split(".")

        current = self.topframe
        for i in range(0, len(path) - 1):
            frames = re.search("frames\[(\d)+\]", path[i])
            popups = re.search("popups\[(\d)+\]", path[i])

            if frames:
                frame_idx = int(frames.group(1))
                try:
                    current = current.frames[frame_idx]
                except KeyError as e:
                    logger.warning(f"""
                        Failed to remove frame '{hierarchy}'
                        because frame '{current.hierarchy()}'
                        does not contain iframe with index {frame_idx}"""
                    )
                    return False
            elif popups:
                popup_idx = int(popups.group(1))
                try:
                    current = current.popups[popup_idx]
                except KeyError as e:
                    logger.warning(f"""
                        Failed to remove frame '{hierarchy}'
                        because frame '{current.hierarchy()}'
                        does not contain popup with index {popup_idx}"""
                    )
                    return False

        last = path[-1]
        frames = re.search("frames\[(\d)+\]", last)
        popups = re.search("popups\[(\d)+\]", last)

        if last == "top":
            self.topframe = None
        elif frames:
            frame_idx = int(frames.group(1))
            if frame_idx in current.frames:
                current.delete_iframe(frame_idx)
        elif popups:
            popup_idx = int(popups.group(1))
            if popup_idx in current.popups:
                current.delete_popup(popup_idx)

        return True
