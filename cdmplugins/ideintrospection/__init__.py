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
import inspect
import linecache
import os
import tracemalloc
from pympler import summary, muppy, tracker, refbrowser
from distutils.version import StrictVersion
from plugins.categories.wizardiface import WizardInterface
from ui.qt import (QWidget, QIcon, QTabBar, QApplication, QCursor, Qt, QMenu,
                   QAction, QMenu, QDialog, QToolButton)
from utils.fileutils import loadJSON, saveJSON
from .introspectionconfigdialog import IntrospectionPluginConfigDialog


PLUGIN_HOME_DIR = os.path.dirname(os.path.abspath(__file__)) + os.path.sep


def display_top(snapshot, key_type='lineno', limit=10):
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        print("#%s: %s:%s: %.1f KiB"
              % (index, filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))


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

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
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

            self.__diffButton = QAction(QIcon(PLUGIN_HOME_DIR + 'diff.png'),
                                        'Memory usage diff', mainToolbar)
            self.__diffButton.triggered.connect(self.__memoryDiff)
            self.__diffButton = mainToolbar.insertAction(beforeWidget,
                                                         self.__diffButton)

            self.__refButton = QAction(QIcon(PLUGIN_HOME_DIR + 'ref.png'),
                                       'Reference browser', mainToolbar)
            self.__refButton.triggered.connect(self.__referenceBrowser)
            self.__refButton = mainToolbar.insertAction(beforeWidget,
                                                        self.__refButton)

            self.__tracker = tracker.SummaryTracker()
            tracemalloc.start()
            self.__lastSnapshot = tracemalloc.take_snapshot()
        except:
            QApplication.restoreOverrideCursor()
            raise
        QApplication.restoreOverrideCursor()

    def __createMemoryMenu(self):
        """Creates the memory button menu"""
        memMenu = QMenu()
        self.fullAct = memMenu.addAction(
            QIcon(PLUGIN_HOME_DIR + 'summary.png'),
            'Full memory objects list')
        self.fullAct.triggered.connect(self.__onFullMemoryReport)
        self.reducedAct = memMenu.addAction(
            QIcon(PLUGIN_HOME_DIR + 'summary.png'),
            'Memory objects without functions and modules')
        self.reducedAct.triggered.connect(self.__onReducedMemoryReport)
        return memMenu

    def deactivate(self):
        """Deactivates the plugin.

        The plugin may override the method to do specific
        plugin deactivation handling.
        Note: if overriden do not forget to call the
              base class deactivate()
        """
        self.__tracker = None

        self.fullAct.triggered.disconnect(self.__onFullMemoryReport)
        self.reducedAct.triggered.disconnect(self.__onReducedMemoryReport)
        self.__diffButton.triggered.disconnect(self.__memoryDiff)
        self.__refButton.triggered.disconnect(self.__referenceBrowser)

        mainToolbar = self.ide.mainWindow.getToolbar()
        mainToolbar.removeAction(self.__memSummaryButton)
        self.__memSummaryButton.deleteLater()
        mainToolbar.removeAction(self.__separator)
        self.__separator.deleteLater()
        self.__diffButton.deleteLater()
        self.__refButton.deleteLater()

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

    def __onFullMemoryReport(self):
        """No reductions memory report"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            allObjects = muppy.get_objects(remove_dups=True,
                                           include_frames=False)
            memSummary = summary.summarize(allObjects)
            summary.print_(memSummary, limit=10000)
        except Exception as exc:
            logging.error(str(exc))
        QApplication.restoreOverrideCursor()

    def __onReducedMemoryReport(self):
        """No functions/no modules memory report"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            allObjects = muppy.get_objects(remove_dups=True,
                                           include_frames=False)
            allObjects = [x for x in allObjects
                             if not inspect.isfunction(x) and
                                not inspect.ismodule(x)]
            memSummary = summary.summarize(allObjects)
            summary.print_(memSummary, limit=10000)

            print('Tracemalloc report')
            display_top(tracemalloc.take_snapshot(), key_type='traceback')

        except Exception as exc:
            logging.error(str(exc))
        QApplication.restoreOverrideCursor()

    def __memoryDiff(self):
        """Prints the memory difference"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            currentSnapshot = tracemalloc.take_snapshot()
            self.__lastSnapshot = tracemalloc.take_snapshot()
            topStats = currentSnapshot.compare_to(self.__lastSnapshot,
                                                  'traceback')
            self.__lastSnapshot = self.__lastSnapshot
            for stat in topStats:
                print(stat)

            self.__tracker.print_diff()
        except Exception as exc:
            logging.error(str(exc))
        QApplication.restoreOverrideCursor()

    def __referenceBrowser(self):
        """Brings up a reference browser"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        ib = None
        try:
            ib = refbrowser.InteractiveBrowser(self.ide.mainWindow)
        except Exception as exc:
            logging.error(str(exc))
        QApplication.restoreOverrideCursor()
        if ib is not None:
            ib.main()

