#!/usr/bin/env python
# coding: utf-8

# In[31]:


#import torch
import sys
sys.path.append('..')

import numpy as np
import polars as pl
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem
from utils.utils import get_data_from_parquet, save_data_to_parquet

def smiles_to_fp(smiles, n_bits=2048):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        # Generowanie Morgan Fingerprint (promień 2 = ECFP4)
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=n_bits)
        return np.array(fp)
    return None


# # Importujemy dane

# In[ ]:


df = get_data_from_parquet("../Chembl203_with_molecule_and_activity.parquet")


# In[27]:


'''
df = df.with_columns([
    pl.col("canonical_smiles").map_elements(smiles_to_fp, return_dtype=pl.List(pl.Int64)).alias("fingerprint")
]).drop_nulls(subset=["fingerprint"])

df = df.with_columns(
    pl.col("pchembl_value").cast(pl.Int64, strict=False)
)
'''



# Konwersja do NumPy (X to macierz [N, 2048], y to [N, 1])
X = np.array(df["fingerprint"].to_list(), dtype=np.float32)
y = df["pchembl_value"].to_numpy().astype(np.float32).reshape(-1, 1)


# In[35]:


save_data_to_parquet(df, file_path="../Chembl203_with_molecule_and_activity.parquet")


# In[ ]:





# In[29]:


df.head()


# In[12]:


from rdkit.Chem.Scaffolds import MurckoScaffold

def get_scaffold(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    return None

# 1. Dodajemy kolumnę ze scaffoldem
df = df.with_columns([
    pl.col("canonical_smiles").map_elements(get_scaffold, return_dtype=pl.Utf8).alias("scaffold")
])

# 2. Pobieramy unikalne scaffoldy i mieszamy je
unique_scaffolds = df["scaffold"].unique().sample(fraction=1.0, shuffle=True)

# 3. Podział unikalnych scaffoldów (80/10/10)
n_scaffolds = len(unique_scaffolds)
train_scaffolds = unique_scaffolds[:int(0.8 * n_scaffolds)]
val_scaffolds = unique_scaffolds[int(0.8 * n_scaffolds):int(0.9 * n_scaffolds)]
test_scaffolds = unique_scaffolds[int(0.9 * n_scaffolds):]

# 4. Filtrowanie głównego DataFrame
train_df = df.filter(pl.col("scaffold").is_in(train_scaffolds))
val_df = df.filter(pl.col("scaffold").is_in(val_scaffolds))
test_df = df.filter(pl.col("scaffold").is_in(test_scaffolds))


# In[14]:


import torch
import torch.nn as nn

class ChemMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(2048, 512),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(128, 1) # Regresja pIC50
        )
        
        # Inicjalizacja wag (He/Kaiming)
        for m in self.model:
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        return self.model(x)

# Hiperparametry
model = ChemMLP()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
criterion = nn.MSELoss()


# In[21]:


# Sprawdź ile NaN/null jest w pchembl_value
print("Nulle w train_df:", train_df["pchembl_value"].null_count())
print("Typ kolumny:", train_df["pchembl_value"].dtype)

# Spróbuj skonwertować i sprawdź
vals = train_df["pchembl_value"].cast(pl.Float32, strict=False)
print("Nulle po konwersji:", vals.null_count())
print("Przykładowe wartości:", vals.head(10))


# In[18]:


import torch
from torch.utils.data import Dataset, DataLoader

class MoleculeDataset(Dataset):
    def __init__(self, df):
        # Konwersja kolumny 'fingerprint' (listy) na macierz NumPy, a potem na Tensor
        self.X = torch.tensor(np.array(df["fingerprint"].to_list()), dtype=torch.float32)
        # Konwersja pIC50 na Tensor
        self.y = torch.tensor(df["pchembl_value"].cast(pl.Float32).to_numpy(),dtype=torch.float32).reshape(-1, 1)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# Tworzymy instancje dla naszych zbiorów ze Scaffold Split
train_dataset = MoleculeDataset(train_df)
val_dataset = MoleculeDataset(val_df)
test_dataset = MoleculeDataset(test_df)

# Parametr batch_size (np. 64) decyduje ile cząsteczek model widzi naraz
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False)


# In[19]:


import matplotlib.pyplot as plt

def train_model(model, train_loader, val_loader, epochs=50, lr=0.001):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
    
    train_losses = []
    val_losses = []

    for epoch in range(epochs):
        # Faza Treningu
        model.train()
        running_train_loss = 0.0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            
            optimizer.zero_grad()        # zerowanie gradientów
            outputs = model(inputs)      # forward pass
            loss = criterion(outputs, targets)
            loss.backward()              # backward pass (obliczanie gradientów)
            optimizer.step()             # aktualizacja wag
            
            running_train_loss += loss.item() * inputs.size(0)
        
        epoch_train_loss = running_train_loss / len(train_loader.dataset)
        train_losses.append(epoch_train_loss)

        # Faza Walidacji (bez obliczania gradientów)
        model.eval()
        running_val_loss = 0.0
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                running_val_loss += loss.item() * inputs.size(0)
        
        epoch_val_loss = running_val_loss / len(val_loader.dataset)
        val_losses.append(epoch_val_loss)

        if (epoch+1) % 5 == 0:
            print(f"Epoka {epoch+1}/{epochs} | Train Loss: {epoch_train_loss:.4f} | Val Loss: {epoch_val_loss:.4f}")

    return train_losses, val_losses

# Uruchomienie
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = ChemMLP().to(device)
train_hist, val_hist = train_model(model, train_loader, val_loader, epochs=50)


# In[20]:


plt.figure(figsize=(10, 5))
plt.plot(train_hist, label="Błąd Treningowy (MSE)")
plt.plot(val_hist, label="Błąd Walidacyjny (MSE)")
plt.xlabel("Epoka")
plt.ylabel("Loss")
plt.title("Postęp uczenia modelu dla CHEMBL_203")
plt.legend()
plt.show()


# In[ ]:




