import os

import cv2
from PyQt5.QtCore import Qt, QPoint, QTimer, QCoreApplication, QRegExp, QLine
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QWidget, QHBoxLayout, QVBoxLayout, QButtonGroup
from PyQt5.QtGui import QIcon, QImage, QPixmap, QRegExpValidator, QPainter, QColor, QPen
from PyQt5 import QtWidgets, QtCore, QtGui
import forgrasplabel
import sys
import numpy as np

def ui_main():

    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.setQuitOnLastWindowClosed(True)

    wind = Gmui()
    wind.setWindowFlags(Qt.WindowMaximizeButtonHint)
    wind.setWindowFlags(Qt.Window)
    # wind.resize(100, 100)
    # wind.move(300, 300)
    wind.setupUi(wind)
    wind.setupUiplus()
    wind.show()

    sys.exit(app.exec_())


class Gmui(QMainWindow, forgrasplabel.Ui_ForGraspLabel):
    def __init__(self):
        super(Gmui, self).__init__()
        self.datasetPath = ''
        self.labelPath = ''
        self.classListFile = ''
        # graph para
        self.index = -1
        self.graphNum = 0
        self.scale = 1
        self.windowsize = [0, 0]
        self.gsize = [0, 0]
        self.fixedHeight = 0
        self.graphcache = None
        # three lists
        self.graphs = []  # hold a list for graph names
        self.labels = []  # for every graph
        self.classes = []  # hold a list for class names
        self.onSelectLabel = -1
        self.onSelectClass = 0
        # last operation: Every item includes the operation code and data, data varies among the code.
        self.undoList = []
        self.redoList = []

        # mouse para
        self.onDrawing = False
        self.startPos = None
        self.lastWidth = 40
        self.defaultWidth = 40
        self.jawWidth = 30
        self.scollSpeed = 1

        self.xs = 0
        self.ys = 0
        self.x0 = 0
        self.y0 = 0

        self.radioGroup = QButtonGroup()

    def setupUiplus(self):
        # UI set
        # menu bar
        self.actionDataset_Path.triggered.connect(self.change_dataset_path)
        self.actionClass_File.triggered.connect(self.change_class_file)
        self.actionLabel_Path.triggered.connect(self.change_label_path)
        self.actionBoth_Path.triggered.connect(self.change_both_path)
        self.actionAutoResize.triggered.connect(self.switch_graph)
        # right panel
        self.lastButton.clicked.connect(self.last_page)
        self.nextButton.clicked.connect(self.next_page)
        self.stepNum.returnPressed.connect(self.jump_page)
        self.saveButton.clicked.connect(self.write_txt)
        self.deleteButton.clicked.connect(self.delete_label)
        self.clearButton.clicked.connect(self.clear_label)
        self.scollSpeedSlider.valueChanged.connect(self.change_scoll_speed)
        self.jawWidthInput.returnPressed.connect(self.change_jaw_width)
        self.undoButton.clicked.connect(self.undo_operation)
        self.redoButton.clicked.connect(self.redo_operation)
        # list behavior
        self.labelList.itemClicked.connect(self.label_list_click)
        self.classList.itemClicked.connect(self.class_list_click)
        # self.labelList.currentRowChanged.connect(self.label_list_select)
        # self.classList.currentRowChanged.connect(self.class_list_select)
        # Radio Button
        self.radioGroup.addButton(self.simpleWidthRadio)
        self.radioGroup.addButton(self.complexWidthRadio)
        self.radioGroup.setExclusive(True)

        # input number only
        reg = QRegExp('[0-9]+$')
        validator = QRegExpValidator(self)
        validator.setRegExp(reg)
        self.stepNum.setValidator(validator)
        self.jawWidthInput.setValidator(validator)
        # start tracking on open
        self.setMouseTracking(True)
        self.widget_2.setMouseTracking(True)
        self.graphWidget.setMouseTracking(True)
        self.centralwidget.setMouseTracking(True)
        self.graphWindow.setMouseTracking(True)
        # set view
        self.fixedHeight = self.height() * 0.8

    # graph operation
    def next_page(self):
        if self.index == -1:
            return
        if self.autosaveCheck.isChecked():
            self.write_txt()  # last graph`s
        if self.index < self.graphNum - 1:
            self.index = self.index + 1
        self.switch_graph()
        # self.stepNum.setText(str(self.index + 1))

    def last_page(self):
        if self.index == -1:
            return
        if self.autosaveCheck.isChecked():
            self.write_txt()  # last graph`s
        if self.index > 0:
            self.index = self.index - 1
        self.switch_graph()
        # self.stepNum.setText(str(self.index+1))

    def jump_page(self):
        if self.index == -1:
            return
        if self.autosaveCheck.isChecked():
            self.write_txt()  # last graph`s
        # page = index + 1
        page = int(self.stepNum.text())
        # do the jump
        if (page - 1) >= self.graphNum:
            self.stepNum.setText(str(self.graphNum))
            page = self.graphNum
        elif (page - 1) < 0:
            self.stepNum.setText('1')
            page = 1
        else:
            self.stepNum.setText(str(page))
        self.index = page - 1
        self.switch_graph()

    def switch_graph(self):
        # clear cache
        self.resize_windows()
        self.onDrawing = False
        self.startPos = None
        self.undoList = []
        self.redoList = []
        # print message
        self.stepNum.setText(str(self.index + 1))
        self.setWindowTitle(str(self.graphs[self.index]) + ' - Grasp Path Marker')
        # read labels
        self.onSelectLabel = -1
        self.load_txt()
        # read and draw image
        self.paint_graph()
        self.windowsize = [self.gsize[0] * self.scale, self.gsize[1] * self.scale]

    def calc_box(self, label):
        # draw polylines
        this_line = np.array(label[:4]).reshape(2, 2).astype(np.float)
        orientation = this_line[1] - this_line[0]
        v_orientation = np.array((orientation[1], -orientation[0]))
        v_orientation /= np.linalg.norm(v_orientation)
        boxOut = np.array([(this_line[0] + v_orientation * (int(label[4]) // 2)).astype(np.int),
                           (this_line[1] + v_orientation * (int(label[4]) // 2)).astype(np.int),
                           (this_line[1] - v_orientation * (int(label[4]) // 2)).astype(np.int),
                           (this_line[0] - v_orientation * (int(label[4]) // 2)).astype(np.int)])
        box = [this_line, boxOut] # line and outer box 
        if len(label) > 6:
            boxIn = np.array([(this_line[0] + v_orientation * (int(label[6]) // 2)).astype(np.int),
                              (this_line[1] + v_orientation * (int(label[6]) // 2)).astype(np.int),
                              (this_line[1] - v_orientation * (int(label[6]) // 2)).astype(np.int),
                              (this_line[0] - v_orientation * (int(label[6]) // 2)).astype(np.int)])
            # box = np.vstack((boxOut, boxIn))
            box.append(boxIn) # inner box
        return box

    def draw_path(self, graph):
        for l in self.labels:
            box = self.calc_box(l)
            cv2.line(graph, box[0][0].astype(np.int), box[0][1].astype(np.int), (255, 255, 255), 2)
            cv2.polylines(graph, [box[1]], True, (255, 0, 0), 1)
            if len(box) > 2:
                cv2.polylines(graph, [box[2]], True, (255, 0, 255), 1)
        # draw high light
        if self.onSelectLabel != -1:
            l = self.labels[self.onSelectLabel]
            box = self.calc_box(l)
            cv2.line(graph, box[0][0].astype(np.int), box[0][1].astype(np.int), (0, 255, 255), 2)
            cv2.polylines(graph, [box[1]], True, (0, 255, 255), 1)
            if len(box) > 2:
                cv2.polylines(graph, [box[2]], True, (0, 255, 255), 1)
        return graph

    def draw_prepath(self, qmap):
        p1 = QPoint(self.startPos[0], self.startPos[1])
        p2 = QPoint(self.xs, self.ys)
        painter = QPainter(qmap)
        c = QColor(255, 255, 255)
        pen = QPen()
        pen.setColor(c)
        pen.setWidth(4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setStyle(Qt.DashDotLine)
        painter.setPen(pen)
        painter.drawLine(p1, p2)
        return qmap

    def paint_graph(self):
        graphRaw = self.load_graph(self.datasetPath + self.graphs[self.index])
        graphDraw = self.draw_path(graphRaw)
        graphShow = cv2.cvtColor(graphDraw, cv2.COLOR_BGR2RGB)
        # to QImage
        showImage = QImage(graphShow.data, graphShow.shape[1], graphShow.shape[0], QImage.Format_RGB888)
        # IMPORTANT calculate the scale for labeling

        self.scale = self.fixedHeight / showImage.height()
        scaled = showImage.scaled(self.scale * showImage.width(), self.scale * showImage.height())
        self.graphcache = scaled
        # if self.onDrawing:
        #     scaled = self.draw_prepath(scaled)
        self.graphWindow.setPixmap(QPixmap.fromImage(scaled))

    def realtime_graph(self):
        # self.graphWindow.setPixmap(QPixmap.fromImage(self.graphcache))
        # self.graphWindow.setPixmap()
        r = self.graphcache.copy()
        rendered = self.draw_prepath(r)
        self.graphWindow.setPixmap(QPixmap.fromImage(r))

    # change file paths  --link to menu bar
    def change_class_file(self):  # refresh classes list at once
        path = QFileDialog.getOpenFileName(self, 'Select File', '', 'Text Files(*.txt)')
        if path[0] != '':
            self.classListFile = path[0]
            # self.classes = None
            self.load_classes()

    def change_dataset_path(self):  # refresh graphs list at once
        path = QFileDialog.getExistingDirectory(self, 'Select Dataset Path')
        if path != '':
            self.datasetPath = path + '/'
            self.load_dataset()

    def change_label_path(self):  # dont refresh the label list, label list is for single graph!
        path = QFileDialog.getExistingDirectory(self, 'Select Label Path')
        if path != '':
            self.labelPath = path + '/'
            if self.datasetPath:
                self.load_dataset()

    def change_both_path(self):  # last two path
        path = QFileDialog.getExistingDirectory(self, 'Select Dataset and Label Path')
        if path != '':
            self.datasetPath = path + '/'
            self.labelPath = path + '/'
            self.load_dataset()

    def resize_windows(self):
        self.fixedHeight = self.graphWindow.height() - 2

    # file operation
    def load_graph(self, src):
        # decode
        graph = cv2.imread(src)
        self.gsize = [graph.shape[1], graph.shape[0]]  # y,x
        # graph.shape[0], graph.shape[1]
        return graph

    def load_txt(self):
        # get txt name
        src = self.labelPath + self.graphs[self.index]
        pos = src.rfind('.')
        src = src[:pos] + '.txt'
        if os.path.exists(src):
            with open(src, "r") as f: 
                lines = f.readlines()
                paths = []
                for l in lines:
                    l = l.strip('\n')
                    path = l.split()
                    paths.append(path)
                self.labels = paths
        else:
            os.mknod(src)
            self.labels = []
            # return None
        self.show_label_list()

    def load_dataset(self):
        self.graphs = []
        graphs = os.listdir(self.datasetPath)
        # do filter
        for g in graphs:
            extension = g.split('.')[-1]
            if extension == 'jpg' or extension == 'png' or extension == 'bmp' or extension == 'jpeg':
                self.graphs.append(g)
        self.index = 0
        self.graphNum = len(self.graphs)
        self.switch_graph()

    def load_classes(self):
        if os.path.exists(self.classListFile):
            with open(self.classListFile, "r") as f:
                lines = f.readlines()
                classes = []
                for l in lines:
                    l = l.strip('\n')
                    className = l
                    classes.append(className)
                self.classes = classes
                self.show_class_list()

    def write_txt(self):
        if self.index == -1:
            return
        # get txt name
        src = self.labelPath + self.graphs[self.index]
        pos = src.rfind('.')
        src = src[:pos] + '.txt'
        if os.path.exists(src):
            with open(src, "w") as f:
                f.truncate(0)  # total clean
                for l in self.labels:
                    if len(l) < 7:
                        f.write(
                            str(l[0]) + ' ' + str(l[1]) + ' ' + str(l[2]) + ' ' + str(l[3]) + ' ' + str(
                                l[4]) + ' ' + str(
                                l[5]) + ' \n')
                    else:
                        f.write(
                            str(l[0]) + ' ' + str(l[1]) + ' ' + str(l[2]) + ' ' + str(l[3]) + ' ' + str(
                                l[4]) + ' ' + str(l[5]) + ' ' + str(l[6])
                            + ' \n')

    # undo and redo operation
    def undo_manage(self, undo):
        self.undoList.append(undo)
        if len(self.undoList) > 100:
            self.undoList.pop(0)
        # print(self.undoList)
        # print(self.onSelectLabel)

    def redo_manage(self, redo):
        self.redoList.append(redo)
        if len(self.redoList) > 100:
            self.redoList.pop(0)
        # print(self.redoList)

    def undo_operation(self):
        if len(self.undoList) == 0:
            return
        undo = self.undoList.pop()
        self.redo_manage(undo)
        # print(self.onSelectLabel)
        # print('undo',undo)
        if undo[0] == 0:  # point A set
            self.onDrawing = False
            self.startPos = None
            self.paint_graph()
        elif undo[0] == 1:  # point B set     two possible situation: has last select or not
            self.labels.pop()
            if undo[1][8] == -1:
                self.onSelectLabel = undo[1][8]
                # self.labels.pop()
            else:
                self.onSelectLabel = undo[1][8]
                # self.labels.pop(undo[1][8] + 1)

            self.show_label_list()
            self.startPos = undo[1][:4]
            self.paint_graph()
            self.realtime_graph()
        elif undo[0] == 2:  # unselect
            self.onSelectLabel = undo[1]
            self.select_label()
            self.paint_graph()
            self.show_label_list()
        elif undo[0] == 3:  # unselect and exit drawing
            self.onSelectLabel = undo[1][4]
            self.select_label()
            self.startPos = undo[1][:4]
            self.onDrawing = True
            self.paint_graph()
            self.realtime_graph()
            self.show_label_list()
        elif undo[0] == 4:  # delete label
            self.labels.insert(undo[1][-1],undo[1][:-1])
            self.onSelectLabel = undo[1][-1]
            self.show_label_list()
            self.paint_graph()
        elif undo[0] == 5:  # clear label
            self.labels=undo[1][:-1]
            self.onSelectLabel = undo[1][-1]
            self.paint_graph()
            self.show_label_list()
        elif undo[0] == 6:  # select label
            self.onSelectLabel = undo[1][0]
            self.select_label()
            self.paint_graph()
            self.show_label_list()
            self.show_class_list()
        elif undo[0] == 7:  # change width
            self.labels[self.onSelectLabel][4] = undo[1][0]
            if len(self.labels[self.onSelectLabel]) > 6:
                self.labels[self.onSelectLabel][6] = undo[1][1]
            self.paint_graph()
            self.show_label_list()
        elif undo[0] == 8:  # change class
            # self.labels[self.onSelectLabel][5] = undo[1][0]
            # self.paint_graph()
            self.onSelectClass = undo[1][0]
            self.activate_class()
            self.show_class_list()
            # self.show_label_list()

    def redo_operation(self):
        if len(self.redoList) == 0:
            return
        redo = self.redoList.pop()
        self.undo_manage(redo)
        # print('redo', redo)
        if redo[0] == 0:
            self.startPos = redo[1][:4]
            self.onDrawing = True
            self.paint_graph()
            self.realtime_graph()
        elif redo[0] == 1:
            # self.labels.append(redo[1][9:])
            self.labels.append(redo[1][9:])
            self.onSelectLabel = len(self.labels) - 1
            self.show_label_list()
            self.startPos = redo[1][4:8]
            self.paint_graph()
            self.realtime_graph()
        elif redo[0] == 2:
            self.unselect_label()
            self.paint_graph()
        elif redo[0] == 3:
            self.unselect_label()
            self.onDrawing = False
            self.startPos = None
            self.paint_graph()
        elif redo[0] == 4:
            # self.labels.pop()
            self.labels.pop(redo[1][-1])
            self.onSelectLabel = -1
            self.paint_graph()
            self.show_label_list()
        elif redo[0] == 5:
            self.labels = []
            self.onSelectLabel = -1
            self.paint_graph()
            self.show_label_list()
        elif redo[0] == 6:
            self.onSelectLabel = redo[1][1]
            self.select_label()
            self.paint_graph()
            self.show_label_list()
            self.show_class_list()
        elif redo[0] == 7:
            self.labels[self.onSelectLabel][4] = redo[1][2]
            if len(self.labels[self.onSelectLabel]) > 6:
                self.labels[self.onSelectLabel][6] = redo[1][3]
            self.paint_graph()
            self.show_label_list()
        elif redo[0] == 8:
            # self.labels[self.onSelectLabel][5] = redo[1][1]
            # self.paint_graph()
            self.onSelectClass = redo[1][1]
            self.activate_class()
            self.show_class_list()
            # self.show_label_list()

    # label operation
    def activate_class(self):  # modify the class of selected label
        if self.onSelectLabel != -1:
            self.labels[self.onSelectLabel][5] = self.onSelectClass
            self.show_label_list()

    def add_label(self, x1, y1, x2, y2):
        if self.simpleWidthRadio.isChecked():
            l = [x1, y1, x2, y2, self.lastWidth, self.onSelectClass]
        else:  # save the obj width
            l = [x1, y1, x2, y2, self.lastWidth, self.onSelectClass, self.lastWidth - self.jawWidth]
        self.labels.append(l)
        self.onSelectLabel = len(self.labels) - 1
        self.select_label()
        self.show_label_list()

    def delete_label(self):
        if self.index == -1:
            return
        # NOT delete the last
        if self.onSelectLabel == -1:
            return
        l = self.labels.pop(self.onSelectLabel)
        self.undo_manage([4, l+[self.onSelectLabel]])
        self.redoList = []
        self.onSelectLabel = self.onSelectLabel - 1
        if self.onSelectLabel < 0:
            self.unselect_label()
        else:
            self.select_label()
        self.show_label_list()

    def clear_label(self):
        self.undo_manage([5, self.labels.copy()+[self.onSelectLabel]])
        self.redoList = []
        self.labels = []
        self.unselect_label()
        self.show_label_list()

    def modify_label(self, value):  # width
        lw = int(self.labels[self.onSelectLabel][4])
        lwo = lw - self.jawWidth
        w = int(int(self.labels[self.onSelectLabel][4]) + value)
        if w < self.jawWidth + 1:
            w = self.jawWidth + 1
        wo = w - self.jawWidth
        self.labels[self.onSelectLabel][4] = w
        self.undo_manage([7, [lw, lwo, w, wo]])
        self.redoList = []
        if len(self.labels[self.onSelectLabel]) > 6:
            self.labels[self.onSelectLabel][6] = wo
        self.lastWidth = w
        self.paint_graph()
        # self.select_label()
        self.show_label_list()

    def select_label(self):
        # self.onSelectLabel = item.index()
        self.onSelectClass = self.labels[self.onSelectLabel][5]
        self.show_class_list()
        self.paint_graph()

    def unselect_label(self):
        self.onSelectLabel = -1
        self.labelList.setCurrentRow(self.onSelectLabel)
        # no need to unselect class
        self.paint_graph()

    # UI function
    def show_label_list(self):
        self.labelList.clear()
        for l in self.labels:
            label = 'P0(' + str(l[0]) + ',' + str(l[1]) + ')' + ' width:' + str(l[4]) + '\nP1(' + str(l[2]) + ',' + str(
                l[3]) + ')' + ' class:' + str(l[5]) + '\n'
            self.labelList.addItem(label)

        self.labelList.setCurrentRow(self.onSelectLabel)

    def show_class_list(self):
        self.classList.clear()
        for className in self.classes:
            self.classList.addItem(className)
        # if self.onSelectClass != -1:
        self.classList.setCurrentRow(int(self.onSelectClass))

    def label_list_select(self):
        if self.labelList.currentRow() > -1:
            # self.onSelectLabel = self.labelList.currentRow()
            self.undo_manage([6, [self.onSelectLabel, self.labelList.currentRow()]])
            self.redoList = []
            self.onSelectLabel = self.labelList.currentRow()
            self.select_label()
        else:
            self.unselect_label()

    def class_list_select(self):
        if self.classList.currentRow() > -1:
            # self.onSelectClass = self.classList.currentRow()
            self.undo_manage([8, [self.onSelectClass, self.classList.currentRow()]])
            self.redoList = []
            self.onSelectClass = self.classList.currentRow()
            self.activate_class()

    def label_list_click(self, item):
        self.labelList.setCurrentRow(self.labelList.row(item))
        self.label_list_select()

    def class_list_click(self, item):
        self.classList.setCurrentRow(self.classList.row(item))
        self.class_list_select()

    def change_scoll_speed(self):
        self.scollSpeed = self.scollSpeedSlider.value()

    def change_jaw_width(self):
        self.jawWidth = int(self.jawWidthInput.text())

    def show_axis(self):
        axis = 'Scaled:(' + str(self.xs) + ',' + str(self.ys) + ')   Origin:(' + str(self.x0) + ',' + str(self.y0) + ')'
        self.axisLabel.setText(axis)

    # overwrite mouse event
    def mouseMoveEvent(self, e):
        # calculate mouse pos
        xs = e.x() - self.graphWidget.geometry().x() - self.graphWindow.geometry().x() - self.centralwidget.geometry().x() - self.widget_2.geometry().x() - 1
        ys = e.y() - self.graphWidget.geometry().y() - self.graphWindow.geometry().y() - self.centralwidget.geometry().y() - self.widget_2.geometry().y() - 1
        if xs < 0:
            xs = 0
        elif xs > self.windowsize[0]:
            xs = self.windowsize[0]
        if ys < 0:
            ys = 0
        elif ys > self.windowsize[1]:
            ys = self.windowsize[1]
        x0 = round(xs / self.scale)
        y0 = round(ys / self.scale)
        # refresh mouse pos
        if 0 < x0 < self.gsize[0] and 0 < y0 < self.gsize[1]:
            self.xs = xs
            self.ys = ys
            self.x0 = x0
            self.y0 = y0
        self.show_axis()
        if self.onDrawing:
            self.realtime_graph()

    def mousePressEvent(self, e):
        if self.graphWindow.underMouse() and self.index != -1:
            if self.onDrawing:
                # leftclick get the post-point, save new label, and go on
                if e.buttons() == QtCore.Qt.LeftButton:
                    # scaled and origin pos, scaled for render and origin for data
                    endPos = [self.xs, self.ys, self.x0, self.y0]
                    s = self.onSelectLabel
                    self.add_label(self.startPos[2], self.startPos[3], endPos[2], endPos[3])
                    self.undo_manage([1, self.startPos.copy()+endPos.copy()+[s]+self.labels[-1]])
                    self.redoList = []
                    # self.undo_manage([1, self.startPos.copy()+[self.onSelectLabel]])
                    self.startPos = endPos
                # rightclick drop pre-point, turn off the drawing state, unselect last label
                elif e.buttons() == QtCore.Qt.RightButton:
                    self.undo_manage([3, self.startPos.copy()+[self.onSelectLabel]])
                    self.redoList = []
                    self.onDrawing = False
                    self.startPos = None
                    self.unselect_label()
            else:
                # leftclick turn on the drawing state and hold a pre-point, (back to default width?)
                if e.buttons() == QtCore.Qt.LeftButton:
                    # self.lastWidth = self.defaultWidth
                    self.onDrawing = True
                    self.startPos = [self.xs, self.ys, self.x0, self.y0]
                    self.undo_manage([0, self.startPos.copy()+[self.onSelectLabel]])
                    self.redoList = []
                # rightclick unselect any label
                elif e.buttons() == QtCore.Qt.RightButton:
                    self.undo_manage([2, self.onSelectLabel])
                    self.redoList = []
                    self.unselect_label()

    def wheelEvent(self, e):
        if self.graphWindow.underMouse() and self.index != -1:
            if self.onSelectLabel != -1:
                self.modify_label(e.angleDelta().y() * self.scollSpeed / 120)

    def keyPressEvent(self, e):
        # label list operation
        if e.key() == Qt.Key_Up:
            if self.labelList.currentRow() == 0 or self.labelList.count() == 0:
                return
            if self.labelList.currentRow() == -1:
                self.labelList.setCurrentRow(self.labelList.count() - 1)
                self.label_list_select()
            else:
                self.labelList.setCurrentRow(self.labelList.currentRow() - 1)
                self.label_list_select()
        elif e.key() == Qt.Key_Down:
            if self.labelList.currentRow() > self.labelList.count() - 2 or self.labelList.count() == 0:
                return
            self.labelList.setCurrentRow(self.labelList.currentRow() + 1)
            self.label_list_select()
        # class list operation
        elif e.key() == Qt.Key_Left:
            if self.classList.currentRow() < 1 or self.classList.count() == 0:
                return
            self.classList.setCurrentRow(self.classList.currentRow() - 1)
            self.class_list_select()
        elif e.key() == Qt.Key_Right:
            if self.classList.currentRow() > self.classList.count() - 2 or self.classList.count() == 0:
                return
            self.classList.setCurrentRow(self.classList.currentRow() + 1)
            self.class_list_select()
        elif e.key() == Qt.Key_Q:
            if self.classList.count() < 1:
                return
            self.classList.setCurrentRow(0)
            self.class_list_select()
        elif e.key() == Qt.Key_W:
            if self.classList.count() < 2:
                return
            self.classList.setCurrentRow(1)
            self.class_list_select()
        elif e.key() == Qt.Key_E:
            if self.classList.count() < 3:
                return
            self.classList.setCurrentRow(2)
            self.class_list_select()
        elif e.key() == Qt.Key_R:
            if self.classList.count() < 4:
                return
            self.classList.setCurrentRow(3)
            self.class_list_select()
        elif e.key() == Qt.Key_T:
            if self.classList.count() < 5:
                return
            self.classList.setCurrentRow(4)
            self.class_list_select()
        elif e.key() == Qt.Key_Y:
            if self.classList.count() < 6:
                return
            self.classList.setCurrentRow(5)
            self.class_list_select()
        elif e.key() == Qt.Key_U:
            if self.classList.count() < 7:
                return
            self.classList.setCurrentRow(6)
            self.class_list_select()
        elif e.key() == Qt.Key_I:
            if self.classList.count() < 8:
                return
            self.classList.setCurrentRow(7)
            self.class_list_select()
        elif e.key() == Qt.Key_O:
            if self.classList.count() < 9:
                return
            self.classList.setCurrentRow(8)
            self.class_list_select()
        elif e.key() == Qt.Key_P:
            if self.classList.count() < 10:
                return
            self.classList.setCurrentRow(9)
            self.class_list_select()
        # right panel operation
        # scollbar
        elif e.key() == Qt.Key_A:
            if self.scollSpeedSlider.value() > 10:
                self.scollSpeedSlider.setValue(self.scollSpeedSlider.value() - 10)
            else:
                self.scollSpeedSlider.setValue(1)
            # self.change_scoll_speed()
        elif e.key() == Qt.Key_D:
            if self.scollSpeedSlider.value() < 90:
                self.scollSpeedSlider.setValue(self.scollSpeedSlider.value() + 10)
            else:
                self.scollSpeedSlider.setValue(100)
            # self.change_scoll_speed()


if __name__ == '__main__':
    ui_main()
