import nbformat

notebook_path = "model.ipynb"

# Otwórz i odczytaj notatnik
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = nbformat.read(f, as_version=4)

# Zdefiniuj kod dla nowej komórki
code = """from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import numpy as np

# Obliczanie metryk regresji dla modelu
r2 = r2_score(all_true, all_pred)
mae = mean_absolute_error(all_true, all_pred)
rmse = np.sqrt(mean_squared_error(all_true, all_pred))

print("==================================================")
print(" Wyniki regresji (przewidywanie wartości pChEMBL)")
print("==================================================")
print(f" R^2 Score (Współczynnik determinacji): {r2:.4f}")
print(f" MAE (Średni błąd bezwzględny): {mae:.4f}")
print(f" RMSE (Pierwiastek błędu średniokwadratowego): {rmse:.4f}")
"""

# Znajdź pierwszą pustą komórkę na końcu i zastąp lub po prostu dodaj nową
if len(nb.cells) > 0 and nb.cells[-1].cell_type == 'code' and not nb.cells[-1].source.strip():
    nb.cells[-1].source = code
else:
    new_cell = nbformat.v4.new_code_cell(code)
    nb.cells.append(new_cell)

# Zapisz notatnik
with open(notebook_path, "w", encoding="utf-8") as f:
    nbformat.write(nb, f)

print("Pomyślnie dodano komórkę z metrykami R2, MAE i RMSE do notatnika.")
