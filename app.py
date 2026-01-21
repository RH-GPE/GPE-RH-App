import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

# Configuration de la page
st.set_page_config(page_title="Registre GPE (Cloud)", layout="wide")

# --- CONNEXION GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    """Charge les données depuis Google Sheets."""
    try:
        # On charge les données (ttl=0 pour ne pas avoir de cache et voir les maj direct)
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        expected_cols = [
            "Nom", "Prénom", "Poste", "Naissance", "Téléphone", 
            "Date Embauche", "Statut", "Salaire", "Contrat", "Etat", "Date Sortie"
        ]
        
        if df.empty:
             return pd.DataFrame(columns=expected_cols)
        
        # S'assurer que toutes les colonnes existent
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        
        # Nettoyage des valeurs NaN (vides)
        df = df.fillna("")
        
        return df[expected_cols]
        
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets : {e}")
        return pd.DataFrame()

def save_data(df):
    """Sauvegarde tout le DataFrame dans Google Sheets."""
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {e}")

# --- INTERFACE ---
st.title("☁️ GPE - RH (Connecté Google Sheets)")
st.markdown("---")

# Chargement
df = load_data()

# Séparation des tables pour l'affichage
if not df.empty:
    df_actifs = df[df['Etat'] != 'Parti'].copy()
    df_anciens = df[df['Etat'] == 'Parti'].copy()
else:
    df_actifs = pd.DataFrame()
    df_anciens = pd.DataFrame()

# TABS
tab_add, tab_active, tab_archived = st.tabs(["➕ Recrutement", "👥 Effectif Actif", "🗂️ Archives & Actions"])

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
                
                updated_df = pd.concat([df, new_entry], ignore_index=True)
                save_data(updated_df)
                st.success("Employé ajouté sur Google Sheets !")
                st.rerun()
            else:
                st.warning("Nom et Prénom obligatoires.")

# --- TAB 2 : ACTIFS ---
with tab_active:
    if not df_actifs.empty:
        st.caption("Double-cliquez sur une case pour modifier, puis cliquez sur Sauvegarder.")
        edited_df = st.data_editor(df_actifs, num_rows="fixed", use_container_width=True, key="editor_actifs")
        
        col_save, col_dep = st.columns([1, 1])
        
        # Sauvegarde modifs
        with col_save:
            if st.button("💾 Sauvegarder les modifications"):
                # On combine les anciens intacts + les actifs modifiés
                df_final = pd.concat([df_anciens, edited_df], ignore_index=True)
                save_data(df_final)
                st.success("Mise à jour effectuée !")
                st.rerun()

        # Gestion Départ
        with col_dep:
            with st.popover("🚪 Signaler un départ"):
                st.write("**Archiver un employé**")
                # Création d'une liste unique pour le selectbox
                liste_actifs = df_actifs['Nom'] + " " + df_actifs['Prénom']
                choix_depart = st.selectbox("Qui part ?", liste_actifs)
                date_depart = st.date_input("Date de fin")
                
                if st.button("Valider le départ"):
                    # On cherche la ligne correspondante dans le DF global
                    mask = (df['Nom'] + " " + df['Prénom']) == choix_depart
                    df.loc[mask, 'Etat'] = 'Parti'
                    df.loc[mask, 'Date Sortie'] = str(date_depart)
                    save_data(df)
                    st.success("Départ enregistré.")
                    st.rerun()
    else:
        st.info("La base est vide ou aucun actif.")

# --- TAB 3 : ARCHIVES (MODIFIÉ) ---
with tab_archived:
    st.header("Gestion des Anciens Employés")
    
    if not df_anciens.empty:
        # Affichage du tableau
        st.dataframe(df_anciens, use_container_width=True)
        
        # Export Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_anciens.to_excel(writer, index=False)
        st.download_button("📥 Télécharger la liste (Excel)", buffer, "anciens_employes.xlsx")
        
        st.markdown("---")
        st.subheader("Actions sur les archives")
        
        col_reintegre, col_delete = st.columns(2)
        
        # Liste des noms archivés pour les menus déroulants
        options_anciens = df_anciens['Nom'] + " " + df_anciens['Prénom']
        
        # 1. RÉINTÉGRATION
        with col_reintegre:
            st.info("↩️ **Réintégration**")
            st.caption("L'employé repassera dans la liste 'Actif'.")
            
            choix_restore = st.selectbox("Choisir l'employé à réintégrer :", options_anciens, key="restore_select")
            
            if st.button("Réintégrer dans les effectifs"):
                # On identifie la personne dans le tableau GLOBAL
                mask = (df['Nom'] + " " + df['Prénom']) == choix_restore
                df.loc[mask, 'Etat'] = 'Actif'
                df.loc[mask, 'Date Sortie'] = "" # On efface la date de sortie
                
                save_data(df)
                st.success(f"{choix_restore} est de nouveau actif !")
                st.rerun()

        # 2. SUPPRESSION DÉFINITIVE
        with col_delete:
            st.error("🗑️ **Suppression Définitive**")
            st.caption("⚠️ Attention : Efface définitivement la ligne du Google Sheet.")
            
            choix_delete = st.selectbox("Choisir l'employé à supprimer :", options_anciens, key="delete_select")
            
            if st.button("Supprimer définitivement", type="primary"):
                # On garde tout le monde SAUF la personne sélectionnée
                mask = (df['Nom'] + " " + df['Prénom']) == choix_delete
                df_new = df[~mask] # Le tilde ~ signifie "l'inverse de"
                
                save_data(df_new)
                st.warning(f"{choix_delete} a été supprimé de la base.")
                st.rerun()

    else:
        st.write("Aucun ancien employé pour le moment.")
