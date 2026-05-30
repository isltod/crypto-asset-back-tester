import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, f1_score

# ----------------------------------------------------
# 1. 설정 변수
# ----------------------------------------------------
CONFIG = {
    'cache_file': 'btc_usdt_1m_cache.csv',
    'seq_len': 60,                # 60분(1시간)의 과거 데이터를 입력으로 사용
    'train_ratio': 0.7,
    'val_ratio': 0.15,
    # test_ratio는 자동 계산 (1 - train - val = 0.15)
    'batch_size': 64,
    'epochs': 30,
    'learning_rate': 0.001,
    'device': 'cuda' if torch.cuda.is_available() else 'cpu',
    'model_save_path': 'trading_model.pth',
    'scaler_save_path': 'scaler_config.json'
}

# ----------------------------------------------------
# 2. 보조지표 계산 함수 (데이터 누수 방지 및 정상성 유지)
# ----------------------------------------------------
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig_line
    return macd_line, sig_line, hist

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

# ----------------------------------------------------
# 3. 데이터 로딩 및 피처 엔지니어링
# ----------------------------------------------------
def prepare_data(config):
    if not os.path.exists(config['cache_file']):
        raise FileNotFoundError(f"캐시 파일을 찾을 수 없습니다: {config['cache_file']}\n먼저 GUI 앱에서 1분봉 데이터를 다운로드하세요.")
        
    print(f"데이터 로딩 중: {config['cache_file']}")
    df = pd.read_csv(config['cache_file'])
    
    # 정렬 확인
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # 피처 엔지니어링 (스케일 불변 비율 위주로 구성)
    print("피처 계산 중...")
    df['close_prev'] = df['close'].shift(1)
    
    # 캔들 변화율 피처
    df['open_pct'] = (df['open'] / df['close_prev']) - 1.0
    df['high_pct'] = (df['high'] / df['close_prev']) - 1.0
    df['low_pct'] = (df['low'] / df['close_prev']) - 1.0
    df['close_pct'] = (df['close'] / df['close_prev']) - 1.0
    
    # 이동평균 대비 이격도
    for p in [20, 50, 100]:
        df[f'sma_{p}_ratio'] = (df['close'] / df['close'].rolling(p).mean()) - 1.0
        
    # RSI (scaled to [-0.5, 0.5])
    df['rsi_14'] = calculate_rsi(df['close'], 14) / 100.0 - 0.5
    
    # MACD 비율 (가격 단위로 스케일 조정)
    macd_val, macd_sig, macd_hist = calculate_macd(df['close'])
    df['macd_ratio'] = macd_val / df['close']
    df['macd_sig_ratio'] = macd_sig / df['close']
    df['macd_hist_ratio'] = macd_hist / df['close']
    
    # 변동성 비율 (가격 대비 ATR)
    df['atr_ratio'] = calculate_atr(df, 14) / df['close']
    
    # 거래량 비율 (20일 평균 거래량 대비 변화율)
    df['vol_ratio'] = (df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)) - 1.0
    
    # 기술지표 생성 중 발생한 결측치(NaN) 행 제거 (최대 rolling window 크기인 100개 가량 제거됨)
    df = df.dropna().reset_index(drop=True)
    
    feature_cols = [
        'open_pct', 'high_pct', 'low_pct', 'close_pct',
        'sma_20_ratio', 'sma_50_ratio', 'sma_100_ratio',
        'rsi_14', 'macd_ratio', 'macd_sig_ratio', 'macd_hist_ratio',
        'atr_ratio', 'vol_ratio'
    ]
    
    print(f"총 데이터 개수 (NaN 제거 후): {len(df)}")
    print(f"사용할 피처 개수: {len(feature_cols)} ({', '.join(feature_cols)})")
    
    return df, feature_cols

# ----------------------------------------------------
# 4. 시퀀스 데이터 생성 및 데이터 누수 방지 스케일링
# ----------------------------------------------------
class TradingDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.LongTensor(y)
        
    def __len__(self):
        return len(self.X)
        
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

