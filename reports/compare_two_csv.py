import pandas as pd

# Load the CSV files
df1 = pd.read_csv('file1.csv')
df2 = pd.read_csv('file2.csv')

# Option A: Find rows in file1 that are NOT in file2
diff_rows = pd.concat([df1, df2]).drop_duplicates(keep=False)
print(diff_rows)

# Option B: Compare line-by-line (if both files have the same structure/order)
comparison = df1.compare(df2)
print(comparison)