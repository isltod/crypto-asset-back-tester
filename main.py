import sys
import datetime
import ccxt
import pandas as pd
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QDateTimeEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QSplitter, QAbstractItemView)
from PySide6.QtCore import QDateTime, Qt

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import mplfinance as mpf

class BinanceDataFetcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Binance Futures BTC OHLCV Downloader")
        self.resize(1000, 800)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Setup Inputs
        self.setup_inputs()
        
        # Setup Views (Chart and Table)
        self.setup_views()
        
    def setup_inputs(self):
        input_layout = QHBoxLayout()
        
        # Start Time
        self.start_label = QLabel("시작 날짜 & 시간:")
        self.start_dt = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_dt.setCalendarPopup(True)
        
        # End Time
        self.end_label = QLabel("종료 날짜 & 시간:")
        self.end_dt = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_dt.setCalendarPopup(True)
        
        # Download Button
        self.download_btn = QPushButton("다운로드")
        self.download_btn.clicked.connect(self.download_data)
        
        input_layout.addWidget(self.start_label)
        input_layout.addWidget(self.start_dt)
        input_layout.addWidget(self.end_label)
        input_layout.addWidget(self.end_dt)
        input_layout.addWidget(self.download_btn)
        
        self.layout.addLayout(input_layout)
        
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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["시간 (Timestamp)", "시가 (Open)", "고가 (High)", "저가 (Low)", "종가 (Close)", "거래량 (Volume)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.splitter.addWidget(self.table)
        
        # 표 더블클릭 이벤트 연결 (차트 동기화)
        self.table.itemDoubleClicked.connect(self.on_table_double_click)
        
        # Set Default Splitter Ratio (e.g., 60% chart, 40% table)
        self.splitter.setSizes([500, 300])
        
    def download_data(self):
        start_ms = self.start_dt.dateTime().toMSecsSinceEpoch()
        end_ms = self.end_dt.dateTime().toMSecsSinceEpoch()
        
        if start_ms >= end_ms:
            QMessageBox.warning(self, "잘못된 입력", "시작 시간은 종료 시간보다 빨라야 합니다.")
            return
            
        self.download_btn.setEnabled(False)
        self.download_btn.setText("데이터 확인 및 다운로드 중...")
        QApplication.processEvents() # Force UI update
        
        try:
            exchange = ccxt.binance({'options': {'defaultType': 'future'}})
            symbol = 'BTC/USDT'
            timeframe = '1m'
            limit = 1500
            cache_file = 'btc_usdt_1m_cache.csv'
            
            import os
            if os.path.exists(cache_file):
                df_cache = pd.read_csv(cache_file)
            else:
                df_cache = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
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
            
        finally:
            self.download_btn.setEnabled(True)
            self.download_btn.setText("다운로드")
            
    def populate_ui(self, df):
        # 1. Populate Table
        # 필터링된 데이터프레임의 기존 인덱스를 0부터 시작하도록 리셋해야 QTableWidget 행 번호와 일치합니다.
        df = df.reset_index(drop=True)
        self.current_df = df  # 더블클릭 이벤트를 위해 데이터 보관
        self.table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            ts_item = QTableWidgetItem(row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'))
            ts_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row_idx, 0, ts_item)
            
            for col_idx, col_name in enumerate(['open', 'high', 'low', 'close', 'volume']):
                item = QTableWidgetItem(f"{row[col_name]:.2f}")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row_idx, col_idx + 1, item)
                
        # 2. Draw Candlestick Chart
        self.fig.clear()
        
        plot_df = df.copy()
        plot_df.set_index('timestamp', inplace=True)
        # Ensure data types are float for mplfinance
        for col in ['open', 'high', 'low', 'close', 'volume']:
            plot_df[col] = plot_df[col].astype(float)
            
        ax = self.fig.add_subplot(111)
        
        # 한국인에게 친숙한 색상 (상승: 빨강, 하락: 파랑)
        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit')
        style = mpf.make_mpf_style(marketcolors=mc)
        
        import matplotlib.dates as mdates
        
        # show_nontrading=True 설정으로 X축을 실제 datetime으로 사용하여 matplotlib 포매터 적용
        mpf.plot(plot_df, type='candle', ax=ax, style=style, xrotation=0, show_nontrading=True, axtitle="BTC/USDT 1m (Binance Futures)", ylabel="Price (USDT)")
        
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
            self.canvas.draw_idle()

    def on_release(self, event):
        if event.button == 1:
            self._dragging = False

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
    
    # 전체 폰트 크기 1.5배로 키우기
    font = app.font()
    if font.pointSize() > 0:
        font.setPointSizeF(font.pointSizeF() * 1.5)
    elif font.pixelSize() > 0:
        font.setPixelSize(int(font.pixelSize() * 1.5))
    else:
        font.setPointSize(15)
    app.setFont(font)
    
    window = BinanceDataFetcher()
    window.show()
    sys.exit(app.exec())
