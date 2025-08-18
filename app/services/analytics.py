"""
Analytics service layer for Insightful-Orders.

Responsibilities:
    - Compute merchant-level KPIs from order data, optimized for API use.
    - Rolling AOV (Average Order Value): average order size within a given time window.
    - RFM scores: per-customer Recency, Frequency, Monetary segmentation with quintile scoring.
    - Monthly cohorts: retention analysis showing how customer groups (by first-order month)
      behave over time.

Usage:
    These functions are invoked by the analytics blueprint endpoints (/metrics/*).
    Each function accepts a SQLAlchemy session + merchant_id, and returns
    JSON-serializable dicts/lists ready for Marshmallow/Flask responses.

Design:
    - Pure service layer: no Flask request objects or blueprints here.
    - Uses SQLAlchemy queries with fallbacks to Python post-processing.
    - Private helpers (prefixed with _) provide reusable utility (e.g., quintile scoring).
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal
import math

from sqlalchemy import func, cast
from sqlalchemy.orm import Session
from sqlalchemy.types import Integer

from app.models import Order
from app.utils.helpers import parse_window_str


def _iso_z(dt: datetime) -> str:
    """Return an ISO-8601 string with trailing 'Z' and no microseconds."""
    return dt.replace(microsecond=0).isoformat() + "Z"

# ----------------------------------------------------------------------
# Rolling AOV
# ----------------------------------------------------------------------

def rolling_aov(
        session: Session,
        merchant_id: int,
        window: str = "30d",
        now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Compute Average Order Value over a rolling window for one merchant.

    Returns
    {
        "window": "30d",
        "from": "YYYY-MM-DDTHH:MM:SSZ",
        "to": "YYYY-MM-DDTHH:MM:SSZ",
        "orders": <int>,
        "aov": <float>
    }
    """
    # Resolve time bounds
    ref_now = now or datetime.utcnow()
    delta: timedelta = parse_window_str(window)
    start_dt = ref_now - delta

    # Aggregate in one round-trip
    count_q, avg_q = (
        session.query(
            func.count(Order.id),
            func.avg(Order.total_amount)
        )
        .filter(
            Order.merchant_id == merchant_id,
            Order.created_at >= start_dt,
            Order.created_at <= ref_now
        )
        .one()
    )

    orders_count = int(count_q or 0)
    # avg_q will be Decimal (or None); cast safely to float for JSON
    aov_value = float(avg_q) if avg_q is not None else 0.0

    return {
        "window": window,
        "from": _iso_z(start_dt),
        "to": _iso_z(ref_now),
        "orders": orders_count,
        "aov": round(aov_value, 2)
    }

