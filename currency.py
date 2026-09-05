import requests
import json
import time
import os

CACHE_FILE = "exchange_rates_cache.json"
CACHE_DURATION = 3600  # 1 hour in seconds


# --- Add this helper function ---
def get_currency_symbol(currency):
    """Return the symbol for a given currency code."""
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "NGN": "₦",
        "JPY": "¥",
        "BRL": "R$",
        "CAD": "C$",
        "AUD": "A$",
        "CHF": "Fr",
        "CNY": "¥",
        "INR": "₹",
    }
    return symbols.get(currency, "$")


# --- Existing functions ---


def get_exchange_rates(base_currency="USD"):
    """
    Fetch exchange rates with caching. Returns dict of {currency: rate}
    relative to base_currency.
    """
    # 1. Check cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if time.time() - data["timestamp"] < CACHE_DURATION:
                return data["rates"]

    # 2. Fetch from exchangerate-api.com (free, no API key)
    url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            rates = response.json()["rates"]
            # Save to cache
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": time.time(), "rates": rates}, f)
            return rates
        else:
            # Fallback to cached (even if expired)
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    return data["rates"]
            else:
                raise Exception(
                    f"API returned {response.status_code} and no cache available."
                )
    except Exception as e:
        # On any error, use cache if available
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                return data["rates"]
        else:
            raise e


def convert(amount, from_currency, to_currency, rates=None):
    """
    Convert an amount from one currency to another.
    If rates is None, fetches fresh rates.
    """
    if from_currency == to_currency:
        return amount
    if rates is None:
        rates = get_exchange_rates(from_currency)
    return amount * rates.get(to_currency, 1.0)


def get_snapshot_rate(base_currency, foreign_currency):
    """
    Fetch the current exchange rate to store as a snapshot.
    """
    if base_currency == foreign_currency:
        return 1.0
    rates = get_exchange_rates(base_currency)
    return rates.get(foreign_currency, 1.0)
