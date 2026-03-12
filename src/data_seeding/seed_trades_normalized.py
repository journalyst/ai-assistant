"""Seed normalized multi-asset trade data from JSON into PostgreSQL."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

JSON_FILE_PATH = Path("sample_data/sample_options_trades_jan_feb_2026.json")


def _sync_serial_sequence(conn, table_name: str, pk_column: str):
    """Align serial sequence with current max PK to avoid duplicate key errors."""
    # Only known internal table names are expected here.
    seq_row = conn.execute(
        text("SELECT pg_get_serial_sequence(:table_name, :pk_column)"),
        {"table_name": table_name, "pk_column": pk_column},
    ).fetchone()
    if not seq_row or not seq_row[0]:
        return

    max_pk_sql = text(f"SELECT COALESCE(MAX({pk_column}), 0) + 1 FROM {table_name}")
    next_value = int(conn.execute(max_pk_sql).scalar() or 1)

    conn.execute(
        text("SELECT setval(:seq_name, :next_value, false)"),
        {"seq_name": seq_row[0], "next_value": next_value},
    )


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return None
    return None


def _to_date(value: Any):
    dt = _to_datetime(value)
    return dt.date() if dt else None


def _upsert_user(conn, user_id: str):
    conn.execute(
        text(
            """
            INSERT INTO users (user_id, username, email)
            VALUES (:user_id, :username, :email)
            ON CONFLICT (user_id) DO NOTHING
            """
        ),
        {
            "user_id": user_id,
            "username": f"user_{user_id[:8]}",
            "email": f"{user_id[:8]}@seed.local",
        },
    )


def _get_or_create_asset(conn, symbol: str) -> int:
    existing = conn.execute(
        text("SELECT asset_id FROM assets WHERE UPPER(symbol) = UPPER(:symbol) LIMIT 1"),
        {"symbol": symbol},
    ).fetchone()
    if existing:
        return int(existing[0])

    row = conn.execute(
        text(
            """
            INSERT INTO assets (symbol, name, asset_type)
            VALUES (:symbol, :name, :asset_type)
            RETURNING asset_id
            """
        ),
        {
            "symbol": symbol,
            "name": symbol,
            "asset_type": "option",
        },
    ).fetchone()
    return int(row[0])


def _get_or_create_strategy(conn, user_id: str, strategy_name: str | None) -> int | None:
    if not strategy_name:
        return None

    existing = conn.execute(
        text(
            """
            SELECT strategy_id
            FROM strategies
            WHERE user_id = :user_id AND LOWER(name) = LOWER(:name)
            LIMIT 1
            """
        ),
        {"user_id": user_id, "name": strategy_name},
    ).fetchone()
    if existing:
        return int(existing[0])

    row = conn.execute(
        text(
            """
            INSERT INTO strategies (user_id, name, description)
            VALUES (:user_id, :name, :description)
            RETURNING strategy_id
            """
        ),
        {
            "user_id": user_id,
            "name": strategy_name,
            "description": "Imported from normalized sample JSON",
        },
    ).fetchone()
    return int(row[0])


def _get_or_create_account(conn, record: dict[str, Any]) -> int | None:
    external_id = record.get("account_id")
    if not external_id:
        return None

    existing = conn.execute(
        text("SELECT account_id FROM accounts WHERE external_account_id = :external_id LIMIT 1"),
        {"external_id": external_id},
    ).fetchone()
    if existing:
        return int(existing[0])

    row = conn.execute(
        text(
            """
            INSERT INTO accounts (
                user_id,
                external_account_id,
                broker_id,
                exchange_id,
                account_type_id,
                account_external_id,
                account_label,
                created_at,
                updated_at
            )
            VALUES (
                :user_id,
                :external_account_id,
                :broker_id,
                :exchange_id,
                :account_type_id,
                :account_external_id,
                :account_label,
                :created_at,
                :updated_at
            )
            RETURNING account_id
            """
        ),
        {
            "user_id": record.get("user_id"),
            "external_account_id": external_id,
            "broker_id": _to_int(record.get("broker_id")),
            "exchange_id": _to_int(record.get("exchange_id")),
            "account_type_id": _to_int(record.get("account_type_id")),
            "account_external_id": record.get("account_external_id"),
            "account_label": record.get("account_external_id") or "Imported account",
            "created_at": _to_datetime(record.get("created_at")) or datetime.utcnow(),
            "updated_at": _to_datetime(record.get("updated_at")) or datetime.utcnow(),
        },
    ).fetchone()
    return int(row[0])


def _upsert_trade(conn, record: dict[str, Any], asset_id: int, strategy_id: int | None, account_id: int | None) -> int:
    entry_dt = _to_datetime(record.get("entry_time"))
    exit_dt = _to_datetime(record.get("exit_time"))
    created_at = _to_datetime(record.get("created_at")) or datetime.utcnow()
    updated_at = _to_datetime(record.get("updated_at")) or created_at

    row = conn.execute(
        text(
            """
            INSERT INTO trades (
                user_id,
                external_trade_id,
                asset_id,
                account_id,
                strategy_id,
                direction,
                trade_direction,
                order_type,
                status,
                market_type,
                import_type,
                quantity,
                entry_price,
                exit_price,
                total_fee,
                take_profit,
                stop_loss,
                trade_outcome,
                confidence,
                version,
                metadata,
                outcome,
                pnl,
                commission,
                trade_date,
                entry_time,
                entry_timestamp,
                exit_timestamp,
                created_at,
                updated_at
            )
            VALUES (
                :user_id,
                :external_trade_id,
                :asset_id,
                :account_id,
                :strategy_id,
                :direction,
                :trade_direction,
                :order_type,
                :status,
                :market_type,
                :import_type,
                :quantity,
                :entry_price,
                :exit_price,
                :total_fee,
                :take_profit,
                :stop_loss,
                :trade_outcome,
                :confidence,
                :version,
                CAST(:metadata AS JSONB),
                :outcome,
                :pnl,
                :commission,
                :trade_date,
                :entry_time,
                :entry_timestamp,
                :exit_timestamp,
                :created_at,
                :updated_at
            )
            ON CONFLICT (external_trade_id)
            DO UPDATE SET
                asset_id = EXCLUDED.asset_id,
                account_id = EXCLUDED.account_id,
                strategy_id = EXCLUDED.strategy_id,
                direction = EXCLUDED.direction,
                trade_direction = EXCLUDED.trade_direction,
                order_type = EXCLUDED.order_type,
                status = EXCLUDED.status,
                market_type = EXCLUDED.market_type,
                import_type = EXCLUDED.import_type,
                quantity = EXCLUDED.quantity,
                entry_price = EXCLUDED.entry_price,
                exit_price = EXCLUDED.exit_price,
                total_fee = EXCLUDED.total_fee,
                take_profit = EXCLUDED.take_profit,
                stop_loss = EXCLUDED.stop_loss,
                trade_outcome = EXCLUDED.trade_outcome,
                confidence = EXCLUDED.confidence,
                version = EXCLUDED.version,
                metadata = EXCLUDED.metadata,
                outcome = EXCLUDED.outcome,
                pnl = EXCLUDED.pnl,
                commission = EXCLUDED.commission,
                trade_date = EXCLUDED.trade_date,
                entry_time = EXCLUDED.entry_time,
                entry_timestamp = EXCLUDED.entry_timestamp,
                exit_timestamp = EXCLUDED.exit_timestamp,
                updated_at = EXCLUDED.updated_at
            RETURNING trade_id
            """
        ),
        {
            "user_id": record.get("user_id"),
            "external_trade_id": record.get("trade_id"),
            "asset_id": asset_id,
            "account_id": account_id,
            "strategy_id": strategy_id,
            "direction": (record.get("trade_direction") or "buy").lower(),
            "trade_direction": record.get("trade_direction"),
            "order_type": record.get("order_type"),
            "status": record.get("status"),
            "market_type": record.get("market_type") or "option",
            "import_type": record.get("import_type"),
            "quantity": _to_float(record.get("quantity")),
            "entry_price": _to_float(record.get("entry_price")),
            "exit_price": _to_float(record.get("exit_price")),
            "total_fee": _to_float(record.get("total_fee")),
            "take_profit": _to_float(record.get("take_profit")),
            "stop_loss": _to_float(record.get("stop_loss")),
            "trade_outcome": record.get("trade_outcome"),
            "confidence": record.get("confidence"),
            "version": record.get("version"),
            "metadata": json.dumps(record.get("metadata") or {}),
            "outcome": (record.get("trade_outcome") or "").lower() or None,
            "pnl": _to_float(record.get("profit")),
            "commission": _to_float(record.get("total_fee")),
            "trade_date": entry_dt.date() if entry_dt else _to_date(record.get("created_at")),
            "entry_time": entry_dt.strftime("%H:%M") if entry_dt else None,
            "entry_timestamp": entry_dt,
            "exit_timestamp": exit_dt,
            "created_at": created_at,
            "updated_at": updated_at,
        },
    ).fetchone()
    return int(row[0])


def _upsert_tags(conn, user_id: str, trade_id: int, tags: list[str]):
    for tag_name in tags:
        if not tag_name:
            continue

        tag_row = conn.execute(
            text(
                """
                WITH existing AS (
                    SELECT tag_id FROM tags WHERE user_id = :user_id AND LOWER(name) = LOWER(:name) LIMIT 1
                ),
                inserted AS (
                    INSERT INTO tags (user_id, name, color)
                    SELECT :user_id, :name, '#808080'
                    WHERE NOT EXISTS (SELECT 1 FROM existing)
                    RETURNING tag_id
                )
                SELECT tag_id FROM existing
                UNION ALL
                SELECT tag_id FROM inserted
                LIMIT 1
                """
            ),
            {"user_id": user_id, "name": tag_name},
        ).fetchone()

        if not tag_row:
            continue

        conn.execute(
            text(
                """
                INSERT INTO trade_tags (trade_id, tag_id)
                VALUES (:trade_id, :tag_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"trade_id": trade_id, "tag_id": int(tag_row[0])},
        )


