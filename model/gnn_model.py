# %% [markdown]
# # Budowa i Trening Modelu GNN (Graph Neural Network)
# W przeciwieństwie do MLP, ta sieć uczy się bezpośrednio na strukturze grafowej molekuł (Atomy jako Węzły, Wiązania jako Krawędzie).

# %%
import torch
import torch.nn as nn
import torch.nn.functional as F
import polars as pl
import numpy as np
import matplotlib.pyplot as plt

from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
from torch_geometric.nn import GCNConv, global_mean_pool
from rdkit import Chem
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

print(f"PyTorch Geometric załadowany pomyślnie! Wersja: {torch.__version__}")

# %% [markdown]
# ### 1. Konwersja SMILES do Obiektów Graph (PyTorch Geometric `Data`)

# %%
def smiles_to_graph(smiles, target_val):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    
    # Cechy węzłów (Rejestrujemy 5 podstawowych atrybutów dla każdego atomu)
    atom_features = []
    for atom in mol.GetAtoms():
        features = [
            atom.GetAtomicNum(),          # Liczba atomowa (np. 6 dla Węgla)
            atom.GetDegree(),             # Liczba sąsiadów
            atom.GetFormalCharge(),       # Ładunek formalny
            atom.GetNumRadicalElectrons(),
            int(atom.GetIsAromatic())     # Czy atom należy do pierścienia aromatycznego (0 lub 1)
        ]
        atom_features.append(features)
        
    x = torch.tensor(atom_features, dtype=torch.float32)
    
    # Cechy krawędzi (Połączenia między atomami)
    edges = []
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        # Grafy molekularne traktujemy jako nieskierowane (wiązanie działa w obie strony)
        edges.append((i, j))
        edges.append((j, i))
        
    if len(edges) == 0:
        edge_index = torch.empty((2, 0), dtype=torch.long)
    else:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        
    # Nasz target
    y = torch.tensor([[target_val]], dtype=torch.float32)
    
    # Obiekt Data to standardowy "Tensor Grafowy" w PyG
    return Data(x=x, edge_index=edge_index, y=y)

# %% [markdown]
# ### 2. Wczytanie i Parsowanie Danych

# %%
df = pl.read_parquet("Chembl203_cleaned.parquet")

# Z powodu wielkości zbioru (10 tysięcy), jeśli masz słabszy komputer, mozesz uciąć ten zbiór na start do testów
# Np. df = df.head(3000)

print("Konwertuję łańcuchy SMILES na grafy... (to może zająć chwilę)")

graph_dataset = []
failed_mols = 0

for row in df.iter_rows(named=True):
    smiles = row["canonical_smiles"]
    pchembl = row["pchembl_value"]
    
    # Ignoruj puste wartości
    if smiles is None or pchembl is None:
        continue
        
    data_obj = smiles_to_graph(smiles, float(pchembl))
    if data_obj is not None:
        graph_dataset.append(data_obj)
    else:
        failed_mols += 1

print(f"Stworzono {len(graph_dataset)} pomyślnych grafów! Odrzucono {failed_mols} niemożliwych układów.")

# %% [markdown]
# ### 3. Random Split i Dataloadery 

# %%
# Dzielimy listę grafów
train_data, temp_data = train_test_split(graph_dataset, test_size=0.2, random_state=42)
val_data, test_data = train_test_split(temp_data, test_size=0.5, random_state=42)

print(f"Grafy T/V/T: {len(train_data)} / {len(val_data)} / {len(test_data)}")

# DataLoadery z PyTorch Geometric inteligentnie łączą grafy o różnej liczbie węzłów w Batch
train_loader = DataLoader(train_data, batch_size=64, shuffle=True)
val_loader = DataLoader(val_data, batch_size=64, shuffle=False)
test_loader = DataLoader(test_data, batch_size=64, shuffle=False)

# %% [markdown]
# ### 4. Architektura Sieci Konwolucyjnej na Grafach (GCN)

