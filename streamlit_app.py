import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re
from collections import Counter

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
    """Determines deployment type from parsed HTML based on specific class labels."""
    if not soup:
        return ""
    has_cloud = soup.find('p', class_='cloud-label') is not None
    has_on_prem = soup.find('p', class_='on-prem-label') is not None
    if has_cloud and has_on_prem:
        return "Alation Cloud Service, Customer Managed"
    if has_cloud:
        return "Alation Cloud Service"
    if has_on_prem:
        return "Customer Managed"
    return "Tag Not Found"

def extract_main_content(soup):
    """Extracts the main textual content from the parsed HTML."""
    if not soup:
        return "Content Not Available"
    main_content = soup.find('article') or soup.find('main') or soup.body
    if main_content:
        return main_content.get_text(separator=' ', strip=True)
    return "Main Content Not Found"

# --- Mapping Functions ---

def find_roles_in_text(text, roles):
    """Finds which roles from a list are present in a given text."""
    if not isinstance(text, str):
        return "Not Searched"
    found_roles = []
    for role in roles:
        if re.search(r'\b' + re.escape(role) + r'\b', text, re.IGNORECASE):
            found_roles.append(role)
    return ", ".join(found_roles) if found_roles else "No Roles Found"

def find_primary_functional_area(row, functional_areas):
    """
    Determines the single most important functional area using a hybrid logic.
    - General Rule: Matches only standalone words.
    - Specific Exception: Excludes "Compose" if it is preceded by "Docker".
    """
    title = row.get('Page Title', '')
    content = row.get('Page Content', '')
    
    if not isinstance(content, str): content = ""
    if not isinstance(title, str): title = ""

    def is_valid_match(text, match, area):
        start_index = match.start()
        end_index = match.end()
        
        # 1. General Standalone Word Check
        is_start_valid = (start_index == 0) or (text[start_index - 1].isspace() or text[start_index - 1] in '(),."\'')
        is_end_valid = (end_index == len(text)) or (text[end_index].isspace() or text[end_index] in '(),."\'')
        
        if not (is_start_valid and is_end_valid):
            return False

        # 2. Specific Exception for "Compose"
        if area.lower() == 'compose':
            preceding_text_start = max(0, start_index - 10) # Check 10 chars before
            preceding_text = text[preceding_text_start:start_index]
            if 'docker' in preceding_text.lower():
                return False # Invalidate if "docker" is found nearby

        return True

    # Priority 1: Check the Page Title
    for area in functional_areas:
        for match in re.finditer(r'\b' + re.escape(area) + r'\b', title, re.IGNORECASE):
            if is_valid_match(title, match, area):
                return area

    # Priority 2: Count frequency in Page Content
    all_matches = []
    for area in functional_areas:
        for match in re.finditer(r'\b' + re.escape(area) + r'\b', content, re.IGNORECASE):
            if is_valid_match(content, match, area):
                all_matches.append(area)
            
    if not all_matches:
        return "No Area Found"
        
    most_common_area = Counter(all_matches).most_common(1)[0][0]
    return most_common_area

# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("📄 Web Content Analyzer and Mapper")
st.markdown("A three-step tool to scrape web content, map user roles, and determine the primary functional area.")

# Step 1: Scrape Content
with st.expander("Step 1: Scrape Content from URLs", expanded=True):
    urls_file_step1 = st.file_uploader("Upload URLs File (.txt)", type="txt", key="step1_uploader")
    if st.button("🚀 Scrape URLs", type="primary"):
        if urls_file_step1:
            urls = [line.strip() for line in io.StringIO(urls_file_step1.getvalue().decode("utf-8")) if line.strip()]
            results = []
            progress_bar = st.progress(0, "Starting...")
            for i, url in enumerate(urls):
                progress_bar.progress((i + 1) / len(urls), f"Processing URL {i+1}/{len(urls)}...")
                soup, title = analyze_page_content(url)
                if soup:
                    results.append({
                        'Page Title': title, 'Page URL': url,
                        'Deployment Type': get_deployment_type_from_scraping(soup),
                        'Page Content': extract_main_content(soup)
                    })
                else:
                    results.append({
                        'Page Title': title, 'Page URL': url,
                        'Deployment Type': 'Fetch Error', 'Page Content': 'Fetch Error'
                    })
            st.session_state.report_df = pd.DataFrame(results)
            if 'mapped_roles_df' in st.session_state: del st.session_state.mapped_roles_df
            if 'final_df' in st.session_state: del st.session_state.final_df
            st.success("✅ Step 1 complete! You can now proceed to Step 2.")
        else:
            st.warning("⚠️ Please upload a URLs file to begin.")

# Step 2: Map User Roles
if 'report_df' in st.session_state:
    with st.expander("Step 2: Map User Roles to Scraped Content", expanded=True):
        roles_file_step2 = st.file_uploader("Upload User Roles File (.txt)", type="txt", key="step2_uploader")
        if st.button("🗺️ Map User Roles"):
            if roles_file_step2:
                user_roles = [line.strip() for line in io.StringIO(roles_file_step2.getvalue().decode("utf-8")) if line.strip()]
                if user_roles:
                    df_to_map = st.session_state.report_df.copy()
                    df_to_map['User Roles'] = df_to_map['Page Content'].apply(lambda text: find_roles_in_text(text, user_roles))
                    st.session_state.mapped_roles_df = df_to_map
                    if 'final_df' in st.session_state: del st.session_state.final_df
                    st.success("✅ Step 2 complete! You can now proceed to Step 3.")
                else:
                    st.warning("⚠️ The roles file is empty.")
            else:
                st.warning("⚠️ Please upload a user roles file.")

# Step 3: Determine Functional Area
if 'mapped_roles_df' in st.session_state:
    with st.expander("Step 3: Determine Primary Functional Area", expanded=True):
        fa_file_step3 = st.file_uploader("Upload Functional Areas File (.txt)", type="txt", key="step3_uploader")
        if st.button("🏆 Determine Functional Areas"):
            if fa_file_step3:
                functional_areas = [line.strip() for line in io.StringIO(fa_file_step3.getvalue().decode("utf-8")) if line.strip()]
                if functional_areas:
                    df_to_map = st.session_state.mapped_roles_df.copy()
                    df_to_map['Functional Area'] = df_to_map.apply(find_primary_functional_area, axis=1, functional_areas=functional_areas)
                    st.session_state.final_df = df_to_map
                    st.success("✅ Analysis complete! The final report is ready below.")
                else:
                    st.warning("⚠️ The functional areas file is empty.")
            else:
                st.warning("⚠️ Please upload a functional areas file.")

# Display and Download Results
st.markdown("---")
st.subheader("📊 Results")

df_to_display = pd.DataFrame()
file_name = "scraped_report.csv"
if 'final_df' in st.session_state:
    st.info("Displaying final report with Functional Areas.")
    df_to_display = st.session_state.final_df
    file_name = "final_web_content_report.csv"
elif 'mapped_roles_df' in st.session_state:
    st.info("Displaying report with User Roles. Complete Step 3 to add Functional Areas.")
    df_to_display = st.session_state.mapped_roles_df
    file_name = "roles_mapped_report.csv"
elif 'report_df' in st.session_state:
    st.info("Displaying initial scraping report. Complete subsequent steps to add more data.")
    df_to_display = st.session_state.report_df

if not df_to_display.empty:
    st.dataframe(df_to_display)
    csv_data = df_to_display.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Download Full Report (CSV)",
        data=csv_data,
        file_name=file_name,
        mime="text/csv"
    )
else:
    st.write("Upload a file in Step 1 and click 'Scrape URLs' to generate a report.")
