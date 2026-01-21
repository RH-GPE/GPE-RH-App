import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

# Configuration de la page
st.set_page_config(page_title="Registre GPE (Cloud)", layout="wide")

# --- CONNEXION GOOGLE SHEETS ---
# On établit la connexion
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    """Charge les données depuis Google Sheets."""
    # Le TTL (Time To Live) à 0 force le rechargement frais à chaque fois
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        # Nettoyage si le fichier est vide ou mal formaté
        expected_cols = [
            "Nom", "Prénom", "Poste", "Naissance", "Téléphone", 
            "Date Embauche", "Statut", "Salaire", "Contrat", "Etat", "Date Sortie"
        ]
        
        # Si le sheet est vide, on renvoie un DF vide avec les bonnes colonnes
        if df.empty:
             return pd.DataFrame(columns=expected_cols)
        
        # On s'assure que toutes les colonnes existent
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
                
        return df[expected_cols] # On force l'ordre des colonnes
        
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets : {e}")
        return pd.DataFrame()

def save_data(df):
    """Sauvegarde tout le DataFrame dans Google Sheets."""
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear() # On vide le cache pour forcer la mise à jour visuelle
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {e}")

# --- INTERFACE ---
st.title("☁️ GPE - RH (Connecté Google Sheets)")
st.markdown("---")

# Chargement
df = load_data()

# Séparation Actifs / Anciens
if not df.empty:
    # Remplissage des valeurs nulles pour éviter les bugs
    df = df.fillna("")
    df_actifs = df[df['Etat'] != 'Parti'].copy()
    df_anciens = df[df['Etat'] == 'Parti'].copy()
else:
    df_actifs = pd.DataFrame()
    df_anciens = pd.DataFrame()

# TABS
tab_add, tab_active, tab_archived = st.tabs(["➕ Recrutement", "👥 Effectif Actif", "🗂️ Archives"])

# --- TAB 1 : RECRUTEMENT ---
with tab_add:
    st.header("Nouvelle Embauche")
    with st.form("form_embauche", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom")
            prenom = st.text_input("Prénom")
            poste = st.text_input("Poste")
            naissance = st.date_input("Naissance", min_value=date(1960, 1, 1))
        with c2:
            tel = st.text_input("Téléphone")
            embauche = st.date_input("Date Embauche")
            statut = st.radio("Statut", ["Non-cadre", "Cadre"], horizontal=True)
            salaire = st.number_input("Salaire", step=100.0)
        
        # Checkbox simple pour le contrat
        contrat_recu = st.checkbox("Contrat papier/PDF bien reçu et archivé")
        
        if st.form_submit_button("Valider"):
            if nom and prenom:
                new_entry = pd.DataFrame([{
                    "Nom": nom.upper(),
                    "Prénom": prenom.capitalize(),
                    "Poste": poste.capitalize(),
                    "Naissance": str(naissance),
                    "Téléphone": str(tel),
                    "Date Embauche": str(embauche),
                    "Statut": statut,
                    "Salaire": salaire,
                    "Contrat": "Oui" if contrat_recu else "Non",
                    "Etat": "Actif",
                    "Date Sortie": ""
                }])
                
                # Ajout et sauvegarde
                updated_df = pd.concat([df, new_entry], ignore_index=True)
                save_data(updated_df)
                st.success("Employé ajouté sur Google Sheets !")
                st.rerun()
            else:
                st.warning("Nom et Prénom obligatoires.")

# --- TAB 2 : ACTIFS ---
with tab_active:
    if not df_actifs.empty:
        # Éditeur
        edited_df = st.data_editor(df_actifs, num_rows="fixed", use_container_width=True, key="editor_actifs")
        
        col_save, col_dep = st.columns([1, 1])
        
        # Bouton Sauvegarder les modifications
        with col_save:
            if st.button("💾 Sauvegarder modifs"):
                # On met à jour le DF principal
                # Technique : On supprime les anciens actifs du DF principal et on remet les nouveaux
                df_restant = df[df['Etat'] == 'Parti']
                df_final = pd.concat([df_restant, edited_df], ignore_index=True)
                save_data(df_final)
                st.success("Google Sheets mis à jour !")
                st.rerun()

        # Gestion Départ
        with col_dep:
            with st.popover("🚪 Signaler un départ"):
                choix_depart = st.selectbox("Qui part ?", df_actifs['Nom'] + " " + df_actifs['Prénom'])
                date_depart = st.date_input("Date de fin")
                if st.button("Valider le départ"):
                    # On retrouve la ligne dans le DF principal
                    mask = (df['Nom'] + " " + df['Prénom']) == choix_depart
                    df.loc[mask, 'Etat'] = 'Parti'
                    df.loc[mask, 'Date Sortie'] = str(date_depart)
                    save_data(df)
                    st.success("Départ enregistré.")
                    st.rerun()
    else:
        st.info("La base est vide.")

# --- TAB 3 : ARCHIVES ---
with tab_archived:
    if not df_anciens.empty:
        st.dataframe(df_anciens)
        # Bouton export Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_anciens.to_excel(writer, index=False)
        st.download_button("Télécharger Excel", buffer, "anciens.xlsx")
    else:
        st.write("Aucun ancien employé.")