# %%
class GCNRegressor(nn.Module):
    def __init__(self, num_node_features=5, hidden_channels=64):
        super(GCNRegressor, self).__init__()
        # Trzy warstwy "rozmawiające" z sąsiadami (Message Passing)
        self.conv1 = GCNConv(num_node_features, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.conv3 = GCNConv(hidden_channels, hidden_channels)
        
        # Warstwy klasycznego perceptronu agregujące wnioski
        self.lin1 = nn.Linear(hidden_channels, 32)
        self.lin2 = nn.Linear(32, 1)

    def forward(self, x, edge_index, batch):
        # 1. Krok: Ekstrakcja cech grafowych
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.3, training=self.training)
        
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.3, training=self.training)
        
        x = self.conv3(x, edge_index)
        x = F.relu(x)
        
        # 2. Global Pooling: zlepia wszystkie węzły danego pojedyńczego grafu w JEDEN wektor ukryty (Readout)
        x = global_mean_pool(x, batch)
        
        # 3. Krok: Ostateczna predykcja pChEMBL z wyciągniętego wektora 
        x = self.lin1(x)
        x = F.relu(x)
        x = F.dropout(x, p=0.3, training=self.training)
        x = self.lin2(x)
        
        return x

# %% [markdown]
# ### 5. Pętla Treningowa i Wyniki

# %%
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = GCNRegressor().to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4) # L2 
criterion = nn.MSELoss()

def train_gnn():
    model.train()
    running_loss = 0.0
    for data in train_loader:
        data = data.to(device)
        optimizer.zero_grad()
        out = model(data.x, data.edge_index, data.batch)
        loss = criterion(out, data.y)
        loss.backward()
        optimizer.step()
        running_loss += loss.item() * data.num_graphs
    return running_loss / len(train_loader.dataset)

def test_gnn(loader):
    model.eval()
    running_loss = 0.0
    with torch.no_grad():
        for data in loader:
            data = data.to(device)
            out = model(data.x, data.edge_index, data.batch)
            loss = criterion(out, data.y)
            running_loss += loss.item() * data.num_graphs
    return running_loss / len(loader.dataset)

epochs = 60
train_h, val_h = [], []

print("Rozpoczęcie treningu modelu GNN...\n")
for epoch in range(1, epochs + 1):
    tr_loss = train_gnn()
    vl_loss = test_gnn(val_loader)
    train_h.append(tr_loss)
    val_h.append(vl_loss)
    
    if epoch % 5 == 0:
        print(f"Epoka: {epoch:02d}/{epochs} | Train MSE: {tr_loss:.4f} | Val MSE: {vl_loss:.4f}")

# %% [markdown]
# ### 6. Wykres oraz docelowe ustrzelenie ROC-AUC

# %%
plt.figure(figsize=(10, 5))
plt.plot(train_h, label="GCN Train MSE", color="blue")
plt.plot(val_h, label="GCN Val MSE", color="orange", linewidth=2)
plt.title("Trening Architektury Grafowej (GCN) na cząsteczkach EGFR")
plt.ylabel("MSE")
plt.xlabel("Epoka")
plt.legend()
plt.grid(True)
plt.show()

# Obliczenie AUC
model.eval()
all_true, all_pred = [], []

with torch.no_grad():
    for data in test_loader: # Tutaj celowo bierzemy zbiór prawdziwie ślepy (Test Set)
        data = data.to(device)
        out = model(data.x, data.edge_index, data.batch)
        
        all_pred.extend(out.detach().cpu().flatten().tolist())
        all_true.extend(data.y.cpu().flatten().tolist())

all_true = np.array(all_true)
all_pred = np.array(all_pred)

threshold = 6.0
binary_true = (all_true >= threshold).astype(int)

try:
    auc = roc_auc_score(binary_true, all_pred)
    print(f"\n[EWALUACJA OSTATECZNA] ROC-AUC na kompletnie ślepym zbiorze Testowym: {auc:.4f}")
except Exception as e:
    print("Błąd AUC - za mało danych w batchu testowym:", e)

# %%
