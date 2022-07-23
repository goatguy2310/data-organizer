import shutil
import json
import time
import sys
import os
import re

import PyQt5
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QDialogButtonBox, QFileDialog, QBoxLayout, QWidget, QPushButton, QLabel, QProgressBar, QMessageBox, QComboBox, QTreeWidget, QTreeWidgetItem
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QThread

class EditDialog(QDialog):
    def __init__(self, title, item, parent):
        super(EditDialog, self).__init__(parent)
        self.item = item
        self.parent = parent
        self.path = None
        if item is not None:
            self.key = item.text(0)
            self.act = item.text(1)
            if not self.act.startswith('Delete'):
                self.path = self.act[8:]
        
        self.setWindowTitle(title)

        self.layout = QBoxLayout(QBoxLayout.TopToBottom)
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel('Choose a hotkey and an action'))

        self.lb_hotkey = QLabel(f"Hotkey: {'None' if item is None else item.text(0)}")
        self.layout.addWidget(self.lb_hotkey)
        self.btn_listen = QPushButton('Listen')
        self.btn_listen.clicked.connect(self.on_listen_clicked)
        self.layout.addWidget(self.btn_listen)

        self.layout.addWidget(QLabel('Choose an action'))

        self.act_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.layout.addLayout(self.act_layout)

        self.cb_action = QComboBox()
        self.cb_action.addItem('Copy to')
        self.cb_action.addItem('Move to')
        self.cb_action.addItem('Delete')
        self.cb_action.currentTextChanged.connect(self.on_action_changed)
        self.act_layout.addWidget(self.cb_action)

        self.btn_dir = QPushButton('Choose a directory')
        if self.path is not None:
            self.btn_dir.setText(self.path)
        self.btn_dir.clicked.connect(self.on_dir_clicked)
        self.act_layout.addWidget(self.btn_dir)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)

    def on_listen_clicked(self):
        self.listen = True
        self.key = None
        self.btn_listen.setText('Listening...')
        self.btn_listen.setEnabled(False)
        self.cb_action.setEnabled(False)
        self.btn_dir.setEnabled(False)
        self.buttonBox.setEnabled(False)

    def keyPressEvent(self, event):
        if self.listen:
            self.listen = False
            self.recorded_key = QKeySequence(event.key()).toString()
            if re.search(r'[\uD800-\uDFFF]', self.recorded_key) is not None:
                self.msg = QMessageBox()
                self.msg.setIcon(QMessageBox.Warning)
                self.msg.setWindowTitle('Invalid key')
                self.msg.setText('This key cannot be used as a hotkey')
                self.msg.show()

                self.btn_listen.setText('Listen')
                self.btn_listen.setEnabled(True)
                self.cb_action.setEnabled(True)
                self.btn_dir.setEnabled(True)
                self.buttonBox.setEnabled(True)
                return

            self.key = QKeySequence(event.key()).toString()

            self.btn_listen.setText('Listen')
            self.btn_listen.setEnabled(True)
            self.cb_action.setEnabled(True)
            self.btn_dir.setEnabled(True)
            self.buttonBox.setEnabled(True)
            self.lb_hotkey.setText(f"Hotkey: {self.key}")

    def on_action_changed(self, event):
        if event == 'Copy to' or event == 'Move to':
            self.btn_dir.setVisible(True)
        else:
            self.btn_dir.setVisible(False)

    def on_dir_clicked(self):
        dir = QFileDialog.getExistingDirectory(self, 'Choose a directory')
        self.btn_dir.setText(dir)

    def accept(self):
        if self.key is None:
            self.msg = QMessageBox()
            self.msg.setIcon(QMessageBox.Warning)
            self.msg.setWindowTitle('Invalid key')
            self.msg.setText('Please choose a hotkey')
            self.msg.show()
            return
        if self.cb_action.currentText() == 'Copy to' or self.cb_action.currentText() == 'Move to':
            if self.btn_dir.text() == 'Choose a directory':
                self.msg = QMessageBox()
                self.msg.setIcon(QMessageBox.Warning)
                self.msg.setWindowTitle('Invalid directory')
                self.msg.setText('Please choose a directory')
                self.msg.show()
                return

        if self.parent.action_tree.findItems(self.key, Qt.MatchExactly) and self.item is None:
            self.msg = QMessageBox()
            self.msg.setIcon(QMessageBox.Warning)
            self.msg.setWindowTitle('Invalid key')
            self.msg.setText('This key is already used')
            self.msg.show()
            return
        
        if self.item is None:
            QTreeWidgetItem(self.parent.action_tree, [self.key, self.cb_action.currentText() + ' ' + self.btn_dir.text() if self.cb_action.currentText() != 'Delete' else 'Delete'])
        else:
            self.item.setText(0, self.key)
            self.item.setText(1, self.cb_action.currentText() + ' ' + self.btn_dir.text() if self.cb_action.currentText() != 'Delete' else 'Delete')

        return super().accept()

