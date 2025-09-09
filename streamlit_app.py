import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import io

# --- Words to Exclude from Keyword Analysis (from the original script) ---
EXCLUSION_LIST = {
    # Generic Documentation Terms
    'documentation', 'overview', 'guide', 'prerequisites', 'steps', 'introduction',
    'feature', 'features', 'alation', 'article', 'articles', 'note', 'see', 'use',
    'using', 'info', 'information', 'details', 'detail',
    # Broad/Context-Specific
    'ports', 'load', 'balancers', 'proxy', 'servers', 'customer-managed', 'cloud', 'service',
    'zip', 'file', 'data', 'catalog', 'instance', 'instances',
    # UI References
    'toggle', 'button', 'click', 'preview', 'import', 'run', 'tab', 'page', 'pages', 'ui',
    'select', 'view', 'edit', 'navigation', 'panel', 'field', 'fields', 'option', 'options',
    'dialog', 'window', 'menu', 'link',
    # Placeholders/Generic Variables
    'name', 's3', 'bucket', 'sql', 'template', 'placeholder', 'values', 'value', 'example',
    'following', 'table', 'column', 'columns', 'user', 'users', 'role', 'roles',
    # SQL/Code Keywords
    'by', 'struct', 'row', 'format', 'tblproperties', 'and', 'or', 'not', 'from', 'where',
    'select', 'group', 'order', 'if', 'then', 'else', 'com', 'https', 'http', 'www',
    # Release Status
    'general', 'availability', 'ga', 'beta',
    # Common English stop words
    'a', 'an', 'the', 'is', 'are', 'in', 'on', 'of', 'for', 'to', 'with', 'it', 'you', 'can',
    'be', 'as', 'at', 'so', 'this', 'that', 'these', 'those', 'will'
}

# --- Core Analysis Functions (adapted for Streamlit) ---

def load_terms_from_uploader(uploaded_file):
    """Loads a list of terms from a Streamlit UploadedFile object."""
    if uploaded_file is None:
        return []
    # Use io.StringIO to treat the string data as a file
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    terms = [line.strip() for line in stringio if line.strip()]
    terms.sort(key=len, reverse=True)
    return terms

@st.cache_data
def analyze_page(url):
    """Caches the result of fetching and parsing a URL to speed up reruns."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title').get_text().strip() if soup.find('title') else 'No Title Found'
        return soup, title
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch {url}: {e}")
        return None, "Fetch Error"

def get_deployment_type(soup):
    if not soup: return "Analysis Error"
    has_cloud = soup.find('p', class_='cloud-label') is not None
    has_on_prem = soup.find('p', class_='on-prem-label') is not None
    if has_cloud and has_on_prem: return "Alation Cloud Service, Customer Managed"
    if has_cloud: return "Alation Cloud Service"
    if has_on_prem: return "Customer Managed"
    return ""

def map_metadata(text_content, term_list):
    if not text_content or not term_list: return ""
    text_lower = text_content.lower()
    found_terms = [term for term in term_list if re.search(r'\b' + re.escape(term.lower()) + r'\b', text_lower)]
    return ', '.join(found_terms)

def extract_keywords(soup, title):
    if not soup: return "Analysis Error"
    content_area = soup.find('article') or soup.find('main') or soup.body
    if not content_area: return "No Content Found"
    
    text = content_area.get_text()
    words = re.findall(r'\b[a-z-]{3,}\b', text.lower())
    filtered_words = [word for word in words if word not in EXCLUSION_LIST]
    word_counts = Counter(filtered_words)
    top_keywords = [word for word, count in word_counts.most_common(20)]

    if "ocf connector" in title.lower():
        match = re.search(r'(\w+)\s+ocf\s+connector', title.lower())
        if match:
            connector_name = match.group(1).capitalize()
            connector_keywords = [f"{connector_name} OCF Connector", f"{connector_name} data source"]
            final_keywords = connector_keywords + [kw for kw in top_keywords if kw not in connector_keywords]
            top_keywords = final_keywords[:20]

    return ', '.join(top_keywords)

# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("📄 Content Analysis and Keyword Extraction App")

st.markdown("""
This application automates the process of content analysis for a list of URLs. 
1.  **Upload your files** in the sidebar.
2.  Click the **"Run Analysis"** button.
3.  View the results and **download the final CSV report**.
""")

# Sidebar for file uploads
with st.sidebar:
    st.header("1. Upload Your Files")
    urls_file = st.file_uploader("Upload URLs File (.txt)", type="txt")
    topics_file = st.file_uploader("Upload Topics File (.txt)", type="txt")
    areas_file = st.file_uploader("Upload Functional Areas File (.txt)", type="txt")
    roles_file = st.file_uploader("Upload User Roles File (.txt)", type="txt")

# Main application body
st.header("2. Run Analysis")

if st.button("🚀 Run Analysis", type="primary"):
    if urls_file and topics_file and areas_file and roles_file:
        # Load data from uploaded files
        urls = [line.strip() for line in io.StringIO(urls_file.getvalue().decode("utf-8")) if line.strip()]
        topics_list = load_terms_from_uploader(topics_file)
        areas_list = load_terms_from_uploader(areas_file)
        roles_list = load_terms_from_uploader(roles_file)

        st.info(f"Found {len(urls)} URLs. Starting analysis... Please wait.")
        
        results = []
        progress_bar = st.progress(0, text="Starting...")

        for i, url in enumerate(urls):
            progress_text = f"Processing URL {i+1}/{len(urls)}: {url.split('/')[-1]}"
            progress_bar.progress((i + 1) / len(urls), text=progress_text)
            
            soup, title = analyze_page(url)
            if soup:
                deployment_type = get_deployment_type(soup)
                keywords = extract_keywords(soup, title)
                content_text = (soup.find('article') or soup.find('main') or soup.body).get_text()
                
                mapped_roles = map_metadata(content_text, roles_list)
                mapped_areas = map_metadata(content_text, areas_list)
                mapped_topics = map_metadata(content_text, topics_list)

                results.append({
                    'Page Title': title,
                    'Page URL': url,
                    'Deployment Type': deployment_type,
                    'User Role': mapped_roles,
                    'Functional Area': mapped_areas,
                    'Topics': mapped_topics,
                    'Keywords': keywords
                })
            else:
                 results.append({
                    'Page Title': title, 'Page URL': url, 'Deployment Type': 'Fetch Error',
                    'User Role': '', 'Functional Area': '', 'Topics': '', 'Keywords': ''
                })
        
        # Store results in session state to persist them
        st.session_state.report_df = pd.DataFrame(results)
        progress_bar.empty() # Clear the progress bar
        st.success("✅ Analysis complete!")

    else:
        st.warning("⚠️ Please upload all four required files in the sidebar.")

# Display results if they exist in the session state
if 'report_df' in st.session_state:
    st.header("3. View and Download Results")
    
    st.dataframe(st.session_state.report_df)
    
    # Convert DataFrame to CSV for downloading
    csv_data = st.session_state.report_df.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 Download Report as CSV",
        data=csv_data,
        file_name="content_analysis_report.csv",
        mime="text/csv",
    )