"""
Хэрэглээний үнийн индекс (CPI) тооцоолол — 2023=100
Монгол Улсын ҮСХ-ийн аргачлалд суурилсан (Laspeyres, COICOP, chain elementary).
"""

from .engine import CPICalculator
from .loader import load_workbook_data

__version__ = "1.0.0"
__all__ = ["CPICalculator", "load_workbook_data"]