class TreeWidget(QTreeWidget):
    def __init__(self, parent):
        super(TreeWidget, self).__init__()
        self.parent = parent
        self.action_tree = None

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        self.key = QKeySequence(event.key()).toString()
        if re.search(r'[\uD800-\uDFFF]', self.key) is not None:
            return

        for i in range(self.action_tree.topLevelItemCount()):
            if self.action_tree.topLevelItem(i).text(0) == self.key:
                self.parent.btn_ac.setText(self.action_tree.topLevelItem(i).text(1))
                self.parent.act[self.parent.lb_file.text()] = self.action_tree.topLevelItem(i).text(1)

                with open(self.parent.img_dir + '/-save-.txt', 'w') as f:
                    f.write(json.dumps(self.parent.act))
                self.parent.lb_saved.setText('Auto-saved to ' + self.parent.img_dir + '/-save-.txt')
                break

class PerformThread(QThread):
    progress_update = PyQt5.QtCore.pyqtSignal()
    def __init__(self, parent):
        super(PerformThread, self).__init__()
        self.act = parent.act.copy()
        self.img_dir = parent.img_dir

    def run(self):
        for i, ac in enumerate(self.act):
            self.progress_update.emit()
            if self.act[ac].startswith('Copy to'):
                shutil.copy(self.img_dir + '/' + ac, self.act[ac][8:])
            elif self.act[ac].startswith('Move to'):
                shutil.move(self.img_dir + '/' + ac, self.act[ac][8:])
            elif self.act[ac].startswith('Delete'):
                os.remove(self.img_dir + '/' + ac)

