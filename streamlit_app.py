import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
from huggingface_hub import InferenceClient
import re
from collections import Counter
import json

# --- Utility and Scraping Functions ---

@st.cache_data
def analyze_page_content(url):
    """Fetches and parses a URL for title and main content analysis."""
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

# --- LLM Analysis Functions ---

@st.cache_data
def get_deployment_type_with_llm(_client, soup):
    """Uses an LLM to infer deployment type if scraping fails."""
    if not soup: return "Analysis Error"
    main_content = soup.find('article') or soup.find('main') or soup.body
    content_text = main_content.get_text(separator=' ', strip=True)[:15000] if main_content else ""

    prompt = f"""You are an expert text classifier. Read the following content and determine if it applies to "Alation Cloud Service", "Customer Managed", or both. Your answer MUST be one of those three options ONLY, with no other text.
    Content: --- {content_text} ---
    Based on the content, the correct deployment type is:"""
    
    try:
        response = _client.text_generation(prompt, model="mistralai/Mixtral-8x7B-Instruct-v0.1", max_new_tokens=20)
        cleaned_response = response.strip()
        valid_responses = ["Alation Cloud Service", "Customer Managed", "Alation Cloud Service, Customer Managed"]
        return f"{cleaned_response} (Inferred by LLM)" if cleaned_response in valid_responses else "LLM Inference Failed"
    except Exception:
        return "LLM API Error"

@st.cache_data
def get_full_analysis_with_llm(_client, soup, roles, areas, topics):
    """Uses an LLM for keyword generation and metadata mapping."""
    if not soup: return {}
    main_content = soup.find('article') or soup.find('main') or soup.body
    content_text = main_content.get_text(separator=' ', strip=True)[:15000] if main_content else ""

    prompt = f"""
    You are an expert content analyst. Analyze the provided technical documentation content.
    
    Perform the following two tasks:
    1.  **Metadata Mapping:** From the provided lists, select the MOST RELEVANT User Role(s), Functional Area(s), and Topic(s). Choose only the best fit.
    2.  **Keyword Generation:** Generate exactly 20 unique, comma-separated technical keywords from the content. Exclude generic words like 'guide', 'documentation', 'button', 'click', 'data', 'alation'.

    **Available User Roles:** {', '.join(roles)}
    **Available Functional Areas:** {', '.join(areas)}
    **Available Topics:** {', '.join(topics)}

    **Content to Analyze:**
    ---
    {content_text}
    ---
    
    Provide your response in a single JSON object format like this example:
    {{
      "user_role": "Steward, Catalog Admin",
      "functional_area": "Data Quality",
      "topics": "Data Quality Monitors, Troubleshooting",
      "keywords": "keyword1, keyword2, keyword3, keyword4, keyword5, keyword6, keyword7, keyword8, keyword9, keyword10, keyword11, keyword12, keyword13, keyword14, keyword15, keyword16, keyword17, keyword18, keyword19, keyword20"
    }}
    """
    
    try:
        response_text = _client.text_generation(prompt, model="mistralai/Mixtral-8x7B-Instruct-v0.1", max_new_tokens=512)
        # Extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "Failed to parse LLM response"}
    except Exception:
        return {"error": "LLM API Error"}

# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("📄 Intelligent Content Analysis Workflow")

# --- Secure Token Management ---
try:
    HF_TOKEN = st.secrets["HUGGING_FACE_TOKEN"]
except KeyError:
    st.error("HUGGING_FACE_TOKEN secret not found. Please add it to your Streamlit Cloud deployment settings.")
    HF_TOKEN = None

# --- App Navigation ---
app_mode = st.sidebar.radio("Choose a Step", ["Step 1: Map Deployment Types", "Step 2: Run Full Content Analysis"])