def create_sequences_and_split(df, feature_cols, config):
    seq_len = config['seq_len']
    total_len = len(df)
    
    # Train / Val / Test 인덱스 계산 (시계열 분할 - 절대 셔플하면 안 됨)
    n_train = int(total_len * config['train_ratio'])
    n_val = int(total_len * config['val_ratio'])
    
    train_end = n_train
    val_end = n_train + n_val
    
    df_train = df.iloc[:train_end].copy()
    df_val = df.iloc[train_end:val_end].copy()
    df_test = df.iloc[val_end:].copy()
    
    print(f"시계열 분할 완료 -> Train: {len(df_train)}개, Val: {len(df_val)}개, Test: {len(df_test)}개")
    
    # StandardScaler 피팅 (Train 세트 정보로만 스케일러 생성하여 데이터 Leakage 방지)
    train_features = df_train[feature_cols].values
    mean = train_features.mean(axis=0)
    std = train_features.std(axis=0) + 1e-9  # 0 division 방지
    
    # 스케일러 파라미터 저장
    scaler_config = {
        'mean': mean.tolist(),
        'std': std.tolist(),
        'feature_cols': feature_cols
    }
    with open(config['scaler_save_path'], 'w', encoding='utf-8') as f:
        json.dump(scaler_config, f, indent=4, ensure_ascii=False)
    print(f"스케일러 파라미터 저장 완료: {config['scaler_save_path']}")
    
    # 스케일링 적용
    def scale_features(df_part):
        features = df_part[feature_cols].values
        scaled = (features - mean) / std
        return scaled
        
    scaled_train = scale_features(df_train)
    scaled_val = scale_features(df_val)
    scaled_test = scale_features(df_test)
    
    # 시퀀스 데이터화
    # ls_label[i]을 예측하기 위해 i-seq_len부터 i-1까지의 피처 시퀀스를 활용함 (Lookahead bias 없음)
    def to_sequences(scaled_data, raw_df):
        X, y = [], []
        for i in range(seq_len, len(scaled_data)):
            X.append(scaled_data[i - seq_len : i])
            # ls_label 값: -1, 0, 1 -> CrossEntropy용 인덱스: 0, 1, 2 로 변환
            lbl = int(raw_df.iloc[i]['ls_label'])
            X_y_mapped = lbl + 1  # -1->0, 0->1, 1->2
            y.append(X_y_mapped)
        return np.array(X), np.array(y)
        
    X_train, y_train = to_sequences(scaled_train, df_train)
    X_val, y_val = to_sequences(scaled_val, df_val)
    X_test, y_test = to_sequences(scaled_test, df_test)
    
    print(f"시퀀스 변환 완료:")
    print(f" - Train X: {X_train.shape}, y: {y_train.shape}")
    print(f" - Val X: {X_val.shape}, y: {y_val.shape}")
    print(f" - Test X: {X_test.shape}, y: {y_test.shape}")
    
    # 클래스 분포 및 가중치 계산 (CrossEntropy Loss용 클래스 비대칭 보정)
    class_counts = np.bincount(y_train)
    print(f"Train 클래스 별 데이터 개수: [Short(-1): {class_counts[0]}, Hold(0): {class_counts[1]}, Long(1): {class_counts[2]}]")
    
    # 역빈도로 클래스 가중치 계산
    class_weights = 1.0 / (class_counts + 1e-9)
    class_weights = class_weights / class_weights.sum() * 3.0
    print(f"보정 클래스 가중치: {class_weights.tolist()}")
    
    return (X_train, y_train, X_val, y_val, X_test, y_test, class_weights)

# ----------------------------------------------------
# 5. CNN-LSTM 하이브리드 모델 정의
# ----------------------------------------------------
class TradingCNNLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, num_classes=3):
        super(TradingCNNLSTM, self).__init__()
        
        # 1D CNN 레이어: 시퀀스의 국소적인 패턴(패턴 추세 변곡점 등) 추출
        # PyTorch Conv1d는 (batch, channel, seq_len)을 요구하므로 입력 차원 순서를 맞춰줌
        self.conv1 = nn.Conv1d(in_channels=input_dim, out_channels=32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(32)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2)
        
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(64)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2)
        
        # LSTM 레이어: CNN 출력을 받아 긴 호흡의 시계열적 종속 관계 분석
        # Conv 거친 후 Sequence length가 maxpool(2) 두 번에 의해 1/4 크기로 줄어듦 (config의 seq_len=60 -> 15로 축소됨)
        # LSTM input format: (batch, seq_len, input_size) -> batch_first=True
        self.lstm = nn.LSTM(input_size=64, hidden_size=hidden_dim, num_layers=2, 
                            batch_first=True, dropout=0.2)
        
        # 분류 헤드 (Fully-connected)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, num_classes)
        )
        
    def forward(self, x):
        # x shape: (batch_size, seq_len, num_features)
        # Conv1d를 위해 차원 변경 -> (batch_size, num_features, seq_len)
        x = x.transpose(1, 2)
        
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu1(x)
        x = self.pool1(x)
        
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu2(x)
        x = self.pool2(x)
        
        # LSTM 입력을 위해 차원 변경 -> (batch_size, reduced_seq_len, channels)
        x = x.transpose(1, 2)
        
        # LSTM 전파
        out, (hn, cn) = self.lstm(x)
        
        # 마지막 타임스텝의 출력 선택
        last_step_out = out[:, -1, :]
        
        # 선형 분류기
        logits = self.fc(last_step_out)
        return logits

