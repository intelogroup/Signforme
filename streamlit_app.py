import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

# Custom CSS for navigation
st.markdown("""
<style>
    .nav-link {
        padding: 10px 15px;
        border-radius: 5px;
        margin: 5px 0;
        text-decoration: none;
        display: flex;
        align-items: center;
        color: white;
        font-weight: bold;
    }
    .nav-upload {
        background-color: #FF4B4B;
    }
    .nav-status {
        background-color: #00CC00;
    }
    .nav-history {
        background-color: #000080;
    }
    .nav-analytics {
        background-color: #FF9900;
    }
    .nav-icon {
        margin-right: 10px;
        font-size: 20px;
    }
</style>
""", unsafe_allow_html=True)

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

STATUS_EMOJIS = {
    'Pending': '⏳',
    'Authorized': '✅',
    'Rejected': '❌',
    'Processing': '🔄',
    'Analyzed': '🔍'
}

def extract_text_content(uploaded_file):
    """Attempt to extract text content from uploaded file"""
    try:
        content = uploaded_file.read()
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return content.decode('latin-1')
    except Exception as e:
        st.warning(f"Note: File content might not be perfectly extracted. Proceeding with best effort.")
        return str(content)

def analyze_with_claude(text):
    try:
        headers = {
            "x-api-key": st.secrets["CLAUDE_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        prompt = """Please analyze this document content carefully. Provide a structured analysis with the following:

1. NAMES: List all person names found in the document, with their context if available
2. KEY INFORMATION: Extract and list the main points or facts
3. DOCUMENT TYPE: Identify the type or purpose of the document
4. DATES & NUMBERS: List any significant dates, numbers, or quantities
5. RELATIONSHIPS: Identify any relationships or connections between named entities
6. SUMMARY: Provide a brief summary of the document's main purpose
7. Name CHECK: Check if the name Maxi raymonville in mentioned in the document

Please be precise and factual. If you're uncertain about any information, indicate that explicitly.

Document content to analyze:

{text}"""
        
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

def login_user(email, password):
    return email == "jimkalinov@gmail.com" and password == "Goldyear2023#*"

def log_user_action(action, details):
    st.session_state['user_actions'].append({
        'timestamp': datetime.now(),
        'action': action,
        'details': details
    })

def check_expired_items():
    current_time = datetime.now()
    for doc_id, expiration_time in list(st.session_state['document_removal_times'].items()):
        if current_time > expiration_time:
            st.session_state['documents'] = [doc for doc in st.session_state['documents'] if doc['id'] != doc_id]
            del st.session_state['document_removal_times'][doc_id]

def show_upload_section():
    st.header("Upload Documents 📤")
    
    # File uploader
    uploaded_files = st.file_uploader("Choose files", type=None, accept_multiple_files=True)
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            doc_id = f"SIGN{st.session_state['doc_id_counter']:03d}"
            st.session_state['doc_id_counter'] += 1
            upload_time = datetime.now()
            
            # Add directly to documents list
            doc_data = {
                'id': doc_id,
                'name': uploaded_file.name,
                'status': 'Pending',
                'upload_time': upload_time,
                'file_type': uploaded_file.type,
                'file_size': uploaded_file.size,
                'content': extract_text_content(uploaded_file),
                'analysis': None  # Will be populated when processed
            }
            
            # Add to both documents and pending analysis
            st.session_state['documents'].append(doc_data)
            st.session_state['pending_analysis'].append(doc_data.copy())
            
            # Add to history
            st.session_state['history'].append({
                'date': upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                'id': doc_id,
                'name': uploaded_file.name,
                'status': f"Pending {STATUS_EMOJIS['Pending']}",
                'analysis': None
            })
            
            log_user_action('upload', f"Uploaded document: {uploaded_file.name}")
        
        st.success(f"Successfully uploaded {len(uploaded_files)} document(s)!")

    # Show documents available for analysis
    if st.session_state['pending_analysis']:
        st.subheader("Documents Available for Analysis")
        
        selected_docs = []
        for doc in st.session_state['pending_analysis']:
            col1, col2 = st.columns([4, 1])
            with col1:
                selected = st.checkbox(
                    f"📄 {doc['name']} ({doc['file_type'] or 'unknown type'}) - {doc['file_size']/1024:.1f} KB",
                    key=f"select_{doc['id']}"
                )
                if selected:
                    selected_docs.append(doc)
        
        if selected_docs:
            if st.button(f"Analyze Selected Documents ({len(selected_docs)})", type="primary"):
                with st.spinner("Analyzing selected documents..."):
                    for doc in selected_docs:
                        # Analyze document
                        analysis = analyze_with_claude(doc['content'])
                        
                        # Update analysis in documents list
                        for stored_doc in st.session_state['documents']:
                            if stored_doc['id'] == doc['id']:
                                stored_doc['analysis'] = analysis
                                break
                        
                        # Update history
                        for hist_doc in st.session_state['history']:
                            if hist_doc['id'] == doc['id']:
                                hist_doc['analysis'] = analysis
                        
                        # Remove from pending analysis
                        st.session_state['pending_analysis'] = [
                            d for d in st.session_state['pending_analysis'] if d['id'] != doc['id']
                        ]
                        
                        log_user_action('analyze', f"Analyzed document: {doc['name']}")
                
                st.success("Selected documents analyzed successfully!")
                st.rerun()

def show_status_section():
    st.header("Document Status 📋")
    check_expired_items()
    
    # Filter options
    status_filter = st.selectbox("Filter by status", ["All", "Pending", "Authorized", "Rejected"])
    
    filtered_docs = st.session_state['documents']
    if status_filter != "All":
        filtered_docs = [doc for doc in filtered_docs if doc['status'] == status_filter]
    
    if filtered_docs:
        for doc in filtered_docs:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.write(f"📄 {doc['name']} | Status: {doc['status']} {STATUS_EMOJIS[doc['status']]}")
                    st.caption(f"Uploaded: {doc['upload_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    if st.button(f"View", key=f"view_{doc['id']}"):
                        with st.expander("Document Details", expanded=True):
                            st.write("File Information:")
                            st.write(f"Type: {doc['file_type'] or 'unknown'}")
                            st.write(f"Size: {doc['file_size']/1024:.1f} KB")
                            if doc.get('analysis'):
                                st.write("Analysis Results:")
                                tab1, tab2 = st.tabs(["Formatted Analysis", "Raw Analysis"])
                                with tab1:
                                    sections = doc['analysis'].split('\n')
                                    for section in sections:
                                        if any(header in section for header in ["NAMES:", "KEY INFORMATION:", 
                                                                              "DOCUMENT TYPE:", "DATES & NUMBERS:", 
                                                                              "RELATIONSHIPS:", "SUMMARY:"]):
                                            st.markdown(f"### {section}")
                                        elif section.strip():
                                            st.write(section)
                                with tab2:
                                    st.text_area("Full Analysis", doc['analysis'], height=300)
                            else:
                                st.info("No analysis available")
                
                if doc['status'] == 'Pending':
                    with col3:
                        if st.button(f"Accept", key=f"accept_{doc['id']}"):
                            doc['status'] = "Authorized"
                            action_time = datetime.now()
                            for hist_doc in st.session_state['history']:
                                if hist_doc['id'] == doc['id']:
                                    hist_doc['status'] = f"Authorized {STATUS_EMOJIS['Authorized']}"
                                    hist_doc['date'] = action_time.strftime("%Y-%m-%d %H:%M:%S")
                            st.session_state['action_times'].append((doc['upload_time'], action_time))
                            st.session_state['document_removal_times'][doc['id']] = datetime.now() + timedelta(minutes=5)
                            log_user_action('authorize', f"Authorized document: {doc['name']}")
                            st.rerun()
                    
                    with col4:
                        if st.button(f"Reject", key=f"reject_{doc['id']}"):
                            doc['status'] = "Rejected"
                            action_time = datetime.now()
                            for hist_doc in st.session_state['history']:
                                if hist_doc['id'] == doc['id']:
                                    hist_doc['status'] = f"Rejected {STATUS_EMOJIS['Rejected']}"
                                    hist_doc['date'] = action_time.strftime("%Y-%m-%d %H:%M:%S")
                            st.session_state['action_times'].append((doc['upload_time'], action_time))
                            st.session_state['document_removal_times'][doc['id']] = datetime.now() + timedelta(minutes=5)
                            log_user_action('reject', f"Rejected document: {doc['name']}")
                            st.rerun()
                st.divider()
    else:
        st.info("No documents found matching the selected filter")

def show_history_section():
    st.header("Document History 📚")
    
    if st.session_state['history']:
        # Add date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", value=datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End date", value=datetime.now())
        
        # Convert history to DataFrame
        history_df = pd.DataFrame(st.session_state['history'])
        history_df['date'] = pd.to_datetime(history_df['date'])
        
        # Apply date filter
        mask = (history_df['date'].dt.date >= start_date) & (history_df['date'].dt.date <= end_date)
        filtered_df = history_df[mask]
        
        if not filtered_df.empty:
            st.dataframe(
                filtered_df.sort_values('date', ascending=False),
                hide_index=True,
                column_config={
                    "date": "Timestamp",
                    "id": "Document ID",
                    "name": "Document Name",
                    "status": "Status"
                }
            )
            
            # Export option
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

def show_enhanced_analytics():
    st.title("Enhanced Analytics Dashboard 📊")
    
    # Main Analytics Tabs
    tabs = st.tabs(["Document Analytics", "User Activity", "Performance Metrics", "Custom Reports"])
    
    with tabs[0]:  # Document Analytics
        st.header("Document Analytics")
        
        if st.session_state['history']:
            col1, col2 = st.columns(2)
            
            with col1:
                # Status Distribution
                st.subheader("Status Distribution")
                df_history = pd.DataFrame(st.session_state['history'])
                status_counts = df_history['status'].apply(lambda x: x.split()[0]).value_counts()
                st.bar_chart(status_counts)
                
                # Document Types Analysis
                st.subheader("Document Types")
                doc_types = pd.DataFrame(st.session_state['documents'])['file_type'].value_counts()
                st.bar_chart(doc_types)
            
            with col2:
                # Quick Stats
                st.subheader("Quick Statistics")
                total_docs = len(df_history)
                pending_analysis = len(st.session_state['pending_analysis'])
                analyzed_docs = len([d for d in st.session_state['documents'] if d.get('analysis')])
                
                st.metric("Total Documents", total_docs)
                st.metric("Pending Analysis", pending_analysis)
                st.metric("Analyzed Documents", analyzed_docs)
                
                # Processing Status
                st.subheader("Processing Status")
                total_processed = len(st.session_state['action_times'])
                if total_processed > 0:
                    st.metric("Documents Processed", total_processed)
                    st.metric("Processing Rate", f"{(total_processed/total_docs*100):.1f}%")
    
    with tabs[1]:  # User Activity
        st.header("User Activity Analysis")
        
        if st.session_state['user_actions']:
            df_actions = pd.DataFrame(st.session_state['user_actions'])
            df_actions['timestamp'] = pd.to_datetime(df_actions['timestamp'])
            
            # Activity Timeline
            st.subheader("Activity Timeline")
            daily_activity = df_actions.groupby(df_actions['timestamp'].dt.date).size()
            st.line_chart(daily_activity)
            
            # Action Type Distribution
            st.subheader("Action Type Distribution")
            action_counts = df_actions['action'].value_counts()
            st.bar_chart(action_counts)
            
            # Recent Activity Log
            st.subheader("Recent Activity")
            recent_actions = df_actions.sort_values('timestamp', ascending=False).head(10)
            for _, action in recent_actions.iterrows():
                st.text(f"{action['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} - {action['action']}: {action['details']}")
    
    with tabs[2]:  # Performance Metrics
        st.header("Performance Metrics")
        
        if st.session_state['history']:
            col1, col2 = st.columns(2)
            
            with col1:
                # Processing Efficiency
                st.subheader("Processing Efficiency")
                time_diffs = [(action - upload).total_seconds() 
                             for upload, action in st.session_state['action_times']]
                if time_diffs:
                    avg_time = sum(time_diffs) / len(time_diffs)
                    max_time = max(time_diffs)
                    min_time = min(time_diffs)
                    
                    st.metric("Average Processing Time", f"{avg_time:.1f}s")
                    st.metric("Fastest Processing", f"{min_time:.1f}s")
                    st.metric("Slowest Processing", f"{max_time:.1f}s")
                    
                    # Time Distribution Chart
                    st.subheader("Processing Time Distribution")
                    time_df = pd.DataFrame(time_diffs, columns=['seconds'])
                    st.line_chart(time_df)
            
            with col2:
                # Success Metrics
                st.subheader("Success Metrics")
                df_history = pd.DataFrame(st.session_state['history'])
                total_docs = len(df_history)
                
                if total_docs > 0:
                    approval_rate = len(df_history[df_history['status'].str.contains('Authorized')]) / total_docs
                    rejection_rate = len(df_history[df_history['status'].str.contains('Rejected')]) / total_docs
                    
                    st.metric("Approval Rate", f"{approval_rate:.1%}")
                    st.metric("Rejection Rate", f"{rejection_rate:.1%}")
                    
                    # Daily Success Rate Trend
                    st.subheader("Daily Success Rate Trend")
                    df_history['date'] = pd.to_datetime(df_history['date'])
                    daily_approval = df_history[df_history['status'].str.contains('Authorized')].groupby(
                        df_history['date'].dt.date
                    ).size()
                    st.line_chart(daily_approval)
    
    with tabs[3]:  # Custom Reports
        st.header("Custom Report Generator")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", 
                                     value=datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date",
                                   value=datetime.now())
        
        metrics = st.multiselect(
            "Choose metrics for your report",
            ["Document Statistics", "Processing Times", "User Activity", "Performance Metrics"],
            default=["Document Statistics"]
        )
        
        if st.button("Generate Report"):
            report_data = {
                "Report Period": f"{start_date} to {end_date}",
                "Generated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Metrics": {}
            }
            
            df_history = pd.DataFrame(st.session_state['history'])
            if not df_history.empty:
                df_history['date'] = pd.to_datetime(df_history['date'])
                mask = (df_history['date'].dt.date >= start_date) & (df_history['date'].dt.date <= end_date)
                filtered_df = df_history[mask]
                
                if "Document Statistics" in metrics:
                    report_data["Metrics"]["Document Statistics"] = {
                        "Total Documents": len(filtered_df),
                        "Status Distribution": filtered_df['status'].apply(
                            lambda x: x.split()[0]).value_counts().to_dict()
                    }
                
                if "Processing Times" in metrics and st.session_state['action_times']:
                    time_diffs = [(action - upload).total_seconds() 
                                 for upload, action in st.session_state['action_times']]
                    report_data["Metrics"]["Processing Times"] = {
                        "Average Time": f"{sum(time_diffs) / len(time_diffs):.1f}s",
                        "Fastest": f"{min(time_diffs):.1f}s",
                        "Slowest": f"{max(time_diffs):.1f}s"
                    }
            
            st.json(report_data)
            
            if st.download_button(
                "Download Report (JSON)",
                data=json.dumps(report_data, indent=2),
                file_name="analytics_report.json",
                mime="application/json"
            ):
                st.success("Report downloaded successfully!")

def show_navigation():
    st.sidebar.markdown("""
        <a href="#" class="nav-link nav-upload" onclick=''>
            <span class="nav-icon">📤</span> Upload
        </a>
        <a href="#" class="nav-link nav-status" onclick=''>
            <span class="nav-icon">📋</span> Status
        </a>
        <a href="#" class="nav-link nav-history" onclick=''>
            <span class="nav-icon">📚</span> History
        </a>
        <a href="#" class="nav-link nav-analytics" onclick=''>
            <span class="nav-icon">📊</span> Analytics
        </a>
    """, unsafe_allow_html=True)
    
    # Hidden radio for actual navigation
    return st.sidebar.radio("", ["Upload", "Status", "History", "Analytics"], 
                          key="selected_view", label_visibility="collapsed")

def main():
    if not st.session_state['logged_in']:
        st.title("Document Analyzer & Signer 📝")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if login_user(email, password):
                    st.session_state['logged_in'] = True
                    log_user_action('login', 'User logged in')
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid email or password")
    else:
        # Header with profile menu
        header_col1, header_col2 = st.columns([0.7, 0.3])
        with header_col1:
            st.title("Signforme.AI   ✒️")
        with header_col2:
            with st.expander("👤 Profile Menu"):
                st.write(f"Welcome, this is a test environment!")
                st.divider()
                if st.button("📊 Dashboard"):
                    st.session_state['selected_view'] = 'Analytics'
                if st.button("ℹ️ About"):
                    st.info("Document Analyzer & Signer v4.0  By Kalinov Jim")
                if st.button("🚪 Logout"):
                    log_user_action('logout', 'User logged out')
                    st.session_state['logged_in'] = False
                    st.rerun()
        
        # Enhanced Navigation
        view = show_navigation()
        
        # Main content based on selected view
        if view == "Upload":
            show_upload_section()
        elif view == "Status":
            show_status_section()
        elif view == "History":
            show_history_section()
        elif view == "Analytics":
            show_enhanced_analytics()

if __name__ == "__main__":
    main()
    
