import csv
import os
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from PySide6.QtCore import Qt, QRectF, QPointF, QSettings, QTimer, QRegularExpression
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.calculator_logic import MAX_BIG_ROLL_LENGTH_M, calculate
from app.db import (
    clear_history,
    count_history,
    fetch_history,
    get_data_dir,
    init_history_db,
    insert_history,
)


class CuttingView(QWidget):
    def __init__(self):
        super().__init__()
        self._result = None

    def set_data(self, result):
        self._result = result
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1b2028"))

        if not self._result:
            return

        margin = 24
        bar_height = 70
        y = self.height() // 2 - bar_height // 2
        usable_width_px = self.width() - margin * 2
        row_padding = 6
        row_gap = 8
        roll_height = (bar_height - row_gap - row_padding * 2) / 2
        if roll_height < 16:
            roll_height = 16
        row_y_top = y + row_padding
        row_y_bottom = y + bar_height - row_padding - roll_height

        material_width = self._result["material_width_mm"]
        useful_width = self._result["useful_width_mm"]
        main_count = self._result["main_count"]
        roll_width = self._result["roll_width_mm"]
        additional_width = self._result["additional_width_mm"]
        waste_per_side = self._result["waste_per_side_mm"]

        if material_width <= 0:
            return

        scale = usable_width_px / material_width

        total_rect = QRectF(margin, y, usable_width_px, bar_height)
        painter.setPen(QPen(QColor("#485569"), 2))
        painter.drawRoundedRect(total_rect, 6, 6)

        x = margin
        row_ranges = {}

        def draw_block(width_mm, color_start, color_end, label=None, row=None):
            nonlocal x
            w = max(width_mm * scale, 0)
            if row is None:
                rect = QRectF(x, y, w, bar_height)
            else:
                rect_y = row_y_top if row == 0 else row_y_bottom
                rect = QRectF(x, rect_y, w, roll_height)
                if w > 0:
                    if row not in row_ranges:
                        row_ranges[row] = [rect.left(), rect.right()]
                    else:
                        row_ranges[row][0] = min(row_ranges[row][0], rect.left())
                        row_ranges[row][1] = max(row_ranges[row][1], rect.right())
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0, QColor(color_start))
            gradient.setColorAt(1, QColor(color_end))
            painter.fillRect(rect, gradient)
            painter.setPen(QPen(QColor("#0f1420"), 1))
            painter.drawRect(rect)
            if label:
                painter.setPen(QPen(Qt.white, 1))
                painter.drawText(rect, Qt.AlignCenter, label)
            x += w

        if waste_per_side > 0:
            draw_block(waste_per_side, "#c53b3b", "#7a1e1e", "ОТХОД")

        roll_index = 0
        for _ in range(main_count):
            draw_block(
                roll_width,
                "#2f63ff",
                "#0b2f9e",
                f"{int(roll_width)}",
                row=roll_index % 2,
            )
            roll_index += 1

        remaining_width = useful_width - main_count * roll_width
        if additional_width:
            draw_block(
                additional_width,
                "#3aa35c",
                "#22613a",
                f"{int(additional_width)}",
                row=roll_index % 2,
            )
            roll_index += 1
            remaining_width = useful_width - main_count * roll_width - additional_width

        if remaining_width > 0:
            draw_block(remaining_width, "#c53b3b", "#7a1e1e", "ОТХ")

        if waste_per_side > 0:
            draw_block(waste_per_side, "#c53b3b", "#7a1e1e", "ОТХОД")

        if row_ranges:
            painter.save()
            shaft_color = QColor("#6c7a92")
            painter.setPen(QPen(shaft_color, 2))
            painter.setBrush(shaft_color)
            shaft_offset = 5
            for row, (min_x, max_x) in row_ranges.items():
                line_y = (
                    row_y_top + roll_height - shaft_offset
                    if row == 0
                    else row_y_bottom + roll_height - shaft_offset
                )
                painter.drawLine(QPointF(min_x, line_y), QPointF(max_x, line_y))
                radius = 3.5
                painter.drawEllipse(QPointF(min_x, line_y), radius, radius)
                painter.drawEllipse(QPointF(max_x, line_y), radius, radius)
            painter.restore()

        painter.setPen(QPen(QColor("#d3b26c"), 1))
        painter.drawText(margin, y - 12, f"{int(useful_width)} мм")

        legend_y = y + bar_height + 18
        painter.setPen(QPen(QColor("#c9d1dc"), 1))
        painter.drawRect(margin, legend_y, 12, 12)
        painter.fillRect(margin, legend_y, 12, 12, QColor("#c53b3b"))
        painter.drawText(margin + 16, legend_y + 10, "Отход")
        painter.fillRect(margin + 90, legend_y, 12, 12, QColor("#2f63ff"))
        painter.drawText(margin + 106, legend_y + 10, "Рулоны")
        painter.fillRect(margin + 190, legend_y, 12, 12, QColor("#3aa35c"))
        painter.drawText(margin + 206, legend_y + 10, "Доп.")

        count_y = legend_y + 22
        painter.setPen(QPen(QColor("#c9d1dc"), 1))
        painter.drawText(
            margin,
            count_y + 12,
            f"Основных: {main_count}",
        )
        painter.drawText(
            margin + 170,
            count_y + 12,
            f"Доп.: {1 if additional_width else 0}",
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Калькулятор производства")
        self.setMinimumSize(1100, 700)

        init_history_db()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        body = QGridLayout()
        body.setHorizontalSpacing(12)
        body.setVerticalSpacing(12)
        body.setColumnStretch(0, 10)
        body.setColumnStretch(1, 11)
        body.setColumnStretch(2, 11)
        body.setColumnStretch(3, 9)
        root.addLayout(body)

        self.left_panel = self._build_left_panel()
        self.center_panel = self._build_center_panel()
        self.right_panel = self._build_right_panel()

        body.addWidget(self.left_panel, 0, 0, 2, 1)
        body.addWidget(self.center_panel, 0, 1, 1, 2)
        body.addWidget(self.right_panel, 0, 3, 2, 1)
        body.addWidget(self.history_panel, 1, 1, 1, 2)

        root.addWidget(self._build_footer())

        self._settings = QSettings("Calculator", "ProductionCalculator")
        self._restore_jamba_inputs()
        self._bind_jamba_persistence()

        self.apply_style()
        self._action_rows = []
        self._load_history()
        self._update_process_count()
        self._schedule_history_clear()

    def _build_header(self):
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("Калькулятор Производства")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        layout.addStretch(1)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("HeaderClock")
        layout.addWidget(self.clock_label)

        for name, color in [
            ("N", "#3aa35c"),
            ("U", "#2f63ff"),
            ("i", "#6c7a92"),
            ("⏻", "#c53b3b"),
        ]:
            btn = QLabel(name)
            btn.setObjectName("HeaderIcon")
            btn.setProperty("accentColor", color)
            layout.addWidget(btn)

        self._start_clock()
        return header

    def _start_clock(self):
        def tick():
            now = datetime.now()
            self.clock_label.setText(now.strftime("%H:%M"))

        tick()
        timer = QTimer(self)
        timer.timeout.connect(tick)
        timer.start(1000)

    def _get_minsk_tz(self):
        if ZoneInfo is not None:
            try:
                return ZoneInfo("Europe/Minsk")
            except Exception:
                pass
        return timezone(timedelta(hours=3))

    def _schedule_history_clear(self):
        now = datetime.now(tz=self._get_minsk_tz())
        next_run = now.replace(hour=0, minute=1, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run + timedelta(days=1)
        delay_ms = int((next_run - now).total_seconds() * 1000)
        QTimer.singleShot(delay_ms, self._run_scheduled_history_clear)

    def _run_scheduled_history_clear(self):
        clear_history()
        self._action_rows.clear()
        self._load_history()
        self._update_process_count()
        self._schedule_history_clear()

    def _build_left_panel(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._panel_title("РАСЧЕТ ЗАКАЗА"))

        tabs = QTabWidget()
        tabs.setObjectName("LeftTabs")

        tab_roll = QWidget()
        tab_order = QWidget()
        roll_layout = QVBoxLayout(tab_roll)
        order_layout = QVBoxLayout(tab_order)
        roll_layout.setSpacing(8)
        order_layout.setSpacing(8)

        self.input_stock_number = self._labeled_input("Порядковый номер складского учета")
        self.input_material_code = self._labeled_input("Код материала")
        self.input_material = self._labeled_input("Общая ширина материала, мм")
        self.input_useful = self._labeled_input("Полезная ширина материала, мм")
        self.input_big_length = self._labeled_input("Намотка, м")

        stock_validator = QRegularExpressionValidator(QRegularExpression(r"(?:\d{1,3}(?:/\d{0,4})?)?"))
        code_validator = QRegularExpressionValidator(QRegularExpression(r"[A-Za-z0-9]*"))
        self.input_stock_number.setValidator(stock_validator)
        self.input_material_code.setValidator(code_validator)

        roll_layout.addWidget(self.input_stock_number)
        roll_layout.addWidget(self.input_material_code)
        roll_layout.addWidget(self.input_material)
        roll_layout.addWidget(self.input_useful)
        roll_layout.addWidget(self.input_big_length)
        roll_layout.addStretch(1)

        self.input_roll_width = self._labeled_input("Ширина готовых рулонов, мм")
        self.input_roll_length = self._labeled_input("Намотка рулонов, м")
        self.input_order = self._labeled_input("Количество рулонов в заказе, шт")

        order_layout.addWidget(self.input_roll_width)
        order_layout.addWidget(self.input_roll_length)
        order_layout.addWidget(self.input_order)

        self.additional_width_checkbox = QCheckBox("\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u0434\u043e\u043f. \u0440\u0430\u0437\u043c\u0435\u0440")
        self.additional_width_checkbox.setObjectName("AdditionalCheck")
        self.additional_width_checkbox.toggled.connect(self._toggle_additional_width)
        order_layout.addWidget(self.additional_width_checkbox)

        self.additional_width_input = self._labeled_input("\u0414\u043e\u043f. \u0440\u0430\u0437\u043c\u0435\u0440, \u043c\u043c")
        self.additional_width_input.setEnabled(False)
        order_layout.addWidget(self.additional_width_input)

        order_layout.addStretch(1)

        tabs.addTab(tab_roll, "Параметры Джамба")
        tabs.addTab(tab_order, "Заказ")

        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        self.btn_clear = QPushButton("ОЧИСТИТЬ")
        self.btn_calc = QPushButton("РАССЧИТАТЬ")
        self.btn_execute = QPushButton("\u0412\u042b\u041f\u041e\u041b\u041d\u0418\u0422\u042c")
        self.btn_clear.clicked.connect(self._clear)
        self.btn_calc.clicked.connect(self._calculate)
        self.btn_execute.clicked.connect(self._execute)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_calc)
        btn_row.addWidget(self.btn_execute)
        layout.addLayout(btn_row)

        self.left_hint = QLabel(
            f"Максимальная длина Джамба: {MAX_BIG_ROLL_LENGTH_M} м"
        )
        self.left_hint.setObjectName("Hint")
        layout.addWidget(self.left_hint)

        layout.addStretch(1)
        return panel

    def _jamba_fields(self):
        return {
            "stock_number": self.input_stock_number,
            "material_code": self.input_material_code,
            "material_width": self.input_material,
            "useful_width": self.input_useful,
            "big_roll_length": self.input_big_length,
        }

    def _format_stock_number(self, value):
        value = value.strip()
        if not value:
            return ""
        if "/" not in value:
            return None
        left, year = value.split("/", 1)
        if not left.isdigit() or not year.isdigit():
            return None
        if len(left) == 0 or len(left) > 3 or len(year) != 4:
            return None
        return f"{left.zfill(3)}/{year}"

    def _apply_stock_number_format(self):
        formatted = self._format_stock_number(self.input_stock_number.text())
        if formatted is None:
            return
        self.input_stock_number.setText(formatted)
        self._settings.setValue("jamba/stock_number", formatted)

    def _restore_jamba_inputs(self):
        for key, widget in self._jamba_fields().items():
            value = self._settings.value(f"jamba/{key}", "")
            if value is None:
                value = ""
            widget.setText(str(value))
        self._apply_stock_number_format()

    def _bind_jamba_persistence(self):
        for key, widget in self._jamba_fields().items():
            widget.textEdited.connect(
                lambda value, key=key: self._settings.setValue(f"jamba/{key}", value)
            )
        self.input_stock_number.editingFinished.connect(self._apply_stock_number_format)

    def _build_center_panel(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._panel_title("ВИЗУАЛЬНАЯ СХЕМА НАРЕЗКИ"))

        self.cutting_view = CuttingView()
        self.cutting_view.setMinimumHeight(220)
        layout.addWidget(self.cutting_view)

        self.history_panel = QFrame()
        self.history_panel.setObjectName("Panel")
        h_layout = QVBoxLayout(self.history_panel)
        h_layout.setContentsMargins(16, 16, 16, 16)
        h_layout.setSpacing(10)

        h_layout.addWidget(self._panel_title("ИСТОРИЯ"))
        self.history_table = QTableWidget(0, 9)
        self.history_table.setHorizontalHeaderLabels(
            ["Время", "№ склада", "Код материала", "Рулон", "Площадь", "Отход (%)", "Склад (осн.)", "Склад (доп.)", "Расход, п.м."]
        )
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setObjectName("HistoryTable")
        h_layout.addWidget(self.history_table)

        return panel

    def _build_right_panel(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._panel_title("РЕЗУЛЬТАТЫ"))

        self.result_rolls = self._result_row("Количество рулонов", "0")
        self.result_additional = self._result_row("Доп. рулон", "0")
        self.result_storage_main = self._result_row("Склад (осн.)", "0")
        self.result_storage_add = self._result_row("Склад (доп.)", "0")
        self.result_linear = self._result_row("Расход материала, п.м.", "0")
        self.result_cycles = self._result_row("Количество циклов", "0")
        self.result_time = self._result_row("\u0412\u0440\u0435\u043c\u044f (\u043e\u0446\u0435\u043d\u043a\u0430)", "\u043d/\u0434")
        self.result_total_area = self._result_row("Общая площадь", "0.0 м²")
        self.result_useful_area = self._result_row("Полезная площадь", "0.0 м²")
        self.result_waste_area = self._result_row("Отходы", "0.0 м²")

        layout.addWidget(self.result_rolls)
        layout.addWidget(self.result_additional)
        layout.addWidget(self.result_storage_main)
        layout.addWidget(self.result_storage_add)
        layout.addWidget(self.result_linear)
        layout.addWidget(self.result_cycles)
        layout.addWidget(self.result_time)
        layout.addWidget(self.result_total_area)
        layout.addWidget(self.result_useful_area)
        layout.addWidget(self.result_waste_area)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        layout.addWidget(self.status_label)

        self.btn_export = QPushButton("ЭКСПОРТ ОТЧЕТА")
        self.btn_export.clicked.connect(self._export_report)
        layout.addWidget(self.btn_export)

        self.id_panel = QFrame()
        self.id_panel.setObjectName("IdPanel")
        id_layout = QVBoxLayout(self.id_panel)
        id_layout.setContentsMargins(12, 12, 12, 12)
        self.id_label = QLabel("ID: 001")
        self.id_label.setObjectName("IdLabel")
        self.proc_label = QLabel("0 процессов")
        self.proc_label.setObjectName("ProcLabel")
        id_layout.addWidget(self.id_label)
        id_layout.addWidget(self.proc_label)
        layout.addWidget(self.id_panel)

        layout.addStretch(1)
        return panel

    def _build_footer(self):
        footer = QFrame()
        footer.setObjectName("Footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 6, 16, 6)
        self.footer_left = QLabel("ID: 001")
        self.footer_left.setObjectName("FooterText")
        self.footer_right = QLabel(datetime.now().strftime("%d.%m.%Y   %H:%M"))
        self.footer_right.setObjectName("FooterText")
        layout.addWidget(self.footer_left)
        layout.addStretch(1)
        layout.addWidget(self.footer_right)
        return footer

    def _panel_title(self, text):
        label = QLabel(text)
        label.setObjectName("PanelTitle")
        return label

    def _labeled_input(self, placeholder):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setObjectName("Input")
        return inp

    def _toggle_additional_width(self, checked):
        self.additional_width_input.setEnabled(checked)
        if not checked:
            self.additional_width_input.clear()

    def _result_row(self, label, value):
        row = QFrame()
        row.setObjectName("ResultRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
        name = QLabel(label)
        name.setObjectName("ResultLabel")
        val = QLabel(value)
        val.setObjectName("ResultValue")
        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(val)
        row._value_label = val
        return row

    def _set_result_row(self, row, value):
        row._value_label.setText(value)

    def _clear(self):
        self.input_material.clear()
        self.input_useful.clear()
        self.input_big_length.clear()
        self.input_roll_width.clear()
        self.input_roll_length.clear()
        self.input_order.clear()
        self.additional_width_checkbox.setChecked(False)
        self.input_stock_number.clear()
        self.input_material_code.clear()
        self.cutting_view.set_data(None)
        self._set_result_row(self.result_rolls, "0")
        self._set_result_row(self.result_additional, "0")
        self._set_result_row(self.result_storage_main, "0")
        self._set_result_row(self.result_storage_add, "0")
        self._set_result_row(self.result_linear, "0")
        self._set_result_row(self.result_cycles, "0")
        self._set_result_row(self.result_time, "\u043d/\u0434")
        self._set_result_row(self.result_total_area, "0.0 м²")
        self._set_result_row(self.result_useful_area, "0.0 м²")
        self._set_result_row(self.result_waste_area, "0.0 м²")
        self.status_label.setText("")

    def _calculate(self):
        try:
            result, record, row = self._compute_result()
            if result is None:
                return
            self._apply_result(result)
            self._add_action_row("calc", row)
            self._set_status_after_result(result, executed=False)
        except ValueError as exc:
            self.status_label.setText(str(exc))
        except Exception:
            self.status_label.setText("Ошибка ввода")

    def _execute(self):
        try:
            result, record, row = self._compute_result()
            if result is None:
                return
            self._apply_result(result)
            insert_history(record)
            self._add_action_row("exec", row)
            self._update_process_count()
            self._set_status_after_result(result, executed=True)
        except ValueError as exc:
            self.status_label.setText(str(exc))
        except Exception:
            self.status_label.setText("Ошибка ввода")

    def _compute_result(self):
        self._apply_stock_number_format()
        stock_number = self._format_stock_number(self.input_stock_number.text())
        if stock_number is None:
            self.status_label.setText("Неверный формат номера склада: 000/0000")
            return None, None, None
        material = float(self.input_material.text())
        useful = float(self.input_useful.text())
        big_length = float(self.input_big_length.text())
        roll_width = float(self.input_roll_width.text())
        roll_length = float(self.input_roll_length.text())
        order_rolls = int(self.input_order.text())

        additional_width = None
        if self.additional_width_checkbox.isChecked():
            if not self.additional_width_input.text().strip():
                self.status_label.setText("Введите доп. размер")
                return None, None, None
            additional_width = float(self.additional_width_input.text())

        result = calculate(
            material,
            useful,
            roll_width,
            roll_length,
            big_length,
            order_rolls,
            additional_width,
        )

        record = {
            "timestamp": datetime.now().strftime("%H:%M"),
            "stock_number": stock_number,
            "material_code": self.input_material_code.text().strip(),
            "material_width": material,
            "useful_width": useful,
            "big_roll_length": big_length,
            "roll_width": roll_width,
            "roll_length": roll_length,
            "main_count": result["main_count"],
            "additional_width": result["additional_width_mm"] or 0,
            "total_rolls": result["total_rolls"],
            "used_length_m": result["used_length_m"],
            "surplus_rolls": result["surplus_rolls"],
            "surplus_main_rolls": result["surplus_main_rolls"],
            "surplus_additional_rolls": result["surplus_additional_rolls"],
            "total_area": result["total_area_m2"],
            "useful_area": result["useful_area_m2"],
            "waste_area": result["waste_area_m2"],
            "waste_percent": result["waste_percent"],
        }

        row = (
            record["timestamp"],
            record["stock_number"],
            record["material_code"],
            record["roll_width"],
            record["useful_area"],
            record["waste_percent"],
            record["surplus_main_rolls"],
            record["surplus_additional_rolls"],
            record["used_length_m"],
        )

        return result, record, row

    def _apply_result(self, result):
        total_rolls = result["total_rolls"]
        self._set_result_row(self.result_rolls, str(total_rolls))
        self._set_result_row(
            self.result_additional, f"{result['total_additional_rolls']} шт"
        )
        width_main = result["roll_width_mm"]
        width_main_str = f"{width_main:.1f}".rstrip("0").rstrip(".")
        additional_width = result["additional_width_mm"]
        if additional_width:
            width_add_str = f"{additional_width:.1f}".rstrip("0").rstrip(".")
            add_label = f"{width_add_str} мм"
        else:
            add_label = "нет"
        self._set_result_row(
            self.result_storage_main, f"{result['surplus_main_rolls']} шт ({width_main_str} мм)"
        )
        self._set_result_row(
            self.result_storage_add, f"{result['surplus_additional_rolls']} шт ({add_label})"
        )
        self._set_result_row(self.result_cycles, f"{result['cycles_used']}")
        estimated_hours = result.get("estimated_hours")
        if estimated_hours is None:
            time_label = "\u043d/\u0434"
        else:
            total_minutes = int((estimated_hours * 60 + 2.5) // 5 * 5) + 15
            hours = total_minutes // 60
            minutes = total_minutes % 60
            time_label = f"{hours:02d} \u0447\u0430\u0441. {minutes:02d} \u043c\u0438\u043d."
        self._set_result_row(self.result_time, time_label)
        self._set_result_row(self.result_linear, f"{result['used_length_m']:.1f} м")
        self._set_result_row(self.result_total_area, f"{result['total_area_m2']:.1f} м²")
        self._set_result_row(self.result_useful_area, f"{result['useful_area_m2']:.1f} м²")
        self._set_result_row(self.result_waste_area, f"{result['waste_area_m2']:.1f} м²")

        self.cutting_view.set_data(result)

    def _set_status_after_result(self, result, executed):
        if result["shortage_rolls"] > 0:
            self.status_label.setText(f"Не хватает {result['shortage_rolls']} рулонов")
        else:
            self.status_label.setText("Выполнено" if executed else "Рассчитано")

    def _add_action_row(self, status, row):
        self._action_rows.insert(0, (status, row))
        if len(self._action_rows) > 20:
            self._action_rows = self._action_rows[:20]
        self._load_history()

    def _load_history(self):
        action_rows = list(self._action_rows)
        remaining = max(0, 20 - len(action_rows))
        db_rows = fetch_history(limit=remaining + len(action_rows))

        executed_rows = [row for status, row in action_rows if status == "exec"]
        filtered_db = []
        for row in db_rows:
            if row in executed_rows:
                executed_rows.remove(row)
                continue
            filtered_db.append(row)
            if len(filtered_db) >= remaining:
                break

        rows = [row for _, row in action_rows] + filtered_db
        self.history_table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self.history_table.insertRow(row_idx)
            for col, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                self.history_table.setItem(row_idx, col, item)
            if row_idx < len(action_rows):
                status = action_rows[row_idx][0]
                if status == "calc":
                    self._style_history_row(row_idx, QColor("#d1a239"), QColor("#1b2028"))
                else:
                    self._style_history_row(row_idx, QColor("#3aa35c"), QColor("#f0f4ff"))
            else:
                self._style_history_row(row_idx, QColor("#3aa35c"), QColor("#f0f4ff"))

    def _style_history_row(self, row_idx, background, foreground):
        for col in range(self.history_table.columnCount()):
            item = self.history_table.item(row_idx, col)
            if item is not None:
                item.setBackground(background)
                item.setForeground(foreground)

    def _update_process_count(self):
        count = count_history()
        self.proc_label.setText(f"{count} процессов")

    def _export_report(self):
        export_dir = os.path.join(get_data_dir(), "exports")
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(export_dir, f"report_{timestamp}.csv")

        rows = fetch_history(limit=1000)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Время", "№ склада", "Код материала", "Рулон", "Площадь", "Отход (%)", "Склад (осн.)", "Склад (доп.)", "Расход, п.м."])
            for row in rows:
                writer.writerow(row)

        QMessageBox.information(self, "Экспорт", f"Отчет сохранен:\n{path}")

    def apply_style(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #1b2028;
                color: #d6deea;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            #Header {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #222a36, stop:1 #2f3947);
                border: 1px solid #3b4d69;
                border-radius: 8px;
            }
            #HeaderTitle {
                font-size: 16px;
                letter-spacing: 1px;
            }
            #HeaderClock {
                font-size: 16px;
                margin-right: 8px;
            }
            #HeaderIcon {
                min-width: 28px;
                min-height: 28px;
                max-width: 28px;
                max-height: 28px;
                border-radius: 14px;
                background: #263041;
                border: 1px solid #4c5f7a;
                qproperty-alignment: AlignCenter;
                margin-left: 6px;
            }
            #Panel {
                background: #263041;
                border: 1px solid #3b4d69;
                border-radius: 10px;
            }
            #PanelTitle {
                font-size: 14px;
                padding: 6px 10px;
                background: #2d3848;
                border-radius: 6px;
                color: #cfd7e6;
            }
            #Input {
                background: #1f2733;
                border: 1px solid #3b4d69;
                padding: 8px 10px;
                border-radius: 6px;
            }
            QCheckBox#AdditionalCheck {
                color: #cfd7e6;
                spacing: 8px;
            }
            QCheckBox#AdditionalCheck::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox#AdditionalCheck::indicator:unchecked {
                border: 1px solid #3b4d69;
                background: #1f2733;
                border-radius: 3px;
            }
            QCheckBox#AdditionalCheck::indicator:checked {
                border: 1px solid #2f63ff;
                background: #2f63ff;
                border-radius: 3px;
            }
            QPushButton {
                background: #2f63ff;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3b71ff;
            }
            QPushButton:pressed {
                background: #244fcb;
            }
            QPushButton#ClearButton {
                background: #c53b3b;
                color: #ffffff;
            }
            QPushButton#ClearButton:hover {
                background: #d44747;
            }
            QPushButton#ClearButton:pressed {
                background: #a93232;
            }
            QPushButton#CalcButton {
                background: #d1a239;
                color: #1d1d1d;
            }
            QPushButton#CalcButton:hover {
                background: #e0b14b;
            }
            QPushButton#CalcButton:pressed {
                background: #b58a2f;
            }
            QPushButton#ExecuteButton {
                background: #3aa35c;
                color: #ffffff;
            }
            QPushButton#ExecuteButton:hover {
                background: #43b567;
            }
            QPushButton#ExecuteButton:pressed {
                background: #2f8a4d;
            }
            #ResultRow {
                background: #2a3546;
                border-radius: 6px;
            }
            #ResultLabel {
                color: #9fb0c8;
            }
            #ResultValue {
                font-size: 16px;
                color: #f0f4ff;
            }
            #StatusLabel {
                color: #d3b26c;
                padding: 4px 2px;
            }
            #IdPanel {
                background: #222a36;
                border: 1px solid #3b4d69;
                border-radius: 10px;
            }
            #IdLabel {
                font-size: 16px;
                color: #d1a239;
            }
            #ProcLabel {
                color: #8aa0bd;
            }
            #Footer {
                background: #222a36;
                border: 1px solid #3b4d69;
                border-radius: 8px;
            }
            #FooterText {
                color: #8aa0bd;
            }
            #HistoryTable {
                background: #1f2733;
                gridline-color: #33465f;
                border: none;
            }
            #LeftTabs::pane {
                border: 1px solid #3b4d69;
                border-radius: 8px;
                padding: 6px;
            }
            #LeftTabs QTabBar::tab {
                background: #2d3848;
                color: #b9c7dd;
                padding: 6px 12px;
                border-radius: 6px;
                margin-right: 6px;
            }
            #LeftTabs QTabBar::tab:selected {
                background: #3b4d69;
                color: #f0f4ff;
            }
            """
        )
        self.btn_clear.setObjectName("ClearButton")
        self.btn_calc.setObjectName("CalcButton")
        self.btn_execute.setObjectName("ExecuteButton")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
