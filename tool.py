import sys
import serial
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from datetime import datetime
import pyqtgraph as pg
from collections import deque
import serial.serialutil

class SerialThread(QThread):
    data_received = pyqtSignal(str, str)

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port # 포트
        self.baudrate = baudrate # 보트레이트
        self.is_running = True # 쓰레드 실행 상태
        self.is_paused = False # 쓰레드 일시 중지 상태

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            while self.is_running:
                if self.is_paused:
                    QThread.msleep(100)
                    continue
                if self.ser.in_waiting > 0:
                    data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    self.data_received.emit(self.port, data) # 시그널 방출, 함수에 데이터 전달
        except serial.serialutil.SerialException as e:
            print(f"오류: {e}")

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.ser.flushInput()
        self.is_paused = False

    def stop(self):
        self.is_running = False
        self.wait()

class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.threads = []
        self.weight_text = "0"
        self.current_row = 0
        self.weight_a = [0] * 9
        self.count = 0
        self.initUI()
        self.setupUI()
        self.setup()
        self.startSerialThread()

        self.installEventFilter(self)

        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(10000)

    def initUI(self):
        self.setWindowTitle('과적 테스트')
        self.resize(2000, 800)
        self.show()

    def setupUI(self):
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setRowCount(4)
        for i in range(5):
            self.table.setHorizontalHeaderItem(i, QTableWidgetItem(f'sensor{i+1}'))
        self.table.setVerticalHeaderLabels(['Laser', 'IMU[x]', 'IMU[y]', 'IMU[z]'])
        self.table.setMaximumHeight(300)
        self.table.setMinimumHeight(250)
        self.table.setMaximumWidth(1000)
        self.table.setMinimumWidth(700)

        self.logging = QTableWidget()
        self.logging.setColumnCount(3)
        self.logging.setHorizontalHeaderLabels(['무게', '포트', '로그'])
        self.logging.setMinimumHeight(300)
        self.logging.setMinimumWidth(500)
        self.logging.horizontalHeader().setStretchLastSection(True)

        self.stop_btn = QPushButton('정지(K)', self)
        self.stop_btn.clicked.connect(self.stop)

        self.restart_btn = QPushButton('재시작(L)', self)
        self.restart_btn.clicked.connect(self.restart)

        self.weight_btn_p = QPushButton('+(P)', self)
        self.weight_btn_p.clicked.connect(self.weightP)

        self.weight_btn_m = QPushButton('-(O)', self)
        self.weight_btn_m.clicked.connect(self.weightM)

        self.weight_btn_z = QPushButton('리셋(I)', self)
        self.weight_btn_z.clicked.connect(self.weightZ)

        self.save_btn = QPushButton('저장(M)', self)
        self.save_btn.clicked.connect(self.save)

        self.save_file_box_log = QTableWidget()
        self.save_file_box_log.setColumnCount(1)
        self.save_file_box_log.setHorizontalHeaderLabels(['저장된 파일'])
        self.save_file_box_log.setMaximumHeight(500)
        self.save_file_box_log.setMaximumWidth(300)
        self.save_file_box_log.horizontalHeader().setStretchLastSection(True)
        self.save_file_box_log.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.weight_table = QTableWidget(3,3)
        self.weight_table.setHorizontalHeaderLabels([f"{i + 1}" for i in range(3)])
        self.weight_table.setVerticalHeaderLabels([f"{i + 1}" for i in range(3)])
        self.weight_table.setMaximumHeight(300)
        self.weight_table.setMinimumHeight(250)
        self.weight_table.setMaximumWidth(1000)
        self.weight_table.setMinimumWidth(500)
        self.weight_table.installEventFilter(self)
        self.weight_table.cellChanged.connect(self.onCellChanged)

        for row in range(3):
            for col in range(3):
                val = QTableWidgetItem(str(self.weight_a[self.count]))
                val.setTextAlignment(Qt.AlignCenter)
                self.weight_table.setItem(row, col, val)
                self.count += 1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_table)

        self.main_layout = QHBoxLayout()
        self.left_layout = QVBoxLayout()

        self.graphWidgets = {}
        self.curves = {}

        self.port_colors = {
            'COM3': 'r',
            'COM4': 'b',
            'COM5': 'g',
            'COM6': 'orange'
        }

        sensor_titles = ["Laser", "IMU[x]", "IMU[y]", "IMU[z]"]

        self.graph_value = pg.PlotWidget()
        self.graph_value.setTitle("Laser Change")
        self.graph_value.setLabel("left", "Change")
        self.graph_value.setLabel("bottom", "Time")
        self.graph_value.addLegend(offset=(30, 30))

        self.curves["Laser Change"] = {}

        for port, color in self.port_colors.items():
            curve = self.graph_value.plot(pen=color, name=f"{port}")
            self.curves["Laser Change"][port] = curve

        self.left_layout.addWidget(self.graph_value)

        for sensor in sensor_titles:
            graph = pg.PlotWidget()
            graph.setTitle(sensor)
            graph.setLabel("left", "Value")
            graph.setLabel("bottom", "Time")

            self.graphWidgets[sensor] = graph

            self.curves[sensor] = {}

            for port, color in self.port_colors.items():
                curve = graph.plot(pen=color)
                self.curves[sensor][port] = curve

            self.left_layout.addWidget(graph)

    def startSerialThread(self):
        self.data_x = {port: deque(maxlen=300) for port in self.port_colors}
        self.data_y = {
            "Laser": {port: deque(maxlen=300) for port in self.port_colors},
            "IMU[x]": {port: deque(maxlen=300) for port in self.port_colors},
            "IMU[y]": {port: deque(maxlen=300) for port in self.port_colors},
            "IMU[z]": {port: deque(maxlen=300) for port in self.port_colors},
        }

        self.laser_changes = {port: deque(maxlen=300) for port in self.port_colors}
        self.prev_laser_values = {port: None for port in self.port_colors}

        ports = list(self.port_colors.keys())
        for port in ports:
            thread = SerialThread(port, 9600)
            thread.data_received.connect(self.handle_serial_data)
            self.threads.append(thread)
            thread.start()

    def handle_serial_data(self, port, data):
        parsed_data = data.split(',')

        if len(parsed_data) < 4:
            return

        try:
            sensor_data = [float(x) if x.replace('.', '', 1).isdigit() else 0 for x in parsed_data]
        except ValueError:
            return

        if not self.data_x[port]:
            self.data_x[port].append(0)
        else:
            self.data_x[port].append(self.data_x[port][-1] + 1)

        self.data_y["Laser"][port].append(sensor_data[0])
        self.data_y["IMU[x]"][port].append(sensor_data[-3])
        self.data_y["IMU[y]"][port].append(sensor_data[-1])
        self.data_y["IMU[z]"][port].append(sensor_data[-2])

        if self.prev_laser_values[port] is not None:
            change = sensor_data[0] - self.prev_laser_values[port]
        else:
            change = 0

        self.laser_changes[port].append(change)
        self.prev_laser_values[port] = sensor_data[0]  # 현재 값을 다음 비교를 위해 저장

        port_index = list(self.port_colors.keys()).index(port)
        self.table.setItem(0, port_index, QTableWidgetItem(str(sensor_data[0])))  # Laser
        self.table.setItem(1, port_index, QTableWidgetItem(str(sensor_data[-3])))  # IMU[x]
        self.table.setItem(2, port_index, QTableWidgetItem(str(sensor_data[-1])))  # IMU[y]
        self.table.setItem(3, port_index, QTableWidgetItem(str(sensor_data[-2])))  # IMU[z]

        for sensor in ["Laser", "IMU[x]", "IMU[y]", "IMU[z]"]:
            x_data = list(self.data_x[port])
            y_data = list(self.data_y[sensor][port])

            min_length = min(len(x_data), len(y_data))
            if min_length > 0:
                self.curves[sensor][port].setData(x_data[-min_length:], y_data[-min_length:])

            if len(x_data) > 30:
                self.graphWidgets[sensor].setXRange(x_data[-20], x_data[-1])

        x_data = list(self.data_x[port])
        y_data = list(self.laser_changes[port])

        min_length = min(len(x_data), len(y_data))
        if min_length > 0:
            self.curves["Laser Change"][port].setData(x_data[-min_length:], y_data[-min_length:])

        if len(x_data) > 30:
            self.graph_value.setXRange(x_data[-20], x_data[-1])

        current_row_count = self.logging.rowCount()
        self.logging.insertRow(current_row_count)
        self.logging.setItem(current_row_count, 0, QTableWidgetItem(str(self.weight_a)))
        self.logging.setItem(current_row_count, 1, QTableWidgetItem(port))
        self.logging.setItem(current_row_count, 2, QTableWidgetItem(data))

        self.logging.scrollToBottom()

    def stop(self):
        for thread in self.threads:
            thread.pause()
        QCoreApplication.processEvents()

    def restart(self):
        for thread in self.threads:
            thread.resume()

    def weightP(self):
        selected_items = self.weight_table.selectedItems()
        if selected_items:
            for val in selected_items:
                try:
                    current_value = int(val.text())

                    row = val.row()
                    col = val.column()

                    index = row * 3 + col
                    self.weight_a[index] = (current_value + 20)
                    val.setText(str(self.weight_a[index]))
                except ValueError:
                    continue

    def weightM(self):
        selected_items = self.weight_table.selectedItems()
        if selected_items:
            for val in selected_items:
                try:
                    current_value = int(val.text())

                    row = val.row()
                    col = val.column()
                    index = row * 3 + col

                    if current_value  < 4:
                        self.weight_a[index] = 0
                        val.setText(str(self.weight_a[index]))
                    else:
                        self.weight_a[index] = (current_value - 20)
                        val.setText(str(self.weight_a[index]))
                except ValueError:
                    continue

    def weightZ(self):
        self.weight_a = [0] * 9
        self.count = 0
        for row in range(3):
            for col in range(3):
                val = QTableWidgetItem(str(self.weight_a[self.count]))
                val.setTextAlignment(Qt.AlignCenter)
                self.weight_table.setItem(row, col, val)
                self.count += 1

    def onCellChanged(self, row, col):
        try:
            item = self.weight_table.item(row, col)
            if item is None:
                return

            new_value = item.text()

            if new_value.isdigit():
                self.weight_a[row * 3 + col] = int(new_value)
            else:
                prev_value = self.weight_a[row * 3 + col]
                item.setText(str(prev_value))
        except Exception as e:
            pass

    def save(self):
        try:
            # 파일 이름 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}.txt"

            with open(file_name, 'w', encoding='utf-8') as file:
                headers = ['Logged Time', '무게', '포트', '로그']
                file.write("\t".join(headers) + "\n")

                row_count = self.logging.rowCount()
                for row in range(row_count):
                    log_data = self.logging.item(row, 2).text() if self.logging.item(row, 2) else ""
                    parsed_data = log_data.split(',')

                    logged_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

                    weight = self.logging.item(row, 0).text() if self.logging.item(row, 0) else ""
                    port = self.logging.item(row, 1).text() if self.logging.item(row, 1) else ""
                    log_content = ",".join(parsed_data[1:]) if len(parsed_data) > 1 else ""

                    file.write(f"{logged_time}\t{weight}\t{port}\t{log_content}\n")

            row_position = self.save_file_box_log.rowCount()
            self.save_file_box_log.insertRow(row_position)
            self.save_file_box_log.setItem(row_position, 0, QTableWidgetItem(file_name))
            self.save_file_box_log.scrollToBottom()

        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"오류 발생: {str(e)}", QMessageBox.Ok)

    def auto_save(self):
        try:
            # 파일 이름 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}.txt"

            with open(file_name, 'w', encoding='utf-8') as file:
                headers = ['Logged Time', '무게', '포트', '로그']
                file.write("\t".join(headers) + "\n")

                row_count = self.logging.rowCount()
                for row in range(row_count):
                    log_data = self.logging.item(row, 2).text() if self.logging.item(row, 2) else ""
                    parsed_data = log_data.split(',')

                    logged_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

                    weight = self.logging.item(row, 0).text() if self.logging.item(row, 0) else ""
                    port = self.logging.item(row, 1).text() if self.logging.item(row, 1) else ""
                    log_content = ",".join(parsed_data[1:]) if len(parsed_data) > 1 else ""

                    file.write(f"{logged_time}\t{weight}\t{port}\t{log_content}\n")

            row_position = self.save_file_box_log.rowCount()
            self.save_file_box_log.insertRow(row_position)
            self.save_file_box_log.setItem(row_position, 0, QTableWidgetItem(file_name))
            self.save_file_box_log.scrollToBottom()

        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"오류 발생: {str(e)}", QMessageBox.Ok)

    def update_table(self):
        if self.current_row < len(self.data):
            row_data = self.data[self.current_row]
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            self.table.setItem(row_position, 0, QTableWidgetItem(row_data))
            self.current_row += 1
        else:
            self.timer.stop()

    def restart_arduino(self):
        for thread in self.threads:
            if hasattr(thread, 'ser') and thread.ser.is_open:
                thread.ser.dtr = False
                QThread.msleep(100)
                thread.ser.dtr = True

    def setup(self):

        weight_input_layout2 = QHBoxLayout()
        weight_input_layout2.addWidget(self.weight_btn_p)
        weight_input_layout2.addWidget(self.weight_btn_m)

        layout_btn1 = QHBoxLayout()
        layout_btn1.addWidget(self.stop_btn)
        layout_btn1.addWidget(self.restart_btn)

        layout_btn2 = QVBoxLayout()
        layout_btn2.addLayout(weight_input_layout2)
        layout_btn2.addWidget(self.weight_btn_z)
        layout_btn2.addLayout(layout_btn1)
        layout_btn2.addWidget(self.save_btn)
        layout_btn2.addWidget(self.save_file_box_log)

        layout1 = QHBoxLayout()
        layout1.addWidget(self.logging)
        layout1.addLayout(layout_btn2)

        table_layout = QHBoxLayout()
        table_layout.addWidget(self.table)
        table_layout.addWidget(self.weight_table)

        layout2 = QVBoxLayout()
        layout2.addLayout(table_layout)
        layout2.addLayout(layout1)

        layout3 = QHBoxLayout()
        layout3.addLayout(layout2)
        layout3.addLayout(self.left_layout, stretch=3)
        self.setLayout(layout3)

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()

            function_keys = {
                Qt.Key_P: self.weightP,
                Qt.Key_O: self.weightM,
                Qt.Key_I: self.weightZ,
                Qt.Key_M: self.save,
                Qt.Key_K: self.stop,
                Qt.Key_L: self.restart
            }

            if key in function_keys:
                function_keys[key]()
                return True

            key_to_cell = {
                Qt.Key_Q: (0, 0), Qt.Key_W: (0, 1), Qt.Key_E: (0, 2),
                Qt.Key_A: (1, 0), Qt.Key_S: (1, 1), Qt.Key_D: (1, 2),
                Qt.Key_Z: (2, 0), Qt.Key_X: (2, 1), Qt.Key_C: (2, 2)
            }

            if key in key_to_cell:
                row, col = key_to_cell[key]
                self.weight_table.setFocus()
                self.weight_table.setCurrentCell(row, col)
                return True

            if key in [Qt.Key_Return, Qt.Key_Enter]:
                self.weight_table.clearFocus()
                self.setFocus()
                return True

        return super().eventFilter(source, event)

    def closeEvent(self, event):
        for thread in self.threads:
            thread.stop()
        event.accept()

if __name__ == '__main__':
   app = QApplication(sys.argv)
   ex = MyApp()
   sys.exit(app.exec_())