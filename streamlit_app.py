import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re
import json
import google.generativeai as genai
from openai import OpenAI
from huggingface_hub import InferenceClient

# --- MASTER PROMPT FOR LLMs ---
MASTER_PROMPT = """
You are an expert content analyst and data enrichment specialist.
Your task is to process an attached CSV file containing a list of URLs and their partially mapped deployment types.
You will perform a five-part analysis for each URL to complete the CSV: 1) Fill in missing deployment types, 2) Fill Missing user roles, 3) Fill missing topics, 4) Map contextual metadata from provided lists, and 5) Generate a set of unique keywords.
The generated metadata will be used to power a faceted search and content recommendation engine for a technical documentation portal, so accuracy and relevance are critical.
**Your Inputs**:

- An attached CSV file named `deployment_report.csv` with columns: `Page Title`, `Page URL`, `Deployment Type`, `User Role`, and `Topics`.
Note that some rows in the `Deployment Type`, `User Role`, and `Topics` columns may be blank.

**Your Goal**:

- Analyze each URL from the CSV and generate a final, complete CSV file with two new columns added and all data populated: `Functional Area` and `Keywords`.
- Please follow these steps precisely for each row in the input CSV:

    - Step 1: Fill Missing Deployment Types

        - For each row where the `Deployment Type` column is blank, you must:

            - Access and analyze the live content of the corresponding Page URL.
            - Determine if the content applies to "Alation Cloud Service", "Customer Managed", or "Alation Cloud Service, Customer Managed".
            - Fill the blank `Deployment Type` cell with the single, most appropriate value.
            - Do not modify rows that already have a value.

    - Step 2: Fill Missing User Roles

        - For each row where the `User Role` column is blank, you must:

            - Access and analyze the live content of the corresponding `Page URL`.
            - Determine which user role applies based on the relevant terms from the `user_roles.txt` list and content analysis.
            - Fill the blank `User Role` cell with one or more appropriate values.
            - Do not modify rows that already have a value.

    - Step 3: Fill Missing Topics

        - For each row where the `Topics` column is blank, you must:

            - Access and analyze the live content of the corresponding `Page URL`.
            - Determine what topics applies based on the relevant terms from the `topics.txt` list and content analysis.
            - Fill the blank `Topics` cell with one or more appropriate values.
            - Do not modify rows that already have a value.	

    - Step 4: Map Contextual Metadata

        - For every row, you must:

            - Access and analyze the live content of the `Page URL`.
            - Based on the page's content, select the most relevant terms according to the following rules:

        - For `Functional Area`: Select only the single most relevant term from the `functional_area.txt` list.
        
    - Step 5: Add and populate two new columns: `Functional Area` and `Keywords`.
    
    - Step 6: Generate Keywords

        - For every row, you must:

            - Perform a deep analysis of the main body content of the `Page URL`.
            - Generate a list of exactly 20 comma-separated, unique technical keywords that are central to the document.
            - Critical Formatting Rule: To ensure correct CSV formatting, the entire comma-separated list of keywords must be enclosed in a single pair of double quotes.
            - For example: `"keyword1, keyword2, keyword3, ..., keyword20"`.

            - Adhere strictly to the following exclusion rules:

                - Do Not Include Generic Terms: "documentation", "overview", "guide", "prerequisites", "steps", "introduction".
                - Do Not Include Broad or Context-Specific Terms: "ports", "load balancers", "proxy servers", "customer-managed", "Alation Cloud Service", "Zip file", "data catalog".
                - Do Not Include UI References: "toggle", "button", "click", "Preview", "Import", "Run".
                - Do Not Include Placeholders: "table name", "S3 bucket name", "SQL template", "placeholder values".
                - Do Not Include SQL Keywords or Release Status Terms.
                - Special OCF Connector Rule: If a document is about an OCF Connector, the keyword list must include both the full connector name (e.g., "Athena OCF Connector") and the corresponding data source name (e.g., "Athena data source").
                
    - Step 7: Add and populate a final new column, `Keywords`, with this list.

**Final Output:**

Your final output should be a single, complete CSV file. Do not provide explanations or summaries;
only output the final, enriched CSV data. The entire output must be enclosed in a single markdown code block starting with ```csv and ending with ```.
The header row should be:
`Page Title,Page URL,Deployment Type,User Role,Functional Area,Topics,Keywords`
"""

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
    return ""

def extract_main_content(soup):
    """Extracts main content by cleaning out boilerplate elements."""
    if not soup: return "Content Not Available"
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

def find_items_in_text(text, items):
    """Finds which items (roles, topics) from a list are present in the text."""
    if not isinstance(text, str): return ""
    
    # CORRECTED LOGIC: Use a standard for-loop to avoid the UnboundLocalError
    found_items = []
    for item in items:
        # Optimization: if an item is already found, no need to search for it again
        if item in found_items:
            continue
            
        for match in re.finditer(r'\b' + re.escape(item) + r'\b', text, re.IGNORECASE):
            if is_standalone_word(text, match):
                found_items.append(item)
                # Once found, break the inner loop to move to the next item
                break
                
    return ", ".join(found_items) if found_items else ""

