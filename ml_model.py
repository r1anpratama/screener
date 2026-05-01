"""
ml_model.py — Modul Machine Learning (Prediksi Probabilitas T+1)
================================================================
Menggunakan XGBoost Classifier untuk memprediksi probabilitas harga
saham naik pada hari trading berikutnya (T+1).

Model menggunakan fitur-fitur teknikal yang sudah dihitung di
feature_engineering.py sebagai input, dan menghasilkan probabilitas
kenaikan (0% - 100%) menggunakan predict_proba().
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score, precision_score, recall_score
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import optuna
from config import RANDOM_SEED


class T1ProbabilityModel:
    """
    Model klasifikasi XGBoost untuk prediksi probabilitas T+1.

    Model ini memprediksi apakah harga saham akan NAIK (1) atau TURUN (0)
    pada hari trading berikutnya. Output utama adalah probabilitas kenaikan
    yang dihasilkan oleh predict_proba().

    Attributes
    ----------
    models : dict
        Kamus model XGBoost (1 model per klaster).
    kmeans : KMeans
        Model clustering untuk mengelompokkan saham.
    scaler : StandardScaler
        Scaler untuk normalisasi profil saham sebelum di-cluster.
    n_clusters : int
        Jumlah klaster (default: 3).
    feature_columns : list[str]
        Daftar kolom fitur yang digunakan untuk prediksi.
    is_trained : bool
        Status apakah model sudah dilatih.
    """

    # Kolom fitur numerik yang digunakan sebagai input model
    FEATURE_COLS = [
        "bb_bandwidth",          # Bollinger Bandwidth (volatilitas)
        "rsi_14",                # RSI 14 hari (momentum)
        "vwap_ratio",            # Rasio Close/VWAP (bandarmologi)
        # === Fitur dari IDX API (data riil BEI) ===
        "foreign_net",           # Net foreign flow (positif = asing beli)
        "bid_offer_ratio",       # Rasio bid/offer volume (sentimen orderbook)
    ]

    # Fitur untuk Profil Saham (K-Means Clustering)
    PROFILE_COLS = [
        "hist_volatility",
        "avg_volume"
    ]

    def __init__(self, n_clusters: int = 3):
        """
        Inisialisasi model Cluster-then-Predict.
        """
        self.n_clusters = n_clusters
        self.models = {}
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=RANDOM_SEED, n_init=10)
        self.scaler = StandardScaler()
        self.feature_columns = self.FEATURE_COLS.copy()
        self.is_trained = False

    def prepare_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Membuat kolom target untuk training: apakah Close T+1 > Close T.

        Label target:
        - 1 = harga NAIK di hari berikutnya (Close[t+1] > Close[t])
        - 0 = harga TURUN/TETAP di hari berikutnya

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame dengan fitur yang sudah dihitung.

        Returns
        -------
        pd.DataFrame
            DataFrame dengan kolom tambahan 'target'.
        """
        result_frames = []

        for ticker, group in df.groupby("ticker"):
            group = group.copy().sort_values("date")

            # Target: apakah Close besok lebih tinggi dari Close hari ini?
            group["next_close"] = group["close"].shift(-1)
            group["target"] = (group["next_close"] > group["close"]).astype(int)

            # Hapus baris terakhir (tidak ada data besok untuk dijadikan label)
            group = group.dropna(subset=["target"])
            group.drop(columns=["next_close"], inplace=True)

            result_frames.append(group)

        return pd.concat(result_frames, ignore_index=True)

    def train(self, df: pd.DataFrame) -> dict:
        """
        Melatih model XGBoost pada data historis.

        Proses:
        1. Pisahkan fitur (X) dan target (y)
        2. Split data menjadi training (80%) dan testing (20%)
        3. Fit model pada training data
        4. Evaluasi pada testing data

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame dengan fitur dan kolom 'target'.

        Returns
        -------
        dict
            Dictionary berisi metrik evaluasi model.
        """
        print("[>] Memulai Training Model XGBoost...")

        # Siapkan fitur dan target, buang baris dengan NaN pada fitur INTI
        # Fitur IDX (foreign_net, bid_offer_ratio) diisi 0 jika tidak tersedia
        # karena data IDX hanya mencakup beberapa hari terakhir
        for col in self.feature_columns:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # Pastikan kolom target tidak NaN
        core_cols = [c for c in self.feature_columns if c in df.columns] + ["target"]
        df_clean = df.dropna(subset=core_cols).copy()

        X = df_clean[self.feature_columns]
        y = df_clean["target"].astype(int)

        print(f"   -> Dataset: {len(X):,} sampel, {len(self.feature_columns)} fitur")
        print(f"   -> Distribusi target: naik={y.sum():,} ({y.mean():.1%}), "
              f"turun={len(y) - y.sum():,} ({1 - y.mean():.1%})")

        # --- 1. TAHAP CLUSTERING (Unsupervised) ---
        print("   -> Mengelompokkan saham ke dalam klaster (K-Means)...")
        # Ekstrak profil unik per saham
        profiles = df_clean.drop_duplicates(subset=["ticker"])[["ticker"] + self.PROFILE_COLS].copy()
        
        # Scaling fitur profil
        profiles_scaled = self.scaler.fit_transform(profiles[self.PROFILE_COLS])
        
        # Fit K-Means
        profiles["cluster"] = self.kmeans.fit_predict(profiles_scaled)
        
        # Gabungkan klaster kembali ke dataset utama
        df_clean = df_clean.merge(profiles[["ticker", "cluster"]], on="ticker", how="left")
        
        print(f"   -> Distribusi Klaster Saham: {profiles['cluster'].value_counts().to_dict()}")

        X_train, X_test, y_train, y_test, cluster_train, cluster_test = train_test_split(
            X, y, df_clean["cluster"], test_size=0.2, random_state=RANDOM_SEED, stratify=y
        )

        # --- 2. TAHAP TRAINING MULTI-MODEL (Supervised) ---
        print("   -> Melatih XGBoost terpisah per klaster...")
        
        y_pred_proba_all = np.zeros(len(y_test))
        y_pred_all = np.zeros(len(y_test))
        
        for cluster_id in range(self.n_clusters):
            # Filter data untuk klaster ini
            idx_train = cluster_train == cluster_id
            idx_test = cluster_test == cluster_id
            
            X_train_c = X_train[idx_train]
            y_train_c = y_train[idx_train]
            X_test_c = X_test[idx_test]
            
            if len(X_train_c) == 0:
                continue
                
            print(f"      -> Tuning Cluster {cluster_id} dengan Optuna (Data: {len(X_train_c)} baris)...")
            
            # --- Fungsi Objective Optuna ---
            def objective(trial):
                param = {
                    'n_estimators': trial.suggest_int('n_estimators', 50, 200),
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
                    'max_depth': trial.suggest_int('max_depth', 3, 7),
                    'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                    'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                    'random_state': RANDOM_SEED,
                    'eval_metric': "logloss"
                }
                
                # Split untuk validasi tuning (agar tidak overfitting pada test set utama)
                if len(X_train_c) > 50:
                    X_tr, X_val, y_tr, y_val = train_test_split(
                        X_train_c, y_train_c, test_size=0.2, random_state=RANDOM_SEED
                    )
                else:
                    # Jika data terlalu sedikit
                    X_tr, X_val, y_tr, y_val = X_train_c, X_train_c, y_train_c, y_train_c

                model_opt = XGBClassifier(**param)
                model_opt.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
                
                preds = model_opt.predict_proba(X_val)[:, 1]
                # Tangani error jika hanya ada 1 class di val
                try:
                    score = roc_auc_score(y_val, preds)
                except:
                    score = 0.5
                return score

            optuna.logging.set_verbosity(optuna.logging.WARNING)
            study = optuna.create_study(direction='maximize')
            # 10 trials cukup untuk menghemat waktu (karena ada 3 klaster)
            study.optimize(objective, n_trials=10)
            
            best_params = study.best_params
            best_params['random_state'] = RANDOM_SEED
            best_params['eval_metric'] = "logloss"
            
            print(f"         [Cluster {cluster_id}] Best AUC: {study.best_value:.4f}")
            
            model = XGBClassifier(**best_params)
            
            # Train final model dengan full training data klaster
            model.fit(X_train_c, y_train_c)
            self.models[cluster_id] = model
            
            if len(X_test_c) > 0:
                y_pred_proba_all[idx_test] = model.predict_proba(X_test_c)[:, 1]
                y_pred_all[idx_test] = model.predict(X_test_c)

        # Evaluasi Gabungan
        roc_auc = roc_auc_score(y_test, y_pred_proba_all)
        acc = accuracy_score(y_test, y_pred_all)
        prec = precision_score(y_test, y_pred_all, zero_division=0)
        rec = recall_score(y_test, y_pred_all, zero_division=0)

        metrics = {
            "roc_auc": roc_auc,
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
        }

        print(f"   -> Gabungan AUC-ROC: {roc_auc:.4f}")
        print(f"   -> Gabungan Accuracy: {acc:.4f}")
        print(f"   -> Gabungan Precision (naik): {prec:.4f}")
        print(f"   -> Gabungan Recall (naik): {rec:.4f}")
        
        self.is_trained = True

        self._print_feature_importance()
        print("[OK] Training selesai!\n")

        return metrics

    def _print_feature_importance(self):
        """Mencetak rata-rata feature importance dari semua model klaster."""
        print("\n[*] Rata-rata Feature Importance (Cross-Cluster):")
        
        total_importance = np.zeros(len(self.feature_columns))
        for cluster_id, model in self.models.items():
            total_importance += model.feature_importances_
            
        avg_importance = total_importance / len(self.models)
        
        importance_df = pd.DataFrame({
            "feature": self.feature_columns,
            "importance": avg_importance
        }).sort_values("importance", ascending=False)

        for _, row in importance_df.iterrows():
            bar = "#" * int(row["importance"] * 50)
            print(f"   {row['feature']:<25} {row['importance']:.4f} {bar}")

    def predict_proba(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prediksi probabilitas kenaikan harga T+1 menggunakan model klaster spesifik.
        """
        if not self.is_trained:
            raise RuntimeError("Model belum dilatih!")

        df = df.copy()

        # Ambil fitur, isi NaN dengan 0 untuk prediksi
        X = df[self.feature_columns].fillna(0)
        
        # 1. Tentukan klaster untuk masing-masing baris
        profiles = df[["ticker"] + self.PROFILE_COLS].copy()
        profiles["hist_volatility"] = profiles["hist_volatility"].fillna(0.02)
        profiles["avg_volume"] = profiles["avg_volume"].fillna(100000)
        
        profiles_scaled = self.scaler.transform(profiles[self.PROFILE_COLS])
        clusters = self.kmeans.predict(profiles_scaled)
        
        df["cluster_id"] = clusters
        
        # 2. Prediksi probabilitas menggunakan model klaster masing-masing
        pred_proba = np.zeros(len(df))
        for i in range(len(df)):
            cluster_id = clusters[i]
            x_row = X.iloc[[i]]
            
            model = self.models.get(cluster_id)
            if model:
                pred_proba[i] = model.predict_proba(x_row)[0, 1]
            else:
                pred_proba[i] = 0.5 # Fail-safe

        # Konversi ke persentase
        df["win_probability"] = np.round(pred_proba * 100, 2)

        return df

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Mengambil feature importance rata-rata dari semua model klaster.
        """
        if not self.is_trained:
            raise RuntimeError("Model belum dilatih!")

        total_importance = np.zeros(len(self.feature_columns))
        for model in self.models.values():
            total_importance += model.feature_importances_
            
        avg_importance = total_importance / len(self.models)
        
        df_imp = pd.DataFrame({
            "feature": self.feature_columns,
            "importance": avg_importance
        })
        df_imp.sort_values("importance", ascending=False, inplace=True)
        return df_imp.reset_index(drop=True)
