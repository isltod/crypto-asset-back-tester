import sys
import datetime
import ccxt
import pandas as pd
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QDateTimeEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QSplitter)
from PySide6.QtCore import QDateTime, Qt

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
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
        self.chart_layout.addWidget(self.canvas)
        self.splitter.addWidget(self.chart_widget)
        
        # Bottom: Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["시간 (Timestamp)", "시가 (Open)", "고가 (High)", "저가 (Low)", "종가 (Close)", "거래량 (Volume)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.splitter.addWidget(self.table)
        
        # Set Default Splitter Ratio (e.g., 60% chart, 40% table)
        self.splitter.setSizes([500, 300])
        
    def download_data(self):
        start_ms = self.start_dt.dateTime().toMSecsSinceEpoch()
        end_ms = self.end_dt.dateTime().toMSecsSinceEpoch()
        
        if start_ms >= end_ms:
            QMessageBox.warning(self, "잘못된 입력", "시작 시간은 종료 시간보다 빨라야 합니다.")
            return
            
        self.download_btn.setEnabled(False)
        self.download_btn.setText("다운로드 중...")
        QApplication.processEvents() # Force UI update
        
        try:
            exchange = ccxt.binance({'options': {'defaultType': 'future'}})
            symbol = 'BTC/USDT'
            timeframe = '1h'
            limit = 1500
            
            all_ohlcv = []
            current_start = start_ms
            
            while current_start < end_ms:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_start, limit=limit)
                    if not ohlcv:
                        break
                        
                    # Filter data within time range
                    filtered_ohlcv = [row for row in ohlcv if row[0] <= end_ms]
                    if not filtered_ohlcv:
                        break
                        
                    all_ohlcv.extend(filtered_ohlcv)
                    
                    last_timestamp = ohlcv[-1][0]
                    if current_start == last_timestamp:
                        break
                    current_start = last_timestamp + 1
                    
                except Exception as e:
                    QMessageBox.warning(self, "API 오류", f"데이터를 가져오는 중 오류가 발생했습니다: {str(e)}")
                    break
                    
            if all_ohlcv:
                df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.drop_duplicates(subset=['timestamp'], inplace=True)
                
                self.populate_ui(df)
            else:
                QMessageBox.information(self, "데이터 없음", "선택한 기간 동안의 데이터가 없습니다.")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"예기치 않은 오류가 발생했습니다: {str(e)}")
            
        finally:
            self.download_btn.setEnabled(True)
            self.download_btn.setText("다운로드")
            
    def populate_ui(self, df):
        # 1. Populate Table
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
        mpf.plot(plot_df, type='candle', ax=ax, style=style, xrotation=0, show_nontrading=True, axtitle="BTC/USDT 1h (Binance Futures)", ylabel="Price (USDT)")
        
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
