# Part 1: Imports, Initialization, and Utility Functions
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'documents' not in st.session_state:
    st.session_state['documents'] = []
if 'pending_analysis' not in st.session_state:
    st.session_state['pending_analysis'] = []
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'doc_id_counter' not in st.session_state:
    st.session_state['doc_id_counter'] = 1
if 'document_removal_times' not in st.session_state:
    st.session_state['document_removal_times'] = {}
if 'action_times' not in st.session_state:
    st.session_state['action_times'] = []
if 'selected_view' not in st.session_state:
    st.session_state['selected_view'] = 'Upload'
if 'user_actions' not in st.session_state:
    st.session_state['user_actions'] = []
if 'analyzed_docs' not in st.session_state:
    st.session_state['analyzed_docs'] = set()
if 'users' not in st.session_state:
    st.session_state['users'] = {
        'jimkalinov@gmail.com': {
            'password': 'Goldyear2023#*',
            'role': 'admin',
            'name': 'Jim Kalinov'
        },
        'userpal@example.com': {
            'password': 'System1234',
            'role': 'user',
            'name': 'User Pal'
        }
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
        
        prompt = """Please extract and summarize the document's key details:
1. KEY POINTS: Main facts and information.
2. NAMES: Important names and their roles.
3. DOCUMENT TYPE: Purpose of the document.
4. DATES & NUMBERS: Noteworthy dates or figures.
5. SUMMARY: Brief summary (2-3 sentences, 200 tokens max).

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
        'analysis': None,
        'uploaded_by': user_email
    })
    st.session_state['doc_id_counter'] += 1

    # Email notification for regular users
    if st.session_state['users'][user_email]['role'] != 'admin':
        subject = f"New Document Upload: {uploaded_file.name}"
        body = f"Document uploaded by {st.session_state['users'][user_email]['name']} ({user_email})."
        send_email_notification(subject, body)
    log_user_action('upload', f"Document uploaded by {user_email}: {uploaded_file.name}")
    return doc_id
# Part 3: Document Analysis, Show Analysis Toggle, and UI Functions
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
        log_user_action('analyze', f"Analyzed document: {doc['name']}")
        return True
    return False

def show_document_card(doc):
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"📄 {doc['name']} | Status: {doc['status']} {STATUS_EMOJIS[doc['status']]}")
            st.caption(f"Uploaded: {doc['upload_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            if st.session_state['current_user']['role'] == 'admin':
                st.caption(f"Uploaded by: {st.session_state['users'][doc['uploaded_by']]['name']}")
        
        if doc.get('analysis'):
            toggle = st.checkbox("Show Analysis", key=f"show_analysis_{doc['id']}")
            if toggle:
                st.markdown("### Analysis Results")
                st.write(doc['analysis'])
        elif st.session_state['current_user']['role'] == 'admin':
            if st.button("🔍 Analyze", key=f"analyze_status_{doc['id']}"):
                with st.spinner("Analyzing document..."):
                    if analyze_document(doc):
                        st.success("Analysis completed!")
                        st.experimental_rerun()
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
    check_expired_items()
    
    filtered_docs = [
        doc for doc in st.session_state['documents'] 
        if doc['uploaded_by'] == st.session_state['current_user']['email'] 
        or st.session_state['current_user']['role'] == 'admin'
    ]
    
    for doc in filtered_docs:
        show_document_card(doc)

def show_history_section():
    st.header("Document History 📚")
    history_df = pd.DataFrame(st.session_state['history'])
    history_df['uploaded_by'] = history_df['uploaded_by'].apply(
        lambda x: st.session_state['users'][x]['name']
    )
    st.dataframe(history_df)

def show_navigation():
    st.sidebar.title("Navigation 📱")
    nav_options = ["Upload", "Status", "History"]
    selected = st.sidebar.radio("Go to", nav_options)
    return selected
# Part 5: Main Application with `login_user` and Supporting Functions

def login_user(email, password):
    """Authenticate user with email and password."""
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

def log_user_action(action, details):
    """Record a user action in the session log."""
    st.session_state['user_actions'].append({
        'timestamp': datetime.now(),
        'action': action,
        'details': details,
        'user': st.session_state['current_user']['email']
    })

def check_expired_items():
    """Remove expired documents based on preset removal times."""
    current_time = datetime.now()
    for doc_id, expiration_time in list(st.session_state['document_removal_times'].items()):
        if current_time > expiration_time:
            st.session_state['documents'] = [doc for doc in st.session_state['documents'] if doc['id'] != doc_id]
            del st.session_state['document_removal_times'][doc_id]

def main():
    if not st.session_state['logged_in']:
        # Login page
        st.title("SignForMe.AI 📝")
        
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                st.markdown("### Welcome Back! 👋")
                st.markdown("Please log in to continue")
                
                email = st.text_input("Email", placeholder="Enter your email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    if login_user(email, password):
                        st.session_state['logged_in'] = True
                        log_user_action('login', 'User logged in successfully')
                        st.success("Login successful! Redirecting...")
                        st.rerun()  # Rerun app to show main content
                    else:
                        st.error("Invalid email or password")
            
            # App info
            with st.expander("ℹ️ About SignForMe.AI"):
                st.markdown("""
                SignForMe.AI is an intelligent document management system that helps you:
                - Upload and analyze documents
                - Track document status
                - Manage approvals
                - Generate insights
                """)
    else:
        # Main application
        header_col1, header_col2 = st.columns([0.7, 0.3])
        with header_col1:
            st.title("SignForMe.AI ✒️")
        with header_col2:
            with st.expander("👤 Profile Menu"):
                st.write(f"Welcome, {st.session_state['current_user']['name']}!")
                st.write(f"Role: {st.session_state['current_user']['role'].title()}")
                st.divider()
                
                if st.session_state['current_user']['role'] == 'admin':
                    if st.button("📊 Dashboard"):
                        st.session_state['selected_view'] = 'Analytics'
                
                if st.button("ℹ️ About"):
                    st.info("""SignForMe.AI v6.0
                    Developed by Kalinov Jim
                    
                    A smart document management system with AI-powered analysis.
                    """)
                
                if st.button("🚪 Logout"):
                    log_user_action('logout', 'User logged out')
                    st.session_state['logged_in'] = False  # Reset login state for next session
                    st.rerun()  # Rerun app to return to the login page
        
        # Sidebar navigation
        view = show_navigation()
        
        # Main content container
        with st.container():
            if view == "Upload":
                show_upload_section()
            elif view == "Status":
                show_status_section()
            elif view == "History":
                show_history_section()
            elif view == "Analytics":
                show_enhanced_analytics()
        
        # Footer
        st.sidebar.divider()
        st.sidebar.caption("""
        © 2024 SignForMe.AI
        Version 6.0
        """)

if __name__ == "__main__":
    main()
