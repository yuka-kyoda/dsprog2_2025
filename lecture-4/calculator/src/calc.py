import math
import flet as ft


class CalcButton(ft.ElevatedButton):
    def __init__(self, text, button_clicked, expand=1):
        super().__init__()
        self.text = text
        self.expand = expand
        self.on_click = button_clicked
        self.data = text


class DigitButton(CalcButton):
    def __init__(self, text, button_clicked, expand=1):
        CalcButton.__init__(self, text, button_clicked, expand)
        self.bgcolor = ft.Colors.WHITE24
        self.color = ft.Colors.WHITE


class ActionButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.ORANGE
        self.color = ft.Colors.WHITE


class ExtraActionButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.BLUE_GREY_100
        self.color = ft.Colors.BLACK


class CalculatorApp(ft.Container):
    def __init__(self):
        super().__init__()
        self.reset()
        self.angle_mode = "DEG"   # "DEG" or "RAD"
        self.sci_mode = False     # 科学計算モード表示/非表示

        self.result = ft.Text(value="0", color=ft.Colors.WHITE, size=20)
        self.width = 380
        self.bgcolor = ft.Colors.BLACK
        self.border_radius = ft.border_radius.all(20)
        self.padding = 20

        # --- 基本ボタン行 ---
        self.row_display = ft.Row(controls=[self.result], alignment="end")

        self.row_top = ft.Row(
            controls=[
                ExtraActionButton(text="AC", button_clicked=self.button_clicked),
                ExtraActionButton(text="+/-", button_clicked=self.button_clicked),
                ExtraActionButton(text="%", button_clicked=self.button_clicked),
                ActionButton(text="/", button_clicked=self.button_clicked),
                ExtraActionButton(text="SCI", button_clicked=self.button_clicked),  # 追加：Sciモード切替
            ]
        )

        self.row_7_9 = ft.Row(
            controls=[
                DigitButton(text="7", button_clicked=self.button_clicked),
                DigitButton(text="8", button_clicked=self.button_clicked),
                DigitButton(text="9", button_clicked=self.button_clicked),
                ActionButton(text="*", button_clicked=self.button_clicked),
            ]
        )
        self.row_4_6 = ft.Row(
            controls=[
                DigitButton(text="4", button_clicked=self.button_clicked),
                DigitButton(text="5", button_clicked=self.button_clicked),
                DigitButton(text="6", button_clicked=self.button_clicked),
                ActionButton(text="-", button_clicked=self.button_clicked),
            ]
        )
        self.row_1_3 = ft.Row(
            controls=[
                DigitButton(text="1", button_clicked=self.button_clicked),
                DigitButton(text="2", button_clicked=self.button_clicked),
                DigitButton(text="3", button_clicked=self.button_clicked),
                ActionButton(text="+", button_clicked=self.button_clicked),
            ]
        )
        self.row_0_dot_eq = ft.Row(
            controls=[
                DigitButton(text="0", expand=2, button_clicked=self.button_clicked),
                DigitButton(text=".", button_clicked=self.button_clicked),
                ActionButton(text="=", button_clicked=self.button_clicked),
            ]
        )

        # --- 科学計算ボタン行（初期は非表示、SCI トグルで挿入/削除） ---
        self.sci_row1 = ft.Row(
            controls=[
                ExtraActionButton(text="sin", button_clicked=self.button_clicked),
                ExtraActionButton(text="cos", button_clicked=self.button_clicked),
                ExtraActionButton(text="tan", button_clicked=self.button_clicked),
                ExtraActionButton(text="DEG", button_clicked=self.button_clicked),  # 角度モード切替ボタン
            ]
        )
        self.sci_row2 = ft.Row(
            controls=[
                ExtraActionButton(text="ln", button_clicked=self.button_clicked),
                ExtraActionButton(text="log10", button_clicked=self.button_clicked),
                ExtraActionButton(text="√", button_clicked=self.button_clicked),
                ActionButton(text="^", button_clicked=self.button_clicked),   # べき乗演算子
                ExtraActionButton(text="exp", button_clicked=self.button_clicked),
            ]
        )
        self.sci_row3 = ft.Row(
            controls=[
                ExtraActionButton(text="π", button_clicked=self.button_clicked),
                ExtraActionButton(text="e", button_clicked=self.button_clicked),
            ]
        )

        # 最初は通常行のみ
        self.content = ft.Column(
            controls=[
                self.row_display,
                self.row_top,
                self.row_7_9,
                self.row_4_6,
                self.row_1_3,
                self.row_0_dot_eq,
            ]
        )

    def button_clicked(self, e):
        data = e.control.data
        # print(f"Button clicked with data = {data}")

        # --- SCI モードの表示/非表示 ---
        if data == "SCI":
            self.sci_mode = not self.sci_mode
            if self.sci_mode:
                # 結果行の直後（top行の後）に追加
                # 挿入インデックスを決めて順序を守る
                # 現在: [display, top, 7-9, 4-6, 1-3, 0-dot-eq]
                if self.sci_row1 not in self.content.controls:
                    self.content.controls.insert(2, self.sci_row1)
                if self.sci_row2 not in self.content.controls:
                    self.content.controls.insert(3, self.sci_row2)
                if self.sci_row3 not in self.content.controls:
                    self.content.controls.insert(4, self.sci_row3)
            else:
                # 取り除く
                for r in [self.sci_row1, self.sci_row2, self.sci_row3]:
                    if r in self.content.controls:
                        self.content.controls.remove(r)
            self.update()
            return

        # --- 角度モード切替（DEG/RAD） ---
        if data in ("DEG", "RAD"):
            self.angle_mode = "RAD" if data == "DEG" else "DEG"
            # ボタン表示とデータを更新
            e.control.text = self.angle_mode
            e.control.data = self.angle_mode
            self.update()
            return

        # --- AC（クリア）または Error 状態からの復帰 ---
        if self.result.value == "Error" or data == "AC":
            self.result.value = "0"
            self.reset()
            self.update()
            return

        # --- 数字・小数点 ---
        if data in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "."):
            if self.result.value == "0" or self.new_operand is True:
                self.result.value = data
                self.new_operand = False
            else:
                self.result.value = str(self.result.value) + data
            self.update()
            return

        # --- 二項演算子（+ - * / ^） ---
        if data in ("+", "-", "*", "/", "^"):
            try:
                current = float(self.result.value)
            except ValueError:
                current = 0.0
            self.result.value = self.calculate(self.operand1, current, self.operator)
            self.operator = data
            if self.result.value == "Error":
                self.operand1 = 0.0
            else:
                self.operand1 = float(self.result.value)
            self.new_operand = True
            self.update()
            return

        # --- イコール ---
        if data == "=":
            try:
                current = float(self.result.value)
            except ValueError:
                current = 0.0
            self.result.value = self.calculate(self.operand1, current, self.operator)
            self.reset()
            self.update()
            return

        # --- パーセント ---
        if data == "%":
            try:
                val = float(self.result.value) / 100.0
                self.result.value = self.format_number(val)
                # パーセントは単項変換後、新オペランド開始
                self.new_operand = True
            except Exception:
                self.result.value = "Error"
                self.reset()
            self.update()
            return

        # --- +/-（符号反転）---
        if data == "+/-":
            try:
                v = float(self.result.value)
                if v > 0:
                    self.result.value = "-" + str(self.result.value)
                elif v < 0:
                    self.result.value = str(self.format_number(abs(v)))
            except Exception:
                self.result.value = "Error"
                self.reset()
            self.update()
            return

        # --- 科学計算：単項関数 ---
        if data in ("sin", "cos", "tan", "ln", "log10", "√", "exp"):
            try:
                x = float(self.result.value)

                if data in ("sin", "cos", "tan"):
                    # 角度モードに応じてラジアンへ
                    rad = x if self.angle_mode == "RAD" else math.radians(x)
                    if data == "sin":
                        y = math.sin(rad)
                    elif data == "cos":
                        y = math.cos(rad)
                    else:  # tan
                        y = math.tan(rad)
                    self.result.value = self.format_number(y)
                    self.new_operand = True

                elif data == "ln":
                    if x <= 0:
                        raise ValueError("ln domain error")
                    y = math.log(x)  # natural log
                    self.result.value = self.format_number(y)
                    self.new_operand = True

                elif data == "log10":
                    if x <= 0:
                        raise ValueError("log10 domain error")
                    y = math.log10(x)
                    self.result.value = self.format_number(y)
                    self.new_operand = True

                elif data == "√":
                    if x < 0:
                        raise ValueError("sqrt domain error")
                    y = math.sqrt(x)
                    self.result.value = self.format_number(y)
                    self.new_operand = True

                elif data == "exp":
                    y = math.exp(x)
                    self.result.value = self.format_number(y)
                    self.new_operand = True

            except (OverflowError, ValueError):
                self.result.value = "Error"
                self.reset()
            except Exception:
                self.result.value = "Error"
                self.reset()

            self.update()
            return

        # --- 定数（π, e） ---
        if data in ("π", "e"):
            const = math.pi if data == "π" else math.e
            self.result.value = self.format_number(const)
            self.new_operand = True  # 次の入力は新しい数値
            self.update()
            return

        # それ以外（未知のボタン）
        self.update()

    def format_number(self, num):
        # 整数なら int に、そうでなければ浮動小数（12桁程度で丸め）に
        try:
            if isinstance(num, (int, float)):
                if float(num).is_integer():
                    return int(num)
                # 12桁の有効数字で丸め
                return float(f"{num:.12g}")
            return num
        except Exception:
            return num

    def calculate(self, operand1, operand2, operator):
        try:
            if operator == "+":
                return self.format_number(operand1 + operand2)

            elif operator == "-":
                return self.format_number(operand1 - operand2)

            elif operator == "*":
                return self.format_number(operand1 * operand2)

            elif operator == "/":
                if operand2 == 0:
                    return "Error"
                else:
                    return self.format_number(operand1 / operand2)

            elif operator == "^":
                # べき乗
                return self.format_number(operand1 ** operand2)

            # 既定（演算子未設定時は足し算扱い）
            return self.format_number(operand1 + operand2)
        except (OverflowError, ValueError, ZeroDivisionError):
            return "Error"
        except Exception:
            return "Error"

    def reset(self):
        self.operator = "+"
        self.operand1 = 0.0
        self.new_operand = True


def main(page: ft.Page):
    page.title = "Simple Calculator (Scientific Mode)"
    calc = CalculatorApp()
    page.add(calc)


ft.app(main)