if app_mode == "Step 1: Map Deployment Types":
    st.header("Step 1: Map Deployment Types")
    st.markdown("Upload a `.txt` file of URLs. This tool will scrape each URL for its deployment type, using an AI model for pages without clear tags. Download the resulting CSV to use in Step 2.")
    
    with st.sidebar:
        urls_file_step1 = st.file_uploader("Upload URLs File (.txt)", type="txt", key="step1_uploader")

    if st.button("🚀 Map Deployment Types", type="primary", disabled=(not HF_TOKEN)):
        if urls_file_step1 and HF_TOKEN:
            client = InferenceClient(token=HF_TOKEN)
            urls = [line.strip() for line in io.StringIO(urls_file_step1.getvalue().decode("utf-8")) if line.strip()]
            
            results, progress_bar = [], st.progress(0, "Starting...")
            for i, url in enumerate(urls):
                progress_bar.progress((i + 1) / len(urls), f"Processing URL {i+1}/{len(urls)}")
                soup, title = analyze_page_content(url)
                if soup:
                    dtype = get_deployment_type_from_scraping(soup) or get_deployment_type_with_llm(client, soup)
                    results.append({'Page Title': title, 'Page URL': url, 'Deployment Type': dtype})
                else:
                    results.append({'Page Title': title, 'Page URL': url, 'Deployment Type': 'Fetch Error'})
            
            st.session_state.report_df_step1 = pd.DataFrame(results)
            st.success("✅ Step 1 complete! You can now download the report.")

    if 'report_df_step1' in st.session_state:
        st.subheader("Results")
        st.dataframe(st.session_state.report_df_step1)
        csv_data = st.session_state.report_df_step1.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Deployment Report (CSV)", csv_data, "deployment_report.csv", "text/csv")

elif app_mode == "Step 2: Run Full Content Analysis":
    st.header("Step 2: Run Full Content Analysis")
    st.markdown("Upload the CSV from Step 1, along with `.txt` files for topics, functional areas, and user roles. The AI will analyze each URL's content to map metadata and generate keywords.")

    with st.sidebar:
        csv_file_step2 = st.file_uploader("Upload Deployment Report (.csv)", type="csv", key="step2_csv_uploader")
        topics_file = st.file_uploader("Upload Topics File (.txt)", type="txt", key="step2_topics")
        areas_file = st.file_uploader("Upload Functional Areas File (.txt)", type="txt", key="step2_areas")
        roles_file = st.file_uploader("Upload User Roles File (.txt)", type="txt", key="step2_roles")

    if st.button("🚀 Run Full Analysis", type="primary", disabled=(not HF_TOKEN)):
        if all([csv_file_step2, topics_file, areas_file, roles_file, HF_TOKEN]):
            client = InferenceClient(token=HF_TOKEN)
            df = pd.read_csv(csv_file_step2)
            
            topics = [line.strip() for line in io.StringIO(topics_file.getvalue().decode("utf-8")) if line.strip()]
            areas = [line.strip() for line in io.StringIO(areas_file.getvalue().decode("utf-8")) if line.strip()]
            roles = [line.strip() for line in io.StringIO(roles_file.getvalue().decode("utf-8")) if line.strip()]

            analysis_results = []
            progress_bar = st.progress(0, "Starting full analysis...")
            for i, row in df.iterrows():
                progress_bar.progress((i + 1) / len(df), f"Analyzing URL {i+1}/{len(df)}")
                soup, _ = analyze_page_content(row['Page URL'])
                if soup:
                    llm_data = get_full_analysis_with_llm(client, soup, roles, areas, topics)
                    row['User Role'] = llm_data.get('user_role', 'Error')
                    row['Functional Area'] = llm_data.get('functional_area', 'Error')
                    row['Topics'] = llm_data.get('topics', 'Error')
                    row['Keywords'] = llm_data.get('keywords', 'Error')
                else:
                    row['User Role'], row['Functional Area'], row['Topics'], row['Keywords'] = 'Fetch Error', 'Fetch Error', 'Fetch Error', 'Fetch Error'
                analysis_results.append(row)
            
            st.session_state.report_df_step2 = pd.DataFrame(analysis_results)
            st.success("✅ Full analysis complete! You can now download the final report.")
        else:
            st.warning("⚠️ Please upload all required files in the sidebar.")

    if 'report_df_step2' in st.session_state:
        st.subheader("Final Report")
        st.dataframe(st.session_state.report_df_step2)
        csv_data = st.session_state.report_df_step2.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Final Report (CSV)", csv_data, "final_content_report.csv", "text/csv")
