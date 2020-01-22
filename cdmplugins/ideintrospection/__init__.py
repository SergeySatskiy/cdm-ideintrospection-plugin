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
from pympler import summary, muppy
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

        self.__where = self.__getConfiguredWhere()
        mainToolbar = self.ide.mainWindow.getToolbar()
        beforeWidget = mainToolbar.findChild(QAction, 'debugSpacer')
        self.__separator = mainToolbar.insertSeparator(beforeWidget)

        memButton = QToolButton(mainToolbar)
        memButton.setIcon(QIcon(PLUGIN_HOME_DIR + 'summary.png'))
        memButton.setToolTip('Print memory objects')
        memButton.setPopupMode(QToolButton.InstantPopup)
        memButton.setMenu(self.__createMemoryMenu())
        memButton.setFocusPolicy(Qt.NoFocus)

        self.__memSummaryButton = mainToolbar.insertWidget(beforeWidget,
                                                           memButton)
        self.__memSummaryButton.setObjectName('memSummaryButton')

    def __createMemoryMenu(self):
        """Creates the memory button menu"""
        memMenu = QMenu()
        fullAct = memMenu.addAction(QIcon(PLUGIN_HOME_DIR + 'summary.png'),
                                    'Full memory objects list')
        fullAct.triggered.connect(self.__onFullMemoryReport)
        reducedAct = memMenu.addAction(QIcon(PLUGIN_HOME_DIR + 'summary.png'),
                                       'Memory objects without functions and modules')
        reducedAct.triggered.connect(self.__onReducedMemoryReport)
        return memMenu

    def deactivate(self):
        """Deactivates the plugin.

        The plugin may override the method to do specific
        plugin deactivation handling.
        Note: if overriden do not forget to call the
              base class deactivate()
        """
        mainToolbar = self.ide.mainWindow.getToolbar()
        self.__memSummaryButton.triggered.disconnect(self.__memSummary)
        mainToolbar.removeAction(self.__memSummaryButton)
        self.__memSummaryButton.deleteLater()
        mainToolbar.removeAction(self.__separator)
        self.__separator.deleteLater()

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
        """Populates the main menu.

        The main menu looks as follows:
        Plugins
            - Plugin manager (fixed item)
            - Separator (fixed item)
            - <Plugin #1 name> (this is the parentMenu passed)
            ...
        If no items were populated by the plugin then there will be no
        <Plugin #N name> menu item shown.
        It is suggested to insert plugin configuration item here if so.
        """
        del parentMenu      # unused argument

    def populateFileContextMenu(self, parentMenu):
        """Populates the file context menu.

        The file context menu shown in the project viewer window will have
        an item with a plugin name and subitems which are populated here.
        If no items were populated then the plugin menu item will not be
        shown.

        When a callback is called the corresponding menu item will have
        attached data with an absolute path to the item.
        """
        del parentMenu      # unused argument

    def populateDirectoryContextMenu(self, parentMenu):
        """Populates the directory context menu.

        The directory context menu shown in the project viewer window will
        have an item with a plugin name and subitems which are populated
        here. If no items were populated then the plugin menu item will not
        be shown.

        When a callback is called the corresponding menu item will have
        attached data with an absolute path to the directory.
        """
        del parentMenu      # unused argument

    def populateBufferContextMenu(self, parentMenu):
        """Populates the editing buffer context menu.

        The buffer context menu shown for the current edited/viewed file
        will have an item with a plugin name and subitems which are
        populated here. If no items were populated then the plugin menu
        item will not be shown.

        Note: when a buffer context menu is selected by the user it always
              refers to the current widget. To get access to the current
              editing widget the plugin can use: self.ide.currentEditorWidget
              The widget could be of different types and some circumstances
              should be considered, e.g.:
              - it could be a new file which has not been saved yet
              - it could be modified
              - it could be that the disk file has already been deleted
              - etc.
              Having the current widget reference the plugin is able to
              retrieve the information it needs.
        """
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

    def __onFullMemoryReport(self):
        """No reductions memory report"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            allObjects = muppy.get_objects(remove_dups=True,
                                           include_frames=False)
            memSummary = summary.summarize(allObjects)
        except Exception as exc:
            logging.error(str(exc))
            QApplication.restoreOverrideCursor()
            return
        QApplication.restoreOverrideCursor()
        summary.print_(memSummary, limit=10000)

    def __onReducedMemoryReport(self):
        """No functions/no modules memory report"""

    def __memSummary(self):
        """Provides the memory summary"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            allObjects = muppy.get_objects(remove_dups=True, include_frames=False)
            memSummary = summary.summarize(allObjects)
        except Exception as exc:
            logging.error(str(exc))
            QApplication.restoreOverrideCursor()
            return
        QApplication.restoreOverrideCursor()
        summary.print_(memSummary, limit=10000)

