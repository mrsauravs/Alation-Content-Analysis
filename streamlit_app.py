import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re
from collections import Counter

# --- Text Analysis and Keyword Generation ---

STOP_WORDS = set([
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can', 'did',
    'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'has',
    'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'i', 'if',

    'in', 'into', 'is', 'it', 'its', 'itself', 'just', 'me', 'more', 'most', 'my', 'myself', 'no', 'nor',
    'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out',
    'over', 'own', 's', 'same', 'she', 'should', 'so', 'some', 'such', 't', 'than', 'that', 'the',
    'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this', 'those',
    'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when',
    'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'you', 'your', 'yours',
    'yourself', 'yourselves', 'use', 'using', 'see', 'following', 'may', 'also', 'able', 'need'
])

EXCLUSION_KEYWORDS = set([
    "documentation", "overview", "guide", "prerequisites", "steps", "introduction", "ports",
    "load balancers", "proxy servers", "customer-managed", "Alation Cloud Service", "Zip file",
    "data catalog", "toggle", "button", "click", "Preview", "Import", "Run", "table name",
    "S3 bucket name", "SQL template", "placeholder values", "select", "from", "where", "update",
    "insert", "delete", "join", "group by", "order by", "ga", "beta", "alpha", "deprecated"
])

def generate_keywords(text):
    """Generates a list of 20 unique technical keywords based on provided guidelines."""
    if not isinstance(text, str) or not text.strip():
        return '""'

    # Preprocess text
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    
    # Remove stop words
    filtered_words = [word for word in words if word not in STOP_WORDS and len(word) > 1]
    
    # Generate 1, 2, and 3-word phrases (n-grams)
    ngrams = []
    ngrams.extend(filtered_words)
    ngrams.extend([' '.join(filtered_words[i:i+2]) for i in range(len(filtered_words)-1)])
    ngrams.extend([' '.join(filtered_words[i:i+3]) for i in range(len(filtered_words)-2)])

    # Filter out n-grams containing any exclusion keyword
    valid_ngrams = []
    for ngram in ngrams:
        if not any(excluded in ngram.split() for excluded in EXCLUSION_KEYWORDS):
            valid_ngrams.append(ngram)
            
    # Rank by frequency
    keyword_counts = Counter(valid_ngrams)
    
    # Start building the final keyword list
    final_keywords = []

    # Special OCF Connector Rule
    ocf_match = re.search(r'(\w+\s+OCF\s+Connector)', text, re.IGNORECASE)
    if ocf_match:
        full_connector_name = ocf_match.group(1)
        data_source_name = full_connector_name.replace(" OCF Connector", " data source")
        final_keywords.append(full_connector_name)
        final_keywords.append(data_source_name)

    # Add the most common keywords, ensuring uniqueness
    for keyword, _ in keyword_counts.most_common(50): # Look at top 50 candidates
        if keyword not in final_keywords:
            final_keywords.append(keyword)
        if len(final_keywords) >= 20:
            break
            
    # Truncate to exactly 20 keywords
    final_keywords = final_keywords[:20]

    # Format for CSV
    return f'"{", ".join(final_keywords)}"'

# --- Utility and Scraping Functions ---

