-- Journalyst AI Assistant - Test Seed Data
-- Based on trading_data_with_pnl.csv schema
-- Tables: users, assets, strategies, tags, trades, trade_tags

-- ============================================
-- DROP EXISTING TABLES (if any)
-- ============================================
DROP TABLE IF EXISTS trade_tags CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS strategies CASCADE;
DROP TABLE IF EXISTS assets CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ============================================
-- CREATE TABLES
-- ============================================

-- Users table
CREATE TABLE users (
    user_id VARCHAR(100) PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Assets table (tradeable instruments)
CREATE TABLE assets (
    asset_id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Strategies table
CREATE TABLE strategies (
    strategy_id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tags table
CREATE TABLE tags (
    tag_id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#808080',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trades table
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    strategy_id INTEGER REFERENCES strategies(strategy_id) ON DELETE SET NULL,
    direction TEXT NOT NULL,
    entry_type TEXT,
    session TEXT,
    timeframe TEXT,
    risk_percentage NUMERIC(5,2),
    risk_reward NUMERIC(5,2),
    outcome TEXT,
    pnl NUMERIC(14,2),
    pnl_percentage NUMERIC(7,4),
    commission NUMERIC(14,2) DEFAULT 0,
    has_news INTEGER DEFAULT 0,
    day_of_week TEXT,
    emotional_state TEXT,
    reason_to_enter TEXT,
    learning TEXT,
    trade_rating TEXT,
    trade_date DATE,
    entry_time TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trade-Tags junction table (many-to-many)
CREATE TABLE trade_tags (
    trade_id INTEGER NOT NULL REFERENCES trades(trade_id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (trade_id, tag_id)
);

-- ============================================
-- CREATE INDEXES
-- ============================================
CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_trades_asset_id ON trades(asset_id);
CREATE INDEX idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX idx_trades_trade_date ON trades(trade_date);
CREATE INDEX idx_trades_outcome ON trades(outcome);
CREATE INDEX idx_strategies_user_id ON strategies(user_id);
CREATE INDEX idx_tags_user_id ON tags(user_id);

-- ============================================
-- USERS TABLE
-- ============================================
INSERT INTO users (user_id, username, email, created_at) VALUES
('user_1', 'trader_mike', 'mike@example.com', '2023-06-15 10:00:00'),
('user_2', 'sarah_fx', 'sarah@example.com', '2023-08-20 14:30:00'),
('user_3', 'alex_trades', 'alex@example.com', '2023-09-01 09:00:00');

-- ============================================
-- ASSETS TABLE (Forex pairs and commodities)
-- ============================================
INSERT INTO assets (asset_id, symbol, name, asset_type, created_at) VALUES
(1, 'EUR/USD', 'Euro / US Dollar', 'forex', '2023-01-01 00:00:00'),
(2, 'GBP/USD', 'British Pound / US Dollar', 'forex', '2023-01-01 00:00:00'),
(3, 'XAU/USD', 'Gold / US Dollar', 'commodity', '2023-01-01 00:00:00'),
(4, 'USD/JPY', 'US Dollar / Japanese Yen', 'forex', '2023-01-01 00:00:00'),
(5, 'USD/CHF', 'US Dollar / Swiss Franc', 'forex', '2023-01-01 00:00:00'),
(6, 'USD/CAD', 'US Dollar / Canadian Dollar', 'forex', '2023-01-01 00:00:00'),
(7, 'NZD/USD', 'New Zealand Dollar / US Dollar', 'forex', '2023-01-01 00:00:00'),
(8, 'AUD/USD', 'Australian Dollar / US Dollar', 'forex', '2023-01-01 00:00:00'),
(9, 'AAPL', 'Apple Inc.', 'stock', '2023-01-01 00:00:00'),
(10, 'NVDA', 'NVIDIA Corporation', 'stock', '2023-01-01 00:00:00'),
(11, 'TSLA', 'Tesla Inc.', 'stock', '2023-01-01 00:00:00'),
(12, 'SPY', 'S&P 500 ETF', 'etf', '2023-01-01 00:00:00');

-- ============================================
-- STRATEGIES TABLE
-- ============================================
INSERT INTO strategies (strategy_id, user_id, name, description, created_at) VALUES
(1, 'user_1', 'breakout', 'Trading breakouts from consolidation zones with volume confirmation', '2023-06-15 10:00:00'),
(2, 'user_1', 'reversal', 'Counter-trend entries at key support/resistance levels', '2023-06-15 10:00:00'),
(3, 'user_1', 'trend-following', 'Following established trends using moving averages', '2023-06-15 10:00:00'),
(4, 'user_2', 'breakout', 'Range breakout strategy for volatile sessions', '2023-08-20 14:30:00'),
(5, 'user_2', 'reversal', 'Mean reversion at extreme levels', '2023-08-20 14:30:00'),
(6, 'user_2', 'trend-following', 'Riding momentum with trailing stops', '2023-08-20 14:30:00'),
(7, 'user_3', 'scalping', 'Quick in-and-out trades on small timeframes', '2023-09-01 09:00:00'),
(8, 'user_3', 'swing', 'Multi-day position trades', '2023-09-01 09:00:00');

-- ============================================
-- TAGS TABLE
-- ============================================
INSERT INTO tags (tag_id, user_id, name, color, created_at) VALUES
-- User 1 tags
(1, 'user_1', 'emotion', '#FF6B6B', '2023-06-15 10:00:00'),
(2, 'user_1', 'fomo', '#FFE66D', '2023-06-15 10:00:00'),
(3, 'user_1', 'discipline', '#4ECDC4', '2023-06-15 10:00:00'),
(4, 'user_1', 'plan', '#95E1D3', '2023-06-15 10:00:00'),
(5, 'user_1', 'mistake', '#F38181', '2023-06-15 10:00:00'),
(6, 'user_1', 'process', '#AA96DA', '2023-06-15 10:00:00'),
(7, 'user_1', 'news-trade', '#74B9FF', '2023-06-15 10:00:00'),
(8, 'user_1', 'patience', '#A8E6CF', '2023-06-15 10:00:00'),
(9, 'user_1', 'overtrading', '#FDCB6E', '2023-06-15 10:00:00'),
(10, 'user_1', 'revenge-trade', '#E17055', '2023-06-15 10:00:00'),
-- User 2 tags
(11, 'user_2', 'emotion', '#FF6B6B', '2023-08-20 14:30:00'),
(12, 'user_2', 'discipline', '#4ECDC4', '2023-08-20 14:30:00'),
(13, 'user_2', 'plan', '#95E1D3', '2023-08-20 14:30:00'),
(14, 'user_2', 'confidence', '#81ECEC', '2023-08-20 14:30:00'),
-- User 3 tags
(15, 'user_3', 'quick-win', '#00B894', '2023-09-01 09:00:00'),
(16, 'user_3', 'patience', '#A8E6CF', '2023-09-01 09:00:00'),
(17, 'user_3', 'mistake', '#F38181', '2023-09-01 09:00:00');

-- ============================================
-- TRADES TABLE - User 1 (50 trades)
-- ============================================
INSERT INTO trades (trade_id, user_id, asset_id, strategy_id, direction, entry_type, session, timeframe, risk_percentage, risk_reward, outcome, pnl, pnl_percentage, commission, has_news, day_of_week, emotional_state, reason_to_enter, learning, trade_rating, trade_date, entry_time, created_at) VALUES
-- January 2024 - User 1
(1, 'user_1', 1, 1, 'buy', 'manual', 'london', '15m', 1.0, 2.0, 'profit', 180.00, 1.80, 3.00, 0, 'Wednesday', 'focused;calm', 'price broke resistance zone after consolidation', 'trust confirmed setups', 'goodwin', '2024-01-03', '09:15', '2024-01-03 09:15:00'),
(2, 'user_1', 2, 2, 'sell', 'limit', 'new_york', '1h', 1.2, 1.5, 'loss', -120.00, -1.20, 3.00, 1, 'Wednesday', 'nervous;hesitant', 'expected reversal from upper channel boundary', 'avoid trading around major news', 'badloss', '2024-01-03', '14:32', '2024-01-03 14:32:00'),
(3, 'user_1', 3, 3, 'buy', 'manual', 'london', '30m', 0.8, 3.0, 'profit', 240.00, 2.40, 4.00, 0, 'Thursday', 'confident;composed', 'retest of upward trendline', 'scaling in works well', 'goodwin', '2024-01-04', '11:20', '2024-01-04 11:20:00'),
(4, 'user_1', 4, 1, 'sell', 'limit', 'asia', '15m', 1.0, 2.5, 'profit', 200.00, 2.00, 2.00, 0, 'Friday', 'attentive;curious', 'break below overnight support', 'be patient after entry', 'goodwin', '2024-01-05', '02:18', '2024-01-05 02:18:00'),
(5, 'user_1', 5, 2, 'buy', 'manual', 'new_york', '1h', 1.5, 1.8, 'loss', -150.00, -1.50, 3.00, 0, 'Friday', 'impatient;hopeful', 'countertrend entry too early', 'wait for confirmation', 'badloss', '2024-01-05', '15:40', '2024-01-05 15:40:00'),
(6, 'user_1', 6, 3, 'sell', 'limit', 'new_york', '4h', 1.0, 2.0, 'breakeven', 0.00, 0.00, 2.00, 1, 'Monday', 'tense;cautious', 'fake breakout before CPI data', 'avoid pre-news entries', 'goodloss', '2024-01-08', '13:05', '2024-01-08 13:05:00'),
(7, 'user_1', 7, 1, 'buy', 'manual', 'asia', '30m', 0.7, 2.2, 'profit', 140.00, 1.40, 2.00, 0, 'Tuesday', 'relaxed;alert', 'bullish engulfing after retracement', 'trust momentum confirmation', 'goodwin', '2024-01-09', '03:50', '2024-01-09 03:50:00'),
(8, 'user_1', 8, 2, 'buy', 'limit', 'asia', '1h', 1.0, 2.0, 'loss', -100.00, -1.00, 2.00, 0, 'Tuesday', 'frustrated;anxious', 'reversal failed due to strong USD tone', 'avoid fading strong trends', 'badloss', '2024-01-09', '05:35', '2024-01-09 05:35:00'),
(9, 'user_1', 1, 3, 'sell', 'manual', 'london', '15m', 1.3, 2.5, 'profit', 260.00, 2.60, 4.00, 1, 'Wednesday', 'confident;focused', 'continuation after ECB minutes', 'when direction confirmed hold longer', 'goodwin', '2024-01-10', '08:25', '2024-01-10 08:25:00'),
(10, 'user_1', 2, 2, 'buy', 'limit', 'new_york', '1h', 1.0, 2.0, 'breakeven', 0.00, 0.00, 3.00, 0, 'Wednesday', 'calm;accepting', 'demand zone tested twice', 'tighten stop on range days', 'goodloss', '2024-01-10', '17:45', '2024-01-10 17:45:00'),
(11, 'user_1', 3, 1, 'sell', 'manual', 'london', '15m', 1.0, 3.0, 'profit', 270.00, 2.70, 5.00, 0, 'Thursday', 'confident;energized', 'strong volume breakout below support', 'follow-through entries best', 'goodwin', '2024-01-11', '10:15', '2024-01-11 10:15:00'),
(12, 'user_1', 4, 3, 'buy', 'limit', 'asia', '30m', 0.8, 2.2, 'profit', 160.00, 1.60, 2.00, 0, 'Thursday', 'alert;confident', 'retest of 20MA on uptrend', 'trend logic works', 'goodwin', '2024-01-11', '23:10', '2024-01-11 23:10:00'),
(13, 'user_1', 5, 2, 'sell', 'manual', 'new_york', '1h', 1.0, 2.5, 'loss', -100.00, -1.00, 3.00, 1, 'Friday', 'nervous;regretful', 'entered before US retail news', 'time entries with data schedule', 'badloss', '2024-01-12', '16:00', '2024-01-12 16:00:00'),
(14, 'user_1', 6, 1, 'buy', 'limit', 'new_york', '4h', 1.0, 2.0, 'profit', 200.00, 2.00, 2.00, 0, 'Monday', 'focused;optimistic', 'strong close above previous high', 'breakout on higher TF reliable', 'goodwin', '2024-01-15', '13:35', '2024-01-15 13:35:00'),
(15, 'user_1', 7, 2, 'sell', 'manual', 'asia', '15m', 1.0, 1.8, 'loss', -100.00, -1.00, 2.00, 0, 'Tuesday', 'anxious;uncertain', 'reversal signal lacked confirmation', 'stick to rules', 'badloss', '2024-01-16', '04:00', '2024-01-16 04:00:00'),
(16, 'user_1', 8, 3, 'buy', 'manual', 'asia', '1h', 0.8, 2.2, 'profit', 180.00, 1.80, 2.00, 0, 'Tuesday', 'calm;focused', 'clean structure of higher lows', 'trust the system', 'goodwin', '2024-01-16', '06:45', '2024-01-16 06:45:00'),
(17, 'user_1', 1, 2, 'buy', 'limit', 'london', '30m', 1.2, 2.0, 'loss', -120.00, -1.20, 3.00, 1, 'Wednesday', 'impatient;stressed', 'entered pre-news fade again', 'avoid early FOMO entries', 'badloss', '2024-01-17', '09:12', '2024-01-17 09:12:00'),
(18, 'user_1', 2, 1, 'buy', 'manual', 'london', '15m', 1.0, 2.0, 'profit', 190.00, 1.90, 3.00, 0, 'Wednesday', 'confident;attentive', 'candle close above range', 'follow clear signals', 'goodwin', '2024-01-17', '12:50', '2024-01-17 12:50:00'),
(19, 'user_1', 3, 3, 'buy', 'limit', 'london', '1h', 1.0, 2.5, 'profit', 240.00, 2.40, 4.00, 0, 'Thursday', 'patient;calm', 'price respecting moving average', 'reward patience', 'goodwin', '2024-01-18', '11:05', '2024-01-18 11:05:00'),
(20, 'user_1', 4, 2, 'sell', 'manual', 'asia', '30m', 1.0, 1.5, 'loss', -100.00, -1.00, 2.00, 0, 'Thursday', 'doubtful;fatigued', 'entered against momentum', 'dont chase reversals', 'badloss', '2024-01-18', '22:25', '2024-01-18 22:25:00'),
(21, 'user_1', 5, 1, 'sell', 'limit', 'london', '15m', 0.8, 2.0, 'profit', 150.00, 1.50, 2.00, 0, 'Friday', 'focused;collected', 'strong momentum after SNB comment', 'context helps setup', 'goodwin', '2024-01-19', '10:55', '2024-01-19 10:55:00'),
(22, 'user_1', 6, 2, 'buy', 'manual', 'new_york', '4h', 1.0, 2.0, 'breakeven', 0.00, 0.00, 3.00, 1, 'Monday', 'composed;cautious', 'entered after oil data spike', 'filter news volatility', 'goodloss', '2024-01-22', '13:28', '2024-01-22 13:28:00'),
(23, 'user_1', 7, 1, 'sell', 'limit', 'asia', '30m', 0.8, 2.4, 'profit', 180.00, 1.80, 2.00, 0, 'Tuesday', 'focused;relieved', 'break of minor support', 'allow trades time to work', 'goodwin', '2024-01-23', '03:40', '2024-01-23 03:40:00'),
(24, 'user_1', 8, 3, 'buy', 'manual', 'asia', '15m', 1.0, 2.0, 'profit', 170.00, 1.70, 3.00, 0, 'Tuesday', 'calm;steady', 'trend continuation pattern formed', 'keep it simple', 'goodwin', '2024-01-23', '07:10', '2024-01-23 07:10:00'),
(25, 'user_1', 1, 1, 'sell', 'manual', 'london', '1h', 1.1, 2.3, 'profit', 200.00, 2.00, 3.00, 1, 'Wednesday', 'focused;alert', 'strong EUR news reaction', 'ride momentum post-news', 'goodwin', '2024-01-24', '09:25', '2024-01-24 09:25:00'),

-- February 2024 - User 1 (continued)
(26, 'user_1', 2, 2, 'buy', 'limit', 'new_york', '4h', 0.9, 1.8, 'loss', -90.00, -0.90, 3.00, 0, 'Wednesday', 'hopeful;tense', 'entered before confirmation candle', 'wait for confirmation', 'badloss', '2024-01-24', '16:40', '2024-01-24 16:40:00'),
(27, 'user_1', 3, 3, 'buy', 'manual', 'london', '15m', 1.0, 2.5, 'profit', 210.00, 2.10, 4.00, 0, 'Thursday', 'confident;grateful', 'strong push after retest', 'trust simple structure', 'goodwin', '2024-01-25', '10:45', '2024-01-25 10:45:00'),
(28, 'user_1', 4, 2, 'sell', 'limit', 'asia', '30m', 1.2, 2.0, 'loss', -120.00, -1.20, 2.00, 0, 'Thursday', 'overconfident;annoyed', 'tried to catch top', 'redundant entry on weak signal', 'badloss', '2024-01-25', '23:00', '2024-01-25 23:00:00'),
(29, 'user_1', 5, 1, 'buy', 'manual', 'new_york', '1h', 1.0, 2.0, 'profit', 200.00, 2.00, 3.00, 1, 'Friday', 'optimistic;energized', 'broke prior day high', 'momentum based setups work', 'goodwin', '2024-01-26', '14:50', '2024-01-26 14:50:00'),
(30, 'user_1', 6, 2, 'sell', 'limit', 'new_york', '4h', 1.0, 2.5, 'profit', 220.00, 2.20, 2.00, 0, 'Monday', 'content;steady', 'clear rejection at resistance', 'trust plan', 'goodwin', '2024-01-29', '13:10', '2024-01-29 13:10:00'),
(31, 'user_1', 7, 3, 'buy', 'manual', 'asia', '1h', 0.8, 2.0, 'profit', 150.00, 1.50, 2.00, 0, 'Tuesday', 'peaceful;alert', 'uptrend maintained structure', 'trend trades feel calm', 'goodwin', '2024-01-30', '04:05', '2024-01-30 04:05:00'),
(32, 'user_1', 8, 2, 'sell', 'manual', 'asia', '15m', 1.0, 1.7, 'loss', -100.00, -1.00, 3.00, 0, 'Tuesday', 'tense;frustrated', 'countertrend trade misjudged momentum', 'trade direction not emotion', 'badloss', '2024-01-30', '06:40', '2024-01-30 06:40:00'),
(33, 'user_1', 1, 2, 'buy', 'limit', 'london', '30m', 1.0, 2.0, 'profit', 180.00, 1.80, 3.00, 1, 'Wednesday', 'confident;composed', 'RB engulfing near demand', 'patience improved timing', 'goodwin', '2024-01-31', '09:10', '2024-01-31 09:10:00'),
(34, 'user_1', 2, 1, 'sell', 'manual', 'new_york', '1h', 1.0, 2.0, 'profit', 200.00, 2.00, 3.00, 0, 'Wednesday', 'focused;relieved', 'strong break below range', 'trust your backtest', 'goodwin', '2024-01-31', '15:20', '2024-01-31 15:20:00'),
(35, 'user_1', 3, 3, 'buy', 'manual', 'london', '15m', 1.0, 2.5, 'profit', 210.00, 2.10, 4.00, 0, 'Thursday', 'steady;pleased', 'strong volume continuation', 'ride the trend', 'goodwin', '2024-02-01', '10:40', '2024-02-01 10:40:00'),
(36, 'user_1', 4, 2, 'sell', 'limit', 'asia', '30m', 1.0, 1.8, 'loss', -100.00, -1.00, 2.00, 0, 'Thursday', 'tired;impatient', 'early short in bullish run', 'avoid forced trades', 'badloss', '2024-02-01', '22:30', '2024-02-01 22:30:00'),
(37, 'user_1', 5, 3, 'buy', 'manual', 'new_york', '4h', 0.8, 2.2, 'profit', 160.00, 1.60, 3.00, 0, 'Friday', 'calm;focused', 'steady USD buying flow', 'steady execution pays off', 'goodwin', '2024-02-02', '15:30', '2024-02-02 15:30:00'),
(38, 'user_1', 6, 1, 'sell', 'limit', 'new_york', '30m', 1.0, 2.5, 'profit', 200.00, 2.00, 3.00, 0, 'Monday', 'alert;confident', 'range break confirmed with volume', 'strong signal alignment', 'goodwin', '2024-02-05', '13:25', '2024-02-05 13:25:00'),
(39, 'user_1', 7, 2, 'buy', 'manual', 'asia', '30m', 1.2, 2.0, 'loss', -120.00, -1.20, 3.00, 1, 'Tuesday', 'nervous;unsure', 'entered pre-RBNZ statement', 'avoid early entries', 'badloss', '2024-02-06', '04:30', '2024-02-06 04:30:00'),
(40, 'user_1', 8, 3, 'buy', 'limit', 'asia', '15m', 1.0, 2.0, 'profit', 180.00, 1.80, 2.00, 0, 'Tuesday', 'calm;positive', 'simple HL pattern again reliable', 'trust process', 'goodwin', '2024-02-06', '07:05', '2024-02-06 07:05:00'),
(41, 'user_1', 1, 1, 'sell', 'manual', 'london', '1h', 1.0, 2.0, 'profit', 200.00, 2.00, 3.00, 0, 'Wednesday', 'focused;relaxed', 'strong bearish engulfing after rate talk', 'stay with momentum', 'goodwin', '2024-02-07', '09:50', '2024-02-07 09:50:00'),
(42, 'user_1', 2, 2, 'buy', 'limit', 'new_york', '30m', 1.0, 1.5, 'loss', -100.00, -1.00, 3.00, 0, 'Wednesday', 'bored;distracted', 'entered against momentum', 'beware overconfidence', 'badloss', '2024-02-07', '18:10', '2024-02-07 18:10:00'),
(43, 'user_1', 3, 3, 'buy', 'manual', 'london', '15m', 0.8, 2.4, 'profit', 160.00, 1.60, 4.00, 0, 'Thursday', 'alert;content', 'clean continuation of gold rally', 'follow structure', 'goodwin', '2024-02-08', '11:00', '2024-02-08 11:00:00'),
(44, 'user_1', 4, 2, 'sell', 'limit', 'asia', '1h', 1.0, 2.0, 'breakeven', 0.00, 0.00, 2.00, 0, 'Thursday', 'restless;reflective', 'range chop closed early', 'patience missing', 'goodloss', '2024-02-08', '22:50', '2024-02-08 22:50:00'),
(45, 'user_1', 5, 3, 'buy', 'manual', 'new_york', '30m', 1.0, 2.2, 'profit', 190.00, 1.90, 3.00, 0, 'Friday', 'calm;collected', 'strong bounce from support', 'confidence building', 'goodwin', '2024-02-09', '14:35', '2024-02-09 14:35:00'),
(46, 'user_1', 6, 2, 'sell', 'limit', 'new_york', '4h', 1.2, 1.8, 'loss', -120.00, -1.20, 3.00, 1, 'Monday', 'anxious;impatient', 'entered before inflation data', 'discipline over excitement', 'badloss', '2024-02-12', '13:20', '2024-02-12 13:20:00'),
(47, 'user_1', 7, 1, 'buy', 'manual', 'asia', '15m', 1.0, 2.0, 'profit', 180.00, 1.80, 2.00, 0, 'Tuesday', 'joyful;alert', 'session breakout caught perfectly', 'clear mind equals clear trade', 'goodwin', '2024-02-13', '04:20', '2024-02-13 04:20:00'),
(48, 'user_1', 8, 3, 'buy', 'limit', 'asia', '30m', 0.8, 2.5, 'profit', 160.00, 1.60, 2.00, 0, 'Tuesday', 'focused;peaceful', 'continued uptrend', 'consistency works', 'goodwin', '2024-02-13', '07:00', '2024-02-13 07:00:00'),
(49, 'user_1', 9, 1, 'buy', 'manual', 'new_york', '15m', 1.0, 2.0, 'loss', -100.00, -1.00, 2.50, 0, 'Wednesday', 'fomo;impulsive', 'chased AAPL breakout without confirmation', 'wait for pullback entry', 'badloss', '2024-02-14', '10:15', '2024-02-14 10:15:00'),
(50, 'user_1', 10, 3, 'buy', 'limit', 'new_york', '1h', 1.2, 2.5, 'profit', 300.00, 3.00, 3.00, 0, 'Thursday', 'patient;disciplined', 'NVDA pullback to 20EMA with volume', 'trust the process on quality setups', 'goodwin', '2024-02-15', '11:30', '2024-02-15 11:30:00'),
-- ============================================
-- TRADES TABLE - User 2 (25 trades - forex focus)
-- ============================================
(51, 'user_2', 1, 4, 'buy', 'manual', 'london', '15m', 1.0, 2.0, 'profit', 220.00, 2.20, 3.00, 0, 'Monday', 'focused;determined', 'clean breakout above consolidation', 'morning setups are best', 'goodwin', '2024-01-08', '08:45', '2024-01-08 08:45:00'),
(52, 'user_2', 3, 6, 'buy', 'limit', 'london', '1h', 0.8, 3.0, 'profit', 280.00, 2.80, 4.00, 0, 'Tuesday', 'patient;calm', 'gold respecting daily uptrend', 'higher timeframe alignment key', 'goodwin', '2024-01-09', '10:30', '2024-01-09 10:30:00'),
(53, 'user_2', 2, 5, 'sell', 'manual', 'new_york', '30m', 1.2, 1.8, 'loss', -140.00, -1.40, 3.00, 1, 'Wednesday', 'anxious;rushed', 'faded NFP move too early', 'respect news momentum', 'badloss', '2024-01-10', '14:45', '2024-01-10 14:45:00'),
(54, 'user_2', 4, 4, 'sell', 'limit', 'asia', '15m', 1.0, 2.2, 'profit', 190.00, 1.90, 2.00, 0, 'Thursday', 'alert;focused', 'yen strength showing clearly', 'follow the flow', 'goodwin', '2024-01-11', '03:20', '2024-01-11 03:20:00'),
(55, 'user_2', 5, 5, 'buy', 'manual', 'new_york', '1h', 1.0, 2.0, 'breakeven', 0.00, 0.00, 3.00, 0, 'Friday', 'cautious;uncertain', 'reversal attempt in ranging market', 'avoid choppy conditions', 'goodloss', '2024-01-12', '15:00', '2024-01-12 15:00:00'),
(56, 'user_2', 6, 6, 'sell', 'limit', 'new_york', '4h', 0.9, 2.5, 'profit', 225.00, 2.25, 2.00, 0, 'Monday', 'confident;steady', 'clear downtrend continuation', 'big picture clarity helps', 'goodwin', '2024-01-15', '14:00', '2024-01-15 14:00:00'),
(57, 'user_2', 7, 4, 'buy', 'manual', 'asia', '30m', 1.0, 2.0, 'profit', 180.00, 1.80, 2.00, 0, 'Tuesday', 'relaxed;attentive', 'asia session breakout pattern', 'simple patterns work', 'goodwin', '2024-01-16', '04:15', '2024-01-16 04:15:00'),
(58, 'user_2', 8, 5, 'sell', 'limit', 'asia', '15m', 1.1, 1.5, 'loss', -110.00, -1.10, 2.00, 0, 'Wednesday', 'frustrated;impatient', 'counter-trend in strong move', 'dont fight the trend', 'badloss', '2024-01-17', '05:30', '2024-01-17 05:30:00'),
(59, 'user_2', 1, 6, 'buy', 'manual', 'london', '1h', 1.0, 2.3, 'profit', 230.00, 2.30, 3.00, 0, 'Thursday', 'calm;methodical', 'trend following with MA support', 'patience on entries', 'goodwin', '2024-01-18', '09:45', '2024-01-18 09:45:00'),
(60, 'user_2', 3, 4, 'sell', 'limit', 'london', '15m', 0.8, 2.5, 'profit', 200.00, 2.00, 4.00, 0, 'Friday', 'focused;energetic', 'gold breakdown from range', 'breakdowns can be powerful', 'goodwin', '2024-01-19', '11:15', '2024-01-19 11:15:00'),
(61, 'user_2', 2, 5, 'buy', 'manual', 'new_york', '30m', 1.0, 2.0, 'loss', -100.00, -1.00, 3.00, 0, 'Monday', 'hopeful;uncertain', 'reversal at weak support', 'need stronger confluence', 'badloss', '2024-01-22', '16:00', '2024-01-22 16:00:00'),
(62, 'user_2', 4, 6, 'buy', 'limit', 'asia', '1h', 1.0, 2.2, 'profit', 200.00, 2.00, 2.00, 0, 'Tuesday', 'patient;disciplined', 'trend continuation on pullback', 'let trades come to you', 'goodwin', '2024-01-23', '02:45', '2024-01-23 02:45:00'),
(63, 'user_2', 5, 4, 'sell', 'manual', 'london', '15m', 1.2, 2.0, 'profit', 240.00, 2.40, 2.00, 0, 'Wednesday', 'confident;focused', 'strong breakout with volume', 'volume confirms direction', 'goodwin', '2024-01-24', '10:00', '2024-01-24 10:00:00'),
(64, 'user_2', 6, 5, 'buy', 'limit', 'new_york', '4h', 1.0, 1.8, 'loss', -100.00, -1.00, 3.00, 1, 'Thursday', 'nervous;tense', 'reversal before FOMC', 'avoid pre-FOMC trades', 'badloss', '2024-01-25', '13:30', '2024-01-25 13:30:00'),
(65, 'user_2', 7, 6, 'sell', 'manual', 'asia', '30m', 0.8, 2.5, 'profit', 200.00, 2.00, 2.00, 0, 'Friday', 'calm;accepting', 'continued weakness in NZD', 'follow weekly bias', 'goodwin', '2024-01-26', '03:50', '2024-01-26 03:50:00'),
(66, 'user_2', 8, 4, 'buy', 'limit', 'asia', '15m', 1.0, 2.0, 'profit', 180.00, 1.80, 2.00, 0, 'Monday', 'alert;optimistic', 'breakout from asia range', 'range breaks are reliable', 'goodwin', '2024-01-29', '04:30', '2024-01-29 04:30:00'),
(67, 'user_2', 1, 5, 'sell', 'manual', 'london', '1h', 1.1, 2.0, 'breakeven', 0.00, 0.00, 3.00, 0, 'Tuesday', 'cautious;reflective', 'reversal at resistance but weak', 'need cleaner setups', 'goodloss', '2024-01-30', '09:15', '2024-01-30 09:15:00'),
(68, 'user_2', 3, 6, 'buy', 'manual', 'london', '30m', 1.0, 2.5, 'profit', 250.00, 2.50, 4.00, 0, 'Wednesday', 'confident;grateful', 'gold trend continuation', 'trust the bigger picture', 'goodwin', '2024-01-31', '10:45', '2024-01-31 10:45:00'),
(69, 'user_2', 2, 4, 'buy', 'limit', 'new_york', '15m', 1.0, 2.0, 'profit', 200.00, 2.00, 3.00, 0, 'Thursday', 'focused;steady', 'clean breakout pattern', 'morning momentum is key', 'goodwin', '2024-02-01', '14:20', '2024-02-01 14:20:00'),
(70, 'user_2', 4, 5, 'sell', 'manual', 'asia', '1h', 1.2, 1.8, 'loss', -120.00, -1.20, 2.00, 0, 'Friday', 'impatient;frustrated', 'premature reversal entry', 'wait for confirmation always', 'badloss', '2024-02-02', '01:30', '2024-02-02 01:30:00'),
(71, 'user_2', 5, 6, 'buy', 'limit', 'london', '4h', 0.8, 3.0, 'profit', 240.00, 2.40, 3.00, 0, 'Monday', 'patient;calm', 'weekly trend alignment', 'bigger TF = bigger moves', 'goodwin', '2024-02-05', '08:00', '2024-02-05 08:00:00'),
(72, 'user_2', 6, 4, 'sell', 'manual', 'new_york', '30m', 1.0, 2.2, 'profit', 220.00, 2.20, 2.00, 0, 'Tuesday', 'focused;determined', 'clear range break', 'simple setups best setups', 'goodwin', '2024-02-06', '15:15', '2024-02-06 15:15:00'),
(73, 'user_2', 7, 5, 'buy', 'limit', 'asia', '15m', 1.0, 2.0, 'loss', -100.00, -1.00, 2.00, 1, 'Wednesday', 'nervous;hesitant', 'reversal before RBA', 'central bank risk is real', 'badloss', '2024-02-07', '03:00', '2024-02-07 03:00:00'),
(74, 'user_2', 8, 6, 'buy', 'manual', 'asia', '1h', 0.9, 2.5, 'profit', 225.00, 2.25, 2.00, 0, 'Thursday', 'calm;confident', 'AUD strength emerging', 'follow intermarket signals', 'goodwin', '2024-02-08', '05:45', '2024-02-08 05:45:00'),
(75, 'user_2', 1, 4, 'sell', 'limit', 'london', '30m', 1.0, 2.0, 'profit', 200.00, 2.00, 3.00, 0, 'Friday', 'steady;pleased', 'breakdown from consolidation', 'end of week setups can work', 'goodwin', '2024-02-09', '11:00', '2024-02-09 11:00:00');
-- ============================================
-- TRADES TABLE - User 3 (15 trades - scalping/swing focus)
-- ============================================
(76, 'user_3', 9, 7, 'buy', 'manual', 'new_york', '5m', 0.5, 1.5, 'profit', 75.00, 0.75, 1.50, 0, 'Monday', 'quick;alert', 'AAPL opening range breakout', 'first 30 min are golden', 'goodwin', '2024-01-15', '09:35', '2024-01-15 09:35:00'),
(77, 'user_3', 10, 7, 'sell', 'manual', 'new_york', '5m', 0.5, 1.5, 'profit', 80.00, 0.80, 1.50, 0, 'Monday', 'focused;fast', 'NVDA rejection at resistance', 'quick scalps need quick exits', 'goodwin', '2024-01-15', '10:45', '2024-01-15 10:45:00'),
(78, 'user_3', 11, 7, 'buy', 'manual', 'new_york', '5m', 0.6, 1.2, 'loss', -72.00, -0.72, 1.50, 0, 'Tuesday', 'greedy;overconfident', 'TSLA chop caught me', 'avoid mid-day scalps', 'badloss', '2024-01-16', '12:30', '2024-01-16 12:30:00'),
(79, 'user_3', 12, 8, 'buy', 'limit', 'new_york', '4h', 1.0, 3.0, 'profit', 300.00, 3.00, 2.00, 0, 'Wednesday', 'patient;calm', 'SPY weekly uptrend continuation', 'swing trades need patience', 'goodwin', '2024-01-17', '10:00', '2024-01-17 10:00:00'),
(80, 'user_3', 9, 7, 'sell', 'manual', 'new_york', '5m', 0.5, 1.5, 'profit', 70.00, 0.70, 1.50, 0, 'Thursday', 'quick;decisive', 'AAPL fade from high', 'morning fade works', 'goodwin', '2024-01-18', '09:50', '2024-01-18 09:50:00'),
(81, 'user_3', 10, 8, 'buy', 'limit', 'new_york', '1d', 1.5, 4.0, 'profit', 600.00, 6.00, 3.00, 0, 'Friday', 'confident;excited', 'NVDA earnings anticipation swing', 'position before catalysts', 'goodwin', '2024-01-19', '15:30', '2024-01-19 15:30:00'),
(82, 'user_3', 11, 7, 'buy', 'manual', 'new_york', '5m', 0.5, 1.3, 'loss', -65.00, -0.65, 1.50, 0, 'Monday', 'impulsive;rushed', 'TSLA false breakout', 'confirm before entry', 'badloss', '2024-01-22', '10:15', '2024-01-22 10:15:00'),
(83, 'user_3', 12, 7, 'sell', 'manual', 'new_york', '5m', 0.5, 1.5, 'profit', 75.00, 0.75, 1.50, 0, 'Tuesday', 'focused;sharp', 'SPY opening fade', 'gap fills are reliable', 'goodwin', '2024-01-23', '09:40', '2024-01-23 09:40:00'),
(84, 'user_3', 9, 8, 'sell', 'limit', 'new_york', '4h', 1.0, 2.5, 'loss', -100.00, -1.00, 2.00, 1, 'Wednesday', 'nervous;uncertain', 'AAPL swing short before earnings', 'dont hold through earnings', 'badloss', '2024-01-24', '14:00', '2024-01-24 14:00:00'),
(85, 'user_3', 10, 7, 'buy', 'manual', 'new_york', '5m', 0.5, 1.5, 'profit', 85.00, 0.85, 1.50, 0, 'Thursday', 'excited;alert', 'NVDA momentum continuation', 'ride the wave', 'goodwin', '2024-01-25', '10:00', '2024-01-25 10:00:00'),
(86, 'user_3', 11, 8, 'buy', 'limit', 'new_york', '1d', 1.2, 3.0, 'profit', 360.00, 3.60, 2.50, 0, 'Friday', 'patient;strategic', 'TSLA weekly support bounce', 'swing lows are entries', 'goodwin', '2024-01-26', '11:00', '2024-01-26 11:00:00'),
(87, 'user_3', 12, 7, 'buy', 'manual', 'new_york', '5m', 0.5, 1.4, 'profit', 70.00, 0.70, 1.50, 0, 'Monday', 'quick;focused', 'SPY VWAP reclaim', 'VWAP is key level', 'goodwin', '2024-01-29', '10:20', '2024-01-29 10:20:00'),
(88, 'user_3', 9, 7, 'sell', 'manual', 'new_york', '5m', 0.5, 1.5, 'breakeven', 0.00, 0.00, 1.50, 0, 'Tuesday', 'cautious;flat', 'AAPL chop zone', 'recognize chop early', 'goodloss', '2024-01-30', '11:30', '2024-01-30 11:30:00'),
(89, 'user_3', 10, 8, 'sell', 'limit', 'new_york', '4h', 1.0, 2.5, 'profit', 250.00, 2.50, 2.00, 0, 'Wednesday', 'calm;analytical', 'NVDA swing from resistance', 'resistance is resistance', 'goodwin', '2024-01-31', '10:30', '2024-01-31 10:30:00'),
(90, 'user_3', 11, 7, 'buy', 'manual', 'new_york', '5m', 0.5, 1.5, 'profit', 75.00, 0.75, 1.50, 0, 'Thursday', 'alert;quick', 'TSLA opening drive', 'first move is often right', 'goodwin', '2024-02-01', '09:35', '2024-02-01 09:35:00');

-- ============================================
-- TRADE_TAGS (linking trades to tags)
-- ============================================
-- User 1 trade tags
INSERT INTO trade_tags (trade_id, tag_id) VALUES
-- Trade 1: discipline, plan
(1, 3), (1, 4),
-- Trade 2: emotion, news-trade
(2, 1), (2, 7),
-- Trade 3: discipline, patience
(3, 3), (3, 8),
-- Trade 4: patience, discipline
(4, 8), (4, 3),
-- Trade 5: mistake, fomo
(5, 5), (5, 2),
-- Trade 6: news-trade, discipline
(6, 7), (6, 3),
-- Trade 7: discipline, process
(7, 3), (7, 6),
-- Trade 8: emotion, mistake
(8, 1), (8, 5),
-- Trade 9: news-trade, discipline
(9, 7), (9, 3),
-- Trade 10: patience, process
(10, 8), (10, 6),
-- Trade 11: discipline, plan
(11, 3), (11, 4),
-- Trade 12: discipline, process
(12, 3), (12, 6),
-- Trade 13: news-trade, mistake
(13, 7), (13, 5),
-- Trade 14: discipline, plan
(14, 3), (14, 4),
-- Trade 15: mistake, emotion
(15, 5), (15, 1),
-- Trade 16: discipline, process
(16, 3), (16, 6),
-- Trade 17: fomo, news-trade, mistake
(17, 2), (17, 7), (17, 5),
-- Trade 18: discipline, plan
(18, 3), (18, 4),
-- Trade 19: patience, discipline
(19, 8), (19, 3),
-- Trade 20: mistake, emotion
(20, 5), (20, 1),
-- Trade 21: discipline, process
(21, 3), (21, 6),
-- Trade 22: news-trade, discipline
(22, 7), (22, 3),
-- Trade 23: patience, discipline
(23, 8), (23, 3),
-- Trade 24: process, discipline
(24, 6), (24, 3),
-- Trade 25: news-trade, discipline
(25, 7), (25, 3),
-- Trade 26: mistake, emotion
(26, 5), (26, 1),
-- Trade 27: discipline, patience
(27, 3), (27, 8),
-- Trade 28: overtrading, mistake
(28, 9), (28, 5),
-- Trade 29: discipline, news-trade
(29, 3), (29, 7),
-- Trade 30: discipline, plan
(30, 3), (30, 4),
-- Trade 31: patience, process
(31, 8), (31, 6),
-- Trade 32: emotion, revenge-trade
(32, 1), (32, 10),
-- Trade 33: patience, discipline
(33, 8), (33, 3),
-- Trade 34: discipline, plan
(34, 3), (34, 4),
-- Trade 35: discipline, process
(35, 3), (35, 6),
-- Trade 36: mistake, emotion
(36, 5), (36, 1),
-- Trade 37: discipline, patience
(37, 3), (37, 8),
-- Trade 38: discipline, plan
(38, 3), (38, 4),
-- Trade 39: news-trade, mistake
(39, 7), (39, 5),
-- Trade 40: process, discipline
(40, 6), (40, 3),
-- Trade 41: discipline, plan
(41, 3), (41, 4),
-- Trade 42: overtrading, mistake
(42, 9), (42, 5),
-- Trade 43: process, discipline
(43, 6), (43, 3),
-- Trade 44: patience
(44, 8),
-- Trade 45: discipline, process
(45, 3), (45, 6),
-- Trade 46: news-trade, fomo
(46, 7), (46, 2),
-- Trade 47: discipline, plan
(47, 3), (47, 4),
-- Trade 48: process, discipline
(48, 6), (48, 3),
-- Trade 49: fomo, mistake
(49, 2), (49, 5),
-- Trade 50: discipline, patience, plan
(50, 3), (50, 8), (50, 4),

-- User 2 trade tags
(51, 12), (51, 13),
(52, 12), (52, 14),
(53, 11), (53, 12),
(54, 12), (54, 13),
(55, 12),
(56, 14), (56, 12),
(57, 12), (57, 13),
(58, 11),
(59, 12), (59, 14),
(60, 12), (60, 13),
(61, 11),
(62, 12), (62, 14),
(63, 14), (63, 12),
(64, 11),
(65, 12), (65, 13),
(66, 12), (66, 13),
(67, 12),
(68, 14), (68, 12),
(69, 12), (69, 13),
(70, 11),
(71, 12), (71, 14),
(72, 12), (72, 13),
(73, 11),
(74, 14), (74, 12),
(75, 12), (75, 13),

-- User 3 trade tags
(76, 15), (76, 16),
(77, 15),
(78, 17),
(79, 16),
(80, 15),
(81, 16),
(82, 17),
(83, 15),
(84, 17),
(85, 15),
(86, 16),
(87, 15),
(88, 16),
(89, 16),
(90, 15);
