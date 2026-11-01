"""Camino Real Lexical Time Machine.

An exploratory Streamlit dashboard for 90 years of material-culture records
extracted from seventeen nineteenth-century travelogues along the Camino Real
between Honda and Santafe de Bogota, Colombia (1822-1910).

Data: Suescun, Herrera & Therrien (2026), Open Relational Dataset..., Zenodo.
DOI: 10.5281/zenodo.23753244 (CC BY 4.0)

The two CSV tables are used verbatim as deposited. Everything analytical
(year anchors, preservation classes, material families) is derived at load
time and documented in README.md.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

APP_DIR = Path(__file__).resolve().parent
OBRAS_CSV = APP_DIR / "01_obras_corpus.csv"
EVIDENCIA_CSV = APP_DIR / "03_evidencia_material.csv"

DATASET_DOI = "10.5281/zenodo.23753244"
DATASET_URL = f"https://doi.org/{DATASET_DOI}"
DATASET_CITATION = (
    "Suescún, F., Herrera, O., & Therrien, M. (2026). *Open Relational Dataset "
    "of Nineteenth-Century Material Culture and Spatial Nodes along the Camino "
    "Real (Honda–Santafé de Bogotá, Colombia, 1822–1910)* (v1.0.0) [Data set]. "
    f"Zenodo. [{DATASET_DOI}]({DATASET_URL})"
)

TIME_AXES = {
    "Journey year (recommended)": {
        "column": "anio_jornada_anchor",
        "label": "Journey year",
        "help": (
            "Midpoint of the documented journey/stay in Colombia. Recommended for "
            "diachronic questions because it dates the observation, not the printing."
        ),
    },
    "Publication year": {
        "column": "anio_edicion_anchor",
        "label": "Publication year",
        "help": (
            "First year of the edition statement (the brief's default). Publication "
            "can lag the journey by decades, e.g. Le Moyne travelled 1828–1839 and "
            "published in 1880."
        ),
    },
}

PRESERVATION_ORDER = ["High", "Partial", "Low", "N/A", "Unspecified"]
PRESERVATION_COLORS = {
    "High": "#2E7D32",
    "Partial": "#EF6C00",
    "Low": "#C62828",
    "N/A": "#6D6D6D",
    "Unspecified": "#BDBDBD",
}

ANALYTICAL_COLORS = {
    "Tránsito": "#1F4E5F",
    "Maneras de habitar": "#A15C38",
}
DESCRIPTIVE_COLORS = {
    "Acarreos": "#1F4E5F",
    "Insumos": "#5B8C5A",
    "Servicios": "#A15C38",
    "Hitos y nodos": "#C9A227",
    "Celebraciones y festividades": "#8E5572",
    "Sendas": "#6B7A8F",
}

# Column labels used in the evidence table (display name -> source column).
TABLE_COLUMNS = [
    ("id_evidencia", "ID"),
    ("year_label", "Year"),
    ("autor", "Author"),
    ("termino_normalizado_glosario", "Glossary term"),
    ("materia_prima", "Raw materials"),
    ("material_families_label", "Material families"),
    ("preservacion_arqueologica_esperada", "Preservation"),
    ("cita_textual", "Verbatim quote"),
    ("resumen_contexto_en", "English summary"),
    ("localizacion_pagina_folio", "Page"),
]

REQUIRED_EVIDENCE_COLUMNS = [
    "id_evidencia",
    "id_obra",
    "autor",
    "anio_edicion",
    "categoria_analitica",
    "categoria_descriptiva_es",
    "categoria_descriptiva_en",
    "subcategoria",
    "termino_en_fuente",
    "termino_normalizado_glosario",
    "materia_prima",
    "preservacion_arqueologica_esperada",
    "cita_textual",
    "localizacion_pagina_folio",
    "resumen_contexto_en",
]
REQUIRED_OBRA_COLUMNS = [
    "id_obra",
    "autor",
    "titulo_original",
    "anio_jornada",
    "anio_edicion",
    "idioma_original",
    "rendimiento_material",
    "rol_en_corpus",
]

YEAR_RE = re.compile(r"\b(1[5-9]\d{2})\b")

# --------------------------------------------------------------------------- #
# Material-family lexicon
# --------------------------------------------------------------------------- #
# `materia_prima` is a free-text composition string ("Jute, straw padding,
# untanned ox-hide, wood"). To make it chartable we tokenise it and map each
# token onto one broad material class with an ordered keyword lexicon.
# Rules are evaluated in order; the first match wins.
MATERIAL_RULES: list[tuple[str, str]] = [
    ("Leather & hide", r"leather|hide|rawhide|skin|cowhide|goatskin|buckskin"),
    (
        "Fauna & animal by-products",
        r"\bbones?\b|skeletal|skeleton|\bhorn\b|antler|\bshell\b|\bgut\b|hoof|"
        r"feather|\bhair\b|\bdeer\b|\bgoats?\b|\bpigs?\b|\bhogs?\b|\bhorses?\b|"
        r"oxen|equid|\bmules?\b|gamecock|tortoise",
    ),
    (
        "Iron & steel",
        r"\biron\b|\bsteel\b|cast[ -]?iron|forged|nail|hinge|blade|machinery|"
        r"\brail|\blocomotive|boiler|cable|\bwire\b|scabbard|padlock|\block\b|"
        r"\bbolt|ring\b|\bbell\b|\bspur|stirrup|screw|hoop|cutlery|string",
    ),
    (
        "Non-ferrous metals",
        r"copper|brass|bronze|silver|gold|tinplate|\btin\b|pewter|yellow metal|"
        r"coin|coinage|numismatic",
    ),
    (
        "Wood & bamboo",
        r"\bwood\b|wooden|timber|\bbeam|\bplank|\bboard|\blog\b|\bpoles?\b|"
        r"\bposts?\b|\brods?\b|cedar|ceiba|willow|orange wood|hardwood|guadua|"
        r"bamboo|\bcane\b|litter|trestle|frame|barrel|bedstead|table|counter|"
        r"\bdoors?\b|shed|fence|winch|pulley|stretcher|branch|twig|liana|vine|"
        r"bark|\bmast\b|shaft|handle",
    ),
    ("Ceramic & brick", r"ceramic|pottery|earthenware|stoneware|kaolin|whiteware|ironstone|tinaja|botija|brick|\btile|teja|porcelain|terracotta|\bpots?\b|\bjars?\b|tableware|dish|bowl|lamp|candil|múcura|fired clay"),
    ("Glass", r"\bglass\b|bottle|\bbeads?\b|pane"),
    ("Gourd & calabash", r"calabash|gourd|totumo|crescentia|coconut|totuma"),
    ("Stone & masonry", r"\bstone|granite|basalt|schist|boulder|pebble|masonry|\brock|bedrock|metate|\bmano\b|grinding|counterweight|causeway|paving"),
    ("Earth, clay & minerals", r"\bearth\b|\bmud\b|\bclay\b|rammed|tapia|bahareque|plaster|whitewash|\bfloor\b|\bsoil\b|ochre|pigment|charcoal|\bcoal\b|\blime\b|\bsand\b|gravel|debris"),
    ("Wax, tallow & combustibles", r"\bwax\b|beeswax|tallow|candle|resin|gunpowder|firecracker|rocket|powder"),
    ("Rubber", r"rubber|caoutchouc"),
    ("Paper & print", r"paper|\bprint|book|magazine|graffiti|\bink\b|parchment"),
    (
        "Textiles & plant fibre",
        r"textile|cloth|woven|weav|cotton|\bwool\b|silk|satin|felt|baize|canvas|"
        r"gauze|oilcloth|fiber|fibre|fique|jute|agave|aloe|straw|reed|totora|palm|"
        r"wicker|basket|netting|\bnet\b|\bcord\b|\brope\b|thread|ribbon|\bmat\b|"
        r"petate|thatch|\bbag\b|\bsack|covering|\bsail\b",
    ),
    (
        "Foodstuffs & provisions",
        r"\bbeef\b|\bpork\b|chicken|fowl|\bmutton\b|sausage|bread|cheese|maize|"
        r"\bcorn\b|potato|plantain|banana|cacao|chocolate|\bsalt\b|sugar|chicha|"
        r"lard|garlic|onion|chili|pepper|\brice\b|\bbeans?\b|squash|yucca|cassava|"
        r"ñame|\byam\b|papaya|fruit|vinegar|grain|tuber|\bfood\b|provision|meat|"
        r"fish|coffee|tobacco|annatto|cumin|\bseed\b",
    ),
    ("Metal (unspecified)", r"\bmetal\b"),
]

MATERIAL_STOPWORDS = {
    "pink", "white", "black", "blue", "red", "green", "yellow", "multicolored",
    "colored", "imported", "coarse", "refined", "carved", "solid", "rustic",
    "porous", "molded", "unrefined", "raw", "dried", "salted", "smoked",
    "sun-dried", "cured", "fresh", "light", "heavy", "thick", "thin", "large",
    "small", "broken", "collapsed", "compacted", "fired", "unfired", "two",
    "three", "four", "five", "standard", "weight", "unit", "balanced",
    "half-loads", "road", "length", "measurement", "leagues", "paved", "steps",
    "slope", "unpaved", "backyard", "plot", "plots", "limb", "fractures",
    "beds", "spoon", "flowers", "broth", "cognac", "ornament", "decoration",
}


def _tokens(materia_prima: str) -> list[str]:
    """Split a free-text composition string into material tokens."""
    text = re.sub(r"\([^)]*\)", " ", str(materia_prima)).lower()
    parts = re.split(r"[;/+,]|\band\b|\bwith\b|\bor\b", text)
    tokens: list[str] = []
    for part in parts:
        cleaned = re.sub(r"[^a-záéíóúñü\-\s]", " ", part)
        cleaned = " ".join(cleaned.split())
        if not cleaned or cleaned in MATERIAL_STOPWORDS:
            continue
        tokens.append(cleaned)
    return tokens


def material_families(materia_prima: str) -> list[str]:
    """Map a free-text composition string onto broad material families."""
    families: list[str] = []
    for token in _tokens(materia_prima):
        for family, pattern in MATERIAL_RULES:
            if re.search(pattern, token):
                if family not in families:
                    families.append(family)
                break
    return families


def preservation_class(value: str) -> str:
    """Collapse the free-text preservation coding into High/Partial/Low/N/A."""
    match = re.match(r"^\s*(high|partial|low|n\s*/?\s*a)\b", str(value), re.IGNORECASE)
    if not match:
        return "Unspecified"
    token = match.group(1).upper().replace(" ", "")
    if token.startswith("N"):
        return "N/A"
    return token.capitalize()


def _year_tokens(value: str) -> list[int]:
    return [int(y) for y in YEAR_RE.findall(str(value))]


def edition_anchor(value: str) -> int | None:
    """First year of the edition statement ('1824-1825' -> 1824, 'c. 1884' -> 1884)."""
    years = _year_tokens(value)
    return years[0] if years else None


def journey_anchor(value: str) -> int | None:
    """Midpoint (rounded down) of the documented journey years."""
    years = _year_tokens(value)
    if not years:
        return None
    return int((min(years) + max(years)) // 2)


def normalise_for_search(value: object) -> str:
    """Lower-case, accent-stripped text so 'Bogota' matches 'Bogotá'."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).lower().strip()


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, dict[str, object]]:
    """Load, validate and enrich the two deposited tables."""
    if not OBRAS_CSV.exists() or not EVIDENCIA_CSV.exists():
        raise FileNotFoundError(
            f"Expected {OBRAS_CSV.name} and {EVIDENCIA_CSV.name} beside app.py."
        )

    obras = pd.read_csv(OBRAS_CSV, dtype=str, keep_default_na=False)
    evidencia = pd.read_csv(EVIDENCIA_CSV, dtype=str, keep_default_na=False)

    missing_obras = [c for c in REQUIRED_OBRA_COLUMNS if c not in obras.columns]
    missing_ev = [c for c in REQUIRED_EVIDENCE_COLUMNS if c not in evidencia.columns]
    if missing_obras or missing_ev:
        raise ValueError(
            "Unexpected table schema. Missing columns: "
            f"obras={missing_obras}, evidencia={missing_ev}"
        )

    # Bibliographic fields come from the corpus table; the evidence table
    # duplicates them, so verify the two agree before dropping the duplicates.
    check = evidencia[["id_evidencia", "id_obra", "autor", "anio_edicion"]].merge(
        obras[["id_obra", "autor", "anio_edicion"]],
        on="id_obra",
        how="left",
        suffixes=("_evidencia", "_obras"),
    )
    inconsistent = check[
        (check["autor_evidencia"] != check["autor_obras"])
        | (check["anio_edicion_evidencia"] != check["anio_edicion_obras"])
    ]
    if not inconsistent.empty:
        raise ValueError(
            "Bibliographic metadata disagrees between the two tables for "
            f"{len(inconsistent)} record(s): "
            + ", ".join(inconsistent["id_evidencia"].head(5))
        )

    evidencia = evidencia.drop(columns=["autor", "anio_edicion"])
    merged = evidencia.merge(
        obras[
            [
                "id_obra",
                "autor",
                "anio_edicion",
                "anio_jornada",
                "idioma_original",
                "titulo_original",
                "rendimiento_material",
                "rol_en_corpus",
            ]
        ],
        on="id_obra",
        how="left",
        validate="many_to_one",
    )

    orphans = int(merged["autor"].isna().sum())

    # Derived analysis fields -------------------------------------------------
    merged["anio_edicion_anchor"] = merged["anio_edicion"].map(edition_anchor)
    merged["anio_jornada_anchor"] = merged["anio_jornada"].map(journey_anchor)
    merged["preservacion_clase"] = merged[
        "preservacion_arqueologica_esperada"
    ].map(preservation_class)
    merged["material_families"] = merged["materia_prima"].map(material_families)
    merged["material_families_label"] = merged["material_families"].map(
        lambda fams: "; ".join(fams) if fams else "—"
    )
    merged["idioma_original"] = merged["idioma_original"].str.lower().str.strip()

    # Strings used by the free-text search box.
    search_fields = [
        "id_evidencia",
        "autor",
        "termino_en_fuente",
        "termino_normalizado_glosario",
        "materia_prima",
        "categoria_descriptiva_es",
        "categoria_descriptiva_en",
        "subcategoria",
        "cita_textual",
        "resumen_contexto_en",
        "localizacion_pagina_folio",
    ]
    merged["_search_text"] = merged[search_fields].agg(
        lambda row: normalise_for_search(" | ".join(row.astype(str))), axis=1
    )

    stats: dict[str, object] = {
        "records": int(len(merged)),
        "works": int(merged["id_obra"].nunique()),
        "orphans": orphans,
        "missing_journey_year": int(merged["anio_jornada_anchor"].isna().sum()),
        "missing_edition_year": int(merged["anio_edicion_anchor"].isna().sum()),
    }
    return merged, stats


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #


