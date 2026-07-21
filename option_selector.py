"""
core/option_selector.py
Given a BUY/SELL signal and a live Dhan option chain, picks the best strike
using DTE + Delta + liquidity filters, flags high-gamma strikes, and computes
SL/TP on the option premium. Never places an order - recommendation only.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional


@dataclass
class StrikeRecommendation:
    expiry: str
    dte: int
    strike: float
    option_type: str
    security_id: int
    ltp: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float
    oi: int
    bid: float
    ask: float
    spread_pct: float
    sl_price: float
    tp_price: float
    gamma_warning: bool
    score: float

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        return d

    def as_alert_text(self) -> str:
        warn = " ⚠️ HIGH GAMMA - premium will swing fast" if self.gamma_warning else ""
        return (
            f"{self.option_type} {self.strike} | Expiry {self.expiry} (DTE {self.dte})\n"
            f"LTP: {self.ltp:.2f}  Delta: {self.delta:.3f}  Gamma: {self.gamma:.5f}  "
            f"Theta: {self.theta:.2f}  IV: {self.iv:.1f}%{warn}\n"
            f"OI: {self.oi:,}  Spread: {self.spread_pct:.2f}%\n"
            f"SL: {self.sl_price:.2f}  TP: {self.tp_price:.2f}"
        )


def _dte(expiry: str) -> int:
    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    return (exp_date - date.today()).days


def select_best_strike(signal: str, option_chain: dict, expiry: str, settings: dict) -> Optional[StrikeRecommendation]:
    dte = _dte(expiry)
    if not (settings["min_dte"] <= dte <= settings["max_dte"]):
        return None

    opt_key = "ce" if signal == "BUY" else "pe"
    candidates = []

    for strike_str, legs in option_chain.get("oc", {}).items():
        leg = legs.get(opt_key)
        if not leg:
            continue

        greeks = leg.get("greeks", {})
        delta = abs(greeks.get("delta", 0))
        gamma = greeks.get("gamma", 0)
        theta = greeks.get("theta", 0)
        vega = greeks.get("vega", 0)
        iv = leg.get("implied_volatility", 0)
        oi = leg.get("oi", 0)
        ltp = leg.get("last_price", 0)
        bid = leg.get("top_bid_price", 0)
        ask = leg.get("top_ask_price", 0)

        if not (settings["delta_min"] <= delta <= settings["delta_max"]):
            continue
        if oi < settings["min_oi"]:
            continue
        if ltp <= 0:
            continue

        spread_pct = ((ask - bid) / ltp) * 100 if ltp else 999
        if spread_pct > settings["max_bid_ask_spread_pct"]:
            continue

        delta_score = abs(delta - settings["preferred_delta"])
        dte_score = abs(dte - settings["preferred_dte"]) / max(settings["max_dte"], 1)
        score = delta_score + 0.3 * dte_score

        risk = ltp * (settings["sl_percent"] / 100)
        sl_price = round(ltp - risk, 2)
        tp_price = round(ltp + risk * settings["tp_r_multiple"], 2)

        candidates.append(StrikeRecommendation(
            expiry=expiry, dte=dte, strike=float(strike_str), option_type=opt_key.upper(),
            security_id=leg.get("security_id", 0), ltp=ltp, delta=delta, gamma=gamma,
            theta=theta, vega=vega, iv=iv, oi=oi, bid=bid, ask=ask, spread_pct=spread_pct,
            sl_price=sl_price, tp_price=tp_price,
            gamma_warning=gamma > settings["gamma_high_warning"], score=score,
        ))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c.score)
    return candidates[0]


def pick_expiry(expiry_list: list, settings: dict) -> Optional[str]:
    valid = [(e, _dte(e)) for e in expiry_list if settings["min_dte"] <= _dte(e) <= settings["max_dte"]]
    if not valid:
        return None
    valid.sort(key=lambda x: abs(x[1] - settings["preferred_dte"]))
    return valid[0][0]