# --- AI Enrichment Functions ---

def process_ai_response(response_text, url):
    """Parses the AI's CSV response and returns the first row as a Series."""
    csv_match = re.search(r'```csv\n(.*?)\n```', response_text, re.DOTALL)
    if csv_match:
        csv_data = csv_match.group(1)
        try:
            enriched_df = pd.read_csv(io.StringIO(csv_data))
            if not enriched_df.empty:
                return enriched_df.iloc[0]
        except Exception as e:
            st.warning(f"Could not parse CSV from AI response for {url}: {e}")
    else:
        st.warning(f"Could not find CSV in AI response for {url}")
    return None

def call_gemini_api(api_key, prompt):
    """Calls the Google Gemini API."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

def call_openai_api(api_key, prompt):
    """Calls the OpenAI API."""
    client = OpenAI(api_key=api_key)
    system_prompt, user_data = prompt.split("Here is the single row of CSV data to process:")
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Here is the single row of CSV data to process:" + user_data}
        ]
    )
    return response.choices[0].message.content

def call_huggingface_api(api_token, model_id, prompt):
    """Calls the Hugging Face Inference API."""
    client = InferenceClient(token=api_token)
    response = client.text_generation(prompt, model=model_id, max_new_tokens=512)
    return response

def enrich_data_with_ai(dataframe, api_key, provider, hf_model_id=None):
    """Iterates through a dataframe, calls the selected AI API, and enriches the data."""
    df_to_process = dataframe.copy()
    total_rows = len(df_to_process)
    pb = st.progress(0, f"Starting AI enrichment for {total_rows} rows...")

    for index, row in df_to_process.iterrows():
        pb.progress((index + 1) / total_rows, f"Processing row {index + 1}/{total_rows}...")
        
        try:
            header = "Page Title,Page URL,Deployment Type,User Role,Topics"
            row_as_csv_string = row[header.split(',')].to_frame().T.to_csv(header=True, index=False)
            full_prompt = MASTER_PROMPT + f"\n\nHere is the single row of CSV data to process:\n```csv\n{row_as_csv_string}```"
            
            response_text = ""
            if provider == "Google Gemini":
                response_text = call_gemini_api(api_key, full_prompt)
            elif provider == "OpenAI (GPT-4)":
                response_text = call_openai_api(api_key, full_prompt)
            elif provider == "Hugging Face":
                response_text = call_huggingface_api(api_key, hf_model_id, full_prompt)
            
            enriched_row = process_ai_response(response_text, row['Page URL'])
            if enriched_row is not None:
                for col in enriched_row.index:
                    df_to_process.loc[index, col] = enriched_row[col]

        except Exception as e:
            st.error(f"An error occurred while processing {row['Page URL']}: {e}")
            continue

    return df_to_process

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("📄 Web Content and Topic Mapper")
st.markdown("A four-step tool to scrape, map, and enrich content using AI.")

# Initialize session state dataframes
if 'df1' not in st.session_state: st.session_state.df1 = pd.DataFrame()
if 'df2' not in st.session_state: st.session_state.df2 = pd.DataFrame()
if 'df3' not in st.session_state: st.session_state.df3 = pd.DataFrame()
if 'df4' not in st.session_state: st.session_state.df4 = pd.DataFrame()

with st.expander("Step 1: Map Deployment Type", expanded=True):
    urls_file = st.file_uploader("Upload URLs File (.txt)", key="step1")
    if st.button("🚀 Scrape URLs", type="primary"):
        if urls_file:
            urls = [line.strip() for line in io.StringIO(urls_file.getvalue().decode("utf-8")) if line.strip()]
            results, pb = [], st.progress(0, "Starting...")
            for i, url in enumerate(urls):
                pb.progress((i + 1) / len(urls), f"Processing URL {i+1}/{len(urls)}...")
                soup, title = analyze_page_content(url)
                data = {'Page Title': title, 'Page URL': url}
                if soup:
                    data.update({'Deployment Type': get_deployment_type_from_scraping(soup), 'Page Content': extract_main_content(soup)})
                else:
                    data.update({'Deployment Type': 'Fetch Error', 'Page Content': 'Fetch Error'})
                results.append(data)
            
            st.session_state.df1 = pd.DataFrame(results)
            st.session_state.df2, st.session_state.df3, st.session_state.df4 = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            st.success("✅ Step 1 complete!")
        else:
            st.warning("⚠️ Please upload a URLs file.")

if not st.session_state.df1.empty:
    with st.expander("Step 2: Map User Roles", expanded=True):
        roles_file = st.file_uploader("Upload User Roles File (.txt)", key="step2")
        if st.button("🗺️ Map User Roles"):
            if roles_file:
                roles = [line.strip() for line in io.StringIO(roles_file.getvalue().decode("utf-8")) if line.strip()]
                if roles:
                    df = st.session_state.df1.copy()
                    df['User Roles'] = df['Page Content'].apply(lambda txt: find_items_in_text(txt, roles))
                    st.session_state.df2 = df
                    st.session_state.df3, st.session_state.df4 = pd.DataFrame(), pd.DataFrame()
                    st.success("✅ Step 2 complete!")
                else: st.warning("⚠️ Roles file is empty.")
            else: st.warning("⚠️ Please upload a roles file.")

if not st.session_state.df2.empty:
    with st.expander("Step 3: Map Topics", expanded=True):
        topics_file = st.file_uploader("Upload Topics File (.txt)", key="step3")
        if st.button("🏷️ Map Topics"):
            if topics_file:
                topics = [line.strip() for line in io.StringIO(topics_file.getvalue().decode("utf-8")) if line.strip()]
                if topics:
                    df = st.session_state.df2.copy()
                    df['Topics'] = df['Page Content'].apply(lambda txt: find_items_in_text(txt, topics))
                    st.session_state.df3 = df
                    st.session_state.df4 = pd.DataFrame()
                    st.success("✅ Step 3 complete!")
                else: st.warning("⚠️ Topics file is empty.")
            else: st.warning("⚠️ Please upload a topics file.")

if not st.session_state.df3.empty:
    with st.expander("Step 4: Enrich Data with AI", expanded=True):
        st.markdown("This final step uses an AI agent to fill in any remaining blank cells and generate new metadata columns.")
        
        ai_provider = st.selectbox("Choose AI Provider", ["Google Gemini", "OpenAI (GPT-4)", "Hugging Face"])
        
        api_key_label = "API Key"
        if ai_provider == "Hugging Face":
            api_key_label = "Hugging Face User Access Token"

        api_key = st.text_input(f"Enter your {api_key_label}", type="password", help=f"Get your key/token from the {ai_provider} website.")
        
        hf_model_id = None
        if ai_provider == "Hugging Face":
            hf_model_id = st.text_input("Enter Hugging Face Model ID", help="e.g., mistralai/Mistral-7B-Instruct-v0.2")

        if st.button("🤖 Fill Blanks with AI"):
            if not api_key:
                st.warning(f"Please enter your {api_key_label} to proceed.")
            elif ai_provider == "Hugging Face" and not hf_model_id:
                st.warning("Please enter a Hugging Face Model ID to proceed.")
            else:
                with st.spinner("AI is processing... This may take several minutes depending on the number of rows."):
                    st.session_state.df4 = enrich_data_with_ai(st.session_state.df3, api_key, ai_provider, hf_model_id)
                st.success("✅ AI enrichment complete! The final report is ready.")

st.markdown("---")
st.subheader("📊 Results")

# Determine which dataframe to show and its final columns
df_to_show = pd.DataFrame()
final_columns = ['Page Title', 'Page URL', 'Deployment Type', 'User Role', 'Topics', 'Functional Area', 'Keywords']
initial_columns = ['Page Title', 'Page URL', 'Deployment Type', 'User Roles', 'Topics'] # Note: 'User Roles' vs 'User Role'

# Check for both 'User Role' and 'User Roles' for compatibility
if 'User Roles' in st.session_state.get('df2', pd.DataFrame()).columns and 'User Role' not in st.session_state.get('df2', pd.DataFrame()).columns:
    st.session_state.get('df2', pd.DataFrame()).rename(columns={'User Roles': 'User Role'}, inplace=True)
if 'User Roles' in st.session_state.get('df3', pd.DataFrame()).columns and 'User Role' not in st.session_state.get('df3', pd.DataFrame()).columns:
    st.session_state.get('df3', pd.DataFrame()).rename(columns={'User Roles': 'User Role'}, inplace=True)


if 'df4' in st.session_state and not st.session_state.df4.empty:
    df_to_show = st.session_state.df4
    display_columns = [col for col in final_columns if col in df_to_show.columns]
elif 'df3' in st.session_state and not st.session_state.df3.empty:
    df_to_show = st.session_state.df3
    display_columns = [col for col in final_columns if col in df_to_show.columns]
elif 'df2' in st.session_state and not st.session_state.df2.empty:
    df_to_show = st.session_state.df2
    display_columns = [col for col in final_columns if col in df_to_show.columns]
elif 'df1' in st.session_state and not st.session_state.df1.empty:
    df_to_show = st.session_state.df1
    display_columns = [col for col in final_columns if col in df_to_show.columns]


if not df_to_show.empty:
    st.dataframe(df_to_show[display_columns])
    csv_data = df_to_show[display_columns].to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Download Report (CSV)", csv_data, "enriched_report.csv", "text/csv")
else:
    st.write("Upload a file in Step 1 and click 'Scrape URLs' to generate a report.")