class StartWindow(QMainWindow):
    def __init__(self):
        super(StartWindow, self).__init__()
        self.setWindowTitle('Start Window')
        
        self.layout = QBoxLayout(QBoxLayout.LeftToRight)
        self._centralWidget = QWidget(self)
        self._centralWidget.setLayout(self.layout)
        self.setCentralWidget(self._centralWidget)

        self.tree_layout = QBoxLayout(QBoxLayout.TopToBottom)
        self.layout.addLayout(self.tree_layout)

        self.tree = TreeWidget(self)
        self.tree.setHeaderLabels(['None'])
        self.tree.setFixedWidth(250)
        self.tree.currentItemChanged.connect(self.on_item_changed)
        self.tree_layout.addWidget(self.tree)

        self.action_tree = TreeWidget(self)
        self.action_tree.setHeaderLabels(['Key', 'Action'])
        self.action_tree.setFixedWidth(250)
        self.action_tree.setColumnCount(2)
        self.action_tree.itemPressed.connect(self.on_action_item_clicked)
        self.tree_layout.addWidget(self.action_tree)

        self.tree.action_tree = self.action_tree
        self.action_tree.action_tree = self.action_tree

        self.ac_btn_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.tree_layout.addLayout(self.ac_btn_layout)

        self.btn_add = QPushButton('Add')
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.ac_btn_layout.addWidget(self.btn_add)

        self.btn_add = QPushButton('Edit')
        self.btn_add.clicked.connect(self.on_edit_clicked)
        self.ac_btn_layout.addWidget(self.btn_add)

        self.btn_del = QPushButton('Delete')
        self.btn_del.clicked.connect(self.on_del_clicked)
        self.ac_btn_layout.addWidget(self.btn_del)

        self.btn_save = QPushButton('Save hotkeys')
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.tree_layout.addWidget(self.btn_save)

        self.btn_save = QPushButton('Load hotkeys')
        self.btn_save.clicked.connect(self.on_load_clicked)
        self.tree_layout.addWidget(self.btn_save)

        self.img_layout = QBoxLayout(QBoxLayout.TopToBottom)
        self.layout.addLayout(self.img_layout)

        self.lb_ins = QLabel('WELCOME TO DATA ORGANIZER!!!!!!!!\nTo get started, please select the image directory. Accepted file types are png, jpg, and jpeg.')
        self.lb_ins.setAlignment(Qt.AlignCenter)
        self.img_layout.addWidget(self.lb_ins)

        self.btn_dir = QPushButton('Select Image Directory')
        self.btn_dir.clicked.connect(self.on_select_dir_clicked)
        self.img_layout.addWidget(self.btn_dir)

        self.fi = True
        self.act = {}
        self.img_dir = ''
    
    def on_select_dir_clicked(self):
        self.old_dir = self.img_dir
        self.img_dir = str(QFileDialog.getExistingDirectory(self, 'Select Image Directory'))
        if self.img_dir == '': return
        self.btn_dir.setText('Change Image Directory')

        if self.fi:
            self.fi = False
            self.lb_ins.setVisible(False)

            self.lb_file = QLabel('No image found')
            self.img_layout.addWidget(self.lb_file)

            self.lb_saved = QLabel('')
            self.img_layout.addWidget(self.lb_saved)

            self.lb_im = QLabel()
            self.img_layout.addWidget(self.lb_im)

            self.btn_ac = QPushButton('None')
            # self.btn_ac.clicked.connect(self.on_ac_clicked)
            self.img_layout.addWidget(self.btn_ac)

            self.btn_con_ac = QPushButton('Confirm Action')
            self.btn_con_ac.clicked.connect(self.on_con_ac_clicked)
            self.tree_layout.addWidget(self.btn_con_ac)
        else:
            self.msg = QMessageBox()
            self.msg.setIcon(QMessageBox.Warning)
            self.msg.setWindowTitle('Warning')
            self.msg.setText(f'Are you sure you want to change directory? (Please check your work and save the hotkeys before quitting)')
            self.msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            self.msg.setDefaultButton(QMessageBox.No)
            ret = self.msg.exec_()
            if ret == QMessageBox.No:
                self.img_dir = self.old_dir
                return
        
        self.lb_saved.setText('')

        self.act.clear()
        if os.path.exists(self.img_dir + '/-save-.txt'):
            with open(self.img_dir + '/-save-.txt') as f:
                self.act = json.load(f)

        self.load_folder(self.img_dir)
        if self.tree.topLevelItem(0) is not None: 
            self.tree.topLevelItem(0).setSelected(True)
            self.on_item_changed(self.tree.topLevelItem(0))

    def on_item_changed(self, item):
        if self.loading or not item.text(0).endswith(('.png', '.jpg', '.jpeg')):
            return
        self.lb_file.setText(item.text(0))
        self.lb_im.setPixmap(QPixmap(self.img_dir + '\\' + item.text(0)))
        self.lb_im.setScaledContents(True)
        self.lb_im.setFixedWidth(self.lb_im.pixmap().width())
        self.lb_im.setFixedHeight(self.lb_im.pixmap().height())
        self.lb_im.setAlignment(Qt.AlignCenter)
        self.btn_ac.setText('None' if item.text(0) not in self.act else self.act[item.text(0)])

    def load_folder(self, path):
        self.loading = True

        self.tree.clear()
        self.tree.setHeaderLabels([path])
        fs = os.listdir(path)
        fs.sort()
        for f in fs:
            if not f.endswith(('.png', '.jpg', '.jpeg')):
                continue
            parent_itm = QTreeWidgetItem(self.tree, [f])
            parent_itm.setIcon(0, PyQt5.QtGui.QIcon('./icons/super_good_icon.ico'))

        for f in fs:
            if f.endswith(('.png', '.jpg', '.jpeg')):
                continue
            parent_itm = QTreeWidgetItem(self.tree, [f])
            parent_itm.setIcon(0, PyQt5.QtGui.QIcon('./icons/super_bad_icon.ico'))
        self.loading = False

    def on_action_item_clicked(self, item):
        if item.text(0) == 'Key':
            return
        if item.text(1) == 'Action':
            return
        self.action_item = item

    def on_add_clicked(self):
        diag_add = EditDialog('Add Action', None, self)
        diag_add.show()

    def on_edit_clicked(self):
        if self.action_tree.currentItem() is None:
            self.msg = QMessageBox()
            self.msg.setIcon(QMessageBox.Warning)
            self.msg.setWindowTitle('Invalid action')
            self.msg.setText('Please choose an action to edit.')
            self.msg.show()
            return
            
        diag_add = EditDialog('Edit Action', self.action_tree.currentItem(), self)
        diag_add.show()
        # TODO: edit dict items after edit dialog is closed

    def on_del_clicked(self):
        if self.action_tree.currentItem() is None:
            self.msg = QMessageBox()
            self.msg.setIcon(QMessageBox.Warning)
            self.msg.setWindowTitle('Invalid action')
            self.msg.setText('Please choose an action to delete.')
            self.msg.show()
            return

        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Warning)
        self.msg.setWindowTitle('Warning')
        self.msg.setText(f'Are you sure you want to delete this action? ({self.action_tree.currentItem().text(1)})')
        self.msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.msg.setDefaultButton(QMessageBox.No)
        ret = self.msg.exec_()

        if ret == QMessageBox.Yes:
            self.action_tree.takeTopLevelItem(self.action_tree.indexOfTopLevelItem(self.action_tree.currentItem()))
        # TODO: delete dict items after delete dialog is closed

    def on_save_clicked(self):
        self.save_file = QFileDialog.getSaveFileName(self, 'Select Save File', filter='Text files (*.txt)')[0]
        if self.save_file == '': return

        self.act_list = {}
        for i in range(self.action_tree.topLevelItemCount()):
            self.act_list[self.action_tree.topLevelItem(i).text(0)] = self.action_tree.topLevelItem(i).text(1)
        with open(self.save_file, 'w') as f:
            f.write(json.dumps(self.act_list))
        
        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setWindowTitle('Saved')
        self.msg.setText('Saved successfully.')
        self.msg.show()

    def on_load_clicked(self):
        self.load_file = QFileDialog.getOpenFileName(self, 'Select Hotkey File', filter='Text files (*.txt)')[0]
        if self.load_file == '': return

        with open(self.load_file, 'r') as f:
            self.act_list = json.loads(f.read())
        self.act = {}
        for k, v in self.act_list.items():
            self.act[k] = v
            self.action_tree.addTopLevelItem(QTreeWidgetItem([k, v]))
        self.action_tree.topLevelItem(0).setSelected(True)

        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setWindowTitle('Loaded')
        self.msg.setText('Hotkeys successfully loaded.')
        self.msg.show()

    def keyPressEvent(self, event):
        self.key = QKeySequence(event.key()).toString()
        if re.search(r'[\uD800-\uDFFF]', self.key) is not None:
            return
        for i in range(self.action_tree.topLevelItemCount()):
            if self.action_tree.topLevelItem(i).text(0) == self.key:
                self.btn_ac.setText(self.action_tree.topLevelItem(i).text(1))
                self.act[self.lb_file.text()] = self.action_tree.topLevelItem(i).text(1)

                with open(self.img_dir + '/-save-.txt', 'w') as f:
                    f.write(json.dumps(self.act))
                self.lb_saved.setText('Auto-saved to ' + self.img_dir + '/-save-.txt')
                break

    def on_con_ac_clicked(self):
        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Warning)
        self.msg.setWindowTitle('Warning')
        self.msg.setText(f'Are you sure you want to proceed? (Please make a backup of your data before proceeding)')
        self.msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.msg.setDefaultButton(QMessageBox.No)
        ret = self.msg.exec_()

        if ret == QMessageBox.Yes:
            self.bar = QProgressBar()
            self.bar.setRange(0, self.act.__len__())
            self.bar.setValue(0)
            self.tree_layout.addWidget(self.bar)

            self.perform = PerformThread(self)
            self.perform.finished.connect(self.on_perform_finished)
            self.perform.progress_update.connect(self.on_progress_update)
            self.perform.start()
    
    def on_progress_update(self):
        self.bar.setValue(self.bar.value() + 1)
    
    def on_perform_finished(self):
        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setWindowTitle('Success')
        self.msg.setText('All actions have been completed.')
        self.msg.show()

        self.load_folder(self.img_dir)
        self.tree_layout.removeWidget(self.bar)
        del self.bar

    def closeEvent(self, event):
        self.msg = QMessageBox()
        self.msg.setIcon(QMessageBox.Warning)
        self.msg.setWindowTitle('Warning')
        self.msg.setText(f'Are you sure you want to quit? (Please check your work and save the hotkeys before quitting)')
        self.msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.msg.setDefaultButton(QMessageBox.No)
        ret = self.msg.exec_()
        if ret == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = StartWindow()
    win.show()
    sys.exit(app.exec_())