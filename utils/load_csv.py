import os
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

def load_csv_df(relative_path=""):
    abs_path = os.path.join(PROJECT_ROOT, relative_path.lstrip("./").replace("../", ""))

    try:
        if not os.path.exists(abs_path):
            print(f"File not found at: {abs_path}")
            return None
        return pd.read_csv(abs_path)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None