@st.cache_data
def analyze_page_content(url):
    """Fetches and parses a URL for its title and HTML content."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title').get_text().strip() if soup.find('title') else 'No Title Found'
        return soup, title
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch {url}: {e}")
        return None, "Fetch Error"

def get_deployment_type_from_scraping(soup):
    """Determines deployment type from parsed HTML."""
    if not soup: return ""
    if soup.find('p', class_='cloud-label') and soup.find('p', class_='on-prem-label'):
        return "Alation Cloud Service, Customer Managed"
    if soup.find('p', class_='cloud-label'): return "Alation Cloud Service"
    if soup.find('p', class_='on-prem-label'): return "Customer Managed"
    return "Tag Not Found"

def extract_main_content(soup):
    """Extracts main content by cleaning out boilerplate elements."""
    if not soup:
        return "Content Not Available"
    main_content = soup.find('article') or soup.find('main') or soup.body
    if main_content:
        for element in main_content.find_all(['nav', 'header', 'footer', 'aside']):
            element.decompose()
        return main_content.get_text(separator=' ', strip=True)
    return "Main Content Not Found"

# --- Mapping Helper Functions ---

def is_standalone_word(text, match):
    """Checks if a regex match is a standalone word."""
    start, end = match.start(), match.end()
    is_start_ok = (start == 0) or (text[start - 1].isspace() or text[start - 1] in '(),."\'')
    is_end_ok = (end == len(text)) or (text[end].isspace() or text[end] in '(),."\'')
    return is_start_ok and is_end_ok

def find_keywords_in_text(text, keywords):
    """Finds which keywords from a list are present in the text."""
    if not isinstance(text, str): return "Not Searched"
    found = []
    for keyword in keywords:
        for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            if is_standalone_word(text, match):
                found.append(keyword)
                break
    return ", ".join(found) if found else "No Keywords Found"


# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("📄 Web Content and Keyword Generator")
st.markdown("A four-step tool to scrape content, map roles and topics, and generate technical keywords.")

with st.expander("Step 1: Scrape Content from URLs", expanded=True):
    urls_file_step1 = st.file_uploader("Upload URLs File (.txt)", key="step1")
    if st.button("🚀 Scrape URLs", type="primary"):
        if urls_file_step1:
            urls = [line.strip() for line in io.StringIO(urls_file_step1.getvalue().decode("utf-8")) if line.strip()]
            results, pb = [], st.progress(0, "Starting...")
            for i, url in enumerate(urls):
                pb.progress((i + 1) / len(urls), f"Processing URL {i+1}/{len(urls)}...")
                soup, title = analyze_page_content(url)
                data = {'Page Title': title, 'Page URL': url}
                if soup:
                    data.update({
                        'Deployment Type': get_deployment_type_from_scraping(soup),
                        'Page Content': extract_main_content(soup)
                    })
                else:
                    data.update({'Deployment Type': 'Fetch Error', 'Page Content': 'Fetch Error'})
                results.append(data)
            
            st.session_state.df1 = pd.DataFrame(results)
            for key in ['df2', 'df3', 'df4']:
                if key in st.session_state: del st.session_state[key]
            st.success("✅ Step 1 complete! Proceed to Step 2.")
        else:
            st.warning("⚠️ Please upload a URLs file.")

if 'df1' in st.session_state:
    with st.expander("Step 2: Map User Roles", expanded=True):
        roles_file = st.file_uploader("Upload User Roles File (.txt)", key="step2")
        if st.button("🗺️ Map User Roles"):
            if roles_file:
                roles = [line.strip() for line in io.StringIO(roles_file.getvalue().decode("utf-8")) if line.strip()]
                if roles:
                    df = st.session_state.df1.copy()
                    df['User Roles'] = df['Page Content'].apply(lambda txt: find_keywords_in_text(txt, roles))
                    st.session_state.df2 = df
                    for key in ['df3', 'df4']:
                        if key in st.session_state: del st.session_state[key]
                    st.success("✅ Step 2 complete! Proceed to Step 3.")
                else: st.warning("⚠️ Roles file is empty.")
            else: st.warning("⚠️ Please upload a roles file.")

if 'df2' in st.session_state:
    with st.expander("Step 3: Map Topics", expanded=True):
        topics_file = st.file_uploader("Upload Topics File (.txt)", key="step3")
        if st.button("🏷️ Map Topics"):
            if topics_file:
                topics = [line.strip() for line in io.StringIO(topics_file.getvalue().decode("utf-8")) if line.strip()]
                if topics:
                    df = st.session_state.df2.copy()
                    df['Topics'] = df['Page Content'].apply(lambda txt: find_keywords_in_text(txt, topics))
                    st.session_state.df3 = df
                    if 'df4' in st.session_state: del st.session_state['df4']
                    st.success("✅ Step 3 complete! Proceed to Step 4.")
                else: st.warning("⚠️ Topics file is empty.")
            else: st.warning("⚠️ Please upload a topics file.")

if 'df3' in st.session_state:
    with st.expander("Step 4: Generate Technical Keywords", expanded=True):
        if st.button("🤖 Generate Keywords"):
            df = st.session_state.df3.copy()
            total = len(df)
            pb = st.progress(0, f"Generating keywords for 1/{total}...")
            keywords_list = []
            for i, row in df.iterrows():
                pb.progress((i + 1) / total, f"Generating keywords for {i+1}/{total}...")
                keywords_list.append(generate_keywords(row['Page Content']))
            df['Keywords'] = keywords_list
            st.session_state.df4 = df
            st.success("✅ Keyword generation complete! The final report is ready.")

st.markdown("---")
st.subheader("📊 Results")

df_to_display, file_name = pd.DataFrame(), "scraped_report.csv"
if 'df4' in st.session_state:
    df_to_display, file_name = st.session_state.df4, "final_keyword_report.csv"
elif 'df3' in st.session_state:
    df_to_display, file_name = st.session_state.df3, "topics_mapped_report.csv"
elif 'df2' in st.session_state:
    df_to_display, file_name = st.session_state.df2, "roles_mapped_report.csv"
elif 'df1' in st.session_state:
    df_to_display = st.session_state.df1

if not df_to_display.empty:
    st.dataframe(df_to_display)
    csv_data = df_to_display.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Download Full Report (CSV)", csv_data, file_name, "text/csv")
else:
    st.write("Upload a file in Step 1 and click 'Scrape URLs' to generate a report.")