def _insert_many_nested(conn, table_name: str, trade_id: int, records: list[dict[str, Any]], field_map: dict[str, str]):
    conn.execute(text(f"DELETE FROM {table_name} WHERE trade_id = :trade_id"), {"trade_id": trade_id})
    for item in records:
        data = {db_key: item.get(src_key) for src_key, db_key in field_map.items()}
        data["trade_id"] = trade_id
        if "created_at" in data:
            data["created_at"] = _to_datetime(data["created_at"]) or datetime.utcnow()
        if "updated_at" in data:
            data["updated_at"] = _to_datetime(data["updated_at"]) or datetime.utcnow()

        columns = ", ".join(data.keys())
        values = ", ".join([f":{k}" for k in data.keys()])
        conn.execute(text(f"INSERT INTO {table_name} ({columns}) VALUES ({values})"), data)


def _upsert_one_detail(conn, table_name: str, trade_id: int, item: dict[str, Any] | None, field_map: dict[str, str]):
    conn.execute(text(f"DELETE FROM {table_name} WHERE trade_id = :trade_id"), {"trade_id": trade_id})
    if not item:
        return

    data = {db_key: item.get(src_key) for src_key, db_key in field_map.items()}
    data["trade_id"] = trade_id
    numeric_fields = {
        "strike_price",
        "premium",
        "market_sentiment_idx",
        "funding_rate",
        "open_interest_change",
        "lot_size",
        "liquidation_price",
        "maintenance_margin",
        "phase_pnl",
        "daily_drawdown_limit",
        "overall_drawdown_limit",
        "profit_target",
        "consistency_rule_percent",
        "swap_long",
        "swap_short",
        "dxy_at_entry",
        "dxy_at_exit",
    }
    for field in numeric_fields:
        if field in data:
            data[field] = _to_float(data[field])

    for key in list(data.keys()):
        if key.endswith("_date"):
            data[key] = _to_date(data[key])

    if "created_at" in data:
        data["created_at"] = _to_datetime(data["created_at"]) or datetime.utcnow()
    if "updated_at" in data:
        data["updated_at"] = _to_datetime(data["updated_at"]) or datetime.utcnow()

    columns = ", ".join(data.keys())
    values = ", ".join([f":{k}" for k in data.keys()])
    conn.execute(text(f"INSERT INTO {table_name} ({columns}) VALUES ({values})"), data)


