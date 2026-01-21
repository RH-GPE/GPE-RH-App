import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from streamlit_gsheets import GSheetsConnection
import time

# Configuration de la page
st.set_page_config(page_title="Registre - RH - GPE ", layout="wide")

# --- GESTION DE LA CONNEXION (LOGIN) ---
def check_password():
    """Retourne True si l'utilisateur est connecté."""
    
    # 1. Initialisation de l'état si non existant
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 2. Si déjà connecté, on passe
    if st.session_state.authenticated:
        return True

    # 3. Écran de connexion
    st.title("🔒 Connexion Sécurisée GPE")
    
    col_login1, col_login2, col_login3 = st.columns([1, 1, 1])
    with col_login2:
        username_input = st.text_input("Identifiant")
        password_input = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter", type="primary"):
            # Vérification via les Secrets
            try:
                # On récupère les vrais identifiants dans les secrets
                secret_user = st.secrets["credentials"]["username"]
                secret_pass = st.secrets["credentials"]["password"]
                
                if username_input == secret_user and password_input == secret_pass:
                    st.session_state.authenticated = True
                    st.success("Connexion réussie !")
                    time.sleep(1) # Petit délai pour voir le message vert
                    st.rerun()    # Recharge la page pour afficher l'app
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except Exception:
                st.error("Erreur : Avez-vous configuré [credentials] dans les Secrets ?")
                
    return False

# --- BLOCAGE DE L'APPLICATION ---
# Si le mot de passe n'est pas bon, on arrête tout ici.
if not check_password():
    st.stop()


# =========================================================
# TOUT LE CODE CI-DESSOUS NE S'EXÉCUTE QUE SI CONNECTÉ
# =========================================================

# --- CONNEXION GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    """Charge les données depuis Google Sheets."""
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        expected_cols = [
            "Nom", "Prénom", "Poste", "Naissance", "Téléphone", 
            "Date Embauche", "Statut", "Salaire", "Contrat", "Etat", "Date Sortie"
        ]
        
        if df.empty:
             return pd.DataFrame(columns=expected_cols)
        
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        
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

# --- MENU LATÉRAL DE DÉCONNEXION ---
with st.sidebar:
    st.write(f"Connecté en tant que : **{st.secrets['credentials']['username']}**")
    if st.button("Se déconnecter"):
        st.session_state.authenticated = False
        st.rerun()

# --- INTERFACE PRINCIPALE ---
st.title("☁️ GPE - RH (Admin)")
st.markdown("---")

df = load_data()

if not df.empty:
    df_actifs = df[df['Etat'] != 'Parti'].copy()
    df_anciens = df[df['Etat'] == 'Parti'].copy()
else:
    df_actifs = pd.DataFrame()
    df_anciens = pd.DataFrame()

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
        st.caption("Modification en direct :")
        edited_df = st.data_editor(df_actifs, num_rows="fixed", use_container_width=True, key="editor_actifs")
        
        col_save, col_dep = st.columns([1, 1])
        with col_save:
            if st.button("💾 Sauvegarder les modifications"):
                df_final = pd.concat([df_anciens, edited_df], ignore_index=True)
                save_data(df_final)
                st.success("Mise à jour effectuée !")
                st.rerun()

        with col_dep:
            with st.popover("🚪 Signaler un départ"):
                liste_actifs = df_actifs['Nom'] + " " + df_actifs['Prénom']
                choix_depart = st.selectbox("Qui part ?", liste_actifs)
                date_depart = st.date_input("Date de fin")
                if st.button("Valider le départ"):
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
    st.header("Gestion des Anciens")
    if not df_anciens.empty:
        st.dataframe(df_anciens, use_container_width=True)
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_anciens.to_excel(writer, index=False)
        st.download_button("📥 Excel Archives", buffer, "anciens.xlsx")
        
        st.markdown("---")
        c_rest, c_del = st.columns(2)
        
        options_anciens = df_anciens['Nom'] + " " + df_anciens['Prénom']
        
        with c_rest:
            st.info("Réintégration")
            choix_restore = st.selectbox("Qui réintégrer ?", options_anciens, key="rest")
            if st.button("Réintégrer"):
                mask = (df['Nom'] + " " + df['Prénom']) == choix_restore
                df.loc[mask, 'Etat'] = 'Actif'
                df.loc[mask, 'Date Sortie'] = ""
                save_data(df)
                st.success("Fait !")
                st.rerun()
                
        with c_del:
            st.error("Suppression")
            choix_delete = st.selectbox("Qui supprimer ?", options_anciens, key="del")
            if st.button("Supprimer définitivement", type="primary"):
                mask = (df['Nom'] + " " + df['Prénom']) == choix_delete
                df_new = df[~mask]
                save_data(df_new)
                st.warning("Supprimé !")
                st.rerun()
    else:
        st.write("Personne.")





