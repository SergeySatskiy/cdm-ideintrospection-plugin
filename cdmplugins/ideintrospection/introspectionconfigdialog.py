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

"""Introspection plugin config dialog"""

from ui.qt import (Qt, QDialog, QVBoxLayout, QGroupBox, QSizePolicy,
                   QRadioButton, QDialogButtonBox)


class IntrospectionPluginConfigDialog(QDialog):

    """Introspection plugin config dialog"""

    LOG = 0
    CONSOLE = 1
    NEW_TAB = 2

    def __init__(self, where, parent=None):
        QDialog.__init__(self, parent)

        self.__createLayout()
        self.setWindowTitle("Introspection plugin configuration")

        if where == IntrospectionPluginConfigDialog.LOG:
            self.__logRButton.setChecked(True)
        elif where == IntrospectionPluginConfigDialog.CONSOLE:
            self.__consoleRButton.setChecked(True)
        else:
            self.__newtabRButton.setChecked(True)

        self.__OKButton.setFocus()

    def __createLayout(self):
        """Creates the dialog layout"""
        self.resize(450, 150)
        self.setSizeGripEnabled(True)

        verticalLayout = QVBoxLayout(self)

        whereGroupbox = QGroupBox(self)
        whereGroupbox.setTitle("Introspection information destination")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            whereGroupbox.sizePolicy().hasHeightForWidth())
        whereGroupbox.setSizePolicy(sizePolicy)

        layoutWhere = QVBoxLayout(whereGroupbox)
        self.__logRButton = QRadioButton(whereGroupbox)
        self.__logRButton.setText("Log tab")
        layoutWhere.addWidget(self.__logRButton)
        self.__consoleRButton = QRadioButton(whereGroupbox)
        self.__consoleRButton.setText("Console")
        layoutWhere.addWidget(self.__consoleRButton)
        self.__newtabRButton = QRadioButton(whereGroupbox)
        self.__newtabRButton.setText("New editor tab")
        layoutWhere.addWidget(self.__newtabRButton)

        verticalLayout.addWidget(whereGroupbox)

        buttonBox = QDialogButtonBox(self)
        buttonBox.setOrientation(Qt.Horizontal)
        buttonBox.setStandardButtons(QDialogButtonBox.Ok |
                                     QDialogButtonBox.Cancel)
        self.__OKButton = buttonBox.button(QDialogButtonBox.Ok)
        self.__OKButton.setDefault(True)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.close)
        verticalLayout.addWidget(buttonBox)

    def getCheckedOption(self):
        """Returns what destination is selected"""
        if self.__logRButton.isChecked():
            return IntrospectionPluginConfigDialog.LOG
        if self.__consoleRButton.isChecked():
            return IntrospectionPluginConfigDialog.CONSOLE
        return IntrospectionPluginConfigDialog.NEW_TAB