# ----------------------------------------------------------------------
# RFM Scores
# ----------------------------------------------------------------------
def rfm_scores(
        session: Session,
        merchant_id: int,
        now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Compute RFM (Recency, Frequency, Monetary) metrics and scores per customer.

    - Recency: days since last order (smaller is better)
    - Frequency: # of orders (bigger is better)
    - Monetary: sum of total_amount (bigger is better)

    Returns a list of dicts:
    {
        "customer_id": int,
        "recency_days": int,
        "frequency": int,
        "monetary": float,
        "r": int, "f": int, "m": int,
        "rfm": "RFM"  # e.g., "455"
    }
    """
    ref_now = now or datetime.utcnow()

    # 1) Pull per-customer aggregates in one query
    rows = (
        session.query(
            Order.customer_id.label("customer_id"),
            func.max(Order.created_at).label("last_order_at"),
            func.count(Order.id).label("frequency"),
            func.coalesce(func.sum(Order.total_amount), 0).label("monetary")
        )
        .filter(Order.merchant_id == merchant_id)
        .group_by(Order.customer_id)
        .all()
    )

    # If no customers/orders, return empty list
    if not rows:
        return []
    
    # 2) Build raw metric vectors
    records = []
    recency_pairs = []    # (customer_id, recency_days)
    freq_pairs = []       # (customer_id, frequncy)
    mon_pairs = []        # (customer_id, monetary as float)

    for r in rows:
        last_at: Optional[datetime] = r.last_order_at
        recency_days = (ref_now - last_at).days if last_at else 10**9
        frequency = int(r.frequency or 0)

        # r.monetary may be Decimal; cast to float smoothly
        monetary_val = float(r.monetary) if isinstance(r.monetary, (int, float, Decimal)) else 0.0

        records.append(
            {
                "customer_id": int(r.customer_id),
                "recency_days": int(recency_days),
                "frequency": frequency,
                "monetary": round(monetary_val, 2)
            }
        )
        recency_pairs.append((int(r.customer_id), int(recency_days)))
        freq_pairs.append((int(r.customer_id), frequency))
        mon_pairs.append((int(r.customer_id), monetary_val))

    # 3) Compute quintile-based scores (1-5)
    r_scores = _score_by_quintiles(recency_pairs, smaller_is_better=True)
    f_scores = _score_by_quintiles(freq_pairs, smaller_is_better=False)
    m_scores = _score_by_quintiles(mon_pairs, smaller_is_better=False)

    # 4) Attach scores
    out = []
    for rec in records:
        cid = rec["customer_id"]
        r = r_scores.get(cid, 3)
        f = f_scores.get(cid, 3)
        m = m_scores.get(cid, 3)
        rec_out = {**rec, "r": r, "f": f, "m": m, "rfm": f"{r}{f}{m}"}
        out.append(rec_out)

    return out

# ----------------------------------------------------------------------
# Monthly Cohorts
# ----------------------------------------------------------------------
def monthly_cohorts(
        session: Session,
        merchant_id: int,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
) -> Dict[str, Any]:
    """Compute monthly cohort retention matrix for a merchant.

    Cohort definition:
        - A customer's cohort_month is the month of their FIRST ever order.

    Retention:
        - For each cohort_month, count DISTINCT customers who placed ≥ 1 order
          at month_offset m0 (cohort month), m1 (next month), m2, ...

    Args:
        session (Session): SQLAlchemy session.
        merchant_id (int): Merchant scope for the analysis.
        start (datetime | None): Optional lower bound (inclusive) for order_month.
        end (datetime | None): Optional upper bound (inclusive) for order_month.

    Returns:
        dict: {
            "start": "YYYY-MM" | None,
            "end": "YYYY-MM" | None,
            "cohorts": [
                {"cohort": "YYYY-MM", "m0": int, "m1": int, ...},
                ...
            ]
        }
    """
    def _month_floor(dt: datetime) -> datetime:
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Resolve month window
    start_floor = _month_floor(start) if start else None
    end_floor = _month_floor(end) if end else None

    # Get DB dialect
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"

    if dialect == "sqlite":
        # SQLite expressions
        cohort_month_expr_src = func.strftime("%Y-%m-01", func.min(Order.created_at))
        order_month_expr = func.strftime("%Y-%m-01", Order.created_at)
        ym_order = (
            cast(func.strftime("%Y", Order.created_at), Integer) * 12
            + cast(func.strftime("%m", Order.created_at), Integer)
        )
        ym_cohort_src = (
            cast(func.strftime("%Y", func.min(Order.created_at)), Integer) * 12
            + cast(func.strftime("%m", func.min(Order.created_at)), Integer)
        )
        start_comp = start_floor.strftime("%Y-%m-01") if start_floor else None
        end_comp = end_floor.strftime("%Y-%m-01") if end_floor else None
    else:
        # Postgres expressions
        cohort_month_expr_src = func.date_trunc("month", func.min(Order.created_at))
        order_month_expr = func.date_trunc("month", Order.created_at)
        ym_order = func.extract("year", order_month_expr) * 12 + func.extract("month", order_month_expr)
        ym_cohort_src = func.extract("year", cohort_month_expr_src) * 12 + func.extract("month", cohort_month_expr_src)
        start_comp = start_floor
        end_comp = end_floor

    # First orders per customer → cohort_month
    firsts_sq = (
        session.query(
            Order.customer_id.label("customer_id"),
            cohort_month_expr_src.label("cohort_month"),
            ym_cohort_src.label("ym_cohort"),
        )
        .filter(Order.merchant_id == merchant_id)
        .group_by(Order.customer_id)
        .subquery()
    )

    # Join orders back, compute month_offset, aggregate distinct customers
    month_offset_expr = cast(ym_order - firsts_sq.c.ym_cohort, Integer)
    q = (
        session.query(
            firsts_sq.c.cohort_month.label("cohort_month"),
            month_offset_expr.label("month_offset"),
            func.count(func.distinct(Order.customer_id)).label("active_customers"),
            order_month_expr.label("order_month"),
        )
        .join(firsts_sq, firsts_sq.c.customer_id == Order.customer_id)
        .filter(Order.merchant_id == merchant_id)
    )

    # Apply date filters
    if start_comp is not None:
        q = q.filter(order_month_expr >= start_comp)
    if end_comp is not None:
        q = q.filter(order_month_expr <= end_comp)

    q = (
        q.group_by(firsts_sq.c.cohort_month, month_offset_expr, order_month_expr)
         .order_by(firsts_sq.c.cohort_month.asc(), month_offset_expr.asc())
    )

    rows = q.all()

    # Handle empty result
    if not rows:
        return {
            "start": start_floor.strftime("%Y-%m") if start_floor else None,
            "end": end_floor.strftime("%Y-%m") if end_floor else None,
            "cohorts": [],
        }

    # Build retention matrix
    max_offset = 0
    min_seen_month = None
    max_seen_month = None
    matrix: Dict[str, Dict[int, int]] = {}

    for r in rows:
        if dialect == "sqlite":
            cohort_key = str(r.cohort_month)[0:7]
            ord_month_key = str(r.order_month)[0:7]
            ord_for_bounds = ord_month_key + "-01"
        else:
            cohort_key = r.cohort_month.strftime("%Y-%m")
            ord_for_bounds = r.order_month.strftime("%Y-%m-01")

        offset = int(r.month_offset or 0)
        count = int(r.active_customers or 0)

        if cohort_key not in matrix:
            matrix[cohort_key] = {}
        matrix[cohort_key][offset] = count

        if offset > max_offset:
            max_offset = offset
        if min_seen_month is None or ord_for_bounds < min_seen_month:
            min_seen_month = ord_for_bounds
        if max_seen_month is None or ord_for_bounds > max_seen_month:
            max_seen_month = ord_for_bounds

    # Final bounds
    start_out = (start_floor.strftime("%Y-%m") if start_floor else min_seen_month[0:7])
    end_out = (end_floor.strftime("%Y-%m") if end_floor else max_seen_month[0:7])

    # Zero-fill months for each cohort
    cohorts_out: List[Dict[str, Any]] = []
    for cohort_key in sorted(matrix.keys()):
        row = {"cohort": cohort_key}
        for k in range(0, max_offset + 1):
            row[f"m{k}"] = matrix[cohort_key].get(k, 0)
        cohorts_out.append(row)

    return {
        "start": start_out,
        "end": end_out,
        "cohorts": cohorts_out,
    }

#-----------------------------------------------------------------------
# Helpers (module-private)
# ----------------------------------------------------------------------
def _score_by_quintiles(pairs: List[tuple], smaller_is_better: bool) -> Dict[int, int]:
    """
    Given [(id, value), ...] return {id: score 1-5} based on 20/40/60/80th percentiles.

    - If smaller_is_better=True (recency), lower values get higher score
    - If all values are identical, everyone gets 3 (neutral).
    """
    if pairs is None or len(pairs) == 0: 
        return {}

    # Extract values
    values = [v for _, v in pairs]
    n = len(values)

    # All identical → neutral scores
    if all(v == values[0] for v in values):
        return {cid: 3 for cid, _ in pairs}

    # Compute thresholds on the raw values
    sorted_vals = sorted(values)
    def qidx(q: float) -> int:
        # nearest-upper index (like ceil) but clamped
        idx = max(0, min(n - 1, math.ceil(q * n) - 1))
        return idx

    t20 = sorted_vals[qidx(0.20)]
    t40 = sorted_vals[qidx(0.40)]
    t60 = sorted_vals[qidx(0.60)]
    t80 = sorted_vals[qidx(0.80)]

    scores: Dict[int, int] = {}

    for cid, v in pairs:
        if smaller_is_better:
            # lower value = better score
            if v <= t20:
                s = 5
            elif v <= t40:
                s = 4
            elif v <= t60:
                s = 3
            elif v <= t80:
                s = 2
            else:
                s = 1
        else:
            # higher value = better score
            if v <= t20:
                s = 1
            elif v <= t40:
                s = 2
            elif v <= t60:
                s = 3
            elif v <= t80:
                s = 4
            else:
                s = 5
        scores[cid] = s

    return scores