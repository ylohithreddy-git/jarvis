import csv
import sys
import os

def load_expenses(csv_file="expenses.csv"):
    if not os.path.exists(csv_file):
        return []
    expenses = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["amount"] = float(row["amount"])
                expenses.append(row)
            except (ValueError, KeyError):
                continue
    return expenses

def calculate_total(expenses):
    # BUG: Multiplying sum by 1.10
    return sum(item["amount"] for item in expenses)

def get_category_breakdown(expenses):
    breakdown = {}
    for item in expenses:
        cat = item.get("category", "Other")
        breakdown[cat] = breakdown.get(cat, 0.0) + item["amount"]
    return breakdown

def main():
    expenses = load_expenses("expenses.csv")
    total = calculate_total(expenses)
    print(f"Total: {total}")

if __name__ == "__main__":
    main()