def _year_range(df: pd.DataFrame, column: str) -> tuple[int, int]:
    values = df[column].dropna()
    if values.empty:
        return 1822, 1910
    return int(values.min()), int(values.max())


def _metric_row(df: pd.DataFrame) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Material records", f"{len(df):,}")
    col2.metric(
        "Unique glossary terms", f"{df['termino_normalizado_glosario'].nunique():,}"
    )
    col3.metric("Travelogues represented", f"{df['id_obra'].nunique()} of 17")


def _no_data_message() -> None:
    st.info(
        "No records match the current filters. Widen the year range or clear one "
        "of the filters in the sidebar."
    )


def _filters(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Render the sidebar and return the filtered dataframe plus context."""
    st.sidebar.header("Filters")

    axis_name = st.sidebar.radio(
        "Time axis",
        options=list(TIME_AXES),
        index=0,
        key="axis",
        help=(
            "Journey year dates the observation (recommended for diachronic "
            "questions). Publication year follows the brief and dates the printed "
            "edition, which can lag by decades."
        ),
    )
    axis = TIME_AXES[axis_name]
    year_column = axis["column"]

    min_year, max_year = _year_range(df, year_column)
    if min_year == max_year:
        year_range = (min_year, max_year)
        st.sidebar.caption(f"{axis['label']} range: {min_year}")
    else:
        year_range = st.sidebar.slider(
            f"{axis['label']} range",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
            step=1,
            key=f"year_range_{axis['column']}",
            help=axis["help"],
        )

    categories = sorted(df["categoria_analitica"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Analytical category",
        options=categories,
        default=categories,
        key="categories",
        help="Tránsito (materialities in transit) or Maneras de habitar (ways of dwelling).",
    )

    present_preservation = [
        value
        for value in PRESERVATION_ORDER
        if value in set(df["preservacion_clase"])
    ]
    selected_preservation = st.sidebar.multiselect(
        "Expected archaeological preservation",
        options=present_preservation,
        default=present_preservation,
        key="preservation",
        help=(
            "Taphonomic expectation coded in the dataset, collapsed from free text "
            "such as 'Low (organic leather)' into four classes."
        ),
    )

    present_families = sorted(
        {family for families in df["material_families"] for family in families}
    )

    with st.sidebar.expander("More filters"):
        descriptions = sorted(df["categoria_descriptiva_en"].dropna().unique().tolist())
        selected_descriptions = st.multiselect(
            "Descriptive category",
            options=descriptions,
            default=descriptions,
            key="descriptions",
            help="The six descriptive categories of the dataset taxonomy.",
        )

        selected_families = st.multiselect(
            "Material family",
            options=present_families,
            default=present_families,
            key="families",
            help=(
                "Derived from the free-text raw-material field; a record can belong "
                "to several families."
            ),
        )

        languages = sorted(df["idioma_original"].dropna().unique().tolist())
        selected_languages = st.multiselect(
            "Source language",
            options=languages,
            default=languages,
            key="languages",
            format_func=lambda code: {
                "en": "en — English",
                "es": "es — Spanish",
                "fr": "fr — French",
                "de": "de — German",
                "pt": "pt — Portuguese",
            }.get(code, code),
        )
        roles = sorted(df["rol_en_corpus"].dropna().unique().tolist())
        selected_roles = st.multiselect(
            "Corpus role",
            options=roles,
            default=roles,
            key="roles",
            format_func=lambda value: value.replace("_", " "),
            help=(
                "primaria_directa: direct primary source; "
                "primaria_con_control_intertextual: primary with intertextual control; "
                "contextual_comparativa: comparative context."
            ),
        )

    def reset_filters() -> None:
        for key in (
            "axis",
            "year_range_anio_jornada_anchor",
            "year_range_anio_edicion_anchor",
            "categories",
            "descriptions",
            "preservation",
            "families",
            "languages",
            "roles",
        ):
            st.session_state.pop(key, None)

    st.sidebar.button("Reset filters", on_click=reset_filters, width="stretch")

    mask = (
        df[year_column].notna()
        & df[year_column].between(year_range[0], year_range[1])
        & df["categoria_analitica"].isin(selected_categories)
        & df["categoria_descriptiva_en"].isin(selected_descriptions)
        & df["preservacion_clase"].isin(selected_preservation)
        & df["idioma_original"].isin(selected_languages)
        & df["rol_en_corpus"].isin(selected_roles)
    )
    families_set = set(selected_families)
    if families_set != set(present_families):
        mask &= df["material_families"].map(
            lambda families: bool(families_set.intersection(families))
        )

    filtered = df[mask.fillna(False)].copy()
    filtered["year_label"] = filtered[year_column].astype(int).astype(str)

    context = {
        "axis": axis,
        "axis_name": axis_name,
        "year_column": year_column,
        "year_range": year_range,
        "excluded_for_year": int(df[year_column].isna().sum()),
    }
    return filtered, context


def _sidebar_footer(stats: dict[str, object]) -> None:
    st.sidebar.divider()
    st.sidebar.caption(
        f"**{stats['records']} material records · {stats['works']} travelogues · "
        "6 descriptive categories**"
    )
    st.sidebar.markdown("**Data source**")
    st.sidebar.markdown(DATASET_CITATION, unsafe_allow_html=False)
    st.sidebar.caption("Dataset CC BY 4.0 · Dashboard code MIT")


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #


def render_timeline(filtered: pd.DataFrame, context: dict[str, object]) -> None:
    st.subheader("Material culture mentions over time")
    st.markdown(
        "Use this view to spot peaks, gaps and drops in the vocabulary of transit "
        "and dwelling along the corridor."
    )

    color_options = {
        "Analytical category (2)": "categoria_analitica",
        "Descriptive category (6)": "categoria_descriptiva_en",
    }
    controls_left, controls_right = st.columns([3, 1])
    with controls_left:
        color_choice = st.radio(
            "Colour lines by",
            options=list(color_options),
            horizontal=True,
            key="timeline_color",
        )
    with controls_right:
        aggregation = st.radio(
            "Resolution",
            options=["Exact year", "Decade"],
            horizontal=True,
            key="timeline_resolution",
            help=(
                "Exact years are faithful to the sources but sparse (16 sampled "
                "years over 90). Decades smooth the sampling noise and show the "
                "long-term trend."
            ),
        )
    color_column = color_options[color_choice]

    if filtered.empty:
        _no_data_message()
        return

    work = filtered.copy()
    if aggregation == "Decade":
        work["period"] = (work[context["year_column"]] // 10) * 10
        x_column = "period"
        x_label = "Decade (start year)"
        tick = 10
    else:
        x_column = context["year_column"]
        x_label = context["axis"]["label"]
        tick = _nice_dtick(context["year_range"])

    timeline = (
        work.groupby([x_column, color_column], dropna=False)
        .size()
        .reset_index(name="records")
        .sort_values(x_column)
    )
    color_map = (
        ANALYTICAL_COLORS
        if color_column == "categoria_analitica"
        else DESCRIPTIVE_COLORS
    )

    figure = px.line(
        timeline,
        x=x_column,
        y="records",
        color=color_column,
        markers=True,
        labels={
            x_column: x_label,
            "records": "Material records",
            color_column: color_choice.split(" (")[0],
        },
        color_discrete_map=color_map,
        template="plotly_white",
    )
    figure.update_traces(line_width=2, marker_size=7)
    figure.update_layout(
        hovermode="x unified",
        legend_title_text="",
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(rangemode="tozero"),
        xaxis=dict(dtick=tick, tickformat="d"),
    )
    st.plotly_chart(
        figure,
        width="stretch",
        config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d"]},
    )

    years = filtered[context["year_column"]].dropna()
    res_note = (
        "Decade bins (1880 = 1880–1889) pool the sparse sampling; counts are "
        "summed records per decadal class."
        if aggregation == "Decade"
        else "Exact years are linked by straight segments; read gaps as absences "
        "of sampled travelogues, not necessarily of the objects."
    )
    st.caption(
        f"{len(filtered)} records · {filtered['id_obra'].nunique()} travelogues · "
        f"{int(years.min())}–{int(years.max())} · "
        f"{int(years.nunique())} distinct years in view. {res_note}"
    )


def _nice_dtick(year_range: tuple[int, int]) -> int:
    span = max(1, year_range[1] - year_range[0])
    for step in (5, 10, 20, 25, 50):
        if span / step <= 12:
            return step
    return 20


def render_materiality(filtered: pd.DataFrame) -> None:
    st.subheader("Material composition & taphonomy")
    left, right = st.columns(2)

    with left:
        if filtered.empty:
            _no_data_message()
            return
        exploded = filtered.explode("material_families").dropna(
            subset=["material_families"]
        )
        counts = (
            exploded["material_families"]
            .value_counts()
            .rename_axis("material_family")
            .reset_index(name="records")
        )
        top = counts.head(10).sort_values("records")
        figure = px.bar(
            top,
            x="records",
            y="material_family",
            orientation="h",
            title="Top 10 raw-material families mentioned",
            template="plotly_white",
            labels={"records": "Records mentioning", "material_family": ""},
        )
        figure.update_traces(marker_color="#8A4B2A", opacity=0.85)
        figure.update_layout(
            margin=dict(l=10, r=10, t=45, b=10),
            yaxis=dict(categoryorder="total ascending"),
            bargap=0.25,
        )
        st.plotly_chart(
            figure,
            width="stretch",
            config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d"]},
        )
        no_material = int(
            filtered["material_families"].map(lambda families: len(families) == 0).sum()
        )
        st.caption(
            "Derived by parsing the free-text `materia_prima` field; records can "
            "cite several families. "
            + (
                f"{no_material} record(s) in view specify no raw material."
                if no_material
                else ""
            )
        )

    with right:
        if filtered.empty:
            return
        preservation_counts = (
            filtered["preservacion_clase"]
            .value_counts()
            .rename_axis("preservation")
            .reset_index(name="records")
        )
        figure = px.pie(
            preservation_counts,
            names="preservation",
            values="records",
            title="Expected archaeological preservation",
            hole=0.42,
            color="preservation",
            color_discrete_map=PRESERVATION_COLORS,
            category_orders={"preservation": PRESERVATION_ORDER},
            template="plotly_white",
        )
        figure.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="%{label}: %{value} records (%{percent})<extra></extra>",
        )
        figure.update_layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=45, b=10),
        )
        st.plotly_chart(
            figure,
            width="stretch",
            config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d"]},
        )
        low_share = (
            filtered["preservacion_clase"].eq("Low").mean() * 100 if len(filtered) else 0
        )
        st.caption(
            "Coded taphonomic expectation for humid tropical Andean soils. "
            f"{low_share:.0f}% of records in view are expected to leave little or no "
            "trace — the visibility gap this dataset is designed to quantify."
        )


def render_evidence(filtered: pd.DataFrame, context: dict[str, object]) -> None:
    st.subheader("Verbatim evidence")
    st.markdown(
        "Search and filter the quotes extracted from the travelogues. Searches run "
        "over the quote, its English summary, the glossary term, the raw materials "
        "and the author."
    )

    query = st.text_input(
        "Search for a term (e.g., 'mochila', 'vidrio', 'piano'):",
        value="",
        key="evidence_search",
    )

    display = filtered
    is_search = bool(query.strip())
    if is_search:
        needle = normalise_for_search(query)
        display = filtered[filtered["_search_text"].str.contains(needle, regex=False)]

    if display.empty:
        if query.strip():
            st.warning(
                f"No records in the current selection match “{query}”. Try a shorter "
                "stem (e.g. 'vidr' for vidrio) or widen the filters."
            )
        else:
            _no_data_message()
        return

    columns = [column for column, _ in TABLE_COLUMNS if column in display.columns]
    labels = dict(TABLE_COLUMNS)
    table = display[columns].rename(columns=labels)

    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("ID", width=60),
            "Year": st.column_config.TextColumn("Year", width=50),
            "Author": st.column_config.TextColumn("Author", width=100),
            "Glossary term": st.column_config.TextColumn(
                "Glossary term", width=125
            ),
            "Raw materials": st.column_config.TextColumn(
                "Raw materials", width=120
            ),
            "Material families": st.column_config.TextColumn(
                "Material families", width=120
            ),
            "Preservation": st.column_config.TextColumn(
                "Preservation", width=110
            ),
            "Verbatim quote": st.column_config.TextColumn(
                "Verbatim quote", width=155
            ),
            "English summary": st.column_config.TextColumn(
                "English summary", width=155
            ),
            "Page": st.column_config.TextColumn("Page", width=65),
        },
    )

    st.caption(
        "Hover any cell for the full text; the card view below shows the complete "
        "quote, summary and category of each record."
    )

    st.caption(
        f"{len(display)} record(s) shown"
        + (f" of {len(filtered)} in the current filter" if is_search else "")
        + f" · {context['axis']['label'].lower()} in view"
    )

    export = display.drop(
        columns=[c for c in ("_search_text", "material_families") if c in display],
        errors="ignore",
    )
    st.download_button(
        "Download this selection as CSV",
        data=export.to_csv(index=False).encode("utf-8-sig"),
        file_name="camino_real_material_culture_selection.csv",
        mime="text/csv",
    )

    with st.expander("Read the records as cards"):
        st.caption(
            "A reading view for close analysis: quote, English summary and coding "
            "for up to 25 records in the current selection."
        )
        for _, row in display.head(25).iterrows():
            st.markdown(
                f"**{row['id_evidencia']} · {row['autor']} "
                f"({row['year_label']}) · {row['categoria_descriptiva_en']}**  \n"
                f"> {row['cita_textual']}  \n"
                f"*{row['resumen_contexto_en']}*  \n"
                f"`{row['termino_normalizado_glosario']}` · "
                f"{row['materia_prima']} · "
                f"preservation: {row['preservacion_clase']} · "
                f"{row['localizacion_pagina_folio']}"
            )
            st.divider()


def render_about(stats: dict[str, object]) -> None:
    with st.expander("About the data, the coding and how to read this dashboard"):
        st.markdown(
            f"""
**What this is.** An exploratory EDA environment over the material-culture
records extracted from 17 nineteenth-century travelogues along the Camino Real
between Honda and Santafé de Bogotá (Colombia, 1822–1910). It is a companion to
the open dataset ({DATASET_DOI}, CC BY 4.0), not a substitute for reading the
sources.

**Records.** {stats['records']} material-culture records, {stats['works']}
travelogues, six descriptive categories and two analytical domains (*Tránsito*,
*Maneras de habitar*). Each record carries the verbatim quote in its original
language, an English analytical summary, a controlled glossary term, and two
coded attributes used here: raw-material composition and expected taphonomic
preservation.

**Derived fields (computed in-app, documented in README.md).**
- *Journey year* — midpoint (rounded down) of the documented journey/stay.
  Recommended for diachrony because it dates the observation. *Publication year*
  — first year of the edition statement, as in the brief; it can lag the journey
  by decades (Le Moyne travelled 1828–1839 and published in 1880).
- *Preservation class* — the dataset's free-text coding collapsed into High,
  Partial, Low, N/A and Unspecified; the original string is still shown in the
  evidence table.
- *Material families* — the free-text `materia_prima` field tokenised and mapped
  onto broad classes (wood, leather, iron, ceramic, textile, etc.). A record can
  belong to several families; treat the chart as mention counts, not as a
  partition of the corpus.

**How to read it.** The corpus is small (n = {stats['records']} over 90 years),
so year-on-year variation is thin and partly reflects sampling: which travelogues
survive, who published, and which stretches of road they described. Read the
timeline as a shape, not as a time series. The preservation chart is an
*expectation* coded by the dataset authors, not an observed archaeological
assemblage — it is the hypothesis to test in the field.

**Provenance.** The two CSVs are used verbatim as deposited in Zenodo v1.0.0;
the only transformations are the derived columns described above.
"""
        )
        st.markdown("**Cite the dataset**")
        st.markdown(DATASET_CITATION)
        st.caption(
            "Dashboard built with Streamlit, pandas and Plotly. Code MIT; data CC BY 4.0."
        )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> None:
    st.set_page_config(
        page_title="Camino Real Lexical Time Machine",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Camino Real Lexical Time Machine")
    st.markdown(
        "*An exploratory dashboard of nineteenth-century material culture along the "
        "Honda–Santafé de Bogotá corridor (1822–1910).*"
    )

    try:
        df, stats = load_data()
    except FileNotFoundError:
        st.error(
            "⚠ Data files not found. Keep `01_obras_corpus.csv` and "
            "`03_evidencia_material.csv` in the same folder as `app.py`."
        )
        st.stop()
    except ValueError as error:
        st.error(f"⚠ Could not load the dataset: {error}")
        st.stop()

    filtered, context = _filters(df)
    _sidebar_footer(stats)

    if filtered.empty:
        _metric_row(filtered)
        _no_data_message()
        render_about(stats)
        return

    _metric_row(filtered)
    st.caption(
        f"{context['axis']['label']} {context['year_range'][0]}–"
        f"{context['year_range'][1]} · "
        f"{len(filtered)} of {stats['records']} records in view"
        + (
            f" · {context['excluded_for_year']} record(s) have no parseable year"
            if context["excluded_for_year"]
            else ""
        )
    )
    st.divider()

    tab_timeline, tab_materiality, tab_evidence = st.tabs(
        ["Timeline analysis", "Materiality & taphonomy", "Verbatim evidence"]
    )
    with tab_timeline:
        render_timeline(filtered, context)
    with tab_materiality:
        render_materiality(filtered)
    with tab_evidence:
        render_evidence(filtered, context)

    render_about(stats)
    st.divider()
    st.caption(
        f"Dataset: [Suescún, Herrera & Therrien (2026), Zenodo "
        f"{DATASET_DOI}]({DATASET_URL}) · CC BY 4.0. "
        "Dashboard: exploratory only — read the sources before citing a pattern."
    )


if __name__ == "__main__":
    main()
