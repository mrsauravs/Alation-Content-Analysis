import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re

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
    """
    Extracts main content by finding a primary container and then removing
    common non-essential elements like navs, headers, and footers before parsing text.
    """
    if not soup:
        return "Content Not Available"

    main_content = soup.find('article') or soup.find('main') or soup.body
    if not main_content:
        return "Main Content Not Found"

    # CRITICAL: Find and remove common boilerplate elements BEFORE extracting text.
    elements_to_remove = main_content.find_all(['nav', 'header', 'footer', 'aside'])
    for element in elements_to_remove:
        element.decompose()

    if main_content:
        return main_content.get_text(separator=' ', strip=True)
    
    return "Main Content Not Found"

# --- Mapping Helper Functions ---

def is_standalone_word(text, match):
    """Checks if a regex match is a standalone word."""
    start_index = match.start()
    end_index = match.end()
    
    if start_index == 0:
        is_start_valid = True
    else:
        char_before = text[start_index - 1]
        is_start_valid = char_before.isspace() or char_before in '(),."\''
    
    if end_index == len(text):
        is_end_valid = True
    else:
        char_after = text[end_index]
        is_end_valid = char_after.isspace() or char_after in '(),."\''
        
    return is_start_valid and is_end_valid

def find_keywords_in_text(text, keywords):
    """Finds which keywords from a list are present in the text as standalone words."""
    if not isinstance(text, str):
        return "Not Searched"
    
    found_keywords = []
    for keyword in keywords:
        # Use finditer to check each potential match for the keyword
        for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            # If it's a standalone word, add it to our list and stop searching for this keyword
            if is_standalone_word(text, match):
                found_keywords.append(keyword)
                break # Optimization: move to the next keyword once found
                
    return ", ".join(found_keywords) if found_keywords else "No Keywords Found"


# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("📄 Web Content and Topic Mapper")
st.markdown("A three-step tool to scrape web content, map user roles, and identify relevant topics.")

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
            # Clear data from subsequent steps when re-running Step 1
            if 'mapped_roles_df' in st.session_state: del st.session_state.mapped_roles_df
            if 'final_df' in st.session_state: del st.session_state.final_df
            st.success("✅ Step 1 complete! You can now proceed to Step 2.")
        else:
            st.warning("⚠️ Please upload a URLs file to begin.")

# Step 2: Map User Roles
if 'report_df' in st.session_state:
    with st.expander("Step 2: Map User Roles", expanded=True):
        roles_file_step2 = st.file_uploader("Upload User Roles File (.txt)", type="txt", key="step2_uploader")
        if st.button("🗺️ Map User Roles"):
            if roles_file_step2:
                user_roles = [line.strip() for line in io.StringIO(roles_file_step2.getvalue().decode("utf-8")) if line.strip()]
                if user_roles:
                    df_to_map = st.session_state.report_df.copy()
                    df_to_map['User Roles'] = df_to_map['Page Content'].apply(lambda text: find_keywords_in_text(text, user_roles))
                    st.session_state.mapped_roles_df = df_to_map
                    if 'final_df' in st.session_state: del st.session_state.final_df
                    st.success("✅ Step 2 complete! You can now proceed to Step 3.")
                else:
                    st.warning("⚠️ The roles file is empty.")
            else:
                st.warning("⚠️ Please upload a user roles file.")

# Step 3: Map Topics
if 'mapped_roles_df' in st.session_state:
    with st.expander("Step 3: Map Topics", expanded=True):
        topics_file_step3 = st.file_uploader("Upload Topics File (.txt)", type="txt", key="step3_uploader")
        if st.button("🏷️ Map Topics"):
            if topics_file_step3:
                topics = [line.strip() for line in io.StringIO(topics_file_step3.getvalue().decode("utf-8")) if line.strip()]
                if topics:
                    df_to_map = st.session_state.mapped_roles_df.copy()
                    # Use the same generic keyword finder for topics
                    df_to_map['Topics'] = df_to_map['Page Content'].apply(lambda text: find_keywords_in_text(text, topics))
                    st.session_state.final_df = df_to_map
                    st.success("✅ Analysis complete! The final report is ready below.")
                else:
                    st.warning("⚠️ The topics file is empty.")
            else:
                st.warning("⚠️ Please upload a topics file.")

# Display and Download Results
st.markdown("---")
st.subheader("📊 Results")

df_to_display = pd.DataFrame()
file_name = "scraped_report.csv"
if 'final_df' in st.session_state:
    st.info("Displaying final report with Topics.")
    df_to_display = st.session_state.final_df
    file_name = "final_content_report.csv"
elif 'mapped_roles_df' in st.session_state:
    st.info("Displaying report with User Roles. Complete Step 3 to add Topics.")
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
