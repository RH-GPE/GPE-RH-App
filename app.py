import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from streamlit_gsheets import GSheetsConnection
import time

# Configuration de la page
st.set_page_config(page_title="GPE - RH - Registre", layout="wide")

# --- GESTION CONNEXION CORRIGÉE (VERSION FINALE) ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""

    if st.session_state.authenticated:
        return True

    st.title("🔒 Connexion GPE")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        user = st.text_input("Identifiant")
        pwd = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter", type="primary"):
            # 1. On récupère les secrets (séparément pour éviter le bug)
            try:
                users_db = st.secrets["credentials"]
            except Exception:
                st.error("❌ Erreur : Section [credentials] introuvable dans les Secrets.")
                return False

            # 2. Vérification du mot de passe
            if user in users_db and users_db[user] == pwd:
                st.session_state.authenticated = True
                st.session_state.username = user
                
                # 3. Logging (isolé pour ne pas bloquer)
                try:
                    log_action(user, "Connexion", "Succès") 
                except Exception as e:
                    print(f"Log échoué: {e}") # On continue même si le log rate
                
                st.success(f"Bonjour {user} !")
                time.sleep(1)
                
                # 4. LE RERUN EST MAINTENANT HORS DE TOUT BLOC 'TRY'
                st.rerun()
                
            else:
                st.error("Identifiant ou mot de passe incorrect.")
                
    return False
    
# --- FONCTION DE LOGGING (NOUVEAU) ---
def log_action(utilisateur, action, details):
    """Écrit une ligne dans l'onglet 'Logs' du Google Sheet."""
    try:
        # Connexion dédiée pour éviter les conflits
        conn_log = st.connection("gsheets", type=GSheetsConnection)
        
        # On essaie de lire les logs existants
        try:
            df_logs = conn_log.read(worksheet="Logs", ttl=0)
        except:
            df_logs = pd.DataFrame(columns=["Date", "Heure", "Utilisateur", "Action", "Détails"])
        
        # Création de la nouvelle ligne
        now = datetime.now()
        new_log = pd.DataFrame([{
            "Date": now.strftime("%Y-%m-%d"),
            "Heure": now.strftime("%H:%M:%S"),
            "Utilisateur": utilisateur,
            "Action": action,
            "Détails": details
        }])
        
        # Concaténation et sauvegarde
        # On gère le cas où le fichier est vide
        if df_logs.empty:
            df_final = new_log
        else:
            df_final = pd.concat([df_logs, new_log], ignore_index=True)
            
        conn_log.update(worksheet="Logs", data=df_final)
        
    except Exception as e:
        print(f"Erreur de log : {e}") # On affiche juste dans la console, on ne bloque pas l'app

if not check_password():
    st.stop()

# --- APP PRINCIPALE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Nom", "Prénom", "Poste", "Naissance", "Téléphone", "Date Embauche", "Statut", "Salaire", "Contrat", "Etat", "Date Sortie"]
        if df.empty: return pd.DataFrame(columns=cols)
        for c in cols: 
            if c not in df.columns: df[c] = None
        return df.fillna("")[cols]
    except: return pd.DataFrame()

def save_data(df):
    conn.update(worksheet="Sheet1", data=df)
    st.cache_data.clear()

# --- SIDEBAR ---
with st.sidebar:
    current_user = st.session_state.username
    st.info(f"👤 **{current_user.capitalize()}**")
    if st.button("Se déconnecter"):
        log_action(current_user, "Déconnexion", "Fin de session")
        st.session_state.authenticated = False
        st.rerun()

st.title("☁️ GPE - Gestion RH")
st.markdown("---")

df = load_data()
if not df.empty:
    df_actifs = df[df['Etat'] != 'Parti'].copy()
    df_anciens = df[df['Etat'] == 'Parti'].copy()
else:
    df_actifs, df_anciens = pd.DataFrame(), pd.DataFrame()

# 4 ONGLETS MAINTENANT
tab1, tab2, tab3, tab4 = st.tabs(["➕ Recrutement", "👥 Actifs", "🗂️ Archives", "📜 Journal (Logs)"])

