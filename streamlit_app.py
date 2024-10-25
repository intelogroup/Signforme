# Part 1: Imports, Initialization, and Utility Functions
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'documents' not in st.session_state:
    st.session_state['documents'] = []
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'doc_id_counter' not in st.session_state:
    st.session_state['doc_id_counter'] = 1
if 'analyzed_docs' not in st.session_state:
    st.session_state['analyzed_docs'] = set()
if 'users' not in st.session_state:
    st.session_state['users'] = {
        'jimkalinov@gmail.com': {'password': 'Goldyear2023#*', 'role': 'admin', 'name': 'Jim Kalinov'},
        'userpal@example.com': {'password': 'System1234', 'role': 'user', 'name': 'User Pal'}
    }
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

STATUS_EMOJIS = {
    'Pending': '⏳',
    'Authorized': '✅',
    'Rejected': '❌',
    'Processing': '🔄',
    'Analyzed': '🔍'
}

def send_email_notification(subject, body):
    try:
        sender_email = st.secrets["GMAIL_ADDRESS"]
        sender_password = st.secrets["GMAIL_APP_PASSWORD"]
        receiver_email = "jimkalinov@gmail.com"  # Admin email

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def extract_text_content(uploaded_file):
    try:
        content = uploaded_file.read()
        return content.decode('utf-8') if content else ""
    except Exception as e:
        st.warning("Error extracting text content.")
        return ""