# ----------------------------------------------------
# 6. 학습 및 평가 파이프라인
# ----------------------------------------------------
def train_model():
    # 데이터 준비
    df, feature_cols = prepare_data(CONFIG)
    X_train, y_train, X_val, y_val, X_test, y_test, class_weights = create_sequences_and_split(df, feature_cols, CONFIG)
    
    train_dataset = TradingDataset(X_train, y_train)
    val_dataset = TradingDataset(X_val, y_val)
    test_dataset = TradingDataset(X_test, y_test)
    
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'], shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=CONFIG['batch_size'], shuffle=False)
    
    # 모델 및 손실 함수/옵티마이저 빌드
    model = TradingCNNLSTM(input_dim=len(feature_cols), hidden_dim=64, num_classes=3).to(CONFIG['device'])
    
    weights_tensor = torch.FloatTensor(class_weights).to(CONFIG['device'])
    criterion = nn.CrossEntropyLoss(weight=weights_tensor)
    optimizer = optim.AdamW(model.parameters(), lr=CONFIG['learning_rate'], weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)
    
    print(f"학습 시작 디바이스: {CONFIG['device']}")
    
    best_val_loss = float('inf')
    
    for epoch in range(1, CONFIG['epochs'] + 1):
        # 훈련 단계
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0
        
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(CONFIG['device']), batch_y.to(CONFIG['device'])
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * batch_x.size(0)
            _, predicted = outputs.max(1)
            total += batch_y.size(0)
            correct += predicted.eq(batch_y).sum().item()
            
        epoch_train_loss = train_loss / total
        epoch_train_acc = correct / total
        
        # 검증 단계
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        all_preds = []
        all_targets = []
        
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(CONFIG['device']), batch_y.to(CONFIG['device'])
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                
                val_loss += loss.item() * batch_x.size(0)
                _, predicted = outputs.max(1)
                val_total += batch_y.size(0)
                val_correct += predicted.eq(batch_y).sum().item()
                
                all_preds.extend(predicted.cpu().numpy())
                all_targets.extend(batch_y.cpu().numpy())
                
        epoch_val_loss = val_loss / val_total
        epoch_val_acc = val_correct / val_total
        epoch_val_f1 = f1_score(all_targets, all_preds, average='macro')
        
        scheduler.step(epoch_val_loss)
        
        print(f"에폭 [{epoch}/{CONFIG['epochs']}] "
              f"Train Loss: {epoch_train_loss:.4f} | Train Acc: {epoch_train_acc*100:.2f}% | "
              f"Val Loss: {epoch_val_loss:.4f} | Val Acc: {epoch_val_acc*100:.2f}% | Val F1(Macro): {epoch_val_f1:.4f}")
              
        # 조기 종료 및 가장 좋은 모델 가중치 저장
        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            torch.save(model.state_dict(), CONFIG['model_save_path'])
            print(f" >> 검증 손실 개선으로 모델 가중치 저장 완료 ({CONFIG['model_save_path']})")
            
    # 최종 테스트 데이터셋 평가
    print("\n" + "="*50)
    print("최종 테스트 데이터셋 평가 시작")
    print("="*50)
    
    # 최고 품질 가중치 파일 로드
    model.load_state_dict(torch.load(CONFIG['model_save_path']))
    model.eval()
    
    test_preds = []
    test_targets = []
    
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            batch_x = batch_x.to(CONFIG['device'])
            outputs = model(batch_x)
            _, predicted = outputs.max(1)
            
            test_preds.extend(predicted.cpu().numpy())
            test_targets.extend(batch_y.numpy())
            
    # 평가 지표 요약 리포트 출력
    target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
    print(classification_report(test_targets, test_preds, target_names=target_names, zero_division=0))
    print(f"최종 테스트 매크로 F1 스코어: {f1_score(test_targets, test_preds, average='macro'):.4f}")

if __name__ == '__main__':
    train_model()
