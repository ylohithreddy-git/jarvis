import unittest
import os
import sys

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import load_expenses, calculate_total, get_category_breakdown

class TestExpenseTracker(unittest.TestCase):
    def setUp(self):
        self.csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expenses.csv")

    def test_load_expenses(self):
        expenses = load_expenses(self.csv_path)
        self.assertEqual(len(expenses), 5)
        self.assertEqual(expenses[0]["category"], "Groceries")

    def test_calculate_total(self):
        expenses = load_expenses(self.csv_path)
        total = calculate_total(expenses)
        # 45.50 + 120.00 + 15.00 + 30.25 + 54.75 = 265.50
        self.assertAlmostEqual(total, 265.50, places=2)

    def test_category_breakdown(self):
        expenses = load_expenses(self.csv_path)
        breakdown = get_category_breakdown(expenses)
        self.assertIn("Utilities", breakdown)
        self.assertEqual(breakdown["Utilities"], 120.00)

if __name__ == "__main__":
    unittest.main()
