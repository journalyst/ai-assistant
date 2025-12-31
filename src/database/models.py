from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime, Text, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Association table for trade-tag many-to-many relationship
trade_tags = Table(
    'trade_tags',
    Base.metadata,
    Column('trade_id', Integer, ForeignKey('trades.trade_id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.tag_id'), primary_key=True)
)


class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(String(100), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False)


class Assets(Base):
    __tablename__ = 'assets'
    
    asset_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    asset_type = Column(String(50), nullable=False)  # forex, crypto, stock, commodity
    created_at = Column(DateTime, nullable=False)


class Strategy(Base):
    __tablename__ = 'strategies'

    strategy_id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.user_id'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class Tag(Base):
    __tablename__ = 'tags'

    tag_id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.user_id'), nullable=False)
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=True)  # hex color code
    created_at = Column(DateTime, nullable=False)


class Trade(Base):
    __tablename__ = 'trades'

    trade_id = Column(Integer, primary_key=True)
    user_id = Column(String(100), ForeignKey('users.user_id'), nullable=False)
    asset_id = Column(Integer, ForeignKey('assets.asset_id'), nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.strategy_id'), nullable=False)
    
    # Trade details
    direction = Column(String(10), nullable=False)  # buy, sell
    entry_type = Column(String(20), nullable=False)  # manual, limit, stop
    session = Column(String(20), nullable=False)  # london, new_york, asia
    timeframe = Column(String(10), nullable=False)  # 15m, 30m, 1h, 4h
    
    # Risk management
    risk_percentage = Column(Numeric(precision=5, scale=2), nullable=False)
    risk_reward = Column(Numeric(precision=5, scale=2), nullable=False)
    
    # Outcome
    outcome = Column(String(20), nullable=False)  # profit, loss, breakeven
    pnl = Column(Numeric(precision=12, scale=2), nullable=False)
    pnl_percentage = Column(Numeric(precision=6, scale=2), nullable=False)
    commission = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Context
    has_news = Column(Integer, default=0)  # 0 or 1 for boolean
    day_of_week = Column(String(15), nullable=False)
    emotional_state = Column(String(100), nullable=True)
    
    # Notes and learnings
    reason_to_enter = Column(Text, nullable=True)
    learning = Column(Text, nullable=True)
    trade_rating = Column(String(20), nullable=True)  # goodwin, badloss, goodloss
    
    # Timestamps
    trade_date = Column(DateTime, nullable=False)
    entry_time = Column(String(10), nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    tags = relationship("Tag", secondary=trade_tags, backref="trades")