# TAB 1 : AJOUT
with tab1:
    with st.form("add"):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom")
            prenom = st.text_input("Prénom")
            poste = st.text_input("Poste")
            naissance = st.date_input("Naissance", date(1980,1,1))
        with c2:
            tel = st.text_input("Tél")
            embauche = st.date_input("Embauche")
            statut = st.radio("Statut", ["Non-cadre", "Cadre"], horizontal=True)
            salaire = st.number_input("Salaire", step=100.0)
        contrat = st.checkbox("Contrat OK")
        
        if st.form_submit_button("Valider"):
            if nom and prenom:
                new = pd.DataFrame([{
                    "Nom": nom.upper(), "Prénom": prenom.capitalize(), "Poste": poste,
                    "Naissance": str(naissance), "Téléphone": tel, "Date Embauche": str(embauche),
                    "Statut": statut, "Salaire": salaire, "Contrat": "Oui" if contrat else "Non",
                    "Etat": "Actif", "Date Sortie": ""
                }])
                save_data(pd.concat([df, new], ignore_index=True))
                
                # LOG
                log_action(current_user, "Recrutement", f"Ajout de {prenom} {nom}")
                
                st.success("Ajouté !")
                st.rerun()

# TAB 2 : ACTIFS
with tab2:
    if not df_actifs.empty:
        edited = st.data_editor(df_actifs, num_rows="fixed", use_container_width=True, key="edit")
        c_save, c_dep = st.columns(2)
        with c_save:
            if st.button("💾 Sauvegarder modifications"):
                save_data(pd.concat([df_anciens, edited], ignore_index=True))
                # LOG
                log_action(current_user, "Modification", "Mise à jour du tableau des actifs")
                st.success("Sauvegardé")
                st.rerun()
        with c_dep:
            with st.popover("Départ"):
                who = st.selectbox("Nom", df_actifs['Nom']+" "+df_actifs['Prénom'])
                d_date = st.date_input("Date")
                if st.button("Valider Départ"):
                    mask = (df['Nom']+" "+df['Prénom']) == who
                    df.loc[mask, 'Etat'] = 'Parti'
                    df.loc[mask, 'Date Sortie'] = str(d_date)
                    save_data(df)
                    # LOG
                    log_action(current_user, "Départ", f"{who} marqué comme parti le {d_date}")
                    st.rerun()

# TAB 3 : ARCHIVES
with tab3:
    if not df_anciens.empty:
        st.dataframe(df_anciens)
        c_res, c_del = st.columns(2)
        opts = df_anciens['Nom']+" "+df_anciens['Prénom']
        
        with c_res:
            who_res = st.selectbox("Réintégrer", opts)
            if st.button("Valider Réintégration"):
                mask = (df['Nom']+" "+df['Prénom']) == who_res
                df.loc[mask, 'Etat'] = 'Actif'
                df.loc[mask, 'Date Sortie'] = ""
                save_data(df)
                # LOG
                log_action(current_user, "Réintégration", f"Retour de {who_res}")
                st.rerun()
                
        with c_del:
            who_del = st.selectbox("Supprimer", opts)
            if st.button("Suppression Totale", type="primary"):
                mask = (df['Nom']+" "+df['Prénom']) == who_del
                save_data(df[~mask])
                # LOG
                log_action(current_user, "Suppression", f"Effacement définitif de {who_del}")
                st.rerun()

# TAB 4 : JOURNAL DES LOGS (NOUVEAU)
with tab4:
    st.header("📜 Historique des actions")
    
    if st.button("🔄 Rafraîchir les logs"):
        st.rerun()
        
    try:
        # On lit l'onglet 'Logs'
        df_logs = conn.read(worksheet="Logs", ttl=0)
        if not df_logs.empty:
            # On trie pour avoir le plus récent en haut (optionnel)
            st.dataframe(df_logs, use_container_width=True)
            
            # Export des logs
            buffer_log = BytesIO()
            with pd.ExcelWriter(buffer_log, engine='xlsxwriter') as writer:
                df_logs.to_excel(writer, index=False)
            st.download_button("Télécharger le Journal", buffer_log, "journal_logs.xlsx")
        else:
            st.info("Le journal est vide pour l'instant.")
    except Exception as e:
        st.error("Impossible de lire l'onglet 'Logs'. Avez-vous bien créé l'onglet dans Google Sheets ?")






