# -*- coding: utf-8 -*-
#
# codimension - graphics python two-way code editor and analyzer
# Copyright (C) 2010-2020  Sergey Satskiy <sergey.satskiy@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""Codimension ide introspection plugin implementation"""


import os.path
import logging
import os
import pdb
import sys
from guppy import hpy
from mem_top import mem_top
from PyQt5.QtCore import pyqtRemoveInputHook, pyqtRestoreInputHook
from distutils.version import StrictVersion
from plugins.categories.wizardiface import WizardInterface
from ui.qt import (QWidget, QIcon, QTabBar, QApplication, QCursor, Qt, QMenu,
                   QAction, QMenu, QDialog, QToolButton)
from utils.fileutils import loadJSON, saveJSON
from .introspectionconfigdialog import IntrospectionPluginConfigDialog


PLUGIN_HOME_DIR = os.path.dirname(os.path.abspath(__file__)) + os.path.sep


class IntrospectionPlugin(WizardInterface):

    """Codimension introspection plugin"""

    def __init__(self):
        WizardInterface.__init__(self)
        self.__where = IntrospectionPluginConfigDialog.CONSOLE
        self.heap = None

    @staticmethod
    def isIDEVersionCompatible(ideVersion):
        """Checks if the IDE version is compatible with the plugin.

        Codimension makes this call before activating a plugin.
        The passed ideVersion is a string representing
        the current IDE version.
        True should be returned if the plugin is compatible with the IDE.
        """
        return StrictVersion(ideVersion) >= StrictVersion('4.7.0')

    def activate(self, ideSettings, ideGlobalData):
        """Activates the plugin.

        The plugin may override the method to do specific
        plugin activation handling.

        ideSettings - reference to the IDE Settings singleton
                      see codimension/src/utils/settings.py
        ideGlobalData - reference to the IDE global settings
                        see codimension/src/utils/globals.py

        Note: if overriden do not forget to call the
              base class activate()
        """
        WizardInterface.activate(self, ideSettings, ideGlobalData)

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:

            self.__where = self.__getConfiguredWhere()
            mainToolbar = self.ide.mainWindow.getToolbar()
            beforeWidget = mainToolbar.findChild(QAction, 'debugSpacer')
            self.__separator = mainToolbar.insertSeparator(beforeWidget)

            self.__memtopButton = QAction(QIcon(PLUGIN_HOME_DIR + 'memtop.png'),
                                          'memtop report', mainToolbar)
            self.__memtopButton.triggered.connect(self.__onMemtop)
            mainToolbar.insertAction(beforeWidget, self.__memtopButton)

            self.__debuggerButton = QAction(QIcon(PLUGIN_HOME_DIR + 'debugger.png'),
                                            'stop with debugger', mainToolbar)
            self.__debuggerButton.triggered.connect(self.__onDebugger)
            mainToolbar.insertAction(beforeWidget, self.__debuggerButton)

            self.hpy = hpy()
            self.hpy.setref()
        except:
            QApplication.restoreOverrideCursor()
            raise
        QApplication.restoreOverrideCursor()

    def deactivate(self):
        """Deactivates the plugin.

        The plugin may override the method to do specific
        plugin deactivation handling.
        Note: if overriden do not forget to call the
              base class deactivate()
        """
        self.hpy = None

        self.__memtopButton.disconnect()
        self.__debuggerButton.disconnect()


        mainToolbar = self.ide.mainWindow.getToolbar()
        mainToolbar.removeAction(self.__separator)
        mainToolbar.removeAction(self.__debuggerButton)
        self.__separator.deleteLater()
        self.__memtopButton.deleteLater()
        self.__debuggerButton.deleteLater()


        WizardInterface.deactivate(self)

    def getConfigFunction(self):
        """Provides a plugun configuration function.

        The plugin can provide a function which will be called when the
        user requests plugin configuring.
        If a plugin does not require any config parameters then None
        should be returned.
        By default no configuring is required.
        """
        return self.configure

    def populateMainMenu(self, parentMenu):
        """Populates the main menu"""
        del parentMenu      # unused argument

    def populateFileContextMenu(self, parentMenu):
        """Populates the file context menu"""
        del parentMenu      # unused argument

    def populateDirectoryContextMenu(self, parentMenu):
        """Populates the directory context menu"""
        del parentMenu      # unused argument

    def populateBufferContextMenu(self, parentMenu):
        """Populates the editing buffer context menu"""
        del parentMenu

    def configure(self):
        """Configure dialog"""
        dlg = IntrospectionPluginConfigDialog(PLUGIN_HOME_DIR,
                                              self.ide.mainWindow)
        if dlg.exec_() == QDialog.Accepted:
            newWhere = dlg.getCheckedOption()
            if newWhere != self.__where:
                self.__where = newWhere
                self.__saveConfiguredWhere()

    def __getConfigFile(self):
        """Provides a directory name where a configuration is stored"""
        return self.ide.settingsDir + "introspection.plugin.json"

    def __getConfiguredWhere(self):
        """Provides the saved configured value"""
        defaultSettings = {'where': IntrospectionPluginConfigDialog.CONSOLE}
        configFile = self.__getConfigFile()
        if not os.path.exists(configFile):
            values = defaultSettings
        else:
            values = loadJSON(configFile,
                              "introspection plugin settings",
                              defaultSettings)
        try:
            value = values['where']
            if value < IntrospectionPluginConfigDialog.LOG or \
               value > IntrospectionPluginConfigDialog.NEW_TAB:
                return IntrospectionPluginConfigDialog.CONSOLE
            return value
        except:
            return IntrospectionPluginConfigDialog.CONSOLE

    def __saveConfiguredWhere(self):
        """Saves the configured where"""
        saveJSON(self.__getConfigFile(), {'where': self.__where},
                 "introspection plugin settings")

    def __onMemtop(self):
        """mem_top report"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            print(mem_top(limit=100, width=400))
        except Exception as exc:
            logging.error(str(exc))
        QApplication.restoreOverrideCursor()

    def __onDebugger(self):
        """Brings up a debugger"""
        heap = self.hpy.heap()
        unreachable = self.hpy.heapu()
        logging.error("Use 'heap' and 'unreachable' objects. Type 'c' when finished.")

        oldstdin = sys.stdin
        oldstdout = sys.stdout
        oldstderr = sys.stderr

        sys.stdin = sys.__stdin__
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        pyqtRemoveInputHook()
        pdb.set_trace()
        pyqtRestoreInputHook()

        sys.stdin = oldstdin
        sys.stdout = oldstdout
        sys.stderr = oldstderr

