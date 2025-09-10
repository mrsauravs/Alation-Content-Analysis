import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
from huggingface_hub import InferenceClient

def analyze_page_for_deployment(url):
    """Fetches and parses a URL for title and deployment type analysis."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title').get_text().strip() if soup.find('title') else 'No Title Found'
        return soup, title
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch {url}: {e}")
        return None, "Fetch Error"

def get_deployment_type_from_scraping(soup):
    """Determines deployment type from parsed HTML based on specific class labels."""
    if not soup: return ""
    has_cloud = soup.find('p', class_='cloud-label') is not None
    has_on_prem = soup.find('p', class_='on-prem-label') is not None
    if has_cloud and has_on_prem: return "Alation Cloud Service, Customer Managed"
    if has_cloud: return "Alation Cloud Service"
    if has_on_prem: return "Customer Managed"
    return ""

@st.cache_data
def get_deployment_type_with_llm(_client, soup):
    """
    Uses an LLM to infer deployment type if scraping fails.
    The _client parameter is used for caching.
    """
    if not soup:
        return "Analysis Error"

    main_content = soup.find('article') or soup.find('main') or soup.body
    if not main_content:
        return "Content Not Found"

    content_text = main_content.get_text(separator=' ', strip=True)[:15000]

    prompt = f"""
    You are an expert text classifier. Read the following technical documentation content and determine if it applies to "Alation Cloud Service", "Customer Managed", or both.

    Your answer MUST be one of these three options ONLY:
    - Alation Cloud Service
    - Customer Managed
    - Alation Cloud Service, Customer Managed

    Do not provide any explanation or other text.

    Content:
    ---
    {content_text}
    ---

    Based on the content, the correct deployment type is:
    """

    try:
        response = _client.text_generation(prompt, model="mistralai/Mixtral-8x7B-Instruct-v0.1", max_new_tokens=20)
        cleaned_response = response.strip()
        valid_responses = ["Alation Cloud Service", "Customer Managed", "Alation Cloud Service, Customer Managed"]
        if cleaned_response in valid_responses:
            return f"{cleaned_response} (Inferred by LLM)"
        else:
            return "LLM Inference Failed"
            
    except Exception as e:
        st.error(f"LLM API Error: {e}")
        return "LLM API Error"

st.set_page_config(layout="wide")
st.title("📄 Intelligent Deployment Type Mapper")

st.markdown("""
This application scrapes a list of URLs to identify their deployment type. For pages without a clear HTML tag, it uses an AI model to infer the correct type.

1.  **Upload a `.txt` file** containing one URL per line using the sidebar.
2.  Click the **"Map Deployment Types"** button to start the analysis.
""")

try:
    HF_TOKEN = st.secrets["HUGGING_FACE_TOKEN"]
except KeyError:
    st.error("HUGGING_FACE_TOKEN secret not found. Please add it to your Streamlit Cloud settings.")
    HF_TOKEN = None

with st.sidebar:
    st.header("Upload URLs")
    urls_file = st.file_uploader("Upload URLs File (.txt)", type="txt")

st.header("Run Analysis")

if st.button("🚀 Map Deployment Types", type="primary", disabled=(not HF_TOKEN)):
    if urls_file and HF_TOKEN:
        client = InferenceClient(token=HF_TOKEN)
        urls = [line.strip() for line in io.StringIO(urls_file.getvalue().decode("utf-8")) if line.strip()]

        st.info(f"Found {len(urls)} URLs. Starting analysis... Please wait.")
        
        results = []
        progress_bar = st.progress(0, text="Starting...")

        for i, url in enumerate(urls):
            progress_text = f"Processing URL {i+1}/{len(urls)}: {url.split('/')[-1]}"
            progress_bar.progress((i + 1) / len(urls), text=progress_text)
            
            soup, title = analyze_page_for_deployment(url)
            
            if soup:
                deployment_type = get_deployment_type_from_scraping(soup)
                if not deployment_type:
                    deployment_type = get_deployment_type_with_llm(client, soup)
                results.append({'Page Title': title, 'Page URL': url, 'Deployment Type': deployment_type})
            else:
                 results.append({'Page Title': title, 'Page URL': url, 'Deployment Type': 'Fetch Error'})
        
        st.session_state.report_df = pd.DataFrame(results)
        progress_bar.empty()
        st.success("✅ Analysis complete!")
    else:
        st.warning("⚠️ Please upload a URLs file in the sidebar.")

if 'report_df' in st.session_state:
    st.header("View and Download Results")
    st.dataframe(st.session_state.report_df)
    csv_data = st.session_state.report_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(label="📥 Download Report as CSV", data=csv_data, file_name="intelligent_deployment_report.csv", mime="text/csv")

