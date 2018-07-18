# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2008 - 2014 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.

"""
Show a dialog with available fonts.
"""


import codecs

from PyQt5.QtCore import QSize, Qt, QSortFilterProxyModel, QRegExp
from PyQt5.QtWidgets import (
    QLabel, QWidget, QLineEdit, QVBoxLayout, QTabWidget, QTextEdit,
    QTreeView
)
from PyQt5.QtGui import(
    QStandardItemModel, QStandardItem
)


import app
import job
import log
import qutil
import widgets.dialog


def show_available_fonts(mainwin, info):
    """Display a dialog with the available fonts of LilyPond specified by info."""
    dlg = ShowFontsDialog(mainwin, info)
    qutil.saveDialogSize(dlg, "engrave/tools/available-fonts/dialog/size", QSize(640, 400))
    if not ShowFontsDialog.names:
        dlg.run_lilypond()
    else:
        dlg.populate_widgets()
    dlg.show()


class ShowFontsDialog(widgets.dialog.Dialog):
    """Dialog to show available fonts)"""

    # Cache data in class variables
    log_history = None
    families = None
    names = None
    config_files = None
    config_dirs = None
    font_dirs = None
    re = ''

    def __init__(self, parent, info):

        def create_log_tab():
            # Show original log
            self.logWidget = QWidget()
            self.log = log.Log(self.logWidget)
            logLayout = QVBoxLayout()
            logLayout.addWidget(self.log)
            self.logWidget.setLayout(logLayout)
            self.tabWidget.addTab(self.logWidget, _("LilyPond output"))

        def create_font_tab():
            # Show Font results
            self.fontTreeWidget = QWidget()
            self.msgLabel = QLabel(self.fontTreeWidget)
            self.filterEdit = QLineEdit()
            self.fontTree = QTreeView(self.fontTreeWidget)
            self.fontTree.setHeaderHidden(True)
            treeLayout = QVBoxLayout()
            treeLayout.addWidget(self.msgLabel)
            treeLayout.addWidget(self.fontTree)
            treeLayout.addWidget(self.filterEdit)
            self.fontTreeWidget.setLayout(treeLayout)
            self.tabWidget.addTab(self.fontTreeWidget, _("Fonts"))

        def create_font_model():
            self.treeModel = QStandardItemModel()
            self.proxy = QSortFilterProxyModel()
            self.proxy.setSourceModel(self.treeModel)
            self.fontTree.setModel(self.proxy)
            self.filterEdit.textChanged.connect(self.update_filter)
            self.filter = QRegExp('', Qt.CaseInsensitive)

        def create_misc_tab():
            self.miscWidget = QWidget()
            self.miscTree = QTreeView(self.miscWidget)
            self.miscTree.setHeaderHidden(True)
            miscLayout = QVBoxLayout()
            miscLayout.addWidget(self.miscTree)
            self.miscWidget.setLayout(miscLayout)
            self.tabWidget.addTab(self.miscWidget, _("Miscellaneous"))

        def create_misc_model():
            self.miscModel = QStandardItemModel()
            self.miscTree.setModel(self.miscModel)

        super(ShowFontsDialog, self).__init__(
            parent,
            #TODO: Add buttons to export/copy/print
            buttons=('close',),
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowModality(Qt.NonModal)

        self.lilypond_info = info

        self.tabWidget = QTabWidget(self)
        self.setMainWidget(self.tabWidget)

        create_log_tab()
        create_font_tab()
        create_font_model()
        create_misc_tab()
        create_misc_model()
        app.translateUI(self)


    def translateUI(self):
        self.setWindowTitle(app.caption(_("Available Fonts")))
        self.filterEdit.setPlaceholderText(_("Filter results (type any part of the font family name)"))

    def populate_widgets(self):
        """Populate widgets."""
        self.msgLabel.setText(
            _("{count} font families detected by {version}").format(
                count=len(ShowFontsDialog.names),
                version=self.lilypond_info.prettyName()))
        self.populate_font_tree()
        self.populate_misc()
        self.tabWidget.setCurrentIndex(1)
        self.filterEdit.setText(ShowFontsDialog.re)
        self.filterEdit.setFocus()


    def populate_font_tree(self):
        """Populate the data model to be displayed in the results"""
        root = self.treeModel.invisibleRootItem()
        for name in ShowFontsDialog.names:
            family = ShowFontsDialog.families[name]
            if (len(family.keys()) == 1) and (name in family.keys()):
                # Single family, multiple styles
                family_item = QStandardItem(name)
                root.appendRow(family_item)
                for style in sorted(family[name]):
                    family_item.appendRow(QStandardItem(style))
            else:
                # Multiple family (e.g. XX, XX Cond, XX Ext)
                family_item = QStandardItem(name)
                root.appendRow(family_item)
                for weight in sorted(family.keys()):
                    if len(family[weight]) == 1:
                        # One style for the weight
                        family_item.appendRow(
                            QStandardItem(
                                '{} ({})'.format(weight,family[weight][0])))
                    else:
                        # Multiple styles for the weight
                        weight_item = QStandardItem(weight)
                        family_item.appendRow(weight_item)
                        for style in family[weight]:
                            weight_item.appendRow(QStandardItem(style))


    def populate_misc(self):
        """Populate the data model for the "Miscellaneous" tab"""
        root = self.miscModel.invisibleRootItem()

        conf_file_item = QStandardItem(_("Configuration Files"))
        root.appendRow(conf_file_item)
        for file in ShowFontsDialog.config_files:
            conf_file_item.appendRow(QStandardItem(file))

        conf_dir_item = QStandardItem(_("Configuration Directories"))
        root.appendRow(conf_dir_item)
        for dir in ShowFontsDialog.config_dirs:
            conf_dir_item.appendRow(QStandardItem(dir))

        font_dir_item = QStandardItem(_("Font Directories"))
        root.appendRow(font_dir_item)
        for dir in ShowFontsDialog.font_dirs:
            font_dir_item.appendRow(QStandardItem(dir))


    def process_results(self):
        """Callback after LilyPond has finished:"""
        self.read_entries()
        self.populate_widgets()


    def run_lilypond(self):
        """Run lilypond from info with the args list, and a job title."""
        j = self.job = job.Job()
        j.decode_errors = 'replace'
        j.decoder_stdout = j.decoder_stderr = codecs.getdecoder('utf-8')
        j.command = [self.lilypond_info.abscommand() or self.lilypond_info.command] + ['-dshow-available-fonts']
        j.set_title(_("Available Fonts"))
        self.msgLabel.setText(_("Running LilyPond to list fonts ..."))
        self.log.connectJob(j)
        j.done.connect(self.process_results)
        j.start()


    def read_entries(self):
        """Parse the job history list to dictionaries."""
        ShowFontsDialog.log_history = []
        ShowFontsDialog.families = {}
        ShowFontsDialog.names = []
        ShowFontsDialog.config_files = []
        ShowFontsDialog.config_dirs = []
        ShowFontsDialog.font_dirs = []
        ShowFontsDialog.re = ''

        # Process job history into flat string list
        for line in self.job.history():
            lines = line[0].split('\n')
            for l in lines:
                ShowFontsDialog.log_history.append(l)

        # Parse entries
        last_family = None
        for e in ShowFontsDialog.log_history:
            if e.startswith('family'):
                last_family = e[7:]
                if not last_family in ShowFontsDialog.families.keys():
                    ShowFontsDialog.families[last_family] = {}
            elif last_family:
                self.update_family(last_family, e)
                last_family = None
            elif e.startswith('Config files:'):
                ShowFontsDialog.config_files.append(e[14:])
            elif e.startswith('Font dir:'):
                ShowFontsDialog.font_dirs.append(e[10:])
            elif e.startswith('Config dir:'):
                ShowFontsDialog.config_dirs.append(e[12:])

        # Store sorted reference lists.
        ShowFontsDialog.names = sorted(
            ShowFontsDialog.families.keys(), key=lambda s: s.lower())
        ShowFontsDialog.config_files = sorted(
            ShowFontsDialog.config_files, key=lambda s: s.lower())
        ShowFontsDialog.config_dirs = sorted(
            ShowFontsDialog.config_dirs, key=lambda s: s.lower())
        ShowFontsDialog.font_dirs = sorted(
            ShowFontsDialog.font_dirs, key=lambda s: s.lower())


    def update_family(self, family_name, input):
        """Parse a font face definition."""
        family = ShowFontsDialog.families[family_name]
        input = input.strip().split(':')
        # This is a safeguard agains improper entries
        if len(input) == 2:
            name = input[0].split(',')[-1]
            if not name in family.keys():
                family[name] = []
            family[name].append(input[1][6:])


    def update_filter(self):
        """Filter font results"""
        ShowFontsDialog.re = re = self.filterEdit.text()
        self.filter.setPattern(re)
        self.proxy.setFilterRegExp(self.filter)