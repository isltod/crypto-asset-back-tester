import sys
import datetime
import ccxt
import pandas as pd
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QDateTimeEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QSplitter, QAbstractItemView, QDialog, QDoubleSpinBox, QSpinBox, QStatusBar, QProgressBar, QCheckBox, QComboBox)
from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtGui import QAction

class DownloadDialog(QDialog):
    def __init__(self, parent=None, start_str=None, end_str=None):
        super().__init__(parent)
        self.setWindowTitle("데이터 다운로드 기간 설정")
        self.resize(350, 150)
        
        layout = QVBoxLayout(self)
        
        # Start Time
        start_layout = QHBoxLayout()
        self.start_label = QLabel("시작 날짜 & 시간:")
        if start_str:
            start_default = QDateTime.fromString(start_str, "yyyy-MM-dd HH:mm:ss")
        else:
            start_default = QDateTime.fromString("2025-07-22 00:00:00", "yyyy-MM-dd HH:mm:ss")
        self.start_dt = QDateTimeEdit(start_default)
        self.start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_dt.setCalendarPopup(True)
        start_layout.addWidget(self.start_label)
        start_layout.addWidget(self.start_dt)
        
        # End Time
        end_layout = QHBoxLayout()
        self.end_label = QLabel("종료 날짜 & 시간:")
        if end_str:
            end_default = QDateTime.fromString(end_str, "yyyy-MM-dd HH:mm:ss")
        else:
            end_default = QDateTime.fromString("2025-07-23 23:59:00", "yyyy-MM-dd HH:mm:ss")
        self.end_dt = QDateTimeEdit(end_default)
        self.end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_dt.setCalendarPopup(True)
        end_layout.addWidget(self.end_label)
        end_layout.addWidget(self.end_dt)
        
        # Download Button
        self.download_btn = QPushButton("설정된 기간 다운로드")
        self.download_btn.clicked.connect(self.accept)
        
        layout.addLayout(start_layout)
        layout.addLayout(end_layout)
        layout.addWidget(self.download_btn)
        
    def get_dates(self):
        # returns start_ms, end_ms
        return self.start_dt.dateTime().toMSecsSinceEpoch(), self.end_dt.dateTime().toMSecsSinceEpoch()

class LabelingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("롱 숏 라벨링 설정")
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        
        # Target Profit (%)
        tp_layout = QHBoxLayout()
        self.tp_label = QLabel("목표 수익률(%):")
        self.tp_spinbox = QDoubleSpinBox()
        self.tp_spinbox.setRange(0.01, 100.0)
        self.tp_spinbox.setSingleStep(0.1)
        self.tp_spinbox.setValue(1.0) # 기본 목표 수익률 1.0%
        tp_layout.addWidget(self.tp_label)
        tp_layout.addWidget(self.tp_spinbox)
        
        # Stop Loss (%)
        sl_layout = QHBoxLayout()
        self.sl_label = QLabel("관리 손실률(%):")
        self.sl_spinbox = QDoubleSpinBox()
        self.sl_spinbox.setRange(0.01, 100.0)
        self.sl_spinbox.setSingleStep(0.1)
        self.sl_spinbox.setValue(0.5) # 기본 손실률 0.5%
        sl_layout.addWidget(self.sl_label)
        sl_layout.addWidget(self.sl_spinbox)
        
        # Action Button
        self.action_btn = QPushButton("탐색 및 라벨링")
        self.action_btn.clicked.connect(self.accept)
        
        layout.addLayout(tp_layout)
        layout.addLayout(sl_layout)
        layout.addWidget(self.action_btn)
        
    def get_parameters(self):
        return self.tp_spinbox.value(), self.sl_spinbox.value()

class SMADialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단순 이동 평균 및 라벨링 추가")
        self.resize(320, 200)
        
        layout = QVBoxLayout(self)
        
        period_layout = QHBoxLayout()
        self.period_label = QLabel("기간 (1~400):")
        self.period_spinbox = QSpinBox()
        self.period_spinbox.setRange(1, 400)
        self.period_spinbox.setValue(20) # 기본 20일/분
        period_layout.addWidget(self.period_label)
        period_layout.addWidget(self.period_spinbox)
        layout.addLayout(period_layout)
        
        self.ls_checkbox = QCheckBox("LS 라벨링 적용")
        layout.addWidget(self.ls_checkbox)
        
        self.ls_widget = QWidget()
        ls_layout = QVBoxLayout(self.ls_widget)
        ls_layout.setContentsMargins(0, 0, 0, 0)
        
        strategy_layout = QHBoxLayout()
        self.strategy_label = QLabel("전략 선택:")
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("단순 돌파 전략")
        strategy_layout.addWidget(self.strategy_label)
        strategy_layout.addWidget(self.strategy_combo)
        
        offset_layout = QHBoxLayout()
        self.offset_label = QLabel("오프셋 (%):")
        self.offset_spinbox = QDoubleSpinBox()
        self.offset_spinbox.setRange(-100.0, 100.0)
        self.offset_spinbox.setSingleStep(0.1)
        self.offset_spinbox.setValue(0.0)
        offset_layout.addWidget(self.offset_label)
        offset_layout.addWidget(self.offset_spinbox)
        
        ls_layout.addLayout(strategy_layout)
        ls_layout.addLayout(offset_layout)
        
        self.ls_widget.setEnabled(False)
        self.ls_checkbox.toggled.connect(self.ls_widget.setEnabled)
        
        layout.addWidget(self.ls_widget)
        
        self.action_btn = QPushButton("차트에 추가")
        self.action_btn.clicked.connect(self.accept)
        layout.addWidget(self.action_btn)
        
    def get_settings(self):
        return (self.period_spinbox.value(), 
                self.ls_checkbox.isChecked(), 
                self.strategy_combo.currentText(), 
                self.offset_spinbox.value())

class SupertrendDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3개의 슈퍼트렌드 설정")
        self.resize(420, 460)

        layout = QVBoxLayout(self)

        # 슈퍼트렌드 1~3 설정
        self.st_widgets = []
        for i in range(1, 4):
            group_label = QLabel(f"슈퍼트렌드 {i}")
            group_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
            layout.addWidget(group_label)

            row = QHBoxLayout()

            atr_label = QLabel("ATR 기간:")
            atr_spin = QSpinBox()
            atr_spin.setRange(1, 200)
            atr_spin.setValue([10, 11, 12][i - 1])

            mult_label = QLabel("멀티플라이어:")
            mult_spin = QDoubleSpinBox()
            mult_spin.setRange(0.1, 20.0)
            mult_spin.setSingleStep(0.1)
            mult_spin.setValue([1.0, 2.0, 3.0][i - 1])

            row.addWidget(atr_label)
            row.addWidget(atr_spin)
            row.addSpacing(12)
            row.addWidget(mult_label)
            row.addWidget(mult_spin)

            layout.addLayout(row)
            self.st_widgets.append((atr_spin, mult_spin))

        # 구분선
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addSpacing(6)
        layout.addWidget(line)
        layout.addSpacing(2)

        # LS 라벨링 체크박스
        self.ls_checkbox = QCheckBox("LS 라벨링 적용")
        layout.addWidget(self.ls_checkbox)

        # MA 설정 위젯 (LS 사용 시만 활성화)
        self.ma_widget = QWidget()
        ma_layout = QVBoxLayout(self.ma_widget)
        ma_layout.setContentsMargins(12, 0, 0, 0)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("MA 종류:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["SMA", "EMA"])
        type_row.addWidget(self.type_combo)
        ma_layout.addLayout(type_row)

        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("MA 기간 (1~400):"))
        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 400)
        self.period_spin.setValue(20)
        period_row.addWidget(self.period_spin)
        ma_layout.addLayout(period_row)

        lookback_row = QHBoxLayout()
        lookback_row.addWidget(QLabel("기울기 룩백 (봉 수):"))
        self.lookback_spin = QSpinBox()
        self.lookback_spin.setRange(1, 200)
        self.lookback_spin.setValue(5)
        lookback_row.addWidget(self.lookback_spin)
        ma_layout.addLayout(lookback_row)

        self.ma_widget.setEnabled(False)
        self.ls_checkbox.toggled.connect(self.ma_widget.setEnabled)
        layout.addWidget(self.ma_widget)

        layout.addSpacing(8)
        self.action_btn = QPushButton("차트에 추가")
        self.action_btn.clicked.connect(self.accept)
        layout.addWidget(self.action_btn)

    def get_settings(self):
        """st_settings=[(atr,mult),...], use_ls, ma_type, ma_period, lookback 반환"""
        st = [(w[0].value(), w[1].value()) for w in self.st_widgets]
        use_ls = self.ls_checkbox.isChecked()
        return (
            st,
            use_ls,
            self.type_combo.currentText() if use_ls else None,
            self.period_spin.value()      if use_ls else None,
            self.lookback_spin.value()    if use_ls else None,
        )


class MASlopeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이동평균 기울기 설정")
        self.resize(340, 180)

        layout = QVBoxLayout(self)

        # MA 종류
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("MA 종류:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["SMA", "EMA"])
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        # MA 기간
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("MA 기간 (1~400):"))
        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 400)
        self.period_spin.setValue(20)
        period_row.addWidget(self.period_spin)
        layout.addLayout(period_row)

        # 기울기 룩백
        lookback_row = QHBoxLayout()
        lookback_row.addWidget(QLabel("기울기 룩백 (봉 수):"))
        self.lookback_spin = QSpinBox()
        self.lookback_spin.setRange(1, 200)
        self.lookback_spin.setValue(5)
        lookback_row.addWidget(self.lookback_spin)
        layout.addLayout(lookback_row)

        self.action_btn = QPushButton("차트에 추가")
        self.action_btn.clicked.connect(self.accept)
        layout.addSpacing(8)
        layout.addWidget(self.action_btn)

    def get_settings(self):
        """(ma_type, ma_period, lookback) 반환"""
        return (self.type_combo.currentText(),
                self.period_spin.value(),
                self.lookback_spin.value())


import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import mplfinance as mpf

class BinanceDataFetcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Binance Futures BTC OHLCV Downloader")
        # 가로는 기존(1000)의 2배, 세로는 기존(800)의 1.5배
        self.resize(2000, 1200)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # State for Indicators
        self.sma_periods = []
        self.supertrend_settings = []   # [(atr_period, multiplier), ...]
        self.ma_slope_settings = []     # [(ma_type, ma_period, lookback), ...]
        
        # Setup Views (Chart and Table)
        self.setup_views()
        
        # Setup Status Bar
        self.setup_statusbar()
        
        # Setup Menu Bar
        self.setup_menu()
        
        # 앱 실행 직후 UI 렌더링이 완료되면 자동으로 다운로드 실행
        QTimer.singleShot(100, self.download_data)

    def setup_menu(self):
        menubar = self.menuBar()
        
        # '데이터' 메뉴 탭 생성
        data_menu = menubar.addMenu("데이터(&D)")
        
        # '데이터 다운로드...' 액션 추가
        download_action = QAction("데이터 다운로드...", self)
        download_action.setShortcut("Ctrl+D")
        download_action.triggered.connect(self.open_download_dialog)
        data_menu.addAction(download_action)
        
        data_menu.addSeparator()
        
        # '롱 숏 라벨링...' 액션 추가
        labeling_action = QAction("롱 숏 라벨링...", self)
        labeling_action.setShortcut("Ctrl+L")
        labeling_action.triggered.connect(self.open_labeling_dialog)
        data_menu.addAction(labeling_action)
        
        # '라벨 차트 표시' 액션 (토글형) 추가
        self.show_label_action = QAction("라벨 차트 표시", self)
        self.show_label_action.setCheckable(True)
        self.show_label_action.setChecked(False) # 기본값: 꺼짐
        self.show_label_action.triggered.connect(self.toggle_label_chart)
        data_menu.addAction(self.show_label_action)

        # '백테스트 실행...' 액션 추가 (기능은 추후 구현)
        backtest_action = QAction("백테스트 실행...", self)
        backtest_action.setShortcut("Ctrl+B")
        backtest_action.triggered.connect(self.run_backtest)
        data_menu.addAction(backtest_action)

        # '지표 설정' 메뉴 탭 생성
        indicator_menu = menubar.addMenu("지표 설정(&I)")
        
        sma_action = QAction("단순 이동 평균...", self)
        sma_action.triggered.connect(self.open_sma_dialog)
        indicator_menu.addAction(sma_action)

        supertrend_action = QAction("3개의 슈퍼트렌드...", self)
        supertrend_action.triggered.connect(self.open_supertrend_dialog)
        indicator_menu.addAction(supertrend_action)

        ma_slope_action = QAction("이동평균 기울기...", self)
        ma_slope_action.triggered.connect(self.open_ma_slope_dialog)
        indicator_menu.addAction(ma_slope_action)

        indicator_menu.addSeparator()

        clear_indicator_action = QAction("지표 초기화", self)
        clear_indicator_action.triggered.connect(self.clear_indicators)
        indicator_menu.addAction(clear_indicator_action)

    def toggle_label_chart(self, checked):
        # 체크 여부가 변경될 때마다 화면(차트 및 표)을 다시 그려서 토글 상태 반영
        if hasattr(self, 'current_df') and not self.current_df.empty:
            self.populate_ui(self.current_df)

    def apply_sma_breakout_labeling(self, period, strategy, offset_pct):
        cache_file = 'btc_usdt_1m_cache.csv'
        import os
        
        if not os.path.exists(cache_file):
            QMessageBox.warning(self, "오류", "캐시 파일이 존재하지 않습니다. 데이터를 먼저 갱신하세요.")
            return
            
        self.setWindowTitle("Binance Futures BTC - 단순 돌파 연산 중...")
        QApplication.processEvents()
        
        try:
            df = pd.read_csv(cache_file)
            
            # SMA 계산 및 오프셋 적용 기준선 생성 (충분한 데이터 없으면 NaN)
            sma = df['close'].rolling(window=period).mean()
            upper_bound = sma * (1 + offset_pct / 100.0)
            lower_bound = sma * (1 - offset_pct / 100.0)
            
            opens = df['open'].values
            
            # 이전 오픈가와 이전 SMA선 접근을 위한 shift 연산
            prev_opens = np.roll(opens, 1)
            prev_opens[0] = opens[0]
            
            prev_upper = np.roll(upper_bound.values, 1)
            prev_lower = np.roll(lower_bound.values, 1)
            
            # 상향 돌파 및 하향 돌파 시그널 식별 (기준을 오프셋 밴드로 원복)
            cross_up = (prev_opens <= prev_upper) & (opens > upper_bound.values)
            cross_down = (prev_opens >= prev_lower) & (opens < lower_bound.values)
            
            # 상태 머신 로직: 이전의 state(label)를 유지하기 위해 Pandas ffill 활용
            signal_series = pd.Series(0, index=df.index)
            signal_series.loc[cross_up] = 1
            signal_series.loc[cross_down] = -1
            
            # 시그널이 없는 구간(0)을 NaN으로 만들어 ffill() 대상이 되게 함
            signal_series = signal_series.replace(0, np.nan)
            
            # 가장 첫 번째 값은 0으로 시작하도록 강제 지정
            if pd.isna(signal_series.iloc[0]):
                signal_series.iloc[0] = 0
                
            # NaN을 이전 상태값으로 덮어씌움 (ffill)
            df['ls_label'] = signal_series.ffill().fillna(0).astype(int).values
            df.to_csv(cache_file, index=False)
            
            QMessageBox.information(self, "라벨링 완료", f"이동평균({period}) 단순 돌파 전략(오프셋 {offset_pct}%) 데이터 갱신 완료!")
            
            if hasattr(self, 'last_start_ms') and hasattr(self, 'last_end_ms'):
                # 캐시 파일을 데이터프레임으로 갱신 후 화면 리렌더링
                self.download_data(self.last_start_ms, self.last_end_ms)
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"라벨링 중 오류 발생: {str(e)}")
        finally:
            self.setWindowTitle("Binance Futures BTC OHLCV Downloader")

    def open_sma_dialog(self):
        dialog = SMADialog(self)
        if dialog.exec():
            period, use_ls, strategy, offset = dialog.get_settings()
            
            if period not in self.sma_periods:
                self.sma_periods.append(period)
                
            if use_ls and strategy == "단순 돌파 전략":
                self.apply_sma_breakout_labeling(period, strategy, offset)
            else:
                if hasattr(self, 'current_df') and not self.current_df.empty:
                    self.populate_ui(self.current_df)

    def open_supertrend_dialog(self):
        dialog = SupertrendDialog(self)
        if dialog.exec():
            st_settings, use_ls, ma_type, ma_period, lookback = dialog.get_settings()
            self.supertrend_settings = st_settings

            if use_ls:
                # MA 지표도 자동 등록 (MA 선 + Slope)
                if ma_type and ma_period and lookback:
                    if (ma_type, ma_period, lookback) not in self.ma_slope_settings:
                        self.ma_slope_settings.append((ma_type, ma_period, lookback))
                    if ma_period not in self.sma_periods:
                        self.sma_periods.append(ma_period)

                # LS 라벨링 수행
                self.apply_supertrend_ls_labeling(st_settings, ma_type, ma_period, lookback)
            else:
                if hasattr(self, 'current_df') and not self.current_df.empty:
                    self.populate_ui(self.current_df)

    def apply_supertrend_ls_labeling(self, st_settings, ma_type, ma_period, lookback):
        """3개 슈퍼트렌드 + MA Slope 조건으로 ls_label 설정 후 화면 갱신"""
        import os
        cache_file = 'btc_usdt_1m_cache.csv'
        if not os.path.exists(cache_file):
            QMessageBox.warning(self, "오류", "캐시 파일이 없습니다. 데이터를 먼저 받아오세요.")
            return

        self.setWindowTitle("Binance Futures BTC - 라벨링 연산 중...")
        QApplication.processEvents()

        try:
            df = pd.read_csv(cache_file)
            if 'ls_label' not in df.columns:
                df['ls_label'] = 0

            # 원본 df로 슈퍼트렌드 3개 계산
            raw = df[['open', 'high', 'low', 'close']].copy()
            directions = []
            for atr_p, mult in st_settings:
                _, d = self.calculate_supertrend(raw, atr_p, mult)
                directions.append(d)  # d[i] = 1(상승) or -1(하락)

            # MA 계산
            if ma_type == 'EMA':
                ma_series = df['close'].ewm(span=ma_period, adjust=False).mean()
            else:
                ma_series = df['close'].rolling(window=ma_period).mean()

            # MA Slope 계산
            slope_series = ma_series - ma_series.shift(lookback)

            opens = df['open'].values
            ma_vals = ma_series.values
            slope_vals = slope_series.values

            # 라벨 초기화 후 조건 적용
            labels = np.zeros(len(df), dtype=int)
            for i in range(len(df)):
                if np.isnan(slope_vals[i]) or np.isnan(ma_vals[i]):
                    continue
                bull_count = sum(1 for d in directions if d[i] == 1)
                bear_count = sum(1 for d in directions if d[i] == -1)

                # 조건 6: 상승
                if (slope_vals[i] > 0
                        and opens[i] > ma_vals[i]
                        and bull_count >= 2):
                    labels[i] = 1
                # 조건 7: 하락
                elif (slope_vals[i] < 0
                        and opens[i] < ma_vals[i]
                        and bear_count >= 2):
                    labels[i] = -1

            df['ls_label'] = labels
            df.to_csv(cache_file, index=False)

            QMessageBox.information(self, "라벨링 완료",
                                    f"슈퍼트렌드 + {ma_type}({ma_period}) Slope({lookback}) 조건으로 "
                                    f"LS 라벨 갱신 완료\n"
                                    f"Long: {(labels==1).sum()}개, Short: {(labels==-1).sum()}개")

            if hasattr(self, 'last_start_ms') and hasattr(self, 'last_end_ms'):
                self.download_data(self.last_start_ms, self.last_end_ms)

        except Exception as e:
            QMessageBox.critical(self, "오류", f"라벨링 중 오류 발생: {str(e)}")
        finally:
            self.setWindowTitle("Binance Futures BTC OHLCV Downloader")

    def open_ma_slope_dialog(self):
        dialog = MASlopeDialog(self)
        if dialog.exec():
            setting = dialog.get_settings()  # (ma_type, ma_period, lookback)
            self.ma_slope_settings.append(setting)
            if hasattr(self, 'current_df') and not self.current_df.empty:
                self.populate_ui(self.current_df)

    def calculate_supertrend(self, df, atr_period, multiplier):
        """TradingView 방식의 슈퍼트렌드 계산.
        - ATR: RMA(Wilder's 평활이동평균, alpha=1/period)
        - 밴드: 이전 밴드값과 비교하여 한 방향으로만 수렴
        - direction: 1=상승(bullish), -1=하락(bearish)
        """
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)
        close = df['close'].values.astype(float)
        n = len(close)

        # True Range
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(high[i] - low[i],
                        abs(high[i] - close[i - 1]),
                        abs(low[i]  - close[i - 1]))

        # ATR via RMA (Wilder's smoothing): 첫 값은 단순평균으로 시드
        atr = np.zeros(n)
        seed_end = min(atr_period, n)
        atr[seed_end - 1] = np.mean(tr[:seed_end])
        alpha = 1.0 / atr_period
        for i in range(seed_end, n):
            atr[i] = alpha * tr[i] + (1.0 - alpha) * atr[i - 1]

        # 기본 밴드
        hl2 = (high + low) / 2.0
        basic_upper = hl2 + multiplier * atr
        basic_lower = hl2 - multiplier * atr

        # 최종 밴드 & 슈퍼트렌드
        final_upper = np.copy(basic_upper)
        final_lower = np.copy(basic_lower)
        supertrend  = np.zeros(n)
        direction   = np.zeros(n, dtype=int)

        # 초기 방향 결정
        direction[0] = 1 if close[0] >= final_lower[0] else -1
        supertrend[0] = final_lower[0] if direction[0] == 1 else final_upper[0]

        for i in range(1, n):
            # Final Upper: 새 밴드가 이전 밴드보다 낮거나, 이전 종가가 이전 밴드를 상향 돌파하면 갱신
            if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i - 1]

            # Final Lower: 새 밴드가 이전 밴드보다 높거나, 이전 종가가 이전 밴드를 하향 돌파하면 갱신
            if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i - 1]

            # 방향 전환 판정
            if direction[i - 1] == -1:   # 이전이 하락(bearish)
                if close[i] > final_upper[i]:
                    direction[i] = 1
                    supertrend[i] = final_lower[i]
                else:
                    direction[i] = -1
                    supertrend[i] = final_upper[i]
            else:                         # 이전이 상승(bullish)
                if close[i] < final_lower[i]:
                    direction[i] = -1
                    supertrend[i] = final_upper[i]
                else:
                    direction[i] = 1
                    supertrend[i] = final_lower[i]

        return supertrend, direction

    def clear_indicators(self):
        if self.sma_periods or self.supertrend_settings or self.ma_slope_settings:
            self.sma_periods.clear()
            self.supertrend_settings.clear()
            self.ma_slope_settings.clear()
            if hasattr(self, 'current_df') and not self.current_df.empty:
                self.populate_ui(self.current_df)
            QMessageBox.information(self, "지표 초기화", "추가된 모든 지표가 차트에서 제거되었습니다.")

    def setup_statusbar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # 라벨링 진행률을 표시할 프로그레스 바 
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusBar.addPermanentWidget(self.progress_bar)

    def open_labeling_dialog(self):
        dialog = LabelingDialog(self)
        if dialog.exec():
            target_profit, stop_loss = dialog.get_parameters()
            self.apply_labeling(target_profit, stop_loss)

    def apply_labeling(self, target_profit_pct, stop_loss_pct):
        cache_file = 'btc_usdt_1m_cache.csv'
        import os
        
        if not os.path.exists(cache_file):
            QMessageBox.warning(self, "오류", "캐시 파일이 존재하지 않습니다. 데이터를 먼저 갱신하세요.")
            return
            
        # 연산 집중 시 UI 멈춤을 방지하기 위한 안내
        self.setWindowTitle("Binance Futures BTC OHLCV Downloader - 라벨링 연산 중...")
        QApplication.processEvents()
        
        try:
            df = pd.read_csv(cache_file)
            if 'ls_label' not in df.columns:
                df['ls_label'] = 0
                
            labels = np.zeros(len(df), dtype=int)
            opens = df['open'].values
            highs = df['high'].values
            lows = df['low'].values
            
            tp = target_profit_pct / 100.0
            sl = stop_loss_pct / 100.0
            
            total_rows = len(df)
            self.progress_bar.setRange(0, total_rows)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.statusBar.showMessage("라벨링 분석 연산 중...")
            
            # 미래 데이터를 훑어보며 조건 시뮬레이션
            for i in range(total_rows):
                if i % 250 == 0:
                    self.progress_bar.setValue(i)
                    QApplication.processEvents()
                    
                entry_price = opens[i]
                long_target = entry_price * (1 + tp)
                long_stop = entry_price * (1 - sl)
                short_target = entry_price * (1 - tp)
                short_stop = entry_price * (1 + sl)
                
                long_hit_idx = -1
                short_hit_idx = -1
                
                for j in range(i + 1, len(df)):
                    curr_high = highs[j]
                    curr_low = lows[j]
                    
                    if long_hit_idx == -1:
                        if curr_low <= long_stop:
                            long_hit_idx = -2 # 먼저 손절에 도달
                        elif curr_high >= long_target:
                            long_hit_idx = j # 정상 익절
                            
                    if short_hit_idx == -1:
                        if curr_high >= short_stop:
                            short_hit_idx = -2
                        elif curr_low <= short_target:
                            short_hit_idx = j
                            
                    if long_hit_idx != -1 and short_hit_idx != -1:
                        break
                        
                is_long_success = (long_hit_idx >= 0)
                is_short_success = (short_hit_idx >= 0)
                
                if is_long_success and not is_short_success:
                    labels[i] = 1
                elif is_short_success and not is_long_success:
                    labels[i] = -1
                elif is_long_success and is_short_success:
                    # 둘 다 목표 도달 시, '먼저' 달성한 진입포지션을 선택
                    if long_hit_idx < short_hit_idx:
                        labels[i] = 1
                    elif short_hit_idx < long_hit_idx:
                        labels[i] = -1
                    else:
                        labels[i] = 0
                else:
                    labels[i] = 0

            self.progress_bar.setValue(total_rows)
            QApplication.processEvents()

            df['ls_label'] = labels
            df.to_csv(cache_file, index=False)
            
            self.progress_bar.setVisible(False)
            self.statusBar.showMessage("라벨링 완료!", 3000)
            
            QMessageBox.information(self, "라벨링 완료", "설정한 비율에 따라 라벨링 작업이 완료되었습니다.")
            
            # 기존 화면에 표시 중이던 기간이 있다면 그 구간을 다시 새로고침하여 표 갱신
            if hasattr(self, 'last_start_ms') and hasattr(self, 'last_end_ms'):
                self.download_data(self.last_start_ms, self.last_end_ms)
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"라벨링 중 예기치 않은 오류 발생: {str(e)}")
            
        finally:
            self.setWindowTitle("Binance Futures BTC OHLCV Downloader")
            self.progress_bar.setVisible(False)
            self.statusBar.clearMessage()

    def run_backtest(self):
        if not hasattr(self, 'current_df') or self.current_df.empty:
            QMessageBox.warning(self, "백테스트", "백테스트를 수행할 데이터가 없습니다.")
            return

        import os
        try:
            # 규칙 1: capital 100으로 초기화
            df = self.current_df.copy()
            df['capital'] = 100.0
            fee_rate = 0.0005  # 0.05%
            balance = 100.0
            pos = 0          # 0: 없음, 1: Long, -1: Short
            entry_price = 0.0

            total_rows = len(df)

            # 규칙 2~6: 봉 단위 가상 거래 시뮬레이션
            for i in range(total_rows):
                label      = int(df.iloc[i]['ls_label'])
                open_price = float(df.iloc[i]['open'])

                # 규칙 5-4: 현재 포지션과 다른 label이 나타나면 청산만 수행
                if pos != 0 and label != pos:
                    balance *= (1 - fee_rate)          # 청산 수수료
                    if pos == 1:
                        pnl = (open_price - entry_price) / entry_price
                    else:  # pos == -1
                        pnl = (entry_price - open_price) / entry_price
                    balance *= (1 + pnl)
                    pos = 0

                # 규칙 5-2/5-3: 포지션이 없고 label이 있으면 진입
                if pos == 0 and label != 0:
                    pos = label
                    entry_price = open_price
                    balance *= (1 - fee_rate)          # 진입 수수료

                # 규칙 5-5: 마지막 봉에 포지션이 남아 있으면 close로 청산
                if i == total_rows - 1 and pos != 0:
                    close_price = float(df.iloc[i]['close'])
                    balance *= (1 - fee_rate)          # 청산 수수료
                    if pos == 1:
                        pnl = (close_price - entry_price) / entry_price
                    else:
                        pnl = (entry_price - close_price) / entry_price
                    balance *= (1 + pnl)
                    pos = 0

                # 규칙 6: 매 봉 capital 기록
                df.at[i, 'capital'] = balance

            # 3. 결과 저장 (캐시 파일 업데이트)
            cache_file = 'btc_usdt_1m_cache.csv'
            if os.path.exists(cache_file):
                full_cache = pd.read_csv(cache_file)
                # 현재 표시된 구간의 데이터만 업데이트 (Timestamp 기준)
                # timestamp가 datetime 객체이므로 다시 ms로 변환하여 매칭 (또는 index 매칭)
                # populate_ui에서 변환한 형식을 고려하여 매칭 진행
                
                # 원본 캐시 데이터의 타임스탬프와 일치시키기 위해 ms 단위로 변환
                # (KST 변환 전의 원본 ms 타임스탬프가 필요함. current_df 생성 시의 정보를 활용)
                
                # 더 안전한 방법: current_df에 있는 원본 timestamp(ms)를 사용하여 매치
                # display_df 생성 시 copy() 했으므로, 원본 ms 값이 소실되었을 수 있음.
                # 다시 확인: download_data에서 display_df 생성 후 timestamp를 datetime으로 변환함.
                # 따라서 datetime을 다시 ms로 역변환하여 매칭.
                
                # KST(UTC+9)이므로 9시간을 빼고 ms로 변환
                df_to_save = df.copy()
                df_to_save['timestamp_ms'] = (pd.to_datetime(df_to_save['timestamp']) - pd.Timedelta(hours=9)).values.astype(np.int64) // 10**6
                
                # full_cache의 해당 timestamp 행들의 capital 업데이트
                full_cache.set_index('timestamp', inplace=True)
                # map을 사용하거나 update 사용
                updates = df_to_save.set_index('timestamp_ms')['capital']
                full_cache.update(updates.to_frame())
                full_cache.reset_index(inplace=True)
                full_cache.to_csv(cache_file, index=False)
            
            # 4. UI 갱신 (테이블 등)
            self.populate_ui(df)
            
            final_capital = df.iloc[-1]['capital']
            roi = (final_capital - 100.0)
            QMessageBox.information(self, "백테스트 완료", 
                                    f"백테스트가 완료되었습니다.\n"
                                    f"최종 자산: {final_capital:.2f} USDT\n"
                                    f"수익률: {roi:.2f}%")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"백테스트 중 오류 발생: {str(e)}")

    def open_download_dialog(self):
        start_str = None
        end_str = None
        
        # 현재 화면(차트 및 표)에 표시 중인 데이터가 있다면 그 시작과 끝 시간을 가져옵니다.
        if hasattr(self, 'current_df') and not self.current_df.empty:
            start_str = self.current_df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M:%S')
            end_str = self.current_df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
            
        # 메뉴에서 데이터 다운로드를 클릭했을 때 뜨는 작은 창(Dialog)에 현재 시간을 전달
        dialog = DownloadDialog(self, start_str=start_str, end_str=end_str)
        if dialog.exec():
            # 다이얼로그에서 설정한 시간을 바탕으로 다운로드 함수 호출
            start_ms, end_ms = dialog.get_dates()
            self.download_data(start_ms, end_ms)
            
    def setup_views(self):
        # Create Vertical Splitter
        self.splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.splitter)
        
        # Top: Chart
        self.chart_widget = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_widget)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.fig = Figure()
        self.canvas = FigureCanvas(self.fig)
        
        # 차트 이동/저장을 돕는 툴바 
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.chart_layout.addWidget(self.toolbar)
        
        self.chart_layout.addWidget(self.canvas)
        self.splitter.addWidget(self.chart_widget)
        
        # 마우스 커스텀 이벤트(스크롤, 이동, 더블클릭) 이벤트 연결
        self._dragging = False
        self.canvas.mpl_connect('scroll_event', self.zoom_chart)
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        
        # Bottom: Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["시간 (Timestamp)", "시가 (Open)", "고가 (High)", "저가 (Low)", "종가 (Close)", "거래량 (Volume)", "LS Label", "자산 (Capital)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.splitter.addWidget(self.table)
        
        # 표 더블클릭 이벤트 연결 (차트 동기화)
        self.table.itemDoubleClicked.connect(self.on_table_double_click)
        
        # Set Default Splitter Ratio (e.g., 60% chart, 40% table)
        self.splitter.setSizes([500, 300])
        
    def download_data(self, start_ms=None, end_ms=None):
        if start_ms is None or end_ms is None:
            # 기본 설정값 (프로그램 최초 실행 시 자동 다운로드용)
            start_ms = QDateTime.fromString("2025-07-22 00:00:00", "yyyy-MM-dd HH:mm:ss").toMSecsSinceEpoch()
            end_ms = QDateTime.fromString("2025-07-23 23:59:00", "yyyy-MM-dd HH:mm:ss").toMSecsSinceEpoch()
            
        if start_ms >= end_ms:
            QMessageBox.warning(self, "잘못된 입력", "시작 시간은 종료 시간보다 빨라야 합니다.")
            return
            
        # UI를 새로고침(또는 라벨링 후 갱신)할 때 기존 구간을 재사용하기 위해 저장
        self.last_start_ms = start_ms
        self.last_end_ms = end_ms
            
        # UI 업데이트 강제 (모달 창 처리)
        QApplication.processEvents() 
        
        try:
            exchange = ccxt.binance({'options': {'defaultType': 'future'}})
            symbol = 'BTC/USDT'
            timeframe = '1m'
            limit = 1500
            cache_file = 'btc_usdt_1m_cache.csv'
            
            import os
            if os.path.exists(cache_file):
                df_cache = pd.read_csv(cache_file)
                if 'ls_label' not in df_cache.columns:
                    df_cache['ls_label'] = 0
                if 'capital' not in df_cache.columns:
                    df_cache['capital'] = 100.0
            else:
                df_cache = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'ls_label', 'capital'])
                
            # 다운로드해야 할 구간 (Intervals) 선별: 빠진 구간(Hole) 찾기 알고리즘
            fetch_intervals = []
            
            # 요청한 시간 범위에서 있어야 할 1분(60000ms) 단위 전체 타임스탬프 집합
            expected_ts = set(range(start_ms, end_ms, 60000))
            if not df_cache.empty:
                existing_ts = set(df_cache['timestamp'])
                # 로컬 캐시에 존재하지 않는 타임스탬프만 필터링하여 정렬
                missing_ts = sorted(list(expected_ts - existing_ts))
            else:
                # 캐시가 빈 경우 전체가 누락됨
                missing_ts = sorted(list(expected_ts))
                
            if missing_ts:
                # 누락된 타임스탬프들을 연속된 구간(Interval)으로 그룹화
                s_idx = 0
                for i in range(1, len(missing_ts) + 1):
                    # 다음 인덱스가 배열 끝이거나, 이전 시간과의 차이가 60000ms를 초과(연속되지 않음)하는 경우 끊습니다.
                    if i == len(missing_ts) or missing_ts[i] - missing_ts[i-1] > 60000:
                        f_start = missing_ts[s_idx]
                        f_end = missing_ts[i-1] + 60000
                        fetch_intervals.append((f_start, f_end))
                        s_idx = i
            
            new_ohlcv = []
            for f_start, f_end in fetch_intervals:
                current_start = f_start
                while current_start < f_end:
                    try:
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_start, limit=limit)
                        if not ohlcv:
                            break
                            
                        # 목표 구간 (f_end)을 넘지 않도록 필터링
                        filtered = [row for row in ohlcv if row[0] <= f_end]
                        if not filtered:
                            break
                            
                        new_ohlcv.extend(filtered)
                        
                        last_ts = ohlcv[-1][0]
                        if current_start == last_ts:
                            break
                        current_start = last_ts + 1
                    except Exception as e:
                        QMessageBox.warning(self, "API 오류", f"데이터를 가져오는 중 오류가 발생했습니다: {str(e)}")
                        break
            
            # 새로 받은 데이터가 있으면 캐시에 병합
            if new_ohlcv:
                df_new = pd.DataFrame(new_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_new['ls_label'] = 0
                df_new['capital'] = 100.0
                df_cache = pd.concat([df_cache, df_new], ignore_index=True)
                
            if not df_cache.empty:
                # 중복 데이터 제거 및 정렬 후 파일로 저장
                df_cache.drop_duplicates(subset=['timestamp'], inplace=True)
                df_cache.sort_values('timestamp', inplace=True)
                df_cache.to_csv(cache_file, index=False)
                
                # 사용자가 요청한 범위에 해당하는 데이터만 추출하여 표시
                display_df = df_cache[(df_cache['timestamp'] >= start_ms) & (df_cache['timestamp'] <= end_ms)].copy()
                
                if not display_df.empty:
                    # 바이낸스 기본 시간은 세계 표준시(UTC)이므로, 대한민국 표준시(KST, UTC+9)로 변환
                    display_df['timestamp'] = pd.to_datetime(display_df['timestamp'], unit='ms') + pd.Timedelta(hours=9)
                    self.populate_ui(display_df)
                else:
                    QMessageBox.information(self, "데이터 없음", "선택한 기간 동안의 데이터가 없습니다.")
            else:
                QMessageBox.information(self, "데이터 없음", "캐시가 비어있고 데이터를 받아오지 못했습니다.")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"예기치 않은 오류가 발생했습니다: {str(e)}")
            
    def populate_ui(self, df):
        # 1. Populate Table
        # 필터링된 데이터프레임의 기존 인덱스를 0부터 시작하도록 리셋해야 QTableWidget 행 번호와 일치합니다.
        df = df.reset_index(drop=True)
        self.current_df = df  # 더블클릭 이벤트를 위해 데이터 보관
        self.table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            ts_item = QTableWidgetItem(row['timestamp'].strftime('%Y-%m-%d %H:%M'))
            ts_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row_idx, 0, ts_item)
            
            for col_idx, col_name in enumerate(['open', 'high', 'low', 'close', 'volume']):
                item = QTableWidgetItem(f"{row[col_name]:.2f}")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row_idx, col_idx + 1, item)
                
            # LS Label 열 표시
            ls_item = QTableWidgetItem(str(int(row.get('ls_label', 0))))
            ls_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row_idx, 6, ls_item)
            
            # Capital (자산) 열 표시
            capital_val = row.get('capital', 100.0)
            cap_item = QTableWidgetItem(f"{capital_val:.2f}")
            cap_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row_idx, 7, cap_item)
                
        # 2. Draw Candlestick Chart
        self.fig.clear()
        
        plot_df = df.copy()
        plot_df.set_index('timestamp', inplace=True)
        # Ensure data types are float for mplfinance
        for col in ['open', 'high', 'low', 'close', 'volume']:
            plot_df[col] = plot_df[col].astype(float)
            
        # MA Slope 패널 여부에 따라 서브플롯 구성
        has_slope = bool(self.ma_slope_settings)
        if has_slope:
            from matplotlib.gridspec import GridSpec
            gs = GridSpec(2, 1, figure=self.fig, height_ratios=[3, 1], hspace=0.08)
            ax = self.fig.add_subplot(gs[0])
            ax_slope = self.fig.add_subplot(gs[1], sharex=ax)
        else:
            ax = self.fig.add_subplot(111)
            ax_slope = None

        # 한국인에게 친숙한 색상 (상승: 빨강, 하락: 파랑)
        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
        style = mpf.make_mpf_style(marketcolors=mc)
        
        import matplotlib.dates as mdates
        import numpy as np
        
        addplots = []
        
        # SMA 렌더링
        sma_colors = ['orange', 'purple', 'green', 'magenta', 'cyan', 'brown']
        if hasattr(self, 'sma_periods') and self.sma_periods:
            for idx, period in enumerate(self.sma_periods):
                col_name = f'SMA_{period}'
                plot_df[col_name] = plot_df['close'].rolling(window=period).mean()
                color = sma_colors[idx % len(sma_colors)]
                addplots.append(mpf.make_addplot(plot_df[col_name], type='line', color=color, width=1.0, ax=ax))

        # 슈퍼트렌드 렌더링 (상승: 초록, 하락: 빨강)
        st_bull_colors = ['#00c853', '#00897b', '#1565c0']  # 3개 각각 구분 색
        st_bear_colors = ['#d50000', '#ff6d00', '#aa00ff']
        if hasattr(self, 'supertrend_settings') and self.supertrend_settings:
            raw_vals = plot_df[['open', 'high', 'low', 'close']].copy().reset_index(drop=True)
            for st_idx, (atr_period, multiplier) in enumerate(self.supertrend_settings):
                st_line, direction = self.calculate_supertrend(raw_vals, atr_period, multiplier)
                bull_arr = np.where(direction == 1, st_line, np.nan)
                bear_arr = np.where(direction == -1, st_line, np.nan)
                bull_series = pd.Series(bull_arr, index=plot_df.index)
                bear_series = pd.Series(bear_arr, index=plot_df.index)
                if not np.isnan(bull_arr).all():
                    addplots.append(mpf.make_addplot(bull_series, type='line',
                                                     color=st_bull_colors[st_idx % 3], width=1.5, ax=ax))
                if not np.isnan(bear_arr).all():
                    addplots.append(mpf.make_addplot(bear_series, type='line',
                                                     color=st_bear_colors[st_idx % 3], width=1.5, ax=ax))

        if hasattr(self, 'show_label_action') and self.show_label_action.isChecked() and 'ls_label' in plot_df.columns:
            offset = plot_df['close'] * 0.0005
            
            long_arr = np.where(plot_df['ls_label'] == 1, plot_df['high'] + offset, np.nan)
            short_arr = np.where(plot_df['ls_label'] == -1, plot_df['low'] - offset, np.nan)
            
            if not np.isnan(long_arr).all():
                # 봉 위에 위쪽 화살표 상승기호(빨간색)
                addplots.append(mpf.make_addplot(long_arr, type='scatter', markersize=0.6, marker='^', color='red', ax=ax))
            if not np.isnan(short_arr).all():
                # 봉 아래쪽에 아래쪽 화살표 하락기호(파란색)
                addplots.append(mpf.make_addplot(short_arr, type='scatter', markersize=0.6, marker='v', color='blue', ax=ax))
                
        # show_nontrading=True 설정으로 X축을 실제 datetime으로 사용하여 matplotlib 포매터 적용
        if addplots:
            mpf.plot(plot_df, type='candle', ax=ax, style=style, xrotation=0, show_nontrading=True, axtitle="BTC/USDT 1m (Binance Futures)", ylabel="Price (USDT)", addplot=addplots)
        else:
            mpf.plot(plot_df, type='candle', ax=ax, style=style, xrotation=0, show_nontrading=True, axtitle="BTC/USDT 1m (Binance Futures)", ylabel="Price (USDT)")

        # MA Slope 패널 렌더링
        if ax_slope is not None:
            slope_line_colors = ['#2196f3', '#ff9800', '#9c27b0']
            ax_slope.axhline(y=0, color='#888888', linewidth=0.8, linestyle='-')
            x_nums = mdates.date2num(plot_df.index.to_pydatetime())
            for idx, (ma_type, ma_period, lookback) in enumerate(self.ma_slope_settings):
                if ma_type == 'EMA':
                    ma_series = plot_df['close'].ewm(span=ma_period, adjust=False).mean()
                else:  # SMA
                    ma_series = plot_df['close'].rolling(window=ma_period).mean()
                slope = ma_series - ma_series.shift(lookback)
                slope_vals = slope.values
                color = slope_line_colors[idx % len(slope_line_colors)]
                ax_slope.plot(x_nums, slope_vals, color=color, linewidth=1.0,
                              label=f'{ma_type}({ma_period}) Slope({lookback})')
                valid = ~np.isnan(slope_vals)
                ax_slope.fill_between(x_nums, slope_vals, 0,
                                      where=valid & (slope_vals >= 0),
                                      color='#00c853', alpha=0.3, interpolate=True)
                ax_slope.fill_between(x_nums, slope_vals, 0,
                                      where=valid & (slope_vals < 0),
                                      color='#d50000', alpha=0.3, interpolate=True)
            ax_slope.set_ylabel('MA Slope', fontsize=8)
            ax_slope.legend(fontsize=7, loc='upper left')
            ax_slope.grid(axis='y', linestyle='--', linewidth=0.4, alpha=0.6)
        
        # 사용자 맞춤형 X축 날짜/시간 포매터 정의
        import matplotlib.ticker as ticker
        class CustomDateFormatter(ticker.Formatter):
            def __call__(self, x, pos=0):
                try:
                    dt = mdates.num2date(x)
                    # 연도가 바뀔 때 (1월 1일 00:00)
                    if dt.month == 1 and dt.day == 1 and dt.hour == 0 and dt.minute == 0:
                        return f"$\\mathbf{{{dt.strftime('%Y')}}}$"
                    # 달이 바뀔 때 (1일 00:00)
                    elif dt.day == 1 and dt.hour == 0 and dt.minute == 0:
                        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                        return f"$\\mathbf{{{month_names[dt.month]}}}$"
                    # 날짜가 바뀔 때 (00:00)
                    elif dt.hour == 0 and dt.minute == 0:
                        return f"$\\mathbf{{{dt.strftime('%d')}}}$"
                    # 기본 표시 (시간)
                    else:
                        return dt.strftime('%H:%M')
                except Exception:
                    return ""
                    
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(CustomDateFormatter())
        ax.format_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M')

        # Slope 패널이 있으면 메인 차트 X축 라벨을 숨기고 slope 패널에 포매터 적용
        if ax_slope is not None:
            import matplotlib.pyplot as plt
            plt.setp(ax.get_xticklabels(), visible=False)
            ax_slope.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax_slope.xaxis.set_major_formatter(CustomDateFormatter())
            ax_slope.format_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M')

        self.update_marker_sizes(ax)

        self.fig.tight_layout()
        self.canvas.draw()
        
    def zoom_chart(self, event):
        # 차트 영역 안에서 발생한 스크롤이 아니면 무시
        if event.inaxes is None:
            return
            
        ax = event.inaxes
        
        # 확대/축소 비율 (한 번 틱에 10% 증감)
        base_scale = 1.1
        if event.step > 0:
            scale = 1 / base_scale # 위로 굴리면 확대
        else:
            scale = base_scale     # 아래로 굴리면 축소
            
        # 파이썬 내장 이벤트 대신 Qt(GUI)에서 직접 현재 키보드 상태(컨트롤 키 눌림 여부)를 감지합니다.
        modifiers = QApplication.keyboardModifiers()
        
        # 컨트롤 키를 누른 상태에서는 세로축(Y축)을 확대/축소
        if modifiers & Qt.ControlModifier:
            ylim = ax.get_ylim()
            ydata = event.ydata
            # Y좌표(가격)를 중심으로 상하 재계산
            new_bottom = ydata - (ydata - ylim[0]) * scale
            new_top = ydata + (ylim[1] - ydata) * scale
            ax.set_ylim([new_bottom, new_top])
        else:
            xlim = ax.get_xlim()
            xdata = event.xdata
            # 마우스가 위치한 곳(xdata)을 기준으로 중심을 잡고 좌우(X축) 좌표 재계산
            new_left = xdata - (xdata - xlim[0]) * scale
            new_right = xdata + (xlim[1] - xdata) * scale
            ax.set_xlim([new_left, new_right])
            
        self.update_marker_sizes(ax)
        self.canvas.draw()
        
    def on_press(self, event):
        if event.inaxes is None:
            return
            
        # 1. 더블 클릭 -> 차트/표 동기화 핸들러로 우회
        if event.dblclick:
            self.handle_double_click(event)
            
        # 2. 좌클릭 단일 누르기 -> 드래그(Pan) 모드 활성화
        elif event.button == 1:
            # 툴바(기본 줌,팬)가 활성화 중일 때는 충돌을 막기 위해 무시
            if hasattr(self, 'toolbar') and self.toolbar.mode != '':
                return
            self._dragging = True
            self._drag_x_start = event.x
            self._drag_y_start = event.y
            self._orig_xlim = event.inaxes.get_xlim()
            self._orig_ylim = event.inaxes.get_ylim()

    def on_motion(self, event):
        if getattr(self, '_dragging', False) and event.inaxes:
            ax = event.inaxes
            
            # 마우스 픽셀 변화량
            dx_px = event.x - self._drag_x_start
            dy_px = event.y - self._drag_y_start
            
            x0, x1 = self._orig_xlim
            y0, y1 = self._orig_ylim
            
            # 현재 창 크기에 맞추어 좌표 변환 (해상도 비례 팬 속도)
            bbox = ax.get_window_extent()
            dx_data = dx_px / bbox.width * (x1 - x0)
            dy_data = dy_px / bbox.height * (y1 - y0)
            
            # 마우스를 끈 방향으로 차트 이동 (반대 단위로 리미트 이동)
            ax.set_xlim([x0 - dx_data, x1 - dx_data])
            ax.set_ylim([y0 - dy_data, y1 - dy_data])
            self.update_marker_sizes(ax)
            self.canvas.draw_idle()

    def on_release(self, event):
        if event.button == 1:
            self._dragging = False

    def update_marker_sizes(self, ax):
        xlim = ax.get_xlim()
        # 현재 화면에 보이는 캔들 개수(x축 범위)
        visible_candles = max(1, xlim[1] - xlim[0])
        # 화살표가 지금도 너무 커서 다시 10분의 1 수준(기초 대비 1/100)으로 대폭 하향
        new_size = max(0.1, min(20, 50 / visible_candles))
        
        import matplotlib.collections as mcoll
        for collection in ax.collections:
            # mpf.make_addplot으로 추가된 scatter 객체(화살표 마커)의 크기 조절
            if isinstance(collection, mcoll.PathCollection):
                collection.set_sizes([new_size])

    def handle_double_click(self, event):
        if not hasattr(self, 'current_df') or self.current_df.empty:
            return
            
        import matplotlib.dates as mdates
        try:
            # 클릭한 X축 좌표를 변환하고 naive datetime으로 맞춤 (표 데이터 시간과 동일하게 만들기 위함)
            clicked_dt = mdates.num2date(event.xdata)
            clicked_ts = pd.Timestamp(clicked_dt).tz_localize(None)
            
            # 현재 표시된 데이터프레임에서 가장 가까운 시점의 행(row)을 찾습니다.
            time_diffs = abs(self.current_df['timestamp'] - clicked_ts)
            closest_idx = time_diffs.idxmin()
            
            # 선택한 표의 행에 하이라이트를 주고 중앙으로 스크롤 이동
            self.table.selectRow(closest_idx)
            item = self.table.item(closest_idx, 0)
            if item:
                self.table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                # 차트를 더블클릭했을 때도 표를 더블클릭한 것과 똑같이 움직이도록 강제 호출해 세로선을 옮겨줌
                self.on_table_double_click(item)
        except Exception as e:
            print("Error navigating to row:", e)

    def on_table_double_click(self, item):
        if not hasattr(self, 'current_df') or self.current_df.empty:
            return
            
        row_idx = item.row()
        if row_idx < 0 or row_idx >= len(self.current_df):
            return
            
        target_ts = self.current_df.iloc[row_idx]['timestamp']
        
        # 차트의 메인 축 가져오기
        if not self.fig.axes:
            return
        ax = self.fig.axes[0]
        
        import matplotlib.dates as mdates
        # 타임스탬프를 matplotlib 수치좌표로 변환
        x_val = mdates.date2num(target_ts)
        
        # 이전에 그려둔 하이라이트 세로선이 있다면 안전하게 제거
        if hasattr(self, 'highlight_vline') and self.highlight_vline in ax.lines:
            try:
                self.highlight_vline.remove()
            except Exception:
                pass
            
        # 캔들 뒤(zorder=0)에 그려지는 보통 굵기의 회색 점선으로 해당 캔들을 마킹
        self.highlight_vline = ax.axvline(x=x_val, color='gray', linestyle='--', linewidth=1.5, alpha=0.8, zorder=0)
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 전체 폰트 크기를 기존 설정의 절반 수준으로 줄이기
    font = app.font()
    if font.pointSize() > 0:
        font.setPointSizeF(font.pointSizeF() * 1.2)
    elif font.pixelSize() > 0:
        font.setPixelSize(int(font.pixelSize() * 1.2))
    else:
        font.setPointSize(8)
    app.setFont(font)
    
    window = BinanceDataFetcher()
    window.show()
    sys.exit(app.exec())