# Part 2: AI Analysis and Document Upload Handling
def analyze_with_claude(text):
    try:
        headers = {
            "x-api-key": st.secrets["CLAUDE_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        prompt = """Extract and summarize the document's key details:
1. KEY POINTS: Main facts.
2. NAMES: Important names.
3. DOCUMENT TYPE: Purpose.
4. DATES & NUMBERS: Noteworthy details.
5. SUMMARY: Brief summary (200 tokens max).

Document:
{text}
"""
        
        data = {
            "model": "claude-3-opus-20240229",
            "messages": [
                {"role": "user", "content": prompt.format(text=text)}
            ],
            "max_tokens": 200,
            "temperature": 0.1
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            st.error(f"API Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def handle_document_upload(uploaded_file, user_email):
    doc_id = f"SIGN{st.session_state['doc_id_counter']:03d}"
    upload_time = datetime.now()
    
    doc_data = {
        'id': doc_id,
        'name': uploaded_file.name,
        'status': 'Pending',
        'upload_time': upload_time,
        'file_type': uploaded_file.type,
        'file_size': uploaded_file.size,
        'content': extract_text_content(uploaded_file),
        'analysis': None,
        'uploaded_by': user_email,
        'show_analysis': False
    }
    
    st.session_state['documents'].append(doc_data)
    st.session_state['history'].append({
        'date': upload_time.strftime("%Y-%m-%d %H:%M:%S"),
        'id': doc_id,
        'name': uploaded_file.name,
        'status': f"Pending {STATUS_EMOJIS['Pending']}",
        'uploaded_by': user_email
    })
    st.session_state['doc_id_counter'] += 1

    if st.session_state['users'][user_email]['role'] != 'admin':
        subject = f"New Document Uploaded: {uploaded_file.name}"
        body = f"Uploaded by {st.session_state['users'][user_email]['name']} ({user_email})."
        send_email_notification(subject, body)
    return doc_id
# Part 3: Document Analysis, Accept/Reject Logic, and UI Functions
def analyze_document(doc):
    if doc['id'] in st.session_state['analyzed_docs']:
        return False
    
    analysis = analyze_with_claude(doc['content'])
    if analysis:
        for stored_doc in st.session_state['documents']:
            if stored_doc['id'] == doc['id']:
                stored_doc['analysis'] = analysis
                break
        st.session_state['analyzed_docs'].add(doc['id'])
        return True
    return False

def update_document_status(doc, new_status):
    doc['status'] = new_status
    for hist_doc in st.session_state['history']:
        if hist_doc['id'] == doc['id']:
            hist_doc['status'] = f"{new_status} {STATUS_EMOJIS[new_status]}"

def show_document_card(doc):
    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(f"📄 {doc['name']} | Status: {doc['status']} {STATUS_EMOJIS[doc['status']]}")
            st.caption(f"Uploaded: {doc['upload_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            if st.session_state['current_user']['role'] == 'admin':
                st.caption(f"Uploaded by: {st.session_state['users'][doc['uploaded_by']]['name']}")
        
        if doc.get('analysis'):
            with col2:
                toggle = st.checkbox("Show Analysis", key=f"show_analysis_{doc['id']}")
            if toggle:
                st.markdown("### Analysis Results")
                st.write(doc['analysis'])

        if st.session_state['current_user']['role'] == 'admin' and doc['status'] == 'Pending':
            with col2:
                if st.button("Accept", key=f"accept_{doc['id']}"):
                    update_document_status(doc, 'Authorized')
                    st.success("Document Accepted")
                    st.rerun()
            with col3:
                if st.button("Reject", key=f"reject_{doc['id']}"):
                    update_document_status(doc, 'Rejected')
                    st.warning("Document Rejected")
                    st.rerun()
        elif st.session_state['current_user']['role'] == 'admin':
            if st.button("Analyze", key=f"analyze_{doc['id']}"):
                with st.spinner("Analyzing document..."):
                    if analyze_document(doc):
                        st.success("Analysis completed!")
                        st.rerun()
                    else:
                        st.error("Analysis failed.")
# Part 4: Upload, Status, History, and Navigation Functions
def show_upload_section():
    st.header("Upload Documents 📤")
    uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True)
    
    if uploaded_files:
        with st.spinner("Processing uploads..."):
            for uploaded_file in uploaded_files:
                handle_document_upload(uploaded_file, st.session_state['current_user']['email'])
        st.success(f"Successfully uploaded {len(uploaded_files)} document(s)!")

def show_status_section():
    st.header("Document Status 📋")
    
    filtered_docs = [
        doc for doc in st.session_state['documents']
        if st.session_state['current_user']['role'] == 'admin' 
        or doc['uploaded_by'] == st.session_state['current_user']['email']
    ]
    
    if filtered_docs:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "Pending", "Authorized", "Rejected"]
        )
        
        if status_filter != "All":
            filtered_docs = [doc for doc in filtered_docs if doc['status'] == status_filter]
        
        for doc in filtered_docs:
            show_document_card(doc)
            st.divider()
    else:
        st.info("No documents found")

def show_history_section():
    st.header("Document History 📚")
    
    if st.session_state['history']:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", value=datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End date", value=datetime.now())
        
        df_history = pd.DataFrame(st.session_state['history'])
        df_history['date'] = pd.to_datetime(df_history['date'])
        
        mask = (df_history['date'].dt.date >= start_date) & (df_history['date'].dt.date <= end_date)
        if st.session_state['current_user']['role'] != 'admin':
            mask &= df_history['uploaded_by'] == st.session_state['current_user']['email']
        
        filtered_df = df_history[mask]
        
        if not filtered_df.empty:
            filtered_df['uploaded_by'] = filtered_df['uploaded_by'].apply(
                lambda x: st.session_state['users'][x]['name']
            )
            
            st.dataframe(
                filtered_df.sort_values('date', ascending=False),
                hide_index=True,
                column_config={
                    "date": "Timestamp",
                    "id": "Document ID",
                    "name": "Document Name",
                    "status": "Status",
                    "uploaded_by": "Uploaded By"
                }
            )
            
            if st.button("Export History"):
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    "document_history.csv",
                    "text/csv",
                    key='download-csv'
                )
        else:
            st.info("No documents found in selected date range")
    else:
        st.info("No document history available")

def login_user(email, password):
    if email in st.session_state['users']:
        user = st.session_state['users'][email]
        if password == user['password']:
            st.session_state['current_user'] = {
                'email': email,
                'role': user['role'],
                'name': user['name']
            }
            return True
    return False

def show_navigation():
    st.sidebar.title("Navigation")
    return st.sidebar.radio(
        "",
        ["Upload", "Status", "History"],
        label_visibility="collapsed",
        format_func=lambda x: f"{STATUS_EMOJIS.get(x, '📄')} {x}"
    )

# Part 5: Main Application Logic
def main():
    if not st.session_state['logged_in']:
        st.title("SignForMe.AI 📝")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                st.markdown("### Welcome! 👋")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    if login_user(email, password):
                        st.session_state['logged_in'] = True
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
    else:
        header_col1, header_col2 = st.columns([0.7, 0.3])
        with header_col1:
            st.title("SignForMe.AI ✒️")
        with header_col2:
            with st.expander("👤 Profile"):
                st.write(f"Welcome, {st.session_state['current_user']['name']}!")
                st.write(f"Role: {st.session_state['current_user']['role'].title()}")
                if st.button("🚪 Logout"):
                    st.session_state['logged_in'] = False
                    st.rerun()
        
        view = show_navigation()
        
        if view == "Upload":
            show_upload_section()
        elif view == "Status":
            show_status_section()
        elif view == "History":
            show_history_section()
        
        # Footer
        st.sidebar.divider()
        st.sidebar.caption("""
        © 2024 SignForMe.AI v6.0
        By Kalinov Jim
        """)

if __name__ == "__main__":
    main()
    
