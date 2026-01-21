import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from streamlit_gsheets import GSheetsConnection
import time

# Configuration de la page
st.set_page_config(page_title="Registre - GPE - RH", layout="wide")

# --- GESTION DE LA CONNEXION (MULTI-UTILISATEURS) ---
def check_password():
    """Gère la connexion avec plusieurs utilisateurs."""
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = "" # Pour savoir QUI est connecté

    if st.session_state.authenticated:
        return True

    # Écran de connexion
    st.title("🔒 Connexion GPE")
    st.caption("Accès réservé au personnel autorisé.")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        username_input = st.text_input("Identifiant")
        password_input = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter", type="primary"):
            try:
                # On charge la liste des utilisateurs depuis les Secrets
                # secrets["credentials"] est maintenant un dictionnaire {user: password, user2: pass2}
                users_db = st.secrets["credentials"]
                
                # 1. On vérifie si l'utilisateur existe dans la liste
                if username_input in users_db:
                    # 2. On vérifie si le mot de passe correspond
                    if users_db[username_input] == password_input:
                        st.session_state.authenticated = True
                        st.session_state.username = username_input # On mémorise le nom
                        st.success(f"Bienvenue, {username_input} !")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Mot de passe incorrect.")
                else:
                    st.error("Identifiant inconnu.")
                    
            except Exception as e:
                st.error("Erreur de configuration des Secrets. Vérifiez la section [credentials].")
                
    return False

# --- SÉCURITÉ : STOP SI PAS CONNECTÉ ---
if not check_password():
    st.stop()


# =========================================================
# APPLICATION PRINCIPALE (Visible uniquement après login)
# =========================================================

# --- CONNEXION GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        expected_cols = [
            "Nom", "Prénom", "Poste", "Naissance", "Téléphone", 
            "Date Embauche", "Statut", "Salaire", "Contrat", "Etat", "Date Sortie"
        ]
        
        if df.empty: return pd.DataFrame(columns=expected_cols)
        
        for col in expected_cols:
            if col not in df.columns: df[col] = None
        
        return df.fillna("")[expected_cols]
    except Exception as e:
        st.error(f"Erreur Google Sheets : {e}")
        return pd.DataFrame()

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erreur sauvegarde : {e}")

# --- BARRE LATÉRALE ---
with st.sidebar:
    # Affiche le nom de la personne connectée
    st.info(f"👤 Utilisateur : **{st.session_state.username.capitalize()}**")
    
    if st.button("Se déconnecter"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

# --- CONTENU ---
st.title(f"☁️ GPE - Espace RH")
st.markdown("---")

df = load_data()

if not df.empty:
    df_actifs = df[df['Etat'] != 'Parti'].copy()
    df_anciens = df[df['Etat'] == 'Parti'].copy()
else:
    df_actifs, df_anciens = pd.DataFrame(), pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["➕ Recrutement", "👥 Effectif Actif", "🗂️ Archives"])

# TAB 1
with tab1:
    st.header("Nouvelle Embauche")
    with st.form("add_form", clear_on_submit=True):
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
        contrat_recu = st.checkbox("Contrat signé et archivé")
        
        if st.form_submit_button("Valider"):
            if nom and prenom:
                new_entry = pd.DataFrame([{
                    "Nom": nom.upper(), "Prénom": prenom.capitalize(), "Poste": poste.capitalize(),
                    "Naissance": str(naissance), "Téléphone": str(tel), "Date Embauche": str(embauche),
                    "Statut": statut, "Salaire": salaire, "Contrat": "Oui" if contrat_recu else "Non",
                    "Etat": "Actif", "Date Sortie": ""
                }])
                save_data(pd.concat([df, new_entry], ignore_index=True))
                st.success("Ajouté !")
                st.rerun()
            else:
                st.warning("Nom/Prénom requis.")

# TAB 2
with tab2:
    if not df_actifs.empty:
        edited_df = st.data_editor(df_actifs, num_rows="fixed", use_container_width=True, key="edit_act")
        
        col_s, col_d = st.columns(2)
        with col_s:
            if st.button("💾 Sauvegarder modifs"):
                save_data(pd.concat([df_anciens, edited_df], ignore_index=True))
                st.success("Sauvegardé.")
                st.rerun()
        with col_d:
            with st.popover("Départ Employé"):
                who = st.selectbox("Nom", df_actifs['Nom']+" "+df_actifs['Prénom'])
                d_date = st.date_input("Date Fin")
                if st.button("Valider Départ"):
                    mask = (df['Nom']+" "+df['Prénom']) == who
                    df.loc[mask, 'Etat'] = 'Parti'
                    df.loc[mask, 'Date Sortie'] = str(d_date)
                    save_data(df)
                    st.rerun()
    else: st.info("Vide")

# TAB 3
with tab3:
    if not df_anciens.empty:
        st.dataframe(df_anciens, use_container_width=True)
        # Export
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df_anciens.to_excel(writer, index=False)
        st.download_button("Télécharger Excel", buffer, "anciens.xlsx")
        
        st.markdown("---")
        c_res, c_del = st.columns(2)
        opts = df_anciens['Nom']+" "+df_anciens['Prénom']
        
        with c_res:
            res_who = st.selectbox("Réintégrer", opts, key="res")
            if st.button("Valider Réintégration"):
                mask = (df['Nom']+" "+df['Prénom']) == res_who
                df.loc[mask, 'Etat'] = 'Actif'
                df.loc[mask, 'Date Sortie'] = ""
                save_data(df)
                st.rerun()
        with c_del:
            del_who = st.selectbox("Supprimer", opts, key="del")
            if st.button("Valider Suppression", type="primary"):
                mask = (df['Nom']+" "+df['Prénom']) == del_who
                save_data(df[~mask])
                st.rerun()
    else: st.info("Aucun ancien")