def seed_normalized_trades() -> bool:
    if not JSON_FILE_PATH.exists():
        logger.info("Normalized trade JSON not found, skipping: %s", JSON_FILE_PATH)
        return True

    with JSON_FILE_PATH.open("r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        logger.error("Expected list of trade records in %s", JSON_FILE_PATH)
        return False

    engine = create_engine(settings.postgres_rw_dsn, connect_args={"connect_timeout": 10})

    inserted = 0
    try:
        with engine.begin() as conn:
            _sync_serial_sequence(conn, "strategies", "strategy_id")
            _sync_serial_sequence(conn, "assets", "asset_id")
            _sync_serial_sequence(conn, "accounts", "account_id")
            _sync_serial_sequence(conn, "tags", "tag_id")
            _sync_serial_sequence(conn, "trades", "trade_id")

            for record in records:
                user_id = str(record.get("user_id") or "").strip()
                symbol = str(record.get("symbol") or "").strip()
                trade_external_id = str(record.get("trade_id") or "").strip()

                if not user_id or not symbol or not trade_external_id:
                    logger.warning("Skipping record with missing user_id/symbol/trade_id")
                    continue

                _upsert_user(conn, user_id)
                asset_id = _get_or_create_asset(conn, symbol)
                strategy_id = _get_or_create_strategy(conn, user_id, record.get("strategy_name"))
                account_id = _get_or_create_account(conn, record)
                trade_id = _upsert_trade(conn, record, asset_id, strategy_id, account_id)

                metadata = record.get("metadata") or {}
                tags = metadata.get("tags") or []
                if isinstance(tags, list):
                    _upsert_tags(conn, user_id, trade_id, [str(t) for t in tags])

                _insert_many_nested(
                    conn,
                    "trade_mistakes",
                    trade_id,
                    record.get("mistakes") or [],
                    {
                        "mistakes_id": "external_mistake_id",
                        "mistake_description": "mistake_description",
                        "mistake_emotional_state": "mistake_emotional_state",
                        "mistake_trigger_and_cause": "mistake_trigger_and_cause",
                        "mistake_risk_plan_violation": "mistake_risk_plan_violation",
                        "mistake_avoidable": "mistake_avoidable",
                        "mistake_reaction_type": "mistake_reaction_type",
                        "mistake_scenario_note": "mistake_scenario_note",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                ideas = record.get("idea") or []
                if isinstance(ideas, dict):
                    ideas = [ideas]
                _insert_many_nested(
                    conn,
                    "trade_ideas",
                    trade_id,
                    ideas,
                    {
                        "idea_id": "external_idea_id",
                        "idea_setup_type": "idea_setup_type",
                        "idea_reason_enter": "idea_reason_enter",
                        "idea_confluence_factors": "idea_confluence_factors",
                        "idea_primary_scenario": "idea_primary_scenario",
                        "idea_alternative_scenario": "idea_alternative_scenario",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _insert_many_nested(
                    conn,
                    "trade_learning_entries",
                    trade_id,
                    record.get("learning") or [],
                    {
                        "learning_id": "external_learning_id",
                        "learning_what_repeated": "learning_what_repeated",
                        "learning_is_recurring": "learning_is_recurring",
                        "learning_core": "learning_core",
                        "learning_expanded_reflection": "learning_expanded_reflection",
                        "learning_action_plan": "learning_action_plan",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_option_details",
                    trade_id,
                    record.get("option"),
                    {
                        "legs_count": "legs_count",
                        "option_type": "option_type",
                        "strike_price": "strike_price",
                        "expiry_date": "expiry_date",
                        "premium": "premium",
                        "exercise_type": "exercise_type",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_stock_details",
                    trade_id,
                    record.get("stock"),
                    {
                        "earnings_impact": "earnings_impact",
                        "earnings_event_date": "earnings_event_date",
                        "volume_profile_notes": "volume_profile_notes",
                        "sector": "sector",
                        "gap_analysis": "gap_analysis",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_crypto_details",
                    trade_id,
                    record.get("crypto"),
                    {
                        "wallet_name": "wallet_name",
                        "market_sentiment_idx": "market_sentiment_idx",
                        "funding_rate": "funding_rate",
                        "open_interest_change": "open_interest_change",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_future_details",
                    trade_id,
                    record.get("future"),
                    {
                        "contract_type": "contract_type",
                        "contract_expiry_date": "contract_expiry_date",
                        "days_to_expiry": "days_to_expiry",
                        "lot_size": "lot_size",
                        "liquidation_price": "liquidation_price",
                        "maintenance_margin": "maintenance_margin",
                        "margin_call_story": "margin_call_story",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_forex_details",
                    trade_id,
                    record.get("forex"),
                    {
                        "swap_long": "swap_long",
                        "swap_short": "swap_short",
                        "swap_decision": "swap_decision",
                        "news_event": "news_event",
                        "news_impact": "news_impact",
                        "news_description": "news_description",
                        "session_analysis": "session_analysis",
                        "correlation_miss": "correlation_miss",
                        "broker_spread_notes": "broker_spread_notes",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_prop_details",
                    trade_id,
                    record.get("prop"),
                    {
                        "prop_firm_id": "prop_firm_id",
                        "challenge_start_date": "challenge_start_date",
                        "phase_tracker": "phase_tracker",
                        "phase_progress": "phase_progress",
                        "phase_pnl": "phase_pnl",
                        "daily_drawdown_limit": "daily_drawdown_limit",
                        "overall_drawdown_limit": "overall_drawdown_limit",
                        "profit_target": "profit_target",
                        "consistency_rule_percent": "consistency_rule_percent",
                        "consistency_check": "consistency_check",
                        "what_kept_me_safe": "what_kept_me_safe",
                        "challenge_reset": "challenge_reset",
                        "prop_rule_conflict": "prop_rule_conflict",
                        "funding_status": "funding_status",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                _upsert_one_detail(
                    conn,
                    "trade_commodity_details",
                    trade_id,
                    record.get("commodity"),
                    {
                        "underlying_symbol": "underlying_symbol",
                        "inventory_impact": "inventory_impact",
                        "supply_chain": "supply_chain",
                        "fundamental_check": "fundamental_check",
                        "cot_positioning": "cot_positioning",
                        "cot_extreme": "cot_extreme",
                        "dxy_at_entry": "dxy_at_entry",
                        "dxy_at_exit": "dxy_at_exit",
                        "weather_impact": "weather_impact",
                        "geopolitical_event": "geopolitical_event",
                        "seasonal_pattern": "seasonal_pattern",
                        "version": "version",
                        "created_at": "created_at",
                        "updated_at": "updated_at",
                    },
                )

                inserted += 1

        logger.info("Normalized trade seeding complete. Records processed: %s", inserted)
        return True
    except Exception as exc:
        logger.exception("Normalized trade seeding failed: %s", exc)
        return False
    finally:
        engine.dispose()


def main():
    if seed_normalized_trades():
        print("\n✓ Normalized trades seeded successfully!")
    else:
        print("\n✗ Normalized trade seeding failed - check logs for details")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
