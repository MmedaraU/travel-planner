# currency.py – no external API
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
