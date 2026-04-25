import streamlit as st
from google import genai
from fpdf import FPDF
import io
import datetime

st.set_page_config(page_title="ImmoCopy AI", page_icon="🏠", layout="wide")

# ─── CSS personnalisé ───────────────────────────────────────────────────────
st.markdown("""
<style>
.stButton > button { border-radius: 8px; font-weight: 500; }
.post-box { background: transparent; border: 1px solid rgba(128,128,128,0.3); border-radius: 10px;
            padding: 20px; font-size: 15px; line-height: 1.7; white-space: pre-wrap;
            color: inherit; }
.compteur { font-size: 13px; color: #888; text-align: center; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ─── Prompts par plateforme ─────────────────────────────────────────────────
PROMPTS = {
    "LinkedIn": (
        "Tu es un agent immobilier expert et copywriter professionnel. "
        "Rédige un post LinkedIn percutant pour ce bien : {description}. "
        "Ton : {ton}. "
        "Agence : {agence}. Slogan : {slogan}. "
        "Règles : commence par une accroche forte (question ou chiffre), "
        "structure avec des sauts de ligne, utilise 3 à 5 emojis max, "
        "termine par un call-to-action et 5 hashtags. Longueur : 150 à 200 mots."
    ),
    "SeLoger": (
        "Tu es un agent immobilier expert. "
        "Rédige une annonce SeLoger professionnelle pour ce bien : {description}. "
        "Ton : {ton}. "
        "Agence : {agence}. Slogan : {slogan}. "
        "Règles : titre accrocheur en MAJUSCULES, bullet points avec tirets, "
        "décris l'environnement et les transports. Pas d'emojis. 120 à 180 mots."
    ),
    "Facebook": (
        "Tu es un agent immobilier sympathique et proche de ses clients. "
        "Rédige un post Facebook pour ce bien : {description}. "
        "Ton : {ton}. "
        "Agence : {agence}. Slogan : {slogan}. "
        "Règles : interpelle la communauté, projette le lecteur dans le bien, "
        "5 à 8 emojis, pose une question, appel à partager. 80 à 120 mots."
    ),
    "Instagram": (
        "Tu es un agent immobilier moderne avec un sens aigu de l'esthétique. "
        "Rédige une légende Instagram pour ce bien : {description}. "
        "Ton : {ton}. "
        "Agence : {agence}. Slogan : {slogan}. "
        "Règles : phrase poétique d'accroche, lifestyle aspirationnel, "
        "8 à 12 emojis, 15 hashtags immobilier FR et EN. 60 à 100 mots + hashtags."
    ),
}

RESEAUX = {
    "LinkedIn":  "💼 LinkedIn",
    "SeLoger":   "🏡 SeLoger",
    "Facebook":  "👥 Facebook",
    "Instagram": "📸 Instagram",
}

TONS = ["Professionnel", "Chaleureux", "Luxe / Prestige", "Urgent / Opportunité"]

# ─── Session state ──────────────────────────────────────────────────────────
if "posts_historique" not in st.session_state:
    st.session_state.posts_historique = []
if "compteur" not in st.session_state:
    st.session_state.compteur = 0
if "variantes" not in st.session_state:
    st.session_state.variantes = []

# ─── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Clé API Google Gemini", type="password")

    st.divider()
    st.markdown("**🏢 Votre agence**")
    nom_agence = st.text_input("Nom de l'agence", placeholder="Ex : Agence Dupont Immobilier")
    slogan = st.text_input("Slogan", placeholder="Ex : Votre bien, notre passion")

    st.divider()
    st.markdown("**📱 Réseau social**")
    reseau_choisi = st.radio(
        "Plateforme :",
        options=list(RESEAUX.keys()),
        format_func=lambda x: RESEAUX[x],
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown("**🎨 Ton**")
    ton_choisi = st.radio(
        "Ton :",
        options=TONS,
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown("**📊 Statistiques**")
    st.metric("Posts générés", st.session_state.compteur)
    if st.button("🗑️ Vider l'historique", use_container_width=True):
        st.session_state.posts_historique = []
        st.session_state.variantes = []
        st.session_state.compteur = 0
        st.rerun()

# ─── Titre et réseau sélectionné ───────────────────────────────────────────
st.title("🏠 ImmoCopy AI")
st.write("Générez des posts immobiliers pro en 2 secondes.")
st.info(f"Plateforme : {RESEAUX[reseau_choisi]}  |  Ton : {ton_choisi}  |  Agence : {nom_agence or '—'}")

# ─── Formulaire structuré ───────────────────────────────────────────────────
st.subheader("📋 Décrivez le bien")

col1, col2, col3 = st.columns(3)
with col1:
    type_bien = st.selectbox("Type de bien", [
        "Appartement", "Maison", "Villa", "Studio", "Loft",
        "Duplex", "Local commercial", "Terrain", "Immeuble"
    ])
    surface = st.number_input("Surface (m²)", min_value=10, max_value=10000, value=65)
with col2:
    nb_pieces = st.number_input("Nombre de pièces", min_value=1, max_value=20, value=3)
    prix = st.number_input("Prix (€)", min_value=0, value=250000, step=5000)
with col3:
    ville = st.text_input("Ville / Quartier", placeholder="Ex : Paris 11e")
    dpe = st.selectbox("DPE", ["A", "B", "C", "D", "E", "F", "G", "Non renseigné"])

points_forts = st.text_area(
    "Points forts du bien",
    placeholder="Ex : refait à neuf, balcon, proche métro, double vitrage, cave, parking...",
    height=80
)

# ─── Construction de la description ────────────────────────────────────────
def build_description():
    parts = [f"{type_bien} de {surface}m²"]
    if nb_pieces:
        parts.append(f"{nb_pieces} pièce(s)")
    if ville:
        parts.append(f"situé à {ville}")
    if prix:
        parts.append(f"au prix de {prix:,}€".replace(",", " "))
    if dpe != "Non renseigné":
        parts.append(f"DPE classe {dpe}")
    if points_forts:
        parts.append(f"Points forts : {points_forts}")
    return ", ".join(parts)

# ─── Génération ─────────────────────────────────────────────────────────────
col_gen1, col_gen2 = st.columns(2)
with col_gen1:
    btn_generer = st.button(
        f"✨ Générer le post {RESEAUX[reseau_choisi]}",
        use_container_width=True,
        type="primary"
    )
with col_gen2:
    btn_variantes = st.button(
        "🔄 Générer 3 variantes",
        use_container_width=True
    )

def generer_post(description, reseau, ton, agence, slogan_text, client):
    prompt = PROMPTS[reseau].format(
        description=description,
        ton=ton,
        agence=agence if agence else "non précisée",
        slogan=slogan_text if slogan_text else "non précisé"
    )
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )
    return response.text

# ─── Action : 1 post ────────────────────────────────────────────────────────
if btn_generer:
    if not api_key:
        st.error("Veuillez entrer votre clé API dans la sidebar.")
    else:
        try:
            client = genai.Client(api_key=api_key)
            description = build_description()
            with st.spinner(f"Rédaction du post {reseau_choisi}..."):
                post = generer_post(description, reseau_choisi, ton_choisi, nom_agence, slogan, client)
            st.session_state.variantes = [post]
            st.session_state.compteur += 1
            st.session_state.posts_historique.insert(0, {
                "reseau": reseau_choisi,
                "ton": ton_choisi,
                "bien": f"{type_bien} {surface}m² — {ville}",
                "post": post,
                "date": datetime.datetime.now().strftime("%H:%M")
            })
        except Exception as e:
            st.error(f"Erreur : {e}")

# ─── Action : 3 variantes ───────────────────────────────────────────────────
if btn_variantes:
    if not api_key:
        st.error("Veuillez entrer votre clé API dans la sidebar.")
    else:
        try:
            client = genai.Client(api_key=api_key)
            description = build_description()
            variantes = []
            with st.spinner("Génération de 3 variantes..."):
                for i in range(3):
                    post = generer_post(description, reseau_choisi, ton_choisi, nom_agence, slogan, client)
                    variantes.append(post)
                    st.session_state.compteur += 1
            st.session_state.variantes = variantes
            for i, post in enumerate(variantes):
                st.session_state.posts_historique.insert(0, {
                    "reseau": reseau_choisi,
                    "ton": ton_choisi,
                    "bien": f"{type_bien} {surface}m² — {ville}",
                    "post": post,
                    "date": datetime.datetime.now().strftime("%H:%M")
                })
        except Exception as e:
            st.error(f"Erreur : {e}")

# ─── Affichage des posts générés ────────────────────────────────────────────
if st.session_state.variantes:
    st.divider()
    nb = len(st.session_state.variantes)
    if nb == 1:
        st.subheader(f"✅ Votre post {RESEAUX[reseau_choisi]}")
    else:
        st.subheader(f"✅ {nb} variantes générées — choisissez la meilleure")

    for i, post in enumerate(st.session_state.variantes):
        if nb > 1:
            st.markdown(f"**Variante {i+1}**")

        st.markdown(f'<div class="post-box">{post}</div>', unsafe_allow_html=True)

        # Bouton copier via JS
        post_js = post.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        copy_html = f"""
        <button onclick="
            navigator.clipboard.writeText(`{post_js}`).then(() => {{
                this.innerText = '✅ Copié !';
                this.style.background = '#0f6e56';
                setTimeout(() => {{
                    this.innerText = '📋 Copier ce post';
                    this.style.background = '#1a1a2e';
                }}, 2000);
            }});
        " style="
            margin-top: 8px;
            background: #1a1a2e;
            color: white;
            border: none;
            padding: 9px 20px;
            border-radius: 7px;
            font-size: 14px;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s;
        ">📋 Copier ce post</button>
        """
        st.components.v1.html(copy_html, height=55)

        # Export PDF
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=12)
            pdf.set_margins(15, 15, 15)
            titre = f"Post {reseau_choisi} — {type_bien} {surface}m² {ville}"
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 8, titre)
            pdf.ln(4)
            pdf.set_font("Helvetica", size=11)
            texte_propre = post.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(0, 7, texte_propre)
            pdf_bytes = pdf.output()
            nom_fichier = f"immocopy_{reseau_choisi.lower()}{'_v'+str(i+1) if nb > 1 else ''}.pdf"
            st.download_button(
                label="📄 Télécharger en PDF",
                data=bytes(pdf_bytes),
                file_name=nom_fichier,
                mime="application/pdf",
                key=f"pdf_{i}"
            )
        except Exception:
            pass

        if nb > 1 and i < nb - 1:
            st.markdown("---")

# ─── Historique ─────────────────────────────────────────────────────────────
if st.session_state.posts_historique:
    st.divider()
    with st.expander(f"📚 Historique de la session ({len(st.session_state.posts_historique)} posts)"):
        for idx, item in enumerate(st.session_state.posts_historique):
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown(f"**{RESEAUX[item['reseau']]}** — {item['bien']} — _{item['ton']}_ — {item['date']}")
            with col_h2:
                if st.button("Recharger", key=f"reload_{idx}"):
                    st.session_state.variantes = [item["post"]]
                    st.rerun()
            st.markdown(f'<div class="post-box" style="font-size:13px">{item["post"]}</div>', unsafe_allow_html=True)
            st.markdown("